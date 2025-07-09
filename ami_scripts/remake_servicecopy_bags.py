#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from pymediainfo import MediaInfo
except ImportError:
    print("Error: pymediainfo is required. Install with: pip install pymediainfo")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
REQUIRED_BAGIT_FILES = ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt']
SILENCE_THRESHOLD = -60.0  # dB
DEFAULT_MATCH_THRESHOLD = 5
DEFAULT_PROBE_DURATION = 120
CHUNK_SIZE = 4096


def is_bag(directory: Path) -> bool:
    """
    Check that a directory has the required BagIt metadata files.
    
    Args:
        directory: Path to directory to check
        
    Returns:
        True if directory contains all required BagIt files
    """
    if not directory.is_dir():
        return False
    
    return all((directory / fname).exists() for fname in REQUIRED_BAGIT_FILES)


def run_command(cmd: List[str], input_data: Optional[bytes] = None, 
                capture_output: bool = True, check: bool = False) -> subprocess.CompletedProcess:
    """
    Run a subprocess command with consistent error handling.
    
    Args:
        cmd: Command and arguments to run
        input_data: Optional input data to pass to stdin
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise exception on non-zero exit
        
    Returns:
        CompletedProcess result
        
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
    """
    try:
        result = subprocess.run(
            cmd, 
            input=input_data, 
            capture_output=capture_output, 
            text=True if input_data is None else False,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        logger.error(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise


def detect_ltc_in_channel(input_file: Path, stream_index: int, channel: str, 
                         probe_duration: int = DEFAULT_PROBE_DURATION, 
                         match_threshold: int = DEFAULT_MATCH_THRESHOLD) -> bool:
    """
    Detect LTC (Linear Time Code) in a specific audio channel.
    
    Args:
        input_file: Path to input media file
        stream_index: Audio stream index
        channel: 'left' or 'right'
        probe_duration: Duration in seconds to analyze
        match_threshold: Minimum matches required to consider LTC valid
        
    Returns:
        True if LTC is detected with sufficient matches
    """
    if channel not in ['left', 'right']:
        raise ValueError("Channel must be 'left' or 'right'")
    
    # Set up channel mapping
    pan_filter = 'pan=mono|c0=c0' if channel == 'left' else 'pan=mono|c0=c1'

    # Build FFmpeg command for audio extraction
    ffmpeg_cmd = [
        "ffmpeg",
        "-t", str(probe_duration),
        "-i", str(input_file),
        "-map", f"0:{stream_index}",
        "-af", pan_filter,
        "-ar", "48000",
        "-ac", "1",
        "-f", "wav",
        "pipe:1"
    ]

    ltcdump_cmd = ["ltcdump", "-"]

    try:
        # Run FFmpeg -> ltcdump pipeline
        with subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as ffmpeg_proc:
            with subprocess.Popen(ltcdump_cmd, stdin=ffmpeg_proc.stdout, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                text=True) as ltcdump_proc:
                ffmpeg_proc.stdout.close()  # Allow ffmpeg to receive SIGPIPE
                ltcdump_out, ltcdump_err = ltcdump_proc.communicate()
                ffmpeg_proc.wait()

        # Extract timecode matches (HH:MM:SS:FF format)
        matches = re.findall(r'\d{2}:\d{2}:\d{2}:\d{2}', ltcdump_out)
        
        logger.debug(f"LTC analysis for {input_file} stream {stream_index} {channel}: {len(matches)} matches")
        if matches:
            logger.debug(f"First few matches: {matches[:5]}")

        return len(matches) >= match_threshold

    except Exception as e:
        logger.warning(f"LTC detection failed for {input_file} stream {stream_index} {channel}: {e}")
        return False


def analyze_audio_volume(input_file: Path, stream_index: int, channel: str, 
                        probe_duration: int = DEFAULT_PROBE_DURATION) -> Optional[float]:
    """
    Analyze the volume of a specific audio channel.
    
    Args:
        input_file: Path to input media file
        stream_index: Audio stream index
        channel: 'left' or 'right'
        probe_duration: Duration in seconds to analyze
        
    Returns:
        Mean volume in dB, or None if analysis fails
    """
    if channel not in ['left', 'right']:
        raise ValueError("Channel must be 'left' or 'right'")
    
    pan_filter = 'pan=mono|c0=c0' if channel == 'left' else 'pan=mono|c0=c1'
    
    cmd = [
        "ffmpeg", "-t", str(probe_duration), "-i", str(input_file),
        "-map", f"0:{stream_index}",
        "-af", f"{pan_filter},volumedetect", "-f", "null", "-"
    ]
    
    try:
        result = run_command(cmd, capture_output=True)
        match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)", result.stderr)
        return float(match.group(1)) if match else None
    except Exception as e:
        logger.warning(f"Volume analysis failed for {input_file} stream {stream_index} {channel}: {e}")
        return None


def detect_audio_pan(input_file: Path, audio_pan: str, 
                    probe_duration: int = DEFAULT_PROBE_DURATION) -> List[str]:
    """
    Generate pan filter strings for audio streams based on analysis.
    
    Args:
        input_file: Path to input media file
        audio_pan: Pan mode ('none', 'left', 'right', 'center', 'auto')
        probe_duration: Duration in seconds to analyze
        
    Returns:
        List of FFmpeg pan filter strings
    """
    if audio_pan not in ['none', 'left', 'right', 'center', 'auto']:
        raise ValueError(f"Invalid audio_pan value: {audio_pan}")
    
    # Get audio stream indices
    ffprobe_cmd = [
        "ffprobe", "-i", str(input_file),
        "-show_entries", "stream=index:stream=codec_type",
        "-select_streams", "a", "-of", "compact=p=0:nk=1", "-v", "0"
    ]
    
    try:
        result = run_command(ffprobe_cmd)
        audio_streams = [
            int(line.split('|')[0]) 
            for line in result.stdout.splitlines() 
            if "audio" in line
        ]
    except Exception as e:
        logger.error(f"Failed to detect audio streams in {input_file}: {e}")
        return []

    logger.info(f"Detected {len(audio_streams)} audio streams: {audio_streams} in {input_file}")

    pan_filters = []
    pan_filter_idx = 0

    for stream_index in audio_streams:
        logger.info(f"Analyzing audio stream: {stream_index}")

        # Analyze channel volumes
        left_volume = analyze_audio_volume(input_file, stream_index, 'left', probe_duration)
        right_volume = analyze_audio_volume(input_file, stream_index, 'right', probe_duration)

        if left_volume is None or right_volume is None:
            logger.warning(f"Stream {stream_index}: Unable to analyze audio. Skipping.")
            continue

        logger.info(f"Stream {stream_index} - Left: {left_volume}dB, Right: {right_volume}dB")

        # LTC detection for auto mode
        left_has_ltc = False
        right_has_ltc = False
        
        if audio_pan == "auto":
            left_has_ltc = detect_ltc_in_channel(input_file, stream_index, 'left', probe_duration)
            right_has_ltc = detect_ltc_in_channel(input_file, stream_index, 'right', probe_duration)

        # Apply logic for stream processing
        if left_has_ltc and not right_has_ltc:
            if right_volume <= SILENCE_THRESHOLD:
                logger.info(f"Stream {stream_index}: LTC + silence detected. Dropping stream.")
                continue
            else:
                logger.info(f"Stream {stream_index}: Left LTC detected. Using right channel.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
        elif right_has_ltc and not left_has_ltc:
            if left_volume <= SILENCE_THRESHOLD:
                logger.info(f"Stream {stream_index}: LTC + silence detected. Dropping stream.")
                continue
            else:
                logger.info(f"Stream {stream_index}: Right LTC detected. Using left channel.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
        else:
            # Handle volume-based panning
            if right_volume > SILENCE_THRESHOLD and left_volume <= SILENCE_THRESHOLD:
                logger.info(f"Stream {stream_index}: Right-only audio. Panning to center.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
            elif left_volume > SILENCE_THRESHOLD and right_volume <= SILENCE_THRESHOLD:
                logger.info(f"Stream {stream_index}: Left-only audio. Panning to center.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
            else:
                logger.info(f"Stream {stream_index}: Balanced audio. No panning.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c1[outa{pan_filter_idx}]")
        
        pan_filter_idx += 1

    return pan_filters


def get_video_resolution(input_file: Path) -> Tuple[int, int]:
    """
    Get video resolution using ffprobe.
    
    Args:
        input_file: Path to video file
        
    Returns:
        Tuple of (width, height) as integers
        
    Raises:
        ValueError: If resolution cannot be determined
    """
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(input_file)
    ]

    try:
        result = run_command(cmd, check=True)
        width_str, height_str = result.stdout.strip().split(",")
        return int(width_str), int(height_str)
    except Exception as e:
        logger.error(f"Failed to get resolution for {input_file}: {e}")
        raise ValueError(f"Could not determine resolution for {input_file}")


def get_video_filter(width: int, height: int) -> str:
    """
    Determine appropriate video filter based on resolution.
    
    Args:
        width: Video width in pixels
        height: Video height in pixels
        
    Returns:
        FFmpeg video filter string
    """
    if (width, height) == (720, 486):
        return "idet,bwdif=1,crop=720:480:0:4,setdar=4/3"
    elif (width, height) == (720, 576):
        return "idet,bwdif=1"
    else:
        logger.warning(f"Unknown resolution {width}×{height}; using deinterlace only")
        return "idet,bwdif=1"


def remake_scs_from_pm(bag_path: Path, audio_pan: str = "none") -> List[str]:
    """
    Create new Service Copy MP4 files from Preservation Master MKV files.
    
    Args:
        bag_path: Path to BagIt bag directory
        audio_pan: Audio panning mode
        
    Returns:
        List of modified file paths
    """
    modified_files = []
    sc_dir = bag_path / 'data' / 'ServiceCopies'
    pm_dir = bag_path / 'data' / 'PreservationMasters'

    if not sc_dir.exists() or not pm_dir.exists():
        logger.warning(f"Required directories not found in {bag_path}")
        return modified_files

    for sc_file in sc_dir.glob('*_sc.mp4'):
        pm_basename = sc_file.name.replace('_sc.mp4', '_pm.mkv')
        pm_file = pm_dir / pm_basename
        
        if not pm_file.is_file():
            logger.warning(f"No PM found for {sc_file.name}; expected {pm_file.name}")
            continue

        logger.info(f"Transcoding SC from PM: {pm_file.name} → {sc_file.name}")
        temp_file = sc_file.with_suffix('.temp.mp4')

        try:
            # Get video properties and filter
            width, height = get_video_resolution(pm_file)
            video_filter = get_video_filter(width, height)

            # Get audio pan filters
            pan_filters = []
            if audio_pan != "none":
                pan_filters = detect_audio_pan(pm_file, audio_pan)

            # Build filter_complex
            filter_parts = [f"[0:v]{video_filter}[v]"]
            filter_parts.extend(pan_filters)
            filter_complex = ";".join(filter_parts)

            # Build FFmpeg command
            cmd = [
                "ffmpeg", "-i", str(pm_file),
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-c:v", "libx264", "-movflags", "faststart", 
                "-pix_fmt", "yuv420p", "-crf", "21",
            ]

            # Add audio mapping
            if pan_filters:
                for idx in range(len(pan_filters)):
                    cmd.extend([
                        "-map", f"[outa{idx}]",
                        "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
                    ])
            else:
                cmd.extend([
                    "-map", "0:a:0",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
                ])

            cmd.append(str(temp_file))

            # Execute transcoding
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            run_command(cmd, check=True)

            # Replace original file
            sc_file.unlink()
            temp_file.rename(sc_file)
            modified_files.append(str(sc_file))

        except Exception as e:
            logger.error(f"Failed to process {sc_file}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            continue

    return modified_files


def remake_scs_from_sc(bag_path: Path, audio_pan: str = "none") -> List[str]:
    """
    Create new Service Copy MP4 files from existing Service Copy files.
    
    Args:
        bag_path: Path to BagIt bag directory
        audio_pan: Audio panning mode
        
    Returns:
        List of modified file paths
    """
    modified_files = []
    sc_dir = bag_path / 'data' / 'ServiceCopies'

    if not sc_dir.exists():
        logger.warning(f"ServiceCopies directory not found in {bag_path}")
        return modified_files

    for sc_file in sc_dir.glob('*_sc.mp4'):
        logger.info(f"Re-transcoding SC file: {sc_file.name}")
        temp_file = sc_file.with_suffix('.temp.mp4')

        try:
            # Get audio pan filters
            pan_filters = []
            if audio_pan != "none":
                pan_filters = detect_audio_pan(sc_file, audio_pan)

            # Build base command
            cmd = [
                "ffmpeg", "-i", str(sc_file),
                "-map", "0:v",
                "-c:v", "libx264", "-movflags", "faststart",
                "-pix_fmt", "yuv420p", "-crf", "21",
                "-vf", "setdar=16/9"
            ]

            # Add audio processing
            if pan_filters:
                cmd.extend(["-filter_complex", ";".join(pan_filters)])
                for idx in range(len(pan_filters)):
                    cmd.extend([
                        "-map", f"[outa{idx}]", 
                        "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
                    ])
            else:
                cmd.extend([
                    "-map", "0:a", 
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
                ])

            cmd.append(str(temp_file))

            # Execute transcoding
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            run_command(cmd, check=True)

            # Replace original file
            sc_file.unlink()
            temp_file.rename(sc_file)
            modified_files.append(str(sc_file))

        except Exception as e:
            logger.error(f"Failed to process {sc_file}: {e}")
            if temp_file.exists():
                temp_file.unlink()
            continue

    return modified_files


def update_sidecar_json(data_dir: Path) -> List[str]:
    """
    Update metadata in Service Copy JSON sidecar files.
    
    Args:
        data_dir: Path to bag data directory
        
    Returns:
        List of modified JSON file paths
    """
    date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    modified_files = []

    for json_file in data_dir.rglob('*_sc.json'):
        mp4_file = json_file.with_suffix('.mp4')

        if not mp4_file.exists():
            logger.warning(f"No corresponding MP4 for {json_file}")
            continue

        try:
            logger.info(f"Updating sidecar: {json_file.name}")
            
            # Get media info
            media_info = MediaInfo.parse(str(mp4_file))
            general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
            
            if not general_tracks:
                logger.warning(f"No general track found in {mp4_file}")
                continue

            general_data = general_tracks[0].to_data()
            raw_date = general_data.get('file_last_modification_date', '') or ''
            file_size = general_data.get('file_size', '0')

            # Extract date
            date_match = date_pattern.search(raw_date)
            date_value = date_match.group(0) if date_match else ""

            # Parse file size
            try:
                size_int = int(file_size)
            except (ValueError, TypeError):
                size_int = 0

            # Update JSON file
            with open(json_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            # Update technical metadata
            technical = data.setdefault("technical", {})
            technical["dateCreated"] = date_value
            
            # Update file size
            if isinstance(technical.get("fileSize"), dict):
                technical["fileSize"]["measure"] = size_int
            else:
                technical["fileSize"] = {"measure": size_int, "unit": "bytes"}

            # Write updated JSON
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            modified_files.append(str(json_file))

        except Exception as e:
            logger.error(f"Failed to update {json_file}: {e}")
            continue

    return modified_files


def calculate_md5(file_path: Path) -> str:
    """
    Calculate MD5 checksum for a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        MD5 checksum as hex string
    """
    logger.debug(f"Calculating MD5 for: {file_path}")
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate MD5 for {file_path}: {e}")
        raise


def update_manifests(bag_path: Path, modified_paths: List[str]) -> None:
    """
    Update BagIt manifest files with new checksums.
    
    Args:
        bag_path: Path to BagIt bag directory
        modified_paths: List of modified file paths relative to bag_path
    """
    manifest_path = bag_path / 'manifest-md5.txt'
    tag_manifest_path = bag_path / 'tagmanifest-md5.txt'

    # Update manifest-md5.txt
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                parts = line.strip().split(' ', 1)
                if len(parts) != 2:
                    updated_lines.append(line)
                    continue
                    
                old_checksum, rel_path = parts
                rel_path = rel_path.strip()
                
                if rel_path in modified_paths:
                    full_path = bag_path / rel_path
                    if full_path.is_file():
                        new_checksum = calculate_md5(full_path)
                        updated_lines.append(f"{new_checksum} {rel_path}\n")
                    else:
                        logger.warning(f"File not found for manifest update: {full_path}")
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)

            with open(manifest_path, 'w') as f:
                f.writelines(updated_lines)
                
            logger.info("Updated manifest-md5.txt")

        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
            raise

    # Update tagmanifest-md5.txt
    if tag_manifest_path.exists() and manifest_path.exists():
        try:
            with open(tag_manifest_path, 'r') as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                parts = line.strip().split(' ', 1)
                if len(parts) != 2:
                    updated_lines.append(line)
                    continue
                    
                old_checksum, filename = parts
                if 'manifest-md5.txt' in filename:
                    new_checksum = calculate_md5(manifest_path)
                    updated_lines.append(f"{new_checksum} {filename}\n")
                else:
                    updated_lines.append(line)

            with open(tag_manifest_path, 'w') as f:
                f.writelines(updated_lines)
                
        except Exception as e:
            logger.error(f"Failed to update tagmanifest: {e}")
            raise


def update_payload_oxum(bag_path: Path) -> None:
    """
    Recalculate and update Payload-Oxum in bag-info.txt.
    
    Args:
        bag_path: Path to BagIt bag directory
    """
    data_path = bag_path / 'data'
    bag_info_path = bag_path / 'bag-info.txt'

    if not data_path.exists():
        logger.warning(f"Data directory not found: {data_path}")
        return

    # Calculate totals
    total_size = 0
    total_files = 0

    for file_path in data_path.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            total_files += 1

    new_oxum = f"{total_size}.{total_files}"
    logger.info(f"Calculated Payload-Oxum: {new_oxum}")

    # Update bag-info.txt
    if bag_info_path.exists():
        try:
            with open(bag_info_path, 'r') as f:
                lines = f.readlines()

            updated_lines = []
            oxum_found = False
            
            for line in lines:
                if line.startswith('Payload-Oxum:'):
                    updated_lines.append(f'Payload-Oxum: {new_oxum}\n')
                    oxum_found = True
                else:
                    updated_lines.append(line)

            if not oxum_found:
                updated_lines.append(f'Payload-Oxum: {new_oxum}\n')

            with open(bag_info_path, 'w') as f:
                f.writelines(updated_lines)
                
        except Exception as e:
            logger.error(f"Failed to update bag-info.txt: {e}")
            raise


def update_tagmanifest(bag_path: Path) -> None:
    """
    Update tagmanifest-md5.txt with new checksums for metadata files.
    
    Args:
        bag_path: Path to BagIt bag directory
    """
    tag_manifest_path = bag_path / 'tagmanifest-md5.txt'
    bag_info_path = bag_path / 'bag-info.txt'
    manifest_path = bag_path / 'manifest-md5.txt'

    if not tag_manifest_path.exists():
        logger.warning(f"tagmanifest-md5.txt not found: {tag_manifest_path}")
        return

    try:
        with open(tag_manifest_path, 'r') as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                updated_lines.append(line)
                continue
                
            old_checksum, filename = parts

            if 'manifest-md5.txt' in filename and manifest_path.exists():
                new_checksum = calculate_md5(manifest_path)
                updated_lines.append(f"{new_checksum} {filename}\n")
            elif 'bag-info.txt' in filename and bag_info_path.exists():
                new_checksum = calculate_md5(bag_info_path)
                updated_lines.append(f"{new_checksum} {filename}\n")
            else:
                updated_lines.append(line)

        with open(tag_manifest_path, 'w') as f:
            f.writelines(updated_lines)
            
        logger.info("Updated tagmanifest-md5.txt")

    except Exception as e:
        logger.error(f"Failed to update tagmanifest: {e}")
        raise


def process_bag(bag_path: Path, source: str, audio_pan: str) -> None:
    """
    Process a single BagIt bag.
    
    Args:
        bag_path: Path to BagIt bag directory
        source: Source type ('pm' or 'sc')
        audio_pan: Audio panning mode
    """
    logger.info(f"Processing BagIt bag: {bag_path}")

    try:
        # Re-encode service copies
        if source == 'sc':
            sc_modified = remake_scs_from_sc(bag_path, audio_pan)
        else:
            sc_modified = remake_scs_from_pm(bag_path, audio_pan)

        # Update JSON sidecars
        json_modified = update_sidecar_json(bag_path / 'data')

        # Convert to relative paths
        all_modified = sc_modified + json_modified
        rel_modified = [
            os.path.relpath(path, start=bag_path).replace('\\', '/')
            for path in all_modified
        ]

        if rel_modified:
            # Update BagIt metadata
            update_manifests(bag_path, rel_modified)
            update_payload_oxum(bag_path)
            update_tagmanifest(bag_path)
            
            logger.info(f"Successfully processed {len(rel_modified)} files in {bag_path}")
        else:
            logger.info(f"No files modified in {bag_path}")

    except Exception as e:
        logger.error(f"Failed to process bag {bag_path}: {e}")
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Remake or fix Service Copy MP4 files in BagIt packages',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-d', '--directory', 
        required=True,
        type=Path,
        help='Directory containing BagIt packages'
    )
    
    parser.add_argument(
        '--source', 
        choices=['pm', 'sc'], 
        default='pm',
        help='Source for re-encoding: pm (Preservation Master) or sc (Service Copy)'
    )
    
    parser.add_argument(
        '-p', '--audio-pan',
        choices=['none', 'left', 'right', 'center', 'auto'],
        default='none',
        help='Audio panning mode: none, left, right, center, or auto (includes LTC detection)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose debug logging'
    )

    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    top_dir = args.directory
    
    if not top_dir.exists():
        logger.error(f"Directory not found: {top_dir}")
        sys.exit(1)
    
    if not top_dir.is_dir():
        logger.error(f"Path is not a directory: {top_dir}")
        sys.exit(1)

    # Process each bag
    processed_count = 0
    error_count = 0
    
    for item in top_dir.iterdir():
        if item.is_dir() and is_bag(item):
            try:
                process_bag(item, args.source, args.audio_pan)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process bag {item}: {e}")
                error_count += 1
                continue
        else:
            logger.debug(f"Skipping non-bag directory: {item}")
    
    # Summary
    logger.info(f"Processing complete: {processed_count} bags processed, {error_count} errors")
    
    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()