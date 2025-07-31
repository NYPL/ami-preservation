#!/usr/bin/env python3

import argparse
import subprocess
import os
import shutil
import pathlib
import itertools
import csv
import re
import logging
from pymediainfo import MediaInfo
import importlib.util


LOGGER = logging.getLogger(__name__)
video_extensions = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
audio_extensions = {'.wav', '.flac'}

# Function to remove hidden files
def remove_hidden_files(directory):
    for item in directory.rglob('.*'):
        if item.is_file():
            item.unlink()
            print(f"Removed hidden file: {item}")

def rename_files(input_directory, extensions):
    files = set(itertools.chain.from_iterable(input_directory.glob(ext) for ext in extensions))
    for file in files:
        new_file_name = file.name.replace("_ffv1", "")
        new_file = file.with_name(new_file_name)
        shutil.move(file, new_file)


def convert_mkv_dv_to_mp4(input_directory, audio_pan):
    # Sort the files so they are processed in alphabetical order
    mkv_files = sorted(input_directory.glob("*.mkv"))
    dv_files  = sorted(input_directory.glob("*.dv"))
    
    for file in itertools.chain(mkv_files, dv_files):
        convert_to_mp4(file, input_directory, audio_pan)


def process_mov_files(input_directory, audio_pan):
    for mov_file in input_directory.glob("*.mov"):
        convert_mov_file(mov_file, input_directory, audio_pan)


def process_dv_files(input_directory):
    """Process .dv files using dvpackager, creating .mkv files."""
    dv_files = list(input_directory.glob("*.dv"))  # Store the .dv files in a list
    processed_directory = input_directory / "ProcessedDV"
    processed_directory.mkdir(exist_ok=True)
    for dv_file in dv_files:
        if not shutil.which("dvpackager"):
            raise FileNotFoundError("dvpackager is not found, please install dvrescue with Homebrew.")
        command = ['dvpackager', '-e', 'mkv', str(dv_file)]
        subprocess.run(command, check=True, input='y', encoding='ascii')
        # after processing, move the file to the processed directory
        shutil.move(str(dv_file), processed_directory)
        
        # rename files based on count
        mkv_files = list(input_directory.glob(f"{dv_file.stem}_part*.mkv"))
        if len(mkv_files) == 1:  # rename the single file to exclude "_part1"
            mkv_files[0].rename(input_directory / f"{dv_file.stem}.mkv")
        elif len(mkv_files) > 1:  # rename multiple files with region naming system
            for i, mkv_file in enumerate(sorted(mkv_files), start=1):
                mkv_file.rename(input_directory / f"{dv_file.stem}r{i:02}_pm.mkv")
    return dv_files  # Return the list of .dv files


def process_hdv_files(input_directory):
    """
    Remux HDV .m2t files to MKV (preserving all streams/codecs),
    then move originals into a ProcessedHDV folder.
    """
    hdv_files = list(input_directory.glob("*.m2t"))
    if not hdv_files:
        return []

    processed_directory = input_directory / "ProcessedHDV"
    processed_directory.mkdir(exist_ok=True)

    for hdv in hdv_files:
        mkv_out = input_directory / f"{hdv.stem}.mkv"
        cmd = [
            "ffmpeg",
            "-i", str(hdv),
            "-c", "copy",
            str(mkv_out)
        ]
        print(f"Rewrapping HDV: {hdv.name} → {mkv_out.name}")
        subprocess.run(cmd, check=True)
        shutil.move(str(hdv), processed_directory / hdv.name)

    return hdv_files


def generate_framemd5_files(input_directory):
    # Sort the files so they are processed in alphabetical order
    mkv_files = sorted(input_directory.glob("*.mkv"))

    for file in mkv_files:
        output_file = input_directory / f"{file.stem}.framemd5"
        if not output_file.exists():
            command = [
                "ffmpeg",
                "-i", str(file),
                "-f", "framemd5", "-an", str(output_file)
            ]
            subprocess.run(command)


def module_exists(module_name):
    return importlib.util.find_spec(module_name) is not None


def transcribe_directory(input_directory, model, output_format):
    media_extensions = {'.mkv'}

    input_dir_path = pathlib.Path(input_directory)

    if module_exists("whisper"):
        import whisper
    else:
        print("Error: The module 'whisper' is not installed. Please install it with 'pip3 install -U openai-whisper'")
        return

    model = whisper.load_model(model)

    for file in input_dir_path.rglob('*'):
        if file.suffix in media_extensions:
            print(f"Processing {file}")
            transcription_response = model.transcribe(str(file), verbose=True)
                
            output_filename = file.with_suffix("." + output_format)
            output_writer = whisper.utils.get_writer(output_format, str(file.parent))
            output_writer(transcription_response, file.stem)


def detect_ltc_in_channel(input_file, stream_index, channel, probe_duration=120, match_threshold=5):
    """
    Detect LTC in a specific channel. Now, in addition to detecting a timecode pattern,
    we require at least `match_threshold` matches to consider the channel as containing LTC.
    """
    # channel_map: c0=c0 for left channel only, c0=c1 for right channel only
    if channel == 'left':
        pan_filter = 'pan=mono|c0=c0'
    else:
        pan_filter = 'pan=mono|c0=c1'

    # Use a WAV container so ltcdump can correctly interpret the header
    ffmpeg_command = [
        "ffmpeg",
        "-t", str(probe_duration),
        "-i", str(input_file),
        "-map", f"0:{stream_index}",
        "-af", pan_filter,
        "-ar", "48000",  # sample rate
        "-ac", "1",      # mono
        "-f", "wav",     # WAV output
        "pipe:1"
    ]

    ltcdump_command = ["ltcdump", "-"]

    ffmpeg_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ltcdump_proc = subprocess.Popen(ltcdump_command, stdin=ffmpeg_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ffmpeg_proc.stdout.close()  # allow ffmpeg_proc to receive SIGPIPE
    ltcdump_out, ltcdump_err = ltcdump_proc.communicate()
    ffmpeg_proc.wait()

    # Use regex to extract all timecode matches of the form HH:MM:SS:FF
    matches = re.findall(r'\d{2}:\d{2}:\d{2}[.:]\d{2}', ltcdump_out)
    print("ltcdump output:", ltcdump_out)
    print("Found LTC matches:", matches)

    # Only consider LTC valid if we see enough matches (e.g., at least 5)
    if len(matches) >= match_threshold:
        return True

    return False


def detect_audio_pan(input_file, audio_pan, probe_duration=120):
    # Use ffprobe to get the number of audio streams
    ffprobe_command = [
        "ffprobe", "-i", str(input_file),
        "-show_entries", "stream=index:stream=codec_type",
        "-select_streams", "a", "-of", "compact=p=0:nk=1", "-v", "0"
    ]
    ffprobe_result = subprocess.run(ffprobe_command, capture_output=True, text=True)
    audio_streams = [int(line.split('|')[0]) for line in ffprobe_result.stdout.splitlines() if "audio" in line]

    print(f"Detected {len(audio_streams)} audio streams: {audio_streams} in {input_file}")

    pan_filters = []
    pan_filter_idx = 0  # separate counter for pan filters
    silence_threshold = -60.0  # dB

    for stream_index in audio_streams:
        print(f"Analyzing audio stream: {stream_index}")

        # Analyze left channel volume
        left_analysis_command = [
            "ffmpeg", "-t", str(probe_duration), "-i", str(input_file),
            "-map", f"0:{stream_index}",
            "-af", "pan=mono|c0=c0,volumedetect", "-f", "null", "-"
        ]
        left_result = subprocess.run(left_analysis_command, capture_output=True, text=True)
        left_output = left_result.stderr

        # Analyze right channel volume
        right_analysis_command = [
            "ffmpeg", "-t", str(probe_duration), "-i", str(input_file),
            "-map", f"0:{stream_index}",
            "-af", "pan=mono|c0=c1,volumedetect", "-f", "null", "-"
        ]
        right_result = subprocess.run(right_analysis_command, capture_output=True, text=True)
        right_output = right_result.stderr

        def get_mean_volume(output):
            match = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?)", output)
            return float(match.group(1)) if match else None

        left_mean_volume = get_mean_volume(left_output)
        right_mean_volume = get_mean_volume(right_output)

        print(f"Stream {stream_index} - Left channel mean volume: {left_mean_volume}")
        print(f"Stream {stream_index} - Right channel mean volume: {right_mean_volume}")

        if left_mean_volume is None or right_mean_volume is None:
            print(f"Stream {stream_index}: Unable to analyze audio. Skipping this stream.")
            continue

        # Initialize LTC detection flags
        left_has_ltc = False
        right_has_ltc = False

        if audio_pan == "auto":
            left_has_ltc = detect_ltc_in_channel(input_file, stream_index, 'left', probe_duration=probe_duration)
            right_has_ltc = detect_ltc_in_channel(input_file, stream_index, 'right', probe_duration=probe_duration)

        # If one channel has LTC but the other channel is silent,
        # assume this stream is timecode only and skip mapping it.
        if left_has_ltc and not right_has_ltc:
            if right_mean_volume <= silence_threshold:
                print(f"Stream {stream_index}: Left channel LTC with silent right channel detected. Dropping stream.")
                continue  # Skip mapping this stream
            else:
                print(f"Stream {stream_index}: Left channel LTC detected. Using right channel as mono source.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
        elif right_has_ltc and not left_has_ltc:
            if left_mean_volume <= silence_threshold:
                print(f"Stream {stream_index}: Right channel LTC with silent left channel detected. Dropping stream.")
                continue  # Skip mapping this stream
            else:
                print(f"Stream {stream_index}: Right channel LTC detected. Using left channel as mono source.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
        else:
            # No (or ambiguous) LTC: apply channel-specific panning or identity for balanced audio
            if right_mean_volume > silence_threshold and left_mean_volume <= silence_threshold:
                print(f"Stream {stream_index}: Detected right-channel-only audio. Applying right-to-center panning.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
            elif left_mean_volume > silence_threshold and right_mean_volume <= silence_threshold:
                print(f"Stream {stream_index}: Detected left-channel-only audio. Applying left-to-center panning.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
            else:
                print(f"Stream {stream_index}: Audio is balanced or both channels have sound. No panning applied.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c1[outa{pan_filter_idx}]")
        pan_filter_idx += 1

    return pan_filters


def convert_to_mp4(input_file, input_directory, audio_pan):
    def get_video_resolution(input_file):
        ffprobe_command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0"
        ]
        result = subprocess.run(
            ffprobe_command + [str(input_file)],
            capture_output=True, text=True
        )

        stdout = result.stdout.strip()
        if result.returncode != 0 or not stdout:
            raise ValueError(
                f"Could not determine resolution for {input_file!r}: "
                f"{result.stderr.strip() or 'no output'}"
            )

        # Remove any trailing commas and split
        clean = stdout.rstrip(",")
        parts = clean.split(",")
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(
                f"Unexpected resolution format for {input_file!r}: '{stdout}'"
            )

        return int(parts[0]), int(parts[1])

    output_file_name = f"{input_file.stem.replace('_pm', '')}_sc.mp4"
    output_file = input_directory / output_file_name

    # Detect all audio streams
    ffprobe_audio = [
        "ffprobe", "-i", str(input_file),
        "-show_entries", "stream=index:stream=codec_type",
        "-select_streams", "a", "-of", "compact=p=0:nk=1", "-v", "0"
    ]
    audio_result = subprocess.run(ffprobe_audio, capture_output=True, text=True)
    audio_streams = [
        int(line.split('|')[0])
        for line in audio_result.stdout.splitlines() if "audio" in line
    ]

    # Build pan filters
    pan_filters = []
    if audio_pan in {"left", "right", "center"}:
        for i, idx in enumerate(audio_streams):
            if audio_pan == "left":
                pan_filters.append(f"[0:{idx}]pan=stereo|c0=c0|c1=c0[outa{i}]")
            elif audio_pan == "right":
                pan_filters.append(f"[0:{idx}]pan=stereo|c0=c1|c1=c1[outa{i}]")
            else:  # center
                pan_filters.append(f"[0:{idx}]pan=stereo|c0=c0+c1|c1=c0+c1[outa{i}]")
    elif audio_pan == "auto":
        pan_filters = detect_audio_pan(input_file, audio_pan)

    # Get resolution and choose video filter
    try:
        width, height = get_video_resolution(input_file)
    except ValueError as e:
        print(f"Skipping {input_file.name}: {e}")
        return None

    if (width, height) == (720, 486):         # NTSC
        video_filter = "idet,bwdif=1,crop=w=720:h=480:x=0:y=4,setdar=4/3"
    elif (width, height) == (720, 576):       # PAL
        video_filter = "idet,bwdif=1"
    elif (width, height) == (1440, 1080):     # HDV 1080-line
        video_filter = "idet,bwdif=1"  # no crop, just deinterlace
    else:
        print(f"Unknown resolution {width}×{height}, using default filter.")
        video_filter = "idet,bwdif=1"

    # Assemble ffmpeg command
    command = [
        "ffmpeg", "-i", str(input_file),
        "-map", "0:v", "-c:v", "libx264", "-movflags", "faststart",
        "-pix_fmt", "yuv420p", "-crf", "21", "-vf", video_filter,
    ]

    if pan_filters:
        filter_complex = ";".join(pan_filters)
        command += ["-filter_complex", filter_complex]
        for i in range(len(pan_filters)):
            command += ["-map", f"[outa{i}]"]
    else:
        for idx in audio_streams:
            command += ["-map", f"0:{idx}", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]

    command.append(str(output_file))

    print(f"FFmpeg command: {' '.join(command)}")
    subprocess.check_call(command)
    print(f"MP4 created: {output_file}")

    return output_file


def convert_mov_file(input_file, input_directory, audio_pan):
    """
    Convert a MOV file to an FFV1 MKV (Preservation Master), then call
    convert_to_mp4 to generate a Service Copy. This approach ensures
    we reuse the same MP4 creation logic (including audio pan).
    """

    def get_video_resolution(path):
        ffprobe_command = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(path)
        ]
        result = subprocess.run(ffprobe_command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            w, h = map(int, result.stdout.strip().split(","))
            return w, h
        else:
            raise ValueError(f"Could not determine video resolution for {path}")

    width, height = get_video_resolution(input_file)

    # Decide field ordering, color metadata, etc. for standard def
    # If HD (or anything else), we skip these for simplicity.
    if width == 720 and height == 486:
        # NTSC (bottom-field-first)
        field_order       = "bt"
        set_field_filter  = "bff"
        dar_filter        = "4/3"
        color_primaries   = "smpte170m"
        color_range       = "tv"
        color_trc         = "bt709"
        colorspace        = "smpte170m"

    elif width == 720 and height == 576:
        # PAL (top-field-first)
        field_order       = "tb"
        set_field_filter  = "tff"
        dar_filter        = "4/3"
        color_primaries   = "bt470bg"
        color_range       = "tv"
        color_trc         = "bt709"
        colorspace        = "bt470bg"

    else:
        # HD or non‐standard
        field_order       = None
        set_field_filter  = None
        dar_filter        = None
        color_primaries   = None
        color_range       = None
        color_trc         = None
        colorspace        = None

    # Build FFmpeg command for MKV (Preservation Master)
    mkv_output = input_directory / f"{input_file.stem}.mkv"
    ffv1_cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-map", "0",      # Map all streams
        "-dn",            # No data streams
        "-c:v", "ffv1",
        "-level", "3",
        "-g", "1",
        "-slicecrc", "1",
        "-slices", "24",
        "-c:a", "flac"    # Copy all audio bit-for-bit
    ]

    # Apply field_order if defined
    if field_order:
        ffv1_cmd += ["-field_order", field_order]

    # Build a -vf filter if we have setfield/dar
    vf_filters = []
    if set_field_filter:
        vf_filters.append(f"setfield={set_field_filter}")
    if dar_filter:
        vf_filters.append(f"setdar={dar_filter}")
    if vf_filters:
        ffv1_cmd += ["-vf", ",".join(vf_filters)]

    # Insert color metadata if relevant
    if color_primaries:
        ffv1_cmd += ["-color_primaries", color_primaries]
    if color_range:
        ffv1_cmd += ["-color_range", color_range]
    if color_trc:
        ffv1_cmd += ["-color_trc", color_trc]
    if colorspace:
        ffv1_cmd += ["-colorspace", colorspace]

    ffv1_cmd.append(str(mkv_output))

    print("Running MKV (FFV1) command:", " ".join(ffv1_cmd))
    subprocess.run(ffv1_cmd, check=True)
    print(f"Created Preservation Master: {mkv_output}")

    # Now create a Service Copy by calling your existing MP4 function,
    # which supports the audio_pan logic (auto, left, right, center, etc.)
    convert_to_mp4(input_file, input_directory, audio_pan)


def create_directories(input_directory, directories):
    for directory in directories:
        (input_directory / directory).mkdir(exist_ok=True)


def move_files(input_directory):
    for file in itertools.chain(input_directory.glob("*.mp4"), input_directory.glob("*.mov"), input_directory.glob("*.mkv"), input_directory.glob("*.framemd5"), input_directory.glob("*.vtt")):
        target_dir = {
            ".mov": "V210",
            ".mkv": "PreservationMasters",
            ".framemd5": "PreservationMasters",
            ".vtt": "PreservationMasters",
            ".mp4": "ServiceCopies"
            }.get(file.suffix)

        shutil.move(file, input_directory / target_dir)


def move_log_files_to_auxiliary_files(input_directory):
    for file in input_directory.glob("*.log"):
        shutil.move(file, input_directory / "AuxiliaryFiles" / file.name)
    for file in input_directory.glob("*.xml.gz"):
        shutil.move(file, input_directory / "PreservationMasters" / file.name)
    for file in input_directory.glob("*.xml"):
        shutil.move(file, input_directory / "AuxiliaryFiles" / file.name)        


def delete_empty_directories(input_directory, directories):
    for directory in directories:
        dir_path = input_directory / directory
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
        except FileNotFoundError:
            pass


def process_directory(directory):
    valid_extensions = video_extensions.union(audio_extensions)
    paths = []
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix.lower() in valid_extensions:
            if "ProcessedDV" not in path.parts and "V210" not in path.parts:
                paths.append(path)
    return paths


def has_mezzanines(file_path):
    for parent in file_path.parents:
        mezzanines_dir = parent / "Mezzanines"
        if mezzanines_dir.is_dir():
            return True
    return False


def extract_track_info(media_info, path, project_code_pattern, valid_extensions):
    # the pattern to match YYYY-MM-DD
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    for track in media_info.tracks:
        if track.track_type == "General":
            file_data = [
                path,
                '.'.join([path.stem, path.suffix[1:]]),
                path.stem,
                path.suffix[1:],
                track.file_size,
                pattern.search(track.file_last_modification_date).group(0) if pattern.search(track.file_last_modification_date) else None,
                track.format,
                track.audio_format_list.split()[0] if track.audio_format_list else None,
                track.codecs_video,
                track.duration,
            ]

            if track.duration:
                human_duration = str(track.other_duration[3]) if track.other_duration else None
                file_data.append(human_duration)
            else:
                file_data.append(None)

            media_type = None
            has_mezzanines_folder = has_mezzanines(path)

            if path.suffix.lower() in video_extensions:
                media_type = 'film' if has_mezzanines_folder else 'video'
            elif path.suffix.lower() in audio_extensions:
                media_type = 'audio'

            file_data.append(media_type)
            file_no_ext = path.stem
            role = file_no_ext.split('_')[-1]
            division = file_no_ext.split('_')[0]
            driveID = path.parts[2]
            file_data.extend([role, division, driveID])
            primaryID = path.stem
            file_data.append(primaryID.split('_')[1] if len(primaryID.split('_')) > 1 else None)

            match = project_code_pattern.search(str(path))
            if match:
                projectcode = match.group(1)
                file_data.append(projectcode)
            else:
                file_data.append(None)

            return file_data

    return None


def main():
    parser = argparse.ArgumentParser(description="Process video files in a specified directory and optionally extract MediaInfo.")
    parser.add_argument("-d", "--directory", type=str, required=True, help="Input directory containing video files.")
    parser.add_argument("-t", "--transcribe", action="store_true", help="Transcribe the audio of the MKV files to VTT format using the Whisper tool.")
    parser.add_argument("-o", "--output", help="Path to save csv (optional). If provided, MediaInfo extraction will be performed.", required=False)
    parser.add_argument("-m", "--model", default='medium', choices=['tiny', 'base', 'small', 'medium', 'large'], help='The Whisper model to use')
    parser.add_argument("-f", "--format", default='vtt', choices=['vtt', 'srt', 'txt', 'json'], help='The subtitle output format to use')
    parser.add_argument("-p", "--audio-pan",
        choices=["left", "right", "none", "center", "auto"],
        default="none",
        help="Pan audio to center from left, right, or auto-detect mono audio.")

    args = parser.parse_args()

    input_dir = pathlib.Path(args.directory)

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a valid directory.")
        exit(1)

    # Remove hidden files before processing
    print("Removing hidden files...")
    remove_hidden_files(input_dir)

    print("Processing DV files...")
    process_dv_files(input_dir)

    print("Processing HDV (.m2t) files...")
    process_hdv_files(input_dir)

    print("Creating directories...")
    create_directories(input_dir, ["AuxiliaryFiles", "V210", "PreservationMasters", "ServiceCopies"])

    print("Converting MKV and DV to MP4...")
    convert_mkv_dv_to_mp4(input_dir, args.audio_pan)

    print("Processing MOV files...")
    process_mov_files(input_dir, args.audio_pan)

    print("Generating framemd5 files...")
    generate_framemd5_files(input_dir)

    print("Renaming files...")
    rename_files(input_dir, video_extensions.union(audio_extensions))

    print("Moving files...")
    move_files(input_dir)

    print("Moving log files...")
    move_log_files_to_auxiliary_files(input_dir)

    if args.transcribe:
        print("Transcribing directory...")
        transcribe_directory(input_dir, args.model, args.format)

    print("Deleting empty directories...")
    delete_empty_directories(input_dir, ["AuxiliaryFiles", "V210", "PreservationMasters", "ServiceCopies", "ProcessedDV"])

    if args.output:
        project_code_pattern = re.compile(r'(\d{4}_\d{2}_\d{2})')
        valid_extensions = video_extensions.union(audio_extensions)
        file_data = []

        for path in process_directory(input_dir):
            media_info = MediaInfo.parse(str(path))
            track_info = extract_track_info(media_info, path, project_code_pattern, valid_extensions)
            if track_info:
                print(file_data)
                file_data.append(track_info)

        with open(args.output, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow([
            'filePath',
            'asset.referenceFilename',
            'technical.filename',
            'technical.extension',
            'technical.fileSize.measure',
            'technical.dateCreated',
            'technical.fileFormat',
            'technical.audioCodec',
            'technical.videoCodec',
            'technical.durationMilli.measure',
            'technical.durationHuman',
            'mediaType',
            'role',
            'divisionCode',
            'driveID',
            'primaryID',
            'projectID'
        ])
            csvwriter.writerows(file_data)

if __name__ == "__main__":
    main()