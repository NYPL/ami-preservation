#!/usr/bin/env python3
"""
Audio Processing Pipeline (Preservation -> Edit Master)
Focus: Bandpass Silence Detection & Loudness Normalization
ENHANCED: Safety checks, validation, and detailed reporting
"""
import argparse
import os
import sys
import subprocess
import logging
import json
from typing import Tuple, Dict

# Strict Dependency Check
try:
    import librosa
    import numpy as np
    from scipy import signal
    from scipy.ndimage import binary_dilation
except ImportError:
    print("\nCRITICAL: Missing required libraries.")
    print("Please install: pip install librosa numpy scipy soundfile\n")
    sys.exit(1)


def get_args():
    p = argparse.ArgumentParser(
        description="Automated Edit Master creation: Silence Removal + Loudness Normalization",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    p.add_argument('-s', '--source', required=True,
                   help='Directory containing PreservationMasters')

    # MODES
    p.add_argument('--trim-only', action='store_true',
                   help='Run silence removal only and save files. Useful for review.')
    p.add_argument('--show-stats', action='store_true',
                   help='Show detailed dB metrics during detection (for debugging).')
    p.add_argument('--dry-run', action='store_true',
                   help='Simulate the process without modifying files.')
    p.add_argument('--preview', action='store_true',
                   help='Analyze files and print cut points without processing.')
    p.add_argument('--force', action='store_true',
                   help='Bypass safety checks (use with caution!)')

    # DETECTION SETTINGS
    p.add_argument('--noise-scan-duration', type=float, default=45.0,
                   help='Seconds to scan for noise floor (default: 45.0, increased from 30)')
    p.add_argument('--headroom', type=float, default=10.0,
                   help='dB above noise floor to set silence threshold (default: 10.0, increased for safety)')
    p.add_argument('--min-silence-duration', type=float, default=0.3,
                   help='Minimum silence duration in seconds (default: 0.3)')
    p.add_argument('--padding', type=float, default=2.5,
                   help='Seconds of silence to pad on each side (default: 2.5)')
    p.add_argument('--max-trim-percent', type=float, default=50.0,
                   help='Safety: Fail if trimming more than this %% (default: 50.0)')
    p.add_argument('--min-content-duration', type=float, default=10.0,
                   help='Safety: Warn if detected content is shorter than this (default: 10.0s)')
    p.add_argument('--min-snr', type=float, default=8.0,
                   help='Safety: Warn if content SNR is below this (default: 8.0 dB)')

    # LOUDNORM SETTINGS
    p.add_argument('--target-I', type=float, default=-20.0, help='Target integrated LUFS')
    p.add_argument('--target-LRA', type=float, default=7.0, help='Target LRA')
    p.add_argument('--target-TP', type=float, default=-2.0, help='Target True Peak')

    return p.parse_args()


def setup_logging():
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.INFO,
        datefmt='%H:%M:%S'
    )
    # Silence third-party libs
    logging.getLogger('numba').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)


def get_audio_duration(path: str) -> float:
    cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except:
        return 0.0


def detect_noise_floor_spectral(path: str, scan_duration: float, show_stats: bool) -> float:
    """
    Measure noise floor with High-Pass filtering and multi-region scanning.
    Strategies:
      1. Head Scan (0-45s)
      2. Tail Scan (End-45s) if Head is dense
      3. Mid Scan if both are dense
    Returns the estimated noise floor in dB.
    """
    try:
        total_duration = get_audio_duration(path)
        scan_regions = []

        # region: (name, start_time)
        scan_regions.append(('HEAD', 0.0))
        
        if total_duration > scan_duration * 2:
            scan_regions.append(('TAIL', total_duration - scan_duration))
        
        if total_duration > scan_duration * 3:
            scan_regions.append(('MID', total_duration / 2 - scan_duration / 2))

        best_floor = 0.0
        best_region = "NONE"
        lowest_density_score = 999.0
        
        # We will collect candidates and pick the best one
        # Candidate format: (floor_db, spread, is_dense, region_name)
        candidates = []

        for name, start in scan_regions:
            # Load audio
            y, sr = librosa.load(path, offset=start, duration=scan_duration, sr=16000, mono=True)
            
            if len(y) < sr * 1.0: # Skip if too short
                continue

            # High-pass filter (100Hz)
            sos = signal.butter(4, 100, 'hp', fs=sr, output='sos')
            y_filtered = signal.sosfiltfilt(sos, y)

            # RMS
            frame_len = int(sr * 0.1)
            rms = librosa.feature.rms(y=y_filtered, frame_length=frame_len, hop_length=frame_len//2)[0]
            rms_db = librosa.amplitude_to_db(rms, ref=1.0)
            
            # Filter -inf
            valid_rms = rms_db[rms_db > -90]
            
            if len(valid_rms) == 0:
                candidates.append((-80.0, 0.0, False, name))
                continue

            # Statistics
            min_db = np.min(valid_rms)
            p1 = np.percentile(valid_rms, 1)
            p15 = np.percentile(valid_rms, 15)
            median = np.median(valid_rms)
            
            # Density Check
            # If P15 is much higher than Min (e.g. > 15dB), it likely contains content
            spread = p15 - min_db
            is_dense = spread > 15.0 or median > -45.0
            
            floor_est = p15
            
            # If extremely dense, P15 is definitely wrong, use P1 as a safer fallback locally
            if spread > 25.0:
                 floor_est = p1
            
            candidates.append({
                'floor': floor_est,
                'min': min_db,
                'p1': p1,
                'p15': p15,
                'median': median,
                'spread': spread,
                'is_dense': is_dense,
                'region': name
            })

            if show_stats:
                d_mark = "(!)" if is_dense else "   "
                logging.info(f"     [Analysis] {name:4} ({start:.0f}s): Min={min_db:.1f} | P1={p1:.1f} | P15={p15:.1f} | Med={median:.1f} | Spread={spread:.1f} {d_mark}")

            # Optimization: If we found a clean region, stop scanning? 
            # Ideally yes, but scanning 3x45s is fast enough to just do all for robustness.

        # DECISION LOGIC
        # 1. Prefer Non-Dense regions
        clean_candidates = [c for c in candidates if not c['is_dense']]
        
        if clean_candidates:
            # Pick lowest floor among clean regions
            winner = min(clean_candidates, key=lambda x: x['p15'])
            logging.info(f"   [Floor] Selected {winner['region']} (Clean): {winner['p15']:.1f}dB")
            return winner['p15']
        
        else:
            # All regions are dense (Active content throughout?)
            # Valid Fallback: Use the region with the lowest P1 (approx min noise) 
            # and Use P1 instead of P15 to be safer
            winner = min(candidates, key=lambda x: x['p1'])
            logging.warning(f"   [Floor] ⚠️ High content density detected in all regions (Spread > 15dB).")
            logging.warning(f"   [Floor] → Fallback: Using P1 from {winner['region']} to avoid cutting content.")
            logging.info(f"   [Floor] Selected {winner['region']} (Fallback P1): {winner['p1']:.1f}dB")
            return winner['p1']

    except Exception as e:
        logging.warning(f"Spectral noise floor detection failed: {e}")
        return -65.0


def show_boundary_context(rms_db, times, start_time, end_time, threshold_db, window=5.0):
    """Display RMS levels around detected boundaries for verification"""

    def find_nearest_idx(t):
        return np.argmin(np.abs(times - t))

    start_idx = find_nearest_idx(start_time)
    end_idx = find_nearest_idx(end_time)

    # Show context around start
    window_samples = int(window / (times[1] - times[0]))
    start_window = slice(max(0, start_idx - window_samples), min(len(rms_db), start_idx + window_samples))

    logging.info(f"     [Boundary Context] Start region ({start_time-window:.1f}s to {start_time+window:.1f}s):")
    logging.info(f"       Before: {np.median(rms_db[max(0, start_idx-window_samples):start_idx]):.1f}dB")
    logging.info(f"       After:  {np.median(rms_db[start_idx:min(len(rms_db), start_idx+window_samples)]):.1f}dB")
    logging.info(f"       Threshold: {threshold_db:.1f}dB")


def detect_silence_boundaries(
    audio_path: str,
    noise_floor_db: float,
    headroom_db: float,
    min_silence_duration: float,
    show_stats: bool
) -> Tuple[float, float, Dict]:

    # Load audio
    target_sr = 22050
    y, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    total_duration = len(y) / sr

    # Bandpass Filter (150Hz - 10kHz) - The key for Analog Tape
    sos = signal.butter(4, [150, 10000], 'bandpass', fs=sr, output='sos')
    y_filt = signal.sosfiltfilt(sos, y)

    # RMS Energy
    hop_length = int(sr * 0.02) # 20ms
    frame_length = int(sr * 0.05)
    rms = librosa.feature.rms(y=y_filt, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=1.0)

    # Determine Threshold
    threshold_db = noise_floor_db + headroom_db
    content_mask = rms_db > threshold_db

    # SHOW STATS: Debugging info
    if show_stats:
        first_5s_frames = int(5.0 * sr / hop_length)
        last_5s_frames = int(5.0 * sr / hop_length)

        if first_5s_frames < len(rms_db):
            start_rms = np.median(rms_db[:first_5s_frames])
            status = "CONTENT" if start_rms > threshold_db else "SILENCE"
            logging.info(f"     [Analysis] Head (0-5s) Avg: {start_rms:.1f}dB (Threshold: {threshold_db:.1f}dB) → {status}")

        if last_5s_frames < len(rms_db):
            end_rms = np.median(rms_db[-last_5s_frames:])
            status = "CONTENT" if end_rms > threshold_db else "SILENCE"
            logging.info(f"     [Analysis] Tail (last 5s) Avg: {end_rms:.1f}dB (Threshold: {threshold_db:.1f}dB) → {status}")

    # Dilate to bridge gaps
    gap_frames = int(min_silence_duration * sr / hop_length)
    if gap_frames > 0:
        content_mask = binary_dilation(content_mask, iterations=gap_frames)

    # Find boundaries
    content_indices = np.where(content_mask)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

    if len(content_indices) == 0:
        logging.warning("  ⚠️ No content detected above threshold! Using full duration.")
        return 0.0, total_duration, {'snr': 0.0, 'warning': 'no_content_detected'}

    start_time = max(0, times[content_indices[0]] - 0.1)
    end_time = min(total_duration, times[content_indices[-1]] + 0.1)

    # --- SMART ONSET VERIFICATION ---
    # Check if the "Start" is actually just loud noise (Flat & Stable)
    # We iterate in 0.5s chunks until we find "Dynamic" content or "Loud" content
    
    current_start_idx = content_indices[0]
    
    while True:
        # Define a check window (e.g., 0.5s) from current start
        check_duration = 0.5
        check_frames = int(check_duration * sr / hop_length)
        
        # Ensure we have enough data
        if current_start_idx + check_frames >= len(rms_db):
            break
            
        region = rms_db[current_start_idx : current_start_idx + check_frames]
        
        # Measure Characteristics
        r_min = np.min(region)
        r_max = np.max(region)
        r_med = np.median(region)
        r_spread = r_max - r_min
        
        # Criteria for "Noise" (even if it's above threshold):
        # 1. It is "Stable/Flat" (Low Spread) < 5dB
        # 2. It is not "Super Loud" (e.g. < -30dB). Real speech/music usually peaks higher.
        
        is_stable_noise = (r_spread < 5.0) and (r_med < -30.0)
        
        if is_stable_noise:
            if show_stats:
                logging.info(f"     [Smart Onset] Skipping block at {times[current_start_idx]:.2f}s: Spread={r_spread:.1f}dB (Flat) | Med={r_med:.1f}dB")
            
            # Move start forward
            current_start_idx += check_frames
            start_time = times[current_start_idx]
            
            # Safety: Don't eat the whole file. Stop if we pass the end.
            if times[current_start_idx] >= end_time:
                # Revert if we skipped everything (maybe it was a drone piece?)
                logging.warning("     [Smart Onset] Skipped entire file as noise! Reverting to original detection.")
                start_time = max(0, times[content_indices[0]] - 0.1)
                break
        else:
            # We found dynamic content (Spread > 5) OR Loud content (Med > -30)
            if show_stats:
                logging.info(f"     [Smart Onset] Valid content found at {times[current_start_idx]:.2f}s: Spread={r_spread:.1f}dB | Med={r_med:.1f}dB")
            break
            
    # Update end time (we don't check tail as aggressively, preserving fade outs is better)

    # Calculate SNR for validation
    content_rms = np.median(rms_db[content_indices])
    snr = content_rms - noise_floor_db

    # Calculate content statistics
    content_duration = end_time - start_time

    metadata = {
        'snr': snr,
        'content_duration': content_duration,
        'content_rms_median': content_rms,
        'noise_floor': noise_floor_db,
        'threshold': threshold_db
    }

    if show_stats:
        logging.info(f"     [Quality] SNR: {snr:.1f}dB | Content RMS: {content_rms:.1f}dB")
        show_boundary_context(rms_db, times, start_time, end_time, threshold_db)

    return start_time, end_time, metadata


def validate_trim_safety(
    orig_dur: float,
    start: float,
    end: float,
    padding: float,
    max_percent: float,
    min_content_dur: float,
    metadata: Dict,
    min_snr: float,
    force: bool
) -> Tuple[bool, str, float, float]:
    """
    Validate that the proposed trim is safe.
    Returns: (is_valid, warning_message, cut_start, cut_end)
    """

    cut_start = max(0, start - padding)
    cut_end = min(orig_dur, end + padding)

    head_cut = cut_start
    tail_cut = max(0, orig_dur - cut_end)
    trim_percent = ((head_cut + tail_cut) / orig_dur) * 100

    content_duration = metadata.get('content_duration', end - start)
    snr = metadata.get('snr', 0)

    warnings = []

    # Check 1: Trim percentage
    if trim_percent > max_percent:
        warnings.append(f"TRIM EXCEEDS SAFETY LIMIT: {trim_percent:.1f}% > {max_percent}% (would remove {head_cut+tail_cut:.1f}s of {orig_dur:.1f}s)")

    # Check 2: Content duration
    if content_duration < min_content_dur:
        warnings.append(f"SUSPICIOUSLY SHORT CONTENT: {content_duration:.1f}s < {min_content_dur}s minimum")

    # Check 3: SNR check
    if snr < min_snr and snr > 0:
        warnings.append(f"LOW SNR: {snr:.1f}dB < {min_snr}dB threshold (content may be questionable)")

    # Check 4: No content detected
    if metadata.get('warning') == 'no_content_detected':
        warnings.append("NO CONTENT DETECTED above threshold")

    if warnings:
        if force:
            return True, "FORCED: " + " | ".join(warnings), cut_start, cut_end
        else:
            return False, " | ".join(warnings), cut_start, cut_end

    return True, "", cut_start, cut_end


def trim_audio_ffmpeg(src: str, dst: str, start: float, end: float, padding: float):
    orig_dur = get_audio_duration(src)
    p_start = max(0, start - padding)
    p_end = min(orig_dur, end + padding)
    dur = p_end - p_start

    ext = os.path.splitext(dst)[1].lower()
    cmd = ['ffmpeg', '-hide_banner', '-y', '-ss', str(p_start), '-t', str(dur), '-i', src]

    if ext == '.wav':
        cmd += ['-f', 'wav', '-rf64', 'auto', '-c:a', 'pcm_s24le', '-ar', '96k']
    else:
        cmd += ['-c:a', 'flac', '-compression_level', '8', '-ar', '96k']

    cmd.append(dst)
    subprocess.run(cmd, check=True, capture_output=True)


def process_trimming(args):
    """Phase 1: Detect Silence & Trim"""
    src_files = [os.path.join(r, f) for r, _, fs in os.walk(args.source) for f in fs if f.lower().endswith(('.wav', '.flac'))]

    if not src_files:
        logging.error("No audio files found")
        sys.exit(1)

    edit_dir = args.source.replace('PreservationMasters', 'EditMasters')
    os.makedirs(edit_dir, exist_ok=True)

    # Statistics tracking
    stats = {
        'processed': 0,
        'skipped': 0,
        'warnings': 0,
        'forced': 0
    }

    for src in sorted(src_files):
        fn = os.path.basename(src)
        base, ext = os.path.splitext(fn)

        # If trim-only, we call it _trim, otherwise _temp (waiting for norm)
        out_suffix = '_trim' if args.trim_only else '_temp'
        out_name = base.replace('_pm', out_suffix) + ext
        if out_name == fn: out_name = base + out_suffix + ext # fallback naming

        dst = os.path.join(edit_dir, out_name)

        logging.info(f"▶ Processing: {fn}")

        try:
            # 1. Measure Floor
            nf = detect_noise_floor_spectral(src, args.noise_scan_duration, args.show_stats)
            logging.info(f"   [Floor] Noise floor detected: {nf:.1f}dB")

            # 2. Detect Content
            start, end, metadata = detect_silence_boundaries(
                src, nf, args.headroom, args.min_silence_duration, args.show_stats
            )

            # 3. Validate Safety
            orig_dur = get_audio_duration(src)
            is_safe, warning_msg, cut_start, cut_end = validate_trim_safety(
                orig_dur, start, end, args.padding,
                args.max_trim_percent, args.min_content_duration,
                metadata, args.min_snr, args.force
            )

            head_cut = cut_start
            tail_cut = max(0, orig_dur - cut_end)
            trim_percent = ((head_cut + tail_cut) / orig_dur) * 100
            content_dur = metadata.get('content_duration', end - start)

            # Display results
            logging.info(f"   [Detection] Content: {start:.2f}s → {end:.2f}s ({content_dur:.1f}s)")
            logging.info(f"   [Trim] Head: -{head_cut:.2f}s | Tail: -{tail_cut:.2f}s | Total: {trim_percent:.1f}%")

            if metadata.get('snr', 0) > 0:
                logging.info(f"   [Quality] SNR: {metadata['snr']:.1f}dB")

            if args.preview:
                if warning_msg:
                    logging.warning(f"   ⚠️ {warning_msg}")
                continue

            # Handle unsafe detections
            if not is_safe:
                logging.error(f"   ❌ SKIPPED: {warning_msg}")
                logging.error(f"   → Use --force to override, or adjust --max-trim-percent/--headroom")
                stats['skipped'] += 1
                continue

            if warning_msg and args.force:
                logging.warning(f"   ⚠️ {warning_msg}")
                stats['forced'] += 1
            elif warning_msg:
                stats['warnings'] += 1

            if args.dry_run:
                logging.info(f"   [DRY] Would create {os.path.basename(dst)}")
                stats['processed'] += 1
                continue

            # 4. Execute Trim
            trim_audio_ffmpeg(src, dst, start, end, args.padding)

            logging.info(f"   ✓ Created → {os.path.basename(dst)}")
            stats['processed'] += 1

        except Exception as e:
            logging.error(f"   ❌ Failed: {e}")
            stats['skipped'] += 1

    # Summary
    logging.info("\n" + "="*60)
    logging.info(f"TRIMMING SUMMARY:")
    logging.info(f"  Processed: {stats['processed']}")
    logging.info(f"  Skipped: {stats['skipped']}")
    logging.info(f"  Warnings: {stats['warnings']}")
    if stats['forced'] > 0:
        logging.info(f"  Forced: {stats['forced']}")
    logging.info("="*60)

    return edit_dir


def loudnorm_pass(edit_path, target_I, target_LRA, target_TP, dry_run):
    """Phase 2: Loudness Normalization"""
    files = [os.path.join(r, f) for r, _, fs in os.walk(edit_path) for f in fs if ('_temp' in f or '_trim' in f) and f.lower().endswith(('.wav', '.flac'))]

    if not files:
        logging.warning("No files found for normalization.")
        return

    for f in sorted(files):
        base, ext = os.path.splitext(f)
        out_name = os.path.basename(base).replace('_temp', '_em').replace('_trim', '_em') + ext
        # Fallback naming if neither suffix found
        if out_name == os.path.basename(f): out_name = base + "_em" + ext

        dst = os.path.join(edit_path, out_name)

        logging.info(f"▶ Loudnorm: {os.path.basename(f)}")

        if dry_run:
            logging.info(f"   [DRY] Would normalize to {os.path.basename(dst)}")
            continue

        try:
            # Pass 1: Measure
            cmd1 = ['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', f'loudnorm=dual_mono=true:I={target_I}:LRA={target_LRA}:TP={target_TP}:print_format=json', '-f', 'null', '-']
            res = subprocess.run(cmd1, check=True, stderr=subprocess.PIPE, text=True)

            # Extract JSON from stderr
            stats = json.loads(res.stderr[res.stderr.find('{'):res.stderr.rfind('}')+1])

            # Pass 2: Apply
            cmd2 = ['ffmpeg', '-hide_banner', '-y', '-i', f,
                    '-af', f"loudnorm=dual_mono=true:linear=true:I={target_I}:LRA={target_LRA}:TP={target_TP}:measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}"]

            if ext == '.wav': cmd2 += ['-f', 'wav', '-rf64', 'auto', '-c:a', 'pcm_s24le', '-ar', '96k']
            else: cmd2 += ['-c:a', 'flac', '-compression_level', '8', '-ar', '96k']

            cmd2.append(dst)
            subprocess.run(cmd2, check=True, capture_output=True)

            if os.path.exists(dst):
                os.remove(f) # Remove intermediate file
                logging.info(f"   ✓ Normalized → {os.path.basename(dst)}")

        except Exception as e:
            logging.error(f"   ❌ Loudnorm failed: {e}")


def main():
    args = get_args()
    setup_logging()

    logging.info("="*60)
    logging.info(f"AUDIO PROCESSING PIPELINE - ENHANCED")
    logging.info("="*60)
    logging.info(f"Source: {args.source}")
    if args.trim_only:
        logging.info("Mode: TRIM ONLY (Review Mode)")
    if args.dry_run:
        logging.info("Mode: DRY RUN (No files will be modified)")
    if args.preview:
        logging.info("Mode: PREVIEW (Analysis only)")
    if args.force:
        logging.warning("Mode: FORCE (Safety checks will be bypassed!)")
    logging.info(f"\nSettings:")
    logging.info(f"  Noise scan: {args.noise_scan_duration}s")
    logging.info(f"  Headroom: {args.headroom}dB")
    logging.info(f"  Padding: {args.padding}s")
    logging.info(f"  Max trim: {args.max_trim_percent}%")
    logging.info(f"  Min content: {args.min_content_duration}s")
    logging.info(f"  Min SNR: {args.min_snr}dB")
    logging.info("="*60 + "\n")

    # 1. Trim
    edit_dir = process_trimming(args)

    if args.preview or args.dry_run or args.trim_only:
        logging.info("\n✅ Batch Complete")
        sys.exit(0)

    # 2. Loudnorm
    logging.info("\n" + "="*60 + "\nStep 2: Loudness Normalization\n" + "="*60)
    loudnorm_pass(edit_dir, args.target_I, args.target_LRA, args.target_TP, False)

    logging.info("\n✅ Processing Complete!")

if __name__ == '__main__':
    main()