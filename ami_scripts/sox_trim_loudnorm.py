#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import re
import logging
import json
import shutil

def get_args():
    p = argparse.ArgumentParser(
        description="Automate: trim via SoX → loudnorm → optional denoise"
    )
    p.add_argument('-s','--source', required=True,
                   help='Directory containing PreservationMasters audio files')
    p.add_argument('--denoise', action='store_true',
                   help='Apply FFmpeg arnndn denoise filter after loudnorm')
    p.add_argument('--noise-scan-duration', type=float, default=30.0,
                   help='Seconds to scan for noise floor (default: 30.0)')
    p.add_argument('--silence-duration', type=float, default=0.1,
                   help='Minimum silence duration in seconds (default: 0.1)')
    p.add_argument('--headroom', type=float, default=3.0,
                   help='dB above noise floor to set silence threshold (default: 3.0)')
    p.add_argument('--padding', type=float, default=2.0,
                   help='Seconds of silence to pad on each side after trimming (default: 2.0)')
    p.add_argument('--dry-run', action='store_true',
                   help="Show commands without running them")
    p.add_argument('--verbose', action='store_true',
                   help="Enable debug logging")
    # loudnorm settings
    p.add_argument('--target-I', type=float, default=-20.0,
                   help='Target integrated loudness LUFS (default: -20.0)')
    p.add_argument('--target-LRA', type=float, default=7.0,
                   help='Target loudness range LRA (default: 7.0)')
    p.add_argument('--target-TP', type=float, default=-2.0,
                   help='Target true peak in dBTP (default: -2.0)')
    return p.parse_args()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=level)

def get_audio_duration(path: str) -> float:
    cmd = ['ffprobe','-v','quiet','-show_entries','format=duration',
           '-of','csv=p=0', path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except:
        return 0.0

def detect_noise_floor(path: str, scan_duration: float) -> float:
    """Measure mean_volume over first N seconds to estimate noise floor."""
    cmd = [
        'ffmpeg','-hide_banner','-nostats',
        '-t', str(scan_duration),
        '-i', path,
        '-af','volumedetect',
        '-f','null','-'
    ]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    m = re.search(r'mean_volume:\s*([-0-9\.]+)\s*dB', proc.stderr)
    if m:
        nf = float(m.group(1))
        logging.debug(f"  [noise floor] mean_volume = {nf:.1f} dB")
        return nf
    logging.warning("  Could not detect noise floor → defaulting to -65 dB")
    return -65.0

def trim_with_sox(args):
    src_files = []
    for root,_,files in os.walk(args.source):
        for f in files:
            if f.lower().endswith(('.wav','flac')):
                src_files.append(os.path.join(root, f))
    if not src_files:
        logging.error("No audio files found to process")
        sys.exit(1)

    edit_dir = args.source.replace('PreservationMasters','EditMasters')
    os.makedirs(edit_dir, exist_ok=True)

    for src in sorted(src_files):
        fn = os.path.basename(src)
        base, ext = os.path.splitext(fn)
        temp_name = base.replace('_pm','_temp') + ext
        dst = os.path.join(edit_dir, temp_name)

        logging.info(f"▶ Trimming {fn}")

        # 1) measure noise floor
        nf = detect_noise_floor(src, args.noise_scan_duration)
        thresh_db = nf + args.headroom
        # convert dB threshold to SoX % amplitude
        pct = 10 ** (thresh_db / 20) * 100
        pct = min(pct, 10.0)  # cap at 10%
        thresh_pct = f"{pct:.2f}%"
        logging.info(f"   noise_floor={nf:.1f}dB → thresh={thresh_db:.1f}dB → {thresh_pct}")

        # 2) SoX silence removal with padding
        cmd = [
            'sox', src, dst,
            'silence', '1', str(args.silence_duration), thresh_pct,
            'reverse',
            'silence', '1', str(args.silence_duration), thresh_pct,
            'reverse',
            'pad', str(args.padding), str(args.padding)
        ]

        if args.dry_run:
            logging.info("   DRY RUN: "+" ".join(cmd))
            continue

        logging.debug("   CMD: "+" ".join(cmd))
        subprocess.run(cmd, check=True)

        new_dur = get_audio_duration(dst)
        logging.info(f"   ✓ trimmed & padded → {new_dur:.2f}s (added {args.padding*2:.1f}s padding)")

def loudnorm_improved(
    edit_path: str,
    target_I: float,
    target_LRA: float,
    target_TP: float,
    dry_run: bool = False
):
    """Fixed loudness normalization with proper JSON parsing."""
    edit_files = sorted(
        os.path.join(edit_path, f)
        for _,_,files in os.walk(edit_path)
        for f in files if f.lower().endswith(('.wav','flac')) and '_temp' in f
    )
    for f in edit_files:
        base, ext = os.path.splitext(f)
        out_name = os.path.basename(base).replace('_temp','_em') + ext
        dst = os.path.join(edit_path, out_name)

        logging.info(f"▶ Loudnorm {os.path.basename(f)}")
        if dry_run:
            logging.info(f"   [DRY RUN] Would create: {dst}")
            continue

        I, LRA, TP = target_I, target_LRA, target_TP
        first_pass = [
            'ffmpeg','-hide_banner','-nostats','-i',f,
            '-af', f'loudnorm=dual_mono=true:I={I}:LRA={LRA}:TP={TP}:print_format=json',
            '-f','null','-'
        ]
        try:
            logging.debug("   First pass: "+" ".join(first_pass))
            proc = subprocess.run(first_pass, stderr=subprocess.PIPE, text=True, check=True)
            stderr = proc.stderr
            js_start = stderr.rfind('{')
            js_end   = stderr.rfind('}')
            if js_start != -1 and js_end > js_start:
                stats = json.loads(stderr[js_start:js_end+1])
            else:
                # fallback line-by-line
                stats = {}
                for line in stderr.splitlines():
                    if ':' in line and '"' in line:
                        k,v = line.strip().strip(',').split(':',1)
                        stats[k.strip().strip('"')] = v.strip().strip('"')
                if 'input_i' not in stats:
                    raise ValueError("no loudnorm JSON")
            logging.debug(f"   Measured: I={stats['input_i']} LRA={stats['input_lra']} TP={stats['input_tp']}")
        except Exception as e:
            logging.error(f"   First pass failed: {e}")
            continue

        second_pass = [
            'ffmpeg','-hide_banner','-y','-i',f,
            '-af',(
                f"loudnorm=dual_mono=true:linear=true:"
                f"I={I}:LRA={LRA}:TP={TP}:"
                f"measured_I={stats['input_i']}:"
                f"measured_LRA={stats['input_lra']}:"
                f"measured_TP={stats['input_tp']}:"
                f"measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}"
            )
        ]
        if ext.lower()=='.wav':
            second_pass += ['-f','wav','-rf64','auto','-c:a','pcm_s24le','-ar','96k']
        else:
            second_pass += ['-c:a','flac','-compression_level','8','-ar','96k']
        second_pass.append(dst)

        try:
            logging.debug("   Second pass: "+" ".join(second_pass))
            subprocess.run(second_pass, check=True)
            if os.path.exists(dst):
                os.remove(f)
                logging.info(f"   ✓ Normalized → {os.path.basename(dst)}")
            else:
                raise FileNotFoundError("Output not created")
        except Exception as e:
            logging.error(f"   Second pass failed: {e}")

def denoise_improved(edit_path: str, dry_run: bool = False):
    """Improved denoising with validation."""
    model_path = "./arnndn-models/bd.rnnn"
    if not os.path.exists(model_path):
        logging.error(f"Model not found: {model_path}")
        return

    dn_files = sorted(
        os.path.join(edit_path, f)
        for _,_,files in os.walk(edit_path)
        for f in files if f.lower().endswith(('.wav','flac')) and '_em' in f
    )
    for f in dn_files:
        base, ext = os.path.splitext(f)
        out_name = os.path.basename(base).replace('_em','_denoise') + ext
        dst = os.path.join(edit_path, out_name)

        logging.info(f"▶ Denoising {os.path.basename(f)}")
        if dry_run:
            logging.info(f"   [DRY RUN] Would create: {dst}")
            continue

        cmd = ['ffmpeg','-hide_banner','-y','-i',f,'-af',f'arnndn=m={model_path}']
        if ext.lower()=='.wav':
            cmd += ['-f','wav','-rf64','auto','-c:a','pcm_s24le','-ar','96k']
        else:
            cmd += ['-c:a','flac','-compression_level','8','-ar','96k']
        cmd.append(dst)

        try:
            logging.debug("   CMD: "+" ".join(cmd))
            subprocess.run(cmd, check=True)
            if os.path.exists(dst):
                os.remove(f)
                logging.info(f"   ✓ Denoised → {os.path.basename(dst)}")
            else:
                raise FileNotFoundError("Output not created")
        except Exception as e:
            logging.error(f"   Denoise failed: {e}")

def main():
    args = get_args()
    setup_logging(args.verbose)

    # 1) Trim silence via SoX → *_temp
    trim_with_sox(args)

    # Determine edit directory
    edit_dir = args.source.replace('PreservationMasters','EditMasters')

    # 2) Loudnorm → *_em
    loudnorm_improved(
        edit_path=edit_dir,
        target_I=args.target_I,
        target_LRA=args.target_LRA,
        target_TP=args.target_TP,
        dry_run=args.dry_run
    )

    # 3) Optional denoise → *_denoise
    if args.denoise:
        denoise_improved(edit_path=edit_dir, dry_run=args.dry_run)

    logging.info("✅ All done!")

if __name__=='__main__':
    main()