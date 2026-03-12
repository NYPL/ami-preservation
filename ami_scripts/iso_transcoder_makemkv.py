#!/usr/bin/env python3

import argparse
from pathlib import Path
import subprocess
import logging
import tempfile
import sys
import os
import shutil
import json
from pymediainfo import MediaInfo
from collections import defaultdict

# Predefined categories for classification (Updated for bwdif=1 double framerates)
CATEGORIES = {
    "NTSC DVD SD (D1 Resolution)": {
        "Width": 720,
        "Height": 480,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "0.889",
        "FrameRate": "59.940",
    },
    "NTSC DVD Widescreen": {
        "Width": 720,
        "Height": 480,
        "DisplayAspectRatio": "1.777",
        "PixelAspectRatio": "1.185",
        "FrameRate": "59.940",
    },
    "NTSC DVD SD (4SIF Resolution)": {
        "Width": 704,
        "Height": 480,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "0.909",
        "FrameRate": "59.940",
    },
    "NTSC DVD (SIF Resolution)": {
        "Width": 352,
        "Height": 240,
        "DisplayAspectRatio": "1.339",
        "PixelAspectRatio": "0.913",
        "FrameRate": "59.940",
    },
    "NTSC DVD (China Video Disc Resolution)": {
        "Width": 352,
        "Height": 480,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "1.818",
        "FrameRate": "59.940",
    },
    "PAL DVD SD (D1 Resolution)": {
        "Width": 720,
        "Height": 576,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "1.067",
        "FrameRate": "50.000",
    },
    "PAL DVD Widescreen": {
        "Width": 720,
        "Height": 576,
        "DisplayAspectRatio": "1.778",
        "PixelAspectRatio": "1.422",
        "FrameRate": "50.000",
    },
    "PAL DVD (CIF Resolution)": {
        "Width": 352,
        "Height": 288,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "1.092",
        "FrameRate": "50.000",
    },
    "PAL DVD Half-D1 Resolution": {
        "Width": 352,
        "Height": 576,
        "DisplayAspectRatio": "1.333",
        "PixelAspectRatio": "2.182",
        "FrameRate": "50.000",
    },
    "PAL DVD Half-D1 Resolution Widescreen": {
        "Width": 352,
        "Height": 576,
        "DisplayAspectRatio": "1.778",
        "PixelAspectRatio": "2.909",
        "FrameRate": "50.000",
    },
}

# Check for colorama installation
try:
    from colorama import Fore, Style
except ImportError:
    print("colorama is not installed. Please install it by running: python3 -m pip install colorama")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def verify_dependencies():
    """Verify MakeMKV, MKVToolNix, and OCR tools are installed."""
    try:
        subprocess.run(["makemkvcon", "-r", "info", "disc:9999"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass  # Expected failure, but makemkvcon is installed.
    except FileNotFoundError:
        logging.error("makemkvcon is not found in your system's path. Please make sure MakeMKV is installed.")
        sys.exit(1)

    for cmd in ['mkvmerge', 'mkvextract', 'vobsub-to-srt']:
        if shutil.which(cmd) is None:
            logging.error(f"Required command '{cmd}' not found in PATH.")
            if cmd == 'vobsub-to-srt':
                logging.error("Please install it: npm install -g vobsub-to-srt")
            elif cmd in ['mkvmerge', 'mkvextract']:
                logging.error("Please install it: brew install mkvtoolnix")
            sys.exit(1)


def process_iso_with_makemkv(iso_path, output_directory):
    logging.info(f"Processing ISO {iso_path} with MakeMKV")
    output_path = Path(tempfile.mkdtemp())  # Temporary directory for MKVs
    
    makemkv_command = ["makemkvcon", "mkv", f"iso:{iso_path}", "all", str(output_path)]
    try:
        subprocess.run(makemkv_command, check=True)
        logging.info(f"MKV files created from {iso_path} in {output_path}")
        return output_path
    except subprocess.CalledProcessError:
        logging.error(f"MakeMKV processing failed for {iso_path}")
        return None
    

def build_ffmpeg_command(input_file, output_file):
    ffmpeg_command = [
        "ffmpeg", "-i", str(input_file),
        "-c:v", "libx264",
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        "-crf", "21", 
        "-vf", "idet,bwdif=1",
        "-c:a", "aac",
        "-b:a", "320000",
        "-ar", "48000",
        str(output_file)
    ]
    return ffmpeg_command


# --- Subtitle Processing Functions ---

def get_subtitle_tracks(mkv_file):
    """Use mkvmerge to identify the exact track IDs for VobSub streams."""
    cmd = ["mkvmerge", "-J", str(mkv_file)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"mkvmerge failed to probe {mkv_file.name}: {e.stderr}")
        return []

    sub_tracks = []
    for track in data.get('tracks', []):
        if track.get('type') == 'subtitles' and track.get('codec') == 'VobSub':
            track_id = track.get('id')
            lang = track.get('properties', {}).get('language', 'eng')
            sub_tracks.append((track_id, lang))
            
    return sub_tracks


def extract_and_ocr(mkv_file, output_dir, final_base_name):
    """Extract VobSub tracks from an MKV using mkvextract and OCR them."""
    sub_tracks = get_subtitle_tracks(mkv_file)
            
    if not sub_tracks:
        logging.info(f"No VobSub tracks found in {mkv_file.name} for extraction.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        for track_id, lang in sub_tracks:
            logging.info(f"[{mkv_file.name}] Extracting Subtitle Track ID {track_id} (Lang: {lang})")
            
            temp_base = Path(temp_dir) / f"sub_{track_id}"
            temp_idx = temp_base.with_suffix('.idx')
            temp_srt = temp_base.with_suffix('.srt')
            
            # Extract idx/sub cleanly using mkvextract
            mkvextract_cmd = [
                "mkvextract", str(mkv_file), "tracks", f"{track_id}:{temp_idx}"
            ]
            
            try:
                subprocess.run(mkvextract_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"mkvextract failed for track ID {track_id}: {e.stderr}")
                continue
            
            if not temp_idx.exists():
                logging.error(f"mkvextract failed to create .idx for track ID {track_id}")
                continue

            # OCR with vobsub-to-srt
            logging.info(f"[{mkv_file.name}] Running Apple Native OCR on Track {track_id}...")
            vobsub_cmd = [
                "vobsub-to-srt", "-i", str(temp_idx), "-o", str(temp_srt), "-q", "accurate"
            ]
            
            try:
                subprocess.run(vobsub_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"OCR failed for track {track_id}: {e.stderr}")
                continue

            # Rename and Move Resulting SRT to match the target MP4 name
            if temp_srt.exists():
                final_srt = output_dir / f"{final_base_name}_{lang}.srt"
                
                # Prevent overwriting if multiple tracks have the same language
                counter = 1
                while final_srt.exists():
                    final_srt = output_dir / f"{final_base_name}_{lang}_{counter}.srt"
                    counter += 1
                    
                shutil.move(str(temp_srt), str(final_srt))
                logging.info(f"Success -> Created SRT: {final_srt.name}")
            else:
                logging.error(f"OCR failed to produce an SRT for track {track_id}")

# --- End Subtitle Processing Functions ---


def verify_mkv_compatibility(mkv_files):
    """Verify that MKV files are compatible for concatenation."""
    if not mkv_files:
        return False
        
    base_props = None
    
    for mkv_file in mkv_files:
        media_info = MediaInfo.parse(str(mkv_file))
        current_props = {}
        
        for track in media_info.tracks:
            if track.track_type == "Video":
                current_props.update({
                    "width": track.width,
                    "height": track.height,
                    "frame_rate": track.frame_rate,
                    "pixel_format": track.pixel_format,
                    "codec_id": track.codec_id
                })
            elif track.track_type == "Audio":
                current_props.update({
                    "audio_format": track.format,
                    "channels": track.channel_s,
                    "sampling_rate": track.sampling_rate
                })
        
        if base_props is None:
            base_props = current_props
        elif current_props != base_props:
            logging.error(f"File {mkv_file.name} has different properties than the first file:")
            for key in base_props:
                if key in current_props and base_props[key] != current_props[key]:
                    logging.error(f"  {key}: {base_props[key]} != {current_props[key]}")
            return False
            
    return True


def concatenate_mkvs(mkv_files):
    """Concatenate MKV files using mkvmerge with enhanced error handling."""
    if not mkv_files:
        logging.error("No MKV files provided for concatenation.")
        return None
        
    # Verify file compatibility first
    if not verify_mkv_compatibility(mkv_files):
        logging.error("MKV files are not compatible for concatenation")
        return None
        
    try:
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp_mkv_file:
            mkvmerge_command = ["mkvmerge", "-o", tmp_mkv_file.name, str(mkv_files[0])]
            for mkv_file in mkv_files[1:]:
                mkvmerge_command.extend(["+", str(mkv_file)])
                
            logging.info(f"Attempting concatenation with command: {' '.join(mkvmerge_command)}")
            result = subprocess.run(mkvmerge_command, capture_output=True, text=True)
            
            if result.returncode == 0:
                logging.info("Concatenation successful")
                return tmp_mkv_file.name
            else:
                logging.warning("First concatenation attempt failed, trying with --append-mode track")
                mkvmerge_command.insert(1, "--append-mode")
                mkvmerge_command.insert(2, "track")
                
                result = subprocess.run(mkvmerge_command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logging.info("Concatenation successful with --append-mode track")
                    return tmp_mkv_file.name
                else:
                    logging.error(f"Both concatenation attempts failed. Error: {result.stderr}")
                    if os.path.exists(tmp_mkv_file.name):
                        os.unlink(tmp_mkv_file.name)
                    return None
                    
    except Exception as e:
        logging.error(f"Unexpected error during concatenation: {str(e)}")
        if 'tmp_mkv_file' in locals() and os.path.exists(tmp_mkv_file.name):
            os.unlink(tmp_mkv_file.name)
        return None


def transcode_mkv_files(mkv_directory, iso_basename, output_directory, force_concat):
    mkv_files = sorted(mkv_directory.glob("*.mkv"))
    if not mkv_files:
        logging.error(f"No MKV files found in {mkv_directory}")
        return False
    
    if force_concat:
        logging.info(f"Found {len(mkv_files)} MKV files to concatenate")
        concatenated_mkv = concatenate_mkvs(mkv_files)
        
        if concatenated_mkv:
            final_base_name = f"{iso_basename}_sc"
            output_file = output_directory / f"{final_base_name}.mp4"
            
            # Run Subtitle Extraction on the concatenated file
            extract_and_ocr(concatenated_mkv, output_directory, final_base_name)
            
            logging.info(f"Transcoding concatenated MKV to {output_file}")
            try:
                ffmpeg_command = build_ffmpeg_command(concatenated_mkv, output_file)
                subprocess.run(ffmpeg_command, check=True)
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Transcoding failed for concatenated MKV: {e}")
                return False
            finally:
                if os.path.exists(concatenated_mkv):
                    os.unlink(concatenated_mkv)
        else:
            logging.error("Concatenation failed, falling back to individual file processing")
            return transcode_mkv_files(mkv_directory, iso_basename, output_directory, force_concat=False)
    else:
        success = True
        for idx, mkv_file in enumerate(mkv_files, start=1):
            # Determine the exact base name for this specific file
            final_base_name = f"{iso_basename}f01r{str(idx).zfill(2)}_sc" if len(mkv_files) > 1 else f"{iso_basename}_sc"
            output_file = output_directory / f"{final_base_name}.mp4"
            
            # Run Subtitle Extraction on the individual file
            extract_and_ocr(mkv_file, output_directory, final_base_name)
            
            logging.info(f"Transcoding {mkv_file} to {output_file}")
            try:
                ffmpeg_command = build_ffmpeg_command(mkv_file, output_file)
                subprocess.run(ffmpeg_command, check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Transcoding failed for {mkv_file}: {e}")
                success = False
                
        return success


def verify_transcoding(iso_paths, make_mkv_failures, output_directory):
    total_isos = len(iso_paths) + len(make_mkv_failures)
    successful_isos = []
    failed_isos = make_mkv_failures[:] 

    print(f"\n{Style.BRIGHT}File Creation Summary:{Style.RESET_ALL}")

    for iso_path in iso_paths:
        iso_basename = iso_path.stem.replace("_pm", "")
        expected_output_files = [file for file in os.listdir(output_directory) if file.startswith(iso_basename) and file.endswith('.mp4')]

        if not expected_output_files:
            logging.error(f"No MP4 files were created for ISO: {iso_path}")
            failed_isos.append(iso_path)
        else:
            logging.info(f"{len(expected_output_files)} MP4 files were created for ISO: {iso_path}")
            successful_isos.append(iso_path)

    print(f"\n{Style.BRIGHT}Processing Summary:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total ISOs processed: {total_isos}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Successfully processed: {len(successful_isos)}{Style.RESET_ALL}")
    print(f"{Fore.RED}Failed to process: {len(failed_isos)}{Style.RESET_ALL}")

    if failed_isos:
        print(f"\n{Fore.RED}List of failed ISOs:{Style.RESET_ALL}")
        for iso in failed_isos:
            print(f" - {iso}")


def extract_video_properties(file_path):
    media_info = MediaInfo.parse(file_path)
    for track in media_info.tracks:
        if track.track_type == "Video":
            return {
                "Width": track.width,
                "Height": track.height,
                "DisplayAspectRatio": track.display_aspect_ratio,
                "PixelAspectRatio": track.pixel_aspect_ratio,
                "FrameRate": track.frame_rate,
            }
    return None


def classify_mp4(mp4_files):
    classification_counts = defaultdict(int)
    outliers = []

    for file in mp4_files:
        properties = extract_video_properties(file)
        if not properties:
            outliers.append(file)
            continue

        classified = False
        for category, criteria in CATEGORIES.items():
            match = True
            for key, value in criteria.items():
                prop_val = properties.get(key)
                if prop_val is None:
                    match = False
                    break
                
                # If it's a number/float (like FrameRate or Aspect Ratio), compare mathematically
                try:
                    if float(prop_val) != float(value):
                        match = False
                        break
                except (ValueError, TypeError):
                    # Fallback to string comparison if it's not a number
                    if str(prop_val) != str(value):
                        match = False
                        break
                        
            if match:
                classification_counts[category] += 1
                classified = True
                break

        if not classified:
            outliers.append(file)

    return classification_counts, outliers


def summarize_classifications(classification_counts, outliers):
    print("\nClassification Summary:")
    for category, count in classification_counts.items():
        print(f"- {category}: {count} MP4(s)")

    print("\nOutliers:")
    if outliers:
        for outlier in outliers:
            print(f"- {outlier}")
    else:
        print("None")


def post_process_check(output_directory):
    mp4_files = list(Path(output_directory).glob("*.mp4"))
    classification_counts, outliers = classify_mp4(mp4_files)
    summarize_classifications(classification_counts, outliers)


def main():
    parser = argparse.ArgumentParser(description='Transcode MKV files created from ISO images to H.264 MP4s and extract OCR subtitles.')
    parser.add_argument('-i', '--input', dest='i', required=True, help='Path to the input directory with ISO files')
    parser.add_argument('-o', '--output', dest='o', required=True, help='Output directory for MP4 and SRT files')
    parser.add_argument('-f', '--force', action='store_true', help='Force concatenation of MKV files before transcoding')
    args = parser.parse_args()

    verify_dependencies()

    input_directory = Path(args.i)
    output_directory = Path(args.o)
    output_directory.mkdir(parents=True, exist_ok=True)

    iso_files = [file for file in sorted(input_directory.glob('*.iso')) if not file.name.startswith('._')]
    processed_iso_paths = []
    make_mkv_failures = []

    for iso_file in iso_files:
        iso_basename = iso_file.stem.replace("_pm", "")
        mkv_output_dir = process_iso_with_makemkv(iso_file, output_directory)

        if mkv_output_dir:
            transcode_success = transcode_mkv_files(mkv_output_dir, iso_basename, output_directory, args.force)
            if transcode_success:
                processed_iso_paths.append(iso_file)
            else:
                logging.error(f"Skipping verification for {iso_file} due to transcoding failure.")
            # Clean up temporary MKV directory
            for mkv_file in mkv_output_dir.glob("*.mkv"):
                mkv_file.unlink()
            mkv_output_dir.rmdir()
        else:
            logging.error(f"MakeMKV processing failed for {iso_file}.")
            make_mkv_failures.append(iso_file)

    verify_transcoding(processed_iso_paths, make_mkv_failures, output_directory)
    post_process_check(output_directory)

if __name__ == "__main__":
    main()