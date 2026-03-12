#!/usr/bin/env python3

import argparse
import subprocess
import logging
import tempfile
import shutil
import sys
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_dependencies():
    """Ensure mkvtoolnix (mkvmerge/mkvextract) and vobsub-to-srt are installed."""
    for cmd in ['mkvmerge', 'mkvextract', 'vobsub-to-srt']:
        if shutil.which(cmd) is None:
            logging.error(f"Required command '{cmd}' not found in PATH.")
            if cmd == 'vobsub-to-srt':
                logging.error("Please install it: npm install -g vobsub-to-srt")
            elif cmd in ['mkvmerge', 'mkvextract']:
                logging.error("Please install it: brew install mkvtoolnix")
            sys.exit(1)

def get_subtitle_tracks(mkv_file):
    """Use mkvmerge to safely identify the exact track IDs for VobSub streams."""
    cmd = [
        "mkvmerge", "-J", str(mkv_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"mkvmerge failed to probe {mkv_file.name}: {e.stderr}")
        return []

    sub_tracks = []
    
    for track in data.get('tracks', []):
        # MKVToolNix identifies dvdsub as 'VobSub' in its JSON output
        if track.get('type') == 'subtitles' and track.get('codec') == 'VobSub':
            track_id = track.get('id')
            lang = track.get('properties', {}).get('language', 'eng')
            sub_tracks.append((track_id, lang))
            
    return sub_tracks

def extract_and_ocr(mkv_file):
    """Extract VobSub tracks from an MKV using mkvextract and OCR them."""
    logging.info(f"Probing: {mkv_file.name}")
    
    sub_tracks = get_subtitle_tracks(mkv_file)
            
    if not sub_tracks:
        logging.info(f"No usable VobSub tracks found in {mkv_file.name}. Skipping.\n" + "-"*40)
        return

    base_name = mkv_file.stem.replace('_pm', '')
    out_dir = mkv_file.parent

    with tempfile.TemporaryDirectory() as temp_dir:
        for track_id, lang in sub_tracks:
            logging.info(f"[{mkv_file.name}] Extracting Subtitle Track ID {track_id} (Lang: {lang})")
            
            temp_base = Path(temp_dir) / f"sub_{track_id}"
            temp_idx = temp_base.with_suffix('.idx')
            temp_srt = temp_base.with_suffix('.srt')
            
            # Step 1: Extract idx/sub cleanly using mkvextract
            mkvextract_cmd = [
                "mkvextract", str(mkv_file), "tracks",
                f"{track_id}:{temp_idx}"
            ]
            
            try:
                subprocess.run(mkvextract_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"mkvextract failed for track ID {track_id} in {mkv_file.name}")
                logging.error(f"Error:\n{e.stderr}")
                continue
            
            if not temp_idx.exists():
                logging.error(f"mkvextract failed to create .idx for track ID {track_id}")
                continue

            # Step 2: OCR with vobsub-to-srt (Apple Vision Framework)
            logging.info(f"[{mkv_file.name}] Running Apple Native OCR on Track {track_id}... (This may take a minute)")
            
            vobsub_cmd = [
                "vobsub-to-srt", "-i", str(temp_idx), "-o", str(temp_srt), "-q", "accurate"
            ]
            
            try:
                subprocess.run(vobsub_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"OCR failed for track {track_id} in {mkv_file.name}")
                logging.debug(f"Error: {e.stderr}")
                continue

            # Step 3: Rename and Move Resulting SRT
            if temp_srt.exists():
                final_srt = out_dir / f"{base_name}_{lang}.srt"
                
                counter = 1
                while final_srt.exists():
                    final_srt = out_dir / f"{base_name}_{lang}_{counter}.srt"
                    counter += 1
                    
                shutil.move(str(temp_srt), str(final_srt))
                logging.info(f"Success -> Created: {final_srt.name}")
            else:
                logging.error(f"OCR failed to produce an SRT for track {track_id}")
                
    print("-" * 40)

def main():
    parser = argparse.ArgumentParser(description='Extract VobSub tracks from MKVs and OCR them to SRT files using macOS Vision.')
    parser.add_argument('-i', '--input', dest='input_path', required=True, help='Path to an MKV file or directory of MKVs')
    args = parser.parse_args()

    check_dependencies()

    input_path = Path(args.input_path)

    if input_path.is_file() and input_path.suffix.lower() == '.mkv':
        extract_and_ocr(input_path)
    elif input_path.is_dir():
        mkv_files = sorted([f for f in input_path.glob('*.mkv') if not f.name.startswith('._')])
        if not mkv_files:
            logging.error(f"No MKV files found in directory: {input_path}")
            sys.exit(1)
            
        for mkv in mkv_files:
            extract_and_ocr(mkv)
    else:
        logging.error("Input must be a valid MKV file or a directory containing MKV files.")
        sys.exit(1)

if __name__ == "__main__":
    main()