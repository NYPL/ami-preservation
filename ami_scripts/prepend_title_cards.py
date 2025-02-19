#!/usr/bin/env python3
import argparse
import subprocess
import os
import glob
import json
import re
from fractions import Fraction

def get_title_cards_for_group(prefix):
    """
    Return a list of title card image paths based on the given prefix.
    Adjust the paths as needed.
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    title_card_dir = os.path.join(os.path.dirname(script_dir), 'title_cards')
    
    nypl_title_card = os.path.join(title_card_dir, 'Title_Card_NYPL.png')
    schomburg_title_card = os.path.join(title_card_dir, 'Title_Card_Schomburg.png')
    lpa_title_card = os.path.join(title_card_dir, 'Title_Card_LPA.png')

    if prefix in ['scb', 'scd']:
        return [nypl_title_card, schomburg_title_card]
    elif prefix in ['myd', 'myt', 'mym', 'myh']:
        return [nypl_title_card, lpa_title_card]
    elif prefix == 'mao':
        return [nypl_title_card]
    else:
        return [nypl_title_card]

def get_video_params(video_path):
    """
    Use ffprobe to extract the video's width, height, frame rate,
    sample aspect ratio, and count of audio streams.
    """
    ffprobe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path
    ]
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    video_stream = None
    audio_count = 0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        if stream.get("codec_type") == "audio":
            audio_count += 1

    if video_stream is None:
        raise Exception("No video stream found in the input file.")

    width = video_stream.get("width")
    height = video_stream.get("height")
    
    fps_str = video_stream.get("avg_frame_rate", "30")
    try:
        fps = float(Fraction(fps_str))
    except Exception:
        fps = 30.0

    sar = video_stream.get("sample_aspect_ratio", "1")
    if sar in ("0", "0:1"):
        sar = "1"
    
    return width, height, fps, sar, audio_count

def build_audio_chain(a, num_title, audio_count, title_duration=5.5, xfade_duration=1):
    """
    Build an audio filter chain for audio channel 'a', adjusting for multiple silent inputs.
    For each title card, we calculate the proper input index and label.
    """
    if num_title > 1:
        silent_segments = []
        for i in range(num_title):
            # Inputs:
            #   indices 0 .. (num_title-1) are title images,
            #   index num_title is the main video,
            #   then silent sources follow.
            # For each title card (with multiple audio streams), add the channel offset 'a'.
            seg_index = num_title + 1 + (i * audio_count) + a

            # Adjust duration for subsequent title cards due to xfade overlap.
            seg_duration = title_duration if i == 0 else title_duration - xfade_duration

            silent_segments.append(
                f"[{seg_index}:a:0]atrim=duration={seg_duration},asetpts=PTS-STARTPTS[silent_{a}_{i}]"
            )
        silent_parts = ";".join(silent_segments)
        silent_inputs = "][".join([f"silent_{a}_{i}" for i in range(num_title)])
        silent_concat = f"{silent_parts};[{silent_inputs}]concat=n={num_title}:v=0:a=1[silent_combined_{a}]"
        
        # Process the main audio stream from the video input.
        main_audio = f";[{num_title}:a:{a}]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5[main_audio_{a}]"
        
        # Final concatenation of the silent segments with the main audio.
        final_concat = f";[silent_combined_{a}][main_audio_{a}]concat=n=2:v=0:a=1[outa{a}]"
        return silent_concat + main_audio + final_concat
    else:
        # Single title card case:
        seg_index = num_title + 1 + a  # Adjust for the audio channel offset.
        silent_segment = f"[{seg_index}:a:0]atrim=duration={title_duration},asetpts=PTS-STARTPTS[silent_{a}_0]"
        main_audio = f";[{num_title}:a:{a}]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5[main_audio_{a}]"
        final_concat = f";[silent_{a}_0][main_audio_{a}]concat=n=2:v=0:a=1[outa{a}]"
        return silent_segment + main_audio + final_concat

def process_video(video_path, asset_flag=False):
    print(f"Processing: {video_path}")
    
    # Extract prefix from filename (assumes prefix is before the first underscore)
    filename = os.path.basename(video_path)
    prefix = filename.split('_')[0]
    title_cards = get_title_cards_for_group(prefix)
    num_title = len(title_cards)
    
    # Get video parameters.
    width, height, fps, sar, audio_count = get_video_params(video_path)
    print(f"Video: {width}x{height} at {fps:.2f} fps, SAR: {sar}, audio streams: {audio_count}")

    # Convert SAR (e.g. "9:10" -> "9/10") for setsar.
    sar_filter = sar.replace(":", "/") if ":" in sar else sar

    # Use 5.5 seconds for each title card input.
    title_duration = 5.5

    # Determine video filter strings for title cards and main video.
    if width == 1920 and height == 1080:
        base_title = f"fps={fps:.2f},scale=1440:1080,pad=1920:1080:240:0:black,setsar={sar_filter}"
        first_title_filter = base_title + ",fade=t=in:st=0:d=1:alpha=1"
        subsequent_title_filter = base_title
        main_video_filter = "fade=t=in:st=0:d=0.5"
    elif width == 720 and height == 480 and sar == "853:720":
        new_width_4_3 = int(480 * (4/3))  # 640
        pad_x = (720 - new_width_4_3) // 2    # 40 pixels
        base_title = f"fps={fps:.2f},scale={new_width_4_3}:480,pad=720:480:{pad_x}:0:black,setsar={sar_filter}"
        first_title_filter = base_title + ",fade=t=in:st=0:d=1:alpha=1"
        subsequent_title_filter = base_title
        main_video_filter = f"scale={width}:{height},setsar={sar_filter},fade=t=in:st=0:d=0.5"
    elif width == 720 and height == 576 and sar == "64:45":
        storage_width_4_3 = int(768 * (45/64))  # ~540
        pad_x = (720 - storage_width_4_3) // 2   # ~90 pixels
        base_title = f"fps={fps:.2f},scale={storage_width_4_3}:576,pad=720:576:{pad_x}:0:black,setsar={sar_filter}"
        first_title_filter = base_title + ",fade=t=in:st=0:d=1:alpha=1"
        subsequent_title_filter = base_title
        main_video_filter = f"scale={width}:{height},setsar={sar_filter},fade=t=in:st=0:d=0.5"
    else:
        base_title = f"fps={fps:.2f},scale={width}:{height},setsar={sar_filter}"
        first_title_filter = base_title + ",fade=t=in:st=0:d=1:alpha=1"
        subsequent_title_filter = base_title
        main_video_filter = f"scale={width}:{height},setsar={sar_filter},fade=t=in:st=0:d=0.5"
    
    # If asset flag is set, append drawtext overlay to main video.
    if asset_flag:
        match = re.search(r'_(\d{6})_', video_path)
        if match:
            asset_id = match.group(1)
        else:
            parts = filename.split('_')
            asset_id = parts[1] if len(parts) > 1 else ""
        drawtext_filter = (
            f",drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=25:"
            f"text='{asset_id}':x=10:y=10:fontcolor=white,"
            f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=20:"
            f"text='%{{pts\\:hms}}':box=1:boxcolor=black@0.5:boxborderw=5:"
            f"x=(w-tw)/2:y=h-th-10:fontcolor=white"
        )
        main_video_filter += drawtext_filter

    # Build the video filter graph.
    if num_title == 1:
        # Single title card: process it then fade-out at (title_duration - 1) seconds.
        video_title_chain = f"[0:v]{first_title_filter},fade=t=out:st={title_duration - 1}:d=1:alpha=1[title_final]"
        main_video_part = f";[{num_title}:v:0]{main_video_filter}[main_processed]"
        video_filter = video_title_chain + main_video_part + f";[title_final][main_processed]concat=n=2:v=1:a=0[outv]"
    else:
        # Multiple title cards: chain them with xfade transitions.
        filter_chain = f"[0:v]{first_title_filter}[tmp0]"
        for i in range(1, num_title):
            filter_chain += f";[{i}:v]{subsequent_title_filter}[tmp{i}]"
            filter_chain += f";[tmp{i-1}][tmp{i}]xfade=transition=fade:duration=1:offset={title_duration - 1}[tmp{i}merged]"
        main_video_part = f";[{num_title}:v:0]{main_video_filter}[main_processed]"
        video_filter = filter_chain + main_video_part + f";[tmp{num_title-1}merged][main_processed]concat=n=2:v=1:a=0[outv]"
    
    # Build the audio filter graph using sequential concatenation.
    audio_filter_parts = []
    for a in range(audio_count):
        audio_filter_parts.append(build_audio_chain(a, num_title, audio_count))
    audio_filter = ";".join(audio_filter_parts)
  
    filter_complex = video_filter + ";" + audio_filter

    # Build the FFmpeg command.
    ffmpeg_cmd = ["ffmpeg", "-y"]
    for img in title_cards:
        ffmpeg_cmd.extend(["-loop", "1", "-t", str(title_duration), "-i", img])
    ffmpeg_cmd.extend(["-i", video_path])
    total_silent = num_title * audio_count
    for _ in range(total_silent):
        ffmpeg_cmd.extend(["-f", "lavfi", "-t", str(title_duration), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000,aformat=sample_fmts=s32"])
    ffmpeg_cmd.extend(["-filter_complex", filter_complex])
    ffmpeg_cmd.extend(["-map", "[outv]"])
    for a in range(audio_count):
        ffmpeg_cmd.extend(["-map", f"[outa{a}]"])
    base_name, ext = os.path.splitext(video_path)
    output_file = base_name + "_with_title" + ext

    # Choose output encoding based on file extension.
    if ext.lower() == ".mov":
        # For ProRes HQ MOV, use prores_ks for video and PCM for audio.
        ffmpeg_cmd.extend([
            "-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s24le",
            output_file
        ])
    else:
        ffmpeg_cmd.extend([
            "-c:v", "libx264", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-b:a", "320k",
            output_file
        ])

    print("Running command:")
    print(" ".join(ffmpeg_cmd))
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"Processed video file: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error processing file {video_path}:")
        print(e)

def main():
    parser = argparse.ArgumentParser(description="Prepend title card(s) to a video file.")
    parser.add_argument('-f', '--file', help='Path to the video file.')
    parser.add_argument('-d', '--directory', help='Path to a directory containing video files.')
    parser.add_argument('-a', '--asset', action='store_true',
                        help='Extract asset ID from the filename and overlay drawtext (asset ID and timecode).')
    args = parser.parse_args()

    if args.file:
        process_video(args.file, asset_flag=args.asset)
    elif args.directory:
        # Process both MP4 and MOV files.
        video_files = sorted(
            glob.glob(os.path.join(args.directory, "*.mp4")) +
            glob.glob(os.path.join(args.directory, "*.mov"))
        )
        if not video_files:
            print("No MP4 or MOV files found in the specified directory.")
        for video_file in video_files:
            process_video(video_file, asset_flag=args.asset)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
