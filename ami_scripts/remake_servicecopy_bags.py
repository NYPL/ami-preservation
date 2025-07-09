#!/usr/bin/env python3

import argparse
import os
import subprocess
import json
import hashlib
import logging
from pathlib import Path
from pymediainfo import MediaInfo
import re
import json


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_bag(directory):
    """
    Check that a directory has the required BagIt metadata files.
    """
    required = ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt']
    return all((Path(directory) / fname).exists() for fname in required)

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
    matches = re.findall(r'\d{2}:\d{2}:\d{2}:\d{2}', ltcdump_out)
    print("ltcdump output:", ltcdump_out)
    print("Found LTC matches:", matches)

    # Only consider LTC valid if we see enough matches (e.g., at least 5)
    if len(matches) >= match_threshold:
        return True

    return False


def detect_audio_pan(input_file, audio_pan, probe_duration=120):
    """
    Returns a list of strings like "[0:1]pan=…[outa0]".
    If audio_pan == "auto", we also run LTC detection to drop timecode streams.
    """
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

def get_video_resolution(input_file):
    """
    Get the width and height of a video file using ffprobe.
    Returns (width, height) as integers.
    """
    ffprobe_command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", input_file
    ]

    try:
        result = subprocess.run(ffprobe_command, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(","))
        return width, height
    except Exception as e:
        logging.error(f"Error detecting resolution for {input_file}: {e}")
        raise ValueError(f"Could not determine resolution for {input_file}")

def remake_scs_from_pm(bag_path, audio_pan="none"):
    """
    Create new Service Copy MP4 files from the Preservation Master MKV
    using a single filter_complex for video + audio.
    """
    modified_files = []
    sc_dir = Path(bag_path) / 'data' / 'ServiceCopies'
    pm_dir = Path(bag_path) / 'data' / 'PreservationMasters'

    for sc_file in sc_dir.glob('*_sc.mp4'):
        pm_basename = sc_file.name.replace('_sc.mp4', '_pm.mkv')
        pm_file = pm_dir / pm_basename
        if not pm_file.is_file():
            logging.warning(f"No PM found for {sc_file}; expected {pm_file}")
            continue

        logging.info(f"Transcoding SC from PM: {pm_file} → {sc_file}")
        temp_fp = sc_file.with_suffix('.temp.mp4')

        # 1) choose video filter
        try:
            w, h = get_video_resolution(str(pm_file))
        except ValueError as e:
            logging.error(e)
            continue

        if (w, h) == (720, 486):
            vid_filt = "idet,bwdif=1,crop=720:480:0:4,setdar=4/3"
        elif (w, h) == (720, 576):
            vid_filt = "idet,bwdif=1"
        else:
            logging.warning(f"Unknown res {w}×{h}; using deinterlace only")
            vid_filt = "idet,bwdif=1"

        # 2) build audio pan filters
        pan_filters = []
        if audio_pan != "none":
            pan_filters = detect_audio_pan(pm_file, audio_pan)

        # 3) assemble filter_complex parts
        fc_parts = []
        # video chain → [v]
        fc_parts.append(f"[0:v]{vid_filt}[v]")
        # audio chains already come as "[0:i]pan=…[outaX]"
        fc_parts.extend(pan_filters)

        # join into one string
        filter_complex = ";".join(fc_parts)

        # 4) build ffmpeg command
        cmd = [
            "ffmpeg", "-i", str(pm_file),
            "-filter_complex", filter_complex,
            # video map + encode:
            "-map", "[v]",
            "-c:v", "libx264", "-movflags", "faststart", "-pix_fmt", "yuv420p", "-crf", "21",
        ]

        # 5) map audio outputs
        if pan_filters:
            for idx in range(len(pan_filters)):
                cmd += [
                    "-map", f"[outa{idx}]",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
                ]
        else:
            # fallback: map first audio stream
            cmd += [
                "-map", "0:a:0",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000"
            ]

        cmd.append(str(temp_fp))

        # 6) run & replace
        logging.debug("FFmpeg command: " + " ".join(cmd))
        subprocess.run(cmd, check=True)

        sc_file.unlink()
        temp_fp.rename(sc_file)
        modified_files.append(str(sc_file))

    return modified_files

def remake_scs_from_sc(bag_path, audio_pan="none"):
    """
    Create new Service Copy MP4 files from existing Service Copy MP4 files.
    Returns a list of the newly updated SC .mp4 paths.
    """
    modified_files = []
    servicecopies_dir = Path(bag_path) / 'data' / 'ServiceCopies'

    for sc_file in servicecopies_dir.glob('*_sc.mp4'):
        logging.info(f"Re-transcoding existing SC file for anamorphic fix: {sc_file}")
        temp_filepath = sc_file.with_suffix('.temp.mp4')

        pan_filters = []
        if audio_pan != "none":
            pan_filters = detect_audio_pan(sc_file, audio_pan)

        cmd = [
            "ffmpeg",
            "-i", str(sc_file),
            "-map", "0:v",
            "-c:v", "libx264",
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-crf", "21",
            "-vf", "setdar=16/9"
        ]

        if pan_filters:
            # add filter_complex and map each outaN
            cmd += ["-filter_complex", ";".join(pan_filters)]
            for idx in range(len(pan_filters)):
                cmd += ["-map", f"[outa{idx}]", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
        else:
            # no pan filters: copy the single main audio track
            cmd += ["-map", "0:a", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]

        cmd.append(str(temp_filepath)) 
        print(cmd)       
        subprocess.run(cmd, check=True)

        os.remove(sc_file)
        os.rename(temp_filepath, sc_file)
        modified_files.append(str(sc_file))

    return modified_files


def modify_json(data_dir):
    """
    Update metadata in all *_sc.json sidecar files within `data_dir`.
    - dateCreated (YYYY-MM-DD extracted via regex)
    - fileSize.measure (in bytes)
    Returns a list of JSON files that were updated.
    """
    date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    modified_json_files = []

    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if not file.endswith('_sc.json'):
                continue

            json_path = os.path.join(root, file)
            sc_mp4_path = json_path.replace('_sc.json', '_sc.mp4')

            if not os.path.exists(sc_mp4_path):
                logging.warning(f"Skipping {json_path}; no corresponding SC MP4 found.")
                continue

            logging.info(f"Updating sidecar JSON: {json_path}")
            media_info = MediaInfo.parse(sc_mp4_path)
            general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
            if not general_tracks:
                logging.warning(f"No 'General' track found in {sc_mp4_path}.")
                continue

            general_data = general_tracks[0].to_data()
            raw_date   = general_data.get('file_last_modification_date', '') or ''
            file_size  = general_data.get('file_size', '0')

            # extract YYYY-MM-DD
            m = date_pattern.search(raw_date)
            date_val = m.group(0) if m else ""

            # now update JSON
            with open(json_path, 'r+', encoding='utf-8-sig') as jf:
                data = json.load(jf)

                tech = data.get("technical", {})
                # set or overwrite dateCreated
                tech["dateCreated"] = date_val

                # update or create fileSize.measure
                try:
                    size_int = int(file_size)
                except ValueError:
                    size_int = 0

                if "fileSize" in tech and isinstance(tech["fileSize"], dict):
                    tech["fileSize"]["measure"] = size_int
                else:
                    tech["fileSize"] = {"measure": size_int, "unit": "bytes"}

                data["technical"] = tech

                jf.seek(0)
                json.dump(data, jf, indent=4)
                jf.truncate()

            modified_json_files.append(json_path)

    return modified_json_files

def calculate_md5(file_path):
    """
    Return the MD5 checksum for the file at file_path.
    """
    logging.info(f"Calculating MD5 for: {file_path}")
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def update_manifests(bag_path, modified_paths):
    """
    Update manifest-md5.txt checksums for each file in `modified_paths`.
    Then update the tagmanifest-md5.txt with the new manifest-md5.txt checksum.
    `modified_paths` should be relative to bag_path.
    """
    manifest_path = Path(bag_path) / 'manifest-md5.txt'
    tag_manifest_path = Path(bag_path) / 'tagmanifest-md5.txt'

    # 1) Update manifest-md5.txt
    if manifest_path.exists():
        with manifest_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                new_lines.append(line)
                continue
            old_checksum, rel_path = parts
            rel_path = rel_path.strip()
            if rel_path in modified_paths:
                full_path = os.path.join(bag_path, rel_path)
                if os.path.isfile(full_path):
                    new_checksum = calculate_md5(full_path)
                    new_line = f"{new_checksum} {rel_path}\n"
                    new_lines.append(new_line)
                else:
                    logging.warning(f"Could not find file for manifest update: {full_path}")
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with manifest_path.open('w') as f:
            f.write(''.join(new_lines))

    # 2) Update tagmanifest-md5.txt for the changed manifest
    if tag_manifest_path.exists() and manifest_path.exists():
        with tag_manifest_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                new_lines.append(line)
                continue
            old_checksum, file_ref = parts
            if 'manifest-md5.txt' in file_ref:
                # Recalculate the manifest's MD5
                new_manifest_md5 = calculate_md5(manifest_path)
                new_line = f"{new_manifest_md5} {file_ref}\n"
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        with tag_manifest_path.open('w') as f:
            f.write(''.join(new_lines))

def update_payload_oxum(bag_path):
    """
    Recalculate Payload-Oxum (total size in bytes . number of files) for all files under data/.
    Update bag-info.txt accordingly.
    """
    data_path = Path(bag_path) / 'data'
    bag_info_path = Path(bag_path) / 'bag-info.txt'

    total_size = 0
    total_files = 0

    for file in data_path.rglob('*'):
        if file.is_file():
            total_size += file.stat().st_size
            total_files += 1

    new_oxum = f"{total_size}.{total_files}"
    logging.info(f"Calculated new Payload-Oxum: {new_oxum}")

    if bag_info_path.exists():
        with bag_info_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        found_oxum = False
        for line in lines:
            if line.startswith('Payload-Oxum:'):
                new_lines.append(f'Payload-Oxum: {new_oxum}\n')
                found_oxum = True
            else:
                new_lines.append(line)

        # If there wasn't a Payload-Oxum line, add it
        if not found_oxum:
            new_lines.append(f'Payload-Oxum: {new_oxum}\n')

        with bag_info_path.open('w') as f:
            f.write(''.join(new_lines))

def update_tagmanifest(bag_path):
    """
    Update the tagmanifest-md5.txt to capture any changes to:
      - bag-info.txt
      - manifest-md5.txt
    """
    tag_manifest_path = Path(bag_path) / 'tagmanifest-md5.txt'
    bag_info_path = Path(bag_path) / 'bag-info.txt'
    manifest_path = Path(bag_path) / 'manifest-md5.txt'

    if not tag_manifest_path.exists():
        return

    with tag_manifest_path.open('r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        parts = line.strip().split(' ', 1)
        if len(parts) != 2:
            new_lines.append(line)
            continue
        old_checksum, filename = parts

        # If the line references manifest-md5.txt, recalc and replace
        if 'manifest-md5.txt' in filename and manifest_path.exists():
            new_manifest_md5 = calculate_md5(manifest_path)
            new_line = f"{new_manifest_md5} {filename}\n"
            new_lines.append(new_line)
        # If the line references bag-info.txt, recalc and replace
        elif 'bag-info.txt' in filename and bag_info_path.exists():
            new_baginfo_md5 = calculate_md5(bag_info_path)
            new_line = f"{new_baginfo_md5} {filename}\n"
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    with tag_manifest_path.open('w') as f:
        f.write(''.join(new_lines))

    logging.info("tagmanifest-md5.txt updated successfully.")

def main():
    parser = argparse.ArgumentParser(
        description='Remake or fix Service Copy MP4 files in BagIt packages'
    )
    parser.add_argument('-d', '--directory', required=True,
                        help='Directory containing BagIt packages')
    parser.add_argument('--source', choices=['pm', 'sc'], default='pm',
                        help=("Choose the source for re-encoding service copies: "
                              "'pm' for Preservation Master MKV (default), "
                              "'sc' for the existing service copy MP4."))
    parser.add_argument(
        "-p", "--audio-pan",
        choices=["none", "left", "right", "center", "auto"],
        default="none",
        help="Pan audio: left/right/center; auto includes LTC timecode detection"
    )

    args = parser.parse_args()
    top_dir = Path(args.directory)

    for bag_name in os.listdir(top_dir):
        bag_path = top_dir / bag_name
        if bag_path.is_dir() and is_bag(bag_path):
            logging.info(f"Processing BagIt bag: {bag_path}")

            # 1) Depending on the --source argument, re-encode from PM or SC
            if args.source == 'sc':
                sc_modified = remake_scs_from_sc(bag_path, args.audio_pan)
            else:
                sc_modified = remake_scs_from_pm(bag_path, args.audio_pan)

            # 2) Update sidecar JSON. 
            #    This might modify a few JSON files that also need fresh checksums.
            json_modified = modify_json(bag_path / 'data')

            # 3) Combine the newly modified files
            #    We need their paths relative to the bag root for manifest updates.
            all_modified = sc_modified + json_modified
            rel_modified = [
                os.path.relpath(path, start=bag_path).replace('\\', '/')
                for path in all_modified
            ]

            # 4) Update the payload manifest
            update_manifests(bag_path, rel_modified)

            # 5) Recalculate the Payload-Oxum in bag-info.txt
            update_payload_oxum(bag_path)

            # 6) Update the tagmanifest checksums for bag-info.txt & manifest-md5.txt
            update_tagmanifest(bag_path)

if __name__ == "__main__":
    main()
