#!/usr/bin/env python3
"""
Audio Processing Pipeline (Preservation -> Edit Master)
ENHANCED VERSION with Multi-Feature Silence Detection
Focus: Robust analog tape noise rejection while preserving content
"""
import argparse
import os
import sys
import subprocess
import logging
import json
from typing import Tuple, Dict, Optional

# Strict Dependency Check
try:
    import librosa
    import numpy as np
    from scipy import signal
    from scipy.ndimage import binary_dilation, median_filter
except ImportError:
    print("\nCRITICAL: Missing required libraries.")
    print("Please install: pip install librosa numpy scipy soundfile\n")
    sys.exit(1)


def get_args():
    p = argparse.ArgumentParser(
        description="Automated Edit Master creation: Enhanced Silence Removal + Loudness Normalization",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    p.add_argument('-s', '--source', required=True,
                   help='Directory containing PreservationMasters')

    # MODES
    p.add_argument('--trim-only', action='store_true',
                   help='Run silence removal only and save files. Useful for review.')
    p.add_argument('--show-stats', action='store_true',
                   help='Show detailed analysis metrics during detection (for debugging).')
    p.add_argument('--dry-run', action='store_true',
                   help='Simulate the process without modifying files.')
    p.add_argument('--preview', action='store_true',
                   help='Analyze files and print cut points without processing.')
    p.add_argument('--force', action='store_true',
                   help='Bypass safety checks (use with caution!)')

    # DETECTION SETTINGS
    p.add_argument('--noise-scan-duration', type=float, default=20.0,
                   help='Seconds to scan for noise floor (default: 20.0)')
    p.add_argument('--headroom', type=float, default=10.0,
                   help='dB above noise floor to set silence threshold (default: 10.0)')
    p.add_argument('--min-silence-duration', type=float, default=0.3,
                   help='Minimum silence duration in seconds (default: 0.3)')
    p.add_argument('--padding', type=float, default=2.5,
                   help='Seconds of silence to pad on each side (default: 2.5)')
    p.add_argument('--adaptive-padding', action='store_true',
                   help='Scale padding based on SNR: cleaner recordings get less padding')
    p.add_argument('--min-padding', type=float, default=0.5,
                   help='Minimum padding for adaptive mode (default: 0.5s)')
    p.add_argument('--max-trim-percent', type=float, default=50.0,
                   help='Safety: Fail if trimming more than this %% (default: 50.0)')
    p.add_argument('--min-content-duration', type=float, default=10.0,
                   help='Safety: Warn if detected content is shorter than this (default: 10.0s)')
    p.add_argument('--min-snr', type=float, default=8.0,
                   help='Safety: Warn if content SNR is below this (default: 8.0 dB)')

    # ENHANCED FEATURE DETECTION
    p.add_argument('--flux-sensitivity', type=float, default=1.5,
                   help='Spectral flux threshold in std devs (default: 1.5, lower=more sensitive)')
    p.add_argument('--centroid-threshold', type=float, default=200.0,
                   help='Spectral centroid variation threshold in Hz (default: 200)')
    p.add_argument('--content-score-min', type=int, default=2,
                   help='Minimum feature score for content detection 0-4 (default: 2)')
    p.add_argument('--use-multiband', action='store_true',
                   help='Enable multi-band noise floor analysis (experimental)')
    p.add_argument('--adaptive-threshold', action='store_true',
                   help='Use adaptive threshold that follows local noise variations')

    # LOUDNORM SETTINGS
    p.add_argument('--target-I', type=float, default=-20.0, help='Target integrated LUFS')
    p.add_argument('--target-LRA', type=float, default=7.0, help='Target LRA')
    p.add_argument('--target-TP', type=float, default=-2.0, help='Target True Peak')
    p.add_argument('--min-flux-avg', type=float, default=-1.0,
                   help='Safety: Fail if avg spectral flux is below this (default: -1.0)')

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
    """Get total duration of audio file using ffprobe"""
    cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except:
        return 0.0


def detect_noise_floor_multiband(
    path: str,
    scan_duration: float,
    show_stats: bool
) -> Dict[str, float]:
    """
    Enhanced multi-band noise floor detection.
    Analyzes different frequency bands to better characterize tape noise.

    Returns: Dict with 'overall' floor and individual band floors
    """
    try:
        total_duration = get_audio_duration(path)
        scan_regions = [('HEAD', 0.0)]

        if total_duration > scan_duration * 2:
            scan_regions.append(('TAIL', total_duration - scan_duration))
        if total_duration > scan_duration * 3:
            scan_regions.append(('MID', total_duration / 2 - scan_duration / 2))

        # Frequency bands for analysis
        bands = {
            'low': (150, 500),      # Low fundamentals
            'mid': (500, 2000),     # Speech clarity
            'high': (2000, 8000),   # Presence/sibilance
            'air': (8000, 15000)    # Tape hiss territory
        }

        best_floor_overall = 0.0
        best_region = "NONE"
        band_floors = {band: [] for band in bands.keys()}

        for name, start in scan_regions:
            y, sr = librosa.load(path, offset=start, duration=scan_duration, sr=16000, mono=True)

            if len(y) < sr * 1.0:
                continue

            # Analyze each frequency band
            region_band_levels = {}
            for band_name, (low_freq, high_freq) in bands.items():
                sos = signal.butter(4, [low_freq, high_freq], 'bandpass', fs=sr, output='sos')
                y_band = signal.sosfiltfilt(sos, y)

                frame_len = int(sr * 0.1)
                rms = librosa.feature.rms(y=y_band, frame_length=frame_len, hop_length=frame_len//2)[0]
                rms_db = librosa.amplitude_to_db(rms, ref=1.0)

                valid_rms = rms_db[rms_db > -90]
                if len(valid_rms) > 0:
                    p15 = np.percentile(valid_rms, 15)
                    region_band_levels[band_name] = p15
                    band_floors[band_name].append(p15)

            # Overall analysis (broadband)
            sos = signal.butter(4, 100, 'hp', fs=sr, output='sos')
            y_filtered = signal.sosfiltfilt(sos, y)

            frame_len = int(sr * 0.1)
            rms = librosa.feature.rms(y=y_filtered, frame_length=frame_len, hop_length=frame_len//2)[0]
            rms_db = librosa.amplitude_to_db(rms, ref=1.0)
            valid_rms = rms_db[rms_db > -90]

            if len(valid_rms) == 0:
                continue

            p1 = np.percentile(valid_rms, 1)
            p15 = np.percentile(valid_rms, 15)
            median = np.median(valid_rms)
            spread = p15 - np.min(valid_rms)

            # Check if this region is relatively clean
            is_dense = spread > 15.0 or median > -45.0

            # Tape noise signature: High energy in 'air' band relative to others
            air_level = region_band_levels.get('air', -80)
            mid_level = region_band_levels.get('mid', -80)
            noise_signature = air_level - mid_level  # Positive = likely just noise

            if show_stats:
                d_mark = "(!)" if is_dense else "   "
                logging.info(f"     [Multi-band] {name:4}: Overall P15={p15:.1f}dB | "
                           f"Air={air_level:.1f} Mid={mid_level:.1f} Diff={noise_signature:.1f}dB {d_mark}")

            # Prefer clean regions
            if not is_dense and (best_floor_overall == 0.0 or p15 < best_floor_overall):
                best_floor_overall = p15
                best_region = name

        # Compile results
        result = {'overall': best_floor_overall if best_floor_overall != 0.0 else -65.0}

        # Average band floors across regions
        for band_name, levels in band_floors.items():
            if levels:
                result[band_name] = np.median(levels)

        if show_stats and len(result) > 1:
            logging.info(f"     [Multi-band Floors] " +
                        " | ".join([f"{k}={v:.1f}dB" for k, v in result.items() if k != 'overall']))

        return result

    except Exception as e:
        logging.warning(f"Multi-band noise floor detection failed: {e}")
        return {'overall': -65.0}


def detect_noise_floor_spectral(
    path: str,
    scan_duration: float,
    show_stats: bool,
    use_multiband: bool = False
) -> float:
    """
    Measure noise floor with High-Pass filtering and multi-region scanning.
    Can optionally use multi-band analysis for enhanced accuracy.
    """
    if use_multiband:
        result = detect_noise_floor_multiband(path, scan_duration, show_stats)
        logging.info(f"   [Floor] Multi-band analysis complete: {result['overall']:.1f}dB")
        return result['overall']

    try:
        total_duration = get_audio_duration(path)
        scan_regions = [('HEAD', 0.0)]

        if total_duration > scan_duration * 2:
            scan_regions.append(('TAIL', total_duration - scan_duration))
        if total_duration > scan_duration * 3:
            scan_regions.append(('MID', total_duration / 2 - scan_duration / 2))

        candidates = []

        for name, start in scan_regions:
            y, sr = librosa.load(path, offset=start, duration=scan_duration, sr=16000, mono=True)

            if len(y) < sr * 1.0:
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
                candidates.append({'floor': -80.0, 'p1': -80.0, 'p15': -80.0,
                                 'median': -80.0, 'spread': 0.0, 'is_dense': False, 'region': name})
                continue

            # Statistics
            min_db = np.min(valid_rms)
            p1 = np.percentile(valid_rms, 1)
            p15 = np.percentile(valid_rms, 15)
            median = np.median(valid_rms)

            # Density Check
            spread = p15 - min_db
            is_dense = spread > 15.0 or median > -45.0

            floor_est = p15
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
                logging.info(f"     [Analysis] {name:4} ({start:.0f}s): Min={min_db:.1f} | "
                           f"P1={p1:.1f} | P15={p15:.1f} | Med={median:.1f} | Spread={spread:.1f} {d_mark}")

        # DECISION LOGIC
        clean_candidates = [c for c in candidates if not c['is_dense']]

        if clean_candidates:
            winner = min(clean_candidates, key=lambda x: x['p15'])
            logging.info(f"   [Floor] Selected {winner['region']} (Clean): {winner['p15']:.1f}dB")
            return winner['p15']
        else:
            winner = min(candidates, key=lambda x: x['p1'])
            logging.warning(f"   [Floor] ⚠️ High content density detected in all regions.")
            logging.warning(f"   [Floor] → Fallback: Using P1 from {winner['region']}.")
            logging.info(f"   [Floor] Selected {winner['region']} (Fallback P1): {winner['p1']:.1f}dB")
            return winner['p1']

    except Exception as e:
        logging.warning(f"Spectral noise floor detection failed: {e}")
        return -65.0


def calculate_spectral_features(y: np.ndarray, sr: int, hop_length: int) -> Dict[str, np.ndarray]:
    """
    Calculate spectral features for content vs noise discrimination.

    Returns:
        - spectral_flux: Rate of spectral change (high for content)
        - spectral_centroid: Center frequency (varies with content)
        - zcr: Zero-crossing rate
        - spectral_rolloff: 85th percentile frequency
    """
    # Spectral centroid (brightness)
    spectral_centroids = librosa.feature.spectral_centroid(
        y=y, sr=sr, hop_length=hop_length
    )[0]

    # Zero-crossing rate
    zcr = librosa.feature.zero_crossing_rate(
        y, frame_length=2048, hop_length=hop_length
    )[0]

    # Spectral rolloff
    spectral_rolloff = librosa.feature.spectral_rolloff(
        y=y, sr=sr, hop_length=hop_length, roll_percent=0.85
    )[0]

    # Spectral flux (change in spectrum over time)
    S = np.abs(librosa.stft(y, hop_length=hop_length))
    spectral_flux = np.concatenate([[0], np.sqrt(np.sum(np.diff(S, axis=1)**2, axis=0))])

    # Pad flux to match other feature lengths if needed
    if len(spectral_flux) < len(spectral_centroids):
        spectral_flux = np.pad(spectral_flux, (0, len(spectral_centroids) - len(spectral_flux)))
    elif len(spectral_flux) > len(spectral_centroids):
        spectral_flux = spectral_flux[:len(spectral_centroids)]

    return {
        'flux': spectral_flux,
        'centroid': spectral_centroids,
        'zcr': zcr,
        'rolloff': spectral_rolloff
    }


def detect_silence_boundaries_enhanced(
    audio_path: str,
    noise_floor_db: float,
    headroom_db: float,
    min_silence_duration: float,
    show_stats: bool,
    flux_sensitivity: float = 1.5,
    centroid_threshold: float = 200.0,
    content_score_min: int = 2,
    use_adaptive: bool = False
) -> Tuple[float, float, Dict]:
    """
    Enhanced silence detection using multi-feature analysis.

    Features used:
    1. RMS energy (traditional)
    2. Spectral flux (detects timbral changes)
    3. Spectral centroid variation (detects tonal movement)
    4. Zero-crossing rate patterns

    This helps distinguish static tape hiss from actual content.
    """
    # Load audio
    target_sr = 22050
    y, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    total_duration = len(y) / sr

    # Bandpass Filter (150Hz - 10kHz) - Focus on content range
    sos = signal.butter(4, [150, 10000], 'bandpass', fs=sr, output='sos')
    y_filt = signal.sosfiltfilt(sos, y)

    # RMS Energy
    hop_length = int(sr * 0.02)  # 20ms
    frame_length = int(sr * 0.05)
    rms = librosa.feature.rms(y=y_filt, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=1.0)

    # Calculate spectral features
    features = calculate_spectral_features(y_filt, sr, hop_length)

    # Ensure all features are same length
    min_len = min(len(rms_db), len(features['flux']), len(features['centroid']), len(features['zcr']))
    rms_db = rms_db[:min_len]
    for key in features:
        features[key] = features[key][:min_len]

    # Determine Threshold
    threshold_db = noise_floor_db + headroom_db

    # Adaptive threshold (optional)
    if use_adaptive:
        window_size = int(2.0 * sr / hop_length)  # 2-second window
        local_floor = median_filter(rms_db, size=window_size, mode='nearest')
        threshold_adaptive = local_floor + headroom_db
        if show_stats:
            logging.info(f"     [Analysis] Using adaptive threshold (follows local variations)")
    else:
        threshold_adaptive = np.full_like(rms_db, threshold_db)

    # Base energy mask
    energy_mask = rms_db > threshold_adaptive

    # Normalize spectral flux for threshold comparison
    flux_median = np.median(features['flux'])
    flux_std = np.std(features['flux'])
    flux_norm = (features['flux'] - flux_median) / (flux_std + 1e-10)

    # Spectral flux mask (detecting spectral change)
    flux_mask = flux_norm > flux_sensitivity

    # Spectral centroid variation (detecting tonal movement)
    # Use rolling window standard deviation
    centroid_window = 10  # frames
    centroid_std_windowed = np.array([
        np.std(features['centroid'][max(0, i-centroid_window):min(len(features['centroid']), i+centroid_window)])
        for i in range(len(features['centroid']))
    ])
    movement_mask = centroid_std_windowed > centroid_threshold

    # Zero-crossing rate variation (speech/music has varying ZCR, noise is steady)
    zcr_window = 10
    zcr_std_windowed = np.array([
        np.std(features['zcr'][max(0, i-zcr_window):min(len(features['zcr']), i+zcr_window)])
        for i in range(len(features['zcr']))
    ])
    zcr_mask = zcr_std_windowed > np.percentile(zcr_std_windowed, 50)  # Above median variation

    # Multi-criteria content mask
    # Content needs energy AND at least one spectral indicator
    spectral_indicators = flux_mask.astype(int) + movement_mask.astype(int) + zcr_mask.astype(int)
    content_mask = energy_mask & (spectral_indicators >= 1)

    # SHOW STATS: Debugging info
    if show_stats:
        first_5s_frames = int(5.0 * sr / hop_length)
        last_5s_frames = int(5.0 * sr / hop_length)

        if first_5s_frames < len(rms_db):
            start_rms = np.median(rms_db[:first_5s_frames])
            start_flux = np.median(flux_norm[:first_5s_frames])
            start_indicators = np.mean(spectral_indicators[:first_5s_frames])
            status = "CONTENT" if start_rms > threshold_db and start_indicators >= 1 else "SILENCE"
            logging.info(f"     [Analysis] Head (0-5s): RMS={start_rms:.1f}dB | Flux={start_flux:.2f} | "
                        f"Indicators={start_indicators:.1f} → {status}")

        if last_5s_frames < len(rms_db):
            end_rms = np.median(rms_db[-last_5s_frames:])
            end_flux = np.median(flux_norm[-last_5s_frames:])
            end_indicators = np.mean(spectral_indicators[-last_5s_frames:])
            status = "CONTENT" if end_rms > threshold_db and end_indicators >= 1 else "SILENCE"
            logging.info(f"     [Analysis] Tail (last 5s): RMS={end_rms:.1f}dB | Flux={end_flux:.2f} | "
                        f"Indicators={end_indicators:.1f} → {status}")

    # Dilate to bridge small gaps
    gap_frames = int(min_silence_duration * sr / hop_length)
    if gap_frames > 0:
        content_mask = binary_dilation(content_mask, iterations=gap_frames)

    # Find boundaries
    content_indices = np.where(content_mask)[0]
    times = librosa.frames_to_time(np.arange(len(rms_db)), sr=sr, hop_length=hop_length)

    if len(content_indices) == 0:
        logging.warning("  ⚠️ No content detected above threshold! Using full duration.")
        return 0.0, total_duration, {'snr': 0.0, 'warning': 'no_content_detected'}

    start_idx = content_indices[0]
    end_idx = content_indices[-1]

    # Enhanced onset verification with multiple features
    check_duration = 0.5
    check_frames = int(check_duration * sr / hop_length)

    onset_iterations = 0
    max_iterations = 20  # Safety limit

    while start_idx + check_frames < len(rms_db) and onset_iterations < max_iterations:
        region_slice = slice(start_idx, start_idx + check_frames)

        # Multi-feature analysis of this region
        r_rms_spread = np.max(rms_db[region_slice]) - np.min(rms_db[region_slice])
        r_rms_median = np.median(rms_db[region_slice])
        r_flux_mean = np.mean(flux_norm[region_slice])
        r_centroid_std = np.std(features['centroid'][region_slice])
        r_zcr_std = np.std(features['zcr'][region_slice])

        # Score the region (4 possible indicators)
        has_dynamic_rms = r_rms_spread > 4.0  # Dynamic energy
        has_spectral_change = r_flux_mean > 1.0  # Changing timbre
        has_tonal_movement = r_centroid_std > centroid_threshold  # Varying pitch/brightness
        is_loud_enough = r_rms_median > -35.0  # Above tape noise level

        content_score = sum([has_dynamic_rms, has_spectral_change, has_tonal_movement, is_loud_enough])

        if content_score >= content_score_min:
            if show_stats:
                logging.info(f"     [Smart Onset] Content found at {times[start_idx]:.2f}s "
                           f"(Score: {content_score}/4 | RMS_spread={r_rms_spread:.1f}dB | "
                           f"Flux={r_flux_mean:.2f} | Centroid_std={r_centroid_std:.0f}Hz)")
            break

        if show_stats:
            logging.info(f"     [Smart Onset] Skipping noise at {times[start_idx]:.2f}s "
                       f"(Score: {content_score}/4 < {content_score_min} threshold)")

        start_idx += check_frames
        onset_iterations += 1

        if start_idx >= end_idx:
            logging.warning("     [Smart Onset] No clear content found, using original detection")
            start_idx = content_indices[0]
            break

    # Enhanced OFFSET verification (Backwards from end)
    # This mirrors the onset detection to find where the content truly ends
    offset_iterations = 0
    while end_idx - check_frames > start_idx and offset_iterations < max_iterations:
        region_slice = slice(end_idx - check_frames, end_idx)

        # Multi-feature analysis of this region
        r_rms_spread = np.max(rms_db[region_slice]) - np.min(rms_db[region_slice])
        r_rms_median = np.median(rms_db[region_slice])
        r_flux_mean = np.mean(flux_norm[region_slice])
        r_centroid_std = np.std(features['centroid'][region_slice])

        # Score the region
        has_dynamic_rms = r_rms_spread > 4.0
        has_spectral_change = r_flux_mean > 1.0
        has_tonal_movement = r_centroid_std > centroid_threshold
        is_loud_enough = r_rms_median > -35.0

        content_score = sum([has_dynamic_rms, has_spectral_change, has_tonal_movement, is_loud_enough])

        if content_score >= content_score_min:
            if show_stats:
                logging.info(f"     [Smart Offset] Content ends at {times[end_idx]:.2f}s "
                           f"(Score: {content_score}/4 | Flux={r_flux_mean:.2f})")
            break

        if show_stats:
            logging.info(f"     [Smart Offset] Trimming tail noise at {times[end_idx]:.2f}s "
                       f"(Score: {content_score}/4 < {content_score_min})")

        end_idx -= check_frames
        offset_iterations += 1

    # Update times
    start_time = max(0, times[start_idx] - 0.1)
    end_time = min(total_duration, times[end_idx] + 0.1)

    # Calculate metrics
    content_rms = np.median(rms_db[content_indices])
    snr = content_rms - noise_floor_db
    content_duration = end_time - start_time

    # Calculate average spectral characteristics of detected content
    content_flux_avg = np.mean(flux_norm[content_indices])
    content_centroid_std = np.std(features['centroid'][content_indices])

    metadata = {
        'snr': snr,
        'content_duration': content_duration,
        'content_rms_median': content_rms,
        'noise_floor': noise_floor_db,
        'threshold': threshold_db,
        'spectral_features_used': True,
        'avg_spectral_flux': content_flux_avg,
        'centroid_variation': content_centroid_std,
        'content_score_min': content_score_min
    }

    if show_stats:
        logging.info(f"     [Quality] SNR: {snr:.1f}dB | Content RMS: {content_rms:.1f}dB")
        logging.info(f"     [Spectral] Avg Flux: {content_flux_avg:.2f} | Centroid Std: {content_centroid_std:.0f}Hz")

    return start_time, end_time, metadata


def calculate_adaptive_padding(snr: float, base_padding: float, min_padding: float) -> float:
    """
    Calculate padding duration based on SNR quality.

    Strategy:
    - SNR >= 45dB (excellent): Use minimum padding (clean digital-quality recordings)
    - SNR 35-45dB (very good): Scale linearly from min to ~60% of base
    - SNR 25-35dB (good): Scale from ~60% to ~80% of base
    - SNR 15-25dB (fair): Scale from ~80% to full base padding
    - SNR < 15dB (poor): Use full base padding (noisy analog tape)

    Args:
        snr: Signal-to-noise ratio in dB
        base_padding: Default padding value from args
        min_padding: Minimum allowed padding value

    Returns:
        Calculated padding in seconds
    """
    if snr >= 45.0:
        # Excellent quality - minimal padding needed
        padding = min_padding
    elif snr >= 35.0:
        # Very good - interpolate from min to 60% of base
        ratio = (45.0 - snr) / 10.0  # 0.0 to 1.0
        padding = min_padding + ratio * (0.6 * base_padding - min_padding)
    elif snr >= 25.0:
        # Good - interpolate from 60% to 80% of base
        ratio = (35.0 - snr) / 10.0  # 0.0 to 1.0
        padding = 0.6 * base_padding + ratio * (0.2 * base_padding)
    elif snr >= 15.0:
        # Fair - interpolate from 80% to 100% of base
        ratio = (25.0 - snr) / 10.0  # 0.0 to 1.0
        padding = 0.8 * base_padding + ratio * (0.2 * base_padding)
    else:
        # Poor quality - use full padding
        padding = base_padding

    return padding


def validate_trim_safety(
    orig_dur: float,
    start: float,
    end: float,
    padding: float,
    max_percent: float,
    min_content_dur: float,
    metadata: Dict,
    min_snr: float,
    min_flux_avg: float,
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
        warnings.append(f"TRIM EXCEEDS SAFETY LIMIT: {trim_percent:.1f}% > {max_percent}% "
                       f"(would remove {head_cut+tail_cut:.1f}s of {orig_dur:.1f}s)")

    # Check 2: Content duration
    if content_duration < min_content_dur:
        warnings.append(f"SUSPICIOUSLY SHORT CONTENT: {content_duration:.1f}s < {min_content_dur}s minimum")

    # Check 3: SNR check
    if snr < min_snr and snr > 0:
        warnings.append(f"LOW SNR: {snr:.1f}dB < {min_snr}dB threshold (content may be questionable)")

    # Check 4: No content detected
    if metadata.get('warning') == 'no_content_detected':
        warnings.append("NO CONTENT DETECTED above threshold")

    # Check 5: Low spectral activity (might be just noise)
    if metadata.get('spectral_features_used'):
        avg_flux = metadata.get('avg_spectral_flux', 0)
        if avg_flux < min_flux_avg:
            warnings.append(f"LOW SPECTRAL ACTIVITY: Flux={avg_flux:.2f} < {min_flux_avg} (content may lack variation)")

    if warnings:
        if force:
            return True, "FORCED: " + " | ".join(warnings), cut_start, cut_end
        else:
            return False, " | ".join(warnings), cut_start, cut_end

    return True, "", cut_start, cut_end


def trim_audio_ffmpeg(src: str, dst: str, start: float, end: float, padding: float):
    """Execute the actual trimming using ffmpeg"""
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
    """Phase 1: Detect Silence & Trim with Enhanced Features"""
    src_files = [
        os.path.join(r, f)
        for r, _, fs in os.walk(args.source)
        for f in fs
        if f.lower().endswith(('.wav', '.flac'))
    ]

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

        # Output naming
        out_suffix = '_trim' if args.trim_only else '_temp'
        out_name = base.replace('_pm', out_suffix) + ext
        if out_name == fn:
            out_name = base + out_suffix + ext

        dst = os.path.join(edit_dir, out_name)

        logging.info(f"▶ Processing: {fn}")

        try:
            # 1. Measure Noise Floor
            nf = detect_noise_floor_spectral(
                src,
                args.noise_scan_duration,
                args.show_stats,
                args.use_multiband
            )
            logging.info(f"   [Floor] Noise floor detected: {nf:.1f}dB")

            # 2. Detect Content with Enhanced Features
            start, end, metadata = detect_silence_boundaries_enhanced(
                src,
                nf,
                args.headroom,
                args.min_silence_duration,
                args.show_stats,
                flux_sensitivity=args.flux_sensitivity,
                centroid_threshold=args.centroid_threshold,
                content_score_min=args.content_score_min,
                use_adaptive=args.adaptive_threshold
            )

            # 2.5. Calculate adaptive padding if enabled
            snr = metadata.get('snr', 0)
            if args.adaptive_padding and snr > 0:
                actual_padding = calculate_adaptive_padding(snr, args.padding, args.min_padding)
                logging.info(f"   [Padding] Adaptive: {actual_padding:.2f}s (SNR: {snr:.1f}dB, base: {args.padding:.2f}s)")
            else:
                actual_padding = args.padding

            # 3. Validate Safety
            orig_dur = get_audio_duration(src)
            is_safe, warning_msg, cut_start, cut_end = validate_trim_safety(
                orig_dur, start, end, actual_padding,
                args.max_trim_percent, args.min_content_duration,
                metadata, args.min_snr, args.min_flux_avg, args.force
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
                logging.error(f"   → Use --force to override, or adjust parameters")
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

            # 4. Execute Trim with calculated padding
            trim_audio_ffmpeg(src, dst, start, end, actual_padding)

            logging.info(f"   ✓ Created → {os.path.basename(dst)}")
            stats['processed'] += 1

        except Exception as e:
            logging.error(f"   ❌ Failed: {e}")
            import traceback
            if args.show_stats:
                traceback.print_exc()
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
    files = [
        os.path.join(r, f)
        for r, _, fs in os.walk(edit_path)
        for f in fs
        if ('_temp' in f or '_trim' in f) and f.lower().endswith(('.wav', '.flac'))
    ]

    if not files:
        logging.warning("No files found for normalization.")
        return

    for f in sorted(files):
        base, ext = os.path.splitext(f)
        out_name = os.path.basename(base).replace('_temp', '_em').replace('_trim', '_em') + ext
        if out_name == os.path.basename(f):
            out_name = os.path.basename(base) + "_em" + ext

        dst = os.path.join(edit_path, out_name)

        logging.info(f"▶ Loudnorm: {os.path.basename(f)}")

        if dry_run:
            logging.info(f"   [DRY] Would normalize to {os.path.basename(dst)}")
            continue

        try:
            # Pass 1: Measure
            cmd1 = [
                'ffmpeg', '-hide_banner', '-nostats', '-i', f,
                '-af', f'loudnorm=dual_mono=true:I={target_I}:LRA={target_LRA}:TP={target_TP}:print_format=json',
                '-f', 'null', '-'
            ]
            res = subprocess.run(cmd1, check=True, stderr=subprocess.PIPE, text=True)

            # Extract JSON from stderr
            json_start = res.stderr.find('{')
            json_end = res.stderr.rfind('}') + 1
            stats = json.loads(res.stderr[json_start:json_end])

            # Pass 2: Apply
            cmd2 = [
                'ffmpeg', '-hide_banner', '-y', '-i', f,
                '-af',
                f"loudnorm=dual_mono=true:linear=true:I={target_I}:LRA={target_LRA}:TP={target_TP}:"
                f"measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:"
                f"measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}"
            ]

            if ext == '.wav':
                cmd2 += ['-f', 'wav', '-rf64', 'auto', '-c:a', 'pcm_s24le', '-ar', '96k']
            else:
                cmd2 += ['-c:a', 'flac', '-compression_level', '8', '-ar', '96k']

            cmd2.append(dst)
            subprocess.run(cmd2, check=True, capture_output=True)

            if os.path.exists(dst):
                os.remove(f)  # Remove intermediate file
                logging.info(f"   ✓ Normalized → {os.path.basename(dst)}")

        except Exception as e:
            logging.error(f"   ❌ Loudnorm failed: {e}")


def main():
    args = get_args()
    setup_logging()

    logging.info("="*60)
    logging.info(f"AUDIO PROCESSING PIPELINE - ENHANCED v2.0")
    logging.info(f"Multi-Feature Silence Detection for Analog Sources")
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

    logging.info(f"\nDetection Settings:")
    logging.info(f"  Noise scan: {args.noise_scan_duration}s")
    logging.info(f"  Headroom: {args.headroom}dB")
    if args.adaptive_padding:
        logging.info(f"  Padding: ADAPTIVE ({args.min_padding}s - {args.padding}s based on SNR)")
    else:
        logging.info(f"  Padding: {args.padding}s (fixed)")
    logging.info(f"  Flux sensitivity: {args.flux_sensitivity} std devs")
    logging.info(f"  Centroid threshold: {args.centroid_threshold}Hz")
    logging.info(f"  Content score min: {args.content_score_min}/4")
    if args.use_multiband:
        logging.info(f"  Multi-band analysis: ENABLED")
    if args.adaptive_threshold:
        logging.info(f"  Adaptive threshold: ENABLED")

    logging.info(f"\nSafety Settings:")
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
    logging.info("\n" + "="*60)
    logging.info("Step 2: Loudness Normalization")
    logging.info("="*60)
    loudnorm_pass(edit_dir, args.target_I, args.target_LRA, args.target_TP, False)

    logging.info("\n✅ Processing Complete!")


if __name__ == '__main__':
    main()
