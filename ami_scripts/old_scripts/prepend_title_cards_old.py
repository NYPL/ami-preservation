#!/usr/bin/env python3

import argparse
import subprocess
import json
import os
import re
import glob
import tempfile
import shutil


def run_ffmpeg_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
    stdout, stderr = '', ''
    while True:
        output = process.stderr.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
            stderr += output
    rc = process.poll()
    return rc, stdout, stderr


def get_title_cards_for_group(prefix):
    # Define the paths for the title card images
    script_dir = os.path.dirname(os.path.realpath(__file__))
    title_card_dir = os.path.join(os.path.dirname(script_dir), 'title_cards')
    
    nypl_title_card = os.path.join(title_card_dir, 'Title_Card_NYPL.png')
    schomburg_title_card = os.path.join(title_card_dir, 'Title_Card_Schomburg.png')
    lpa_title_card = os.path.join(title_card_dir, 'Title_Card_LPA.png')

    # Group logic
    if prefix in ['scb', 'scd']:
        return [nypl_title_card, schomburg_title_card]
    elif prefix in ['myd', 'myt', 'mym', 'myh']:
        return [nypl_title_card, lpa_title_card]
    elif prefix == 'mao':
        return [nypl_title_card]
    else:
        return [nypl_title_card]


def process_video(video_path, asset_flag):
    
    # Extract prefix from filename
    filename = os.path.basename(video_path)
    prefix = filename.split('_')[0]

    # Get the appropriate title cards based on the group
    title_cards = get_title_cards_for_group(prefix)
    
    # Get info about the video file
    ffmpeg_probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path]
    video_info_json = subprocess.check_output(ffmpeg_probe_cmd)
    video_info = json.loads(video_info_json)

    video_streams = [stream for stream in video_info['streams'] if stream['codec_type'] == 'video']
    assert len(video_streams) > 0, "No video streams found in the input video file."
    video_stream = video_streams[0]


    audio_streams = [stream for stream in video_info['streams'] if stream['codec_type'] == 'audio']

    # Get the video specs
    width = video_stream['width']
    height = video_stream['height']
    pixel_format = video_stream['pix_fmt']
    video_codec = video_stream['codec_name']
    frame_rate = video_stream['avg_frame_rate']
    interlaced = video_stream['field_order'] in ['tb', 'bt']

    # Extract the encoder from the format tags
    encoder = video_info['format']['tags'].get('encoder', 'Unknown')

    # Check for display aspect ratio and assign it if present
    display_aspect_ratio = video_stream.get('display_aspect_ratio', None)
  
    # Prepare output file path
    base_name, extension = os.path.splitext(video_path)
    output_file = base_name + '_with_title' + extension

    # Check if the video needs transcoding
    if width == 720 and height == 486 and display_aspect_ratio is None:
        # Prepare transcoded file path
        transcoded_video_path = f"{base_name}_transcoded.mp4"
        
        # Transcoding command
        transcode_command = [
            "ffmpeg",
            "-i", video_path,
            "-map", "0:v", "-map", "0:a",
            "-c:v", "libx264",
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-b:v", "3500000", "-bufsize", "1750000", "-maxrate", "3500000",
            "-vf", "setdar=dar=4/3",
            "-c:a", "aac", "-b:a", "320000", "-ar", "48000", transcoded_video_path
        ]
        # Execute transcoding
        subprocess.check_output(transcode_command)

        # Use the transcoded video for further processing
        video_path = transcoded_video_path
    
    image_video_files = []

    for idx, image in enumerate(title_cards):
        # Create a temp file for the image video
        image_video_file_name = f"{base_name}_temp_{idx}.mp4"
        image_video_files.append(image_video_file_name)

        # Create silent video
        filters = [
            f"fade=t=in:st=0:d=2",
            f"fade=t=out:st=4:d=1:color=black",
            f"format={pixel_format}"
        ]

        # Check if the video is HD and pillarboxed
        if width == 1920 and height == 1080:
            # Calculate new dimensions for 4:3 aspect ratio within 1920x1080
            new_width = 1440  # 1080p height with 4:3 aspect ratio
            new_height = 1080
            pad_x = (1920 - new_width) // 2
            pad_y = 0

            # Scale and pad the image to fit 1920x1080 without stretching
            filters.extend([
                f"scale={new_width}:{new_height}",
                f"pad=1920:1080:{pad_x}:{pad_y}:black"
            ])
        elif width == 720 and height == 480:
            # Check if the video is SD widescreen (16:9 aspect ratio)
            if video_stream.get('display_aspect_ratio') == '16:9':
                # Calculate new dimensions for 4:3 aspect ratio within 720x480
                new_width_4_3 = int(480 * (4 / 3))  # 640 for 4:3 aspect ratio
                pad_x = (720 - new_width_4_3) // 2  # Padding for left and right

                # Scale and pad the image to fit 720x480 without stretching
                filters.extend([
                    f"scale={new_width_4_3}:{height}",
                    f"pad=720:480:{pad_x}:0:black",
                    "setdar=16/9"
                ])
            elif video_stream.get('display_aspect_ratio') == '3:2':
                # Handling for videos with 3:2 aspect ratio
                filters.extend([
                    f"scale={width}:{height}",
                    "setsar=1",
                    "setdar=3/2"
                ])
            elif video_stream.get('display_aspect_ratio') == '15:11':
                # Handling for videos with 3:2 aspect ratio
                filters.extend([
                    f"scale={width}:{height}",
                    "setsar=1",
                    "setdar=15/11"
                ])            
            else:
                # For other 720x480 videos, scale as usual
                filters.extend([
                    f"scale={width}:{height}",
                    "setsar=1",
                    "setdar=4/3"
                ])
        elif width == 720 and height == 576 and video_stream.get('display_aspect_ratio') == '5:4':
            # Check if the video is 5:4 PAL
                filters.extend([
                    f"scale={width}:{height}",
                    "setsar=1",
                    "setdar=5/4"
                ])
        elif width == 720 and height == 486 and video_stream.get('display_aspect_ratio') == '400:297':
            # Check if the video is oddball Telestream DAR video
            filters.extend([
                f"scale={width}:{height}",
                
                "setsar=10/11",
            ])
        elif width == 654 and height == 480 and video_stream.get('display_aspect_ratio') == '94:69':
            # Check if the video is oddball Telestream DAR video
            filters.extend([
                f"scale={width}:{height}",
                "setsar=7520/7521",
                "setdar=94/69"
            ])
        else:
            # For other resolutions, scale as usual
            filters.extend([
                f"scale={width}:{height}",
                "setsar=1",
                "setdar=4/3"
            ])

        ffmpeg_image_to_video_cmd = [
            'ffmpeg', '-y', '-loop', '1', '-i', image, '-t', '5', '-c:v', video_codec, '-r', frame_rate, 
            '-vf', ','.join(filters)
        ]

        if interlaced:
            ffmpeg_image_to_video_cmd += ['-flags', '+ilme+ildct']

        ffmpeg_image_to_video_cmd.append(image_video_file_name)
        print(ffmpeg_image_to_video_cmd)
        subprocess.check_output(ffmpeg_image_to_video_cmd)

        if audio_streams:  # Add silent audio to each title card video
            audio_stream = audio_streams[0]
            audio_codec = audio_stream['codec_name']
            channel_layout = audio_stream.get('channel_layout', 'stereo')
            sample_rate = audio_stream.get('sample_rate', '48000')
            bitrate = audio_stream.get('bit_rate', '320k')
            
            ffmpeg_add_audio_cmd = [
                'ffmpeg', '-i', image_video_file_name, '-f', 'lavfi', 
                '-t', '5', '-i', f'anullsrc=channel_layout={channel_layout}:sample_rate={sample_rate}',
                '-c:v', 'copy', '-c:a', audio_codec, '-b:a', bitrate, '-shortest', f"{base_name}_temp_with_audio_{idx}.mp4"
            ]
            
            print(ffmpeg_add_audio_cmd)
            subprocess.check_output(ffmpeg_add_audio_cmd)
            os.rename(f"{base_name}_temp_with_audio_{idx}.mp4", image_video_file_name)
    
    # Get the directory of the video file
    video_directory = os.path.dirname(video_path)

    # Create a list file for concat
    concat_list = os.path.join(video_directory, 'concat_list.txt')
    with open(concat_list, 'w') as f:
        for file in image_video_files:
            f.write(f"file '{file}'\n")
        f.write(f"file '{video_path}'\n")

    # Concatenate the title card videos and the original video
    temp_output_path = os.path.join(os.path.dirname(video_path), 'temp_concat_output.mp4')

    # First concatenation attempt
    ffmpeg_concat_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list, '-c', 'copy', temp_output_path]
    returncode, stdout, stderr = run_ffmpeg_command(ffmpeg_concat_cmd)

    if "Non-monotonic DTS in output stream 0:1" in stderr or "Non-monotonous DTS in output stream 0:1" in stderr or "Non-monotonic DTS" in stderr:
        print("Non-monotonic DTS error detected. Attempting alternative concatenation method.")

        # Remove the possibly corrupted file
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)

                # After determining the video bitrate and aspect ratio based on resolution
        if width == 1920 and height == 1080:  # HD content
            video_bitrate = "8000000"
            bufsize = "8000000"
            maxrate = "8000000"
            additional_filters = ""
        else:  # Other SD content
            video_bitrate = "3500000"
            bufsize = "1750000"
            maxrate = "3500000"
            additional_filters = ""

        # Construct the alternative concatenation command with bitrate settings
        alternative_concat_cmd = ['ffmpeg']
        filter_complex_cmd = []

        # Add each image video file and construct the filter_complex part
        for idx, image_file in enumerate(image_video_files):
            alternative_concat_cmd.extend(['-i', image_file])
            filter_complex_cmd.extend([f"[{idx}:v:0][{idx}:a:0]"])

        # Add the original video file
        alternative_concat_cmd.extend(['-i', video_path])
        filter_complex_cmd.extend([f"[{len(image_video_files)}:v:0][{len(image_video_files)}:a:0]"])

        # Finalize the filter_complex command
        filter_complex_string = ''.join(filter_complex_cmd) + f"concat=n={len(image_video_files) + 1}:v=1:a=1[outv][outa]"
        alternative_concat_cmd.extend([
            '-filter_complex', filter_complex_string,
            '-map', '[outv]', '-map', '[outa]', 
            '-b:v', video_bitrate, '-bufsize', bufsize, '-maxrate', maxrate,
            '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '320k'
        ])

        alternative_concat_cmd.append(temp_output_path)

        # Run the alternative concatenation command
        returncode, stdout, stderr = run_ffmpeg_command(alternative_concat_cmd)
        if returncode != 0:
            print(f"Error during alternative concatenation: {stderr}")
    else:
        print("Concatenation successful.")

    # Apply text and timecode to the main video after title cards
    if asset_flag:
        title_cards_duration = len(title_cards) * 5  # Assuming each title card is 5 seconds
        output_path = os.path.join(os.path.dirname(video_path), base_name + '_with_title' + extension)

        # First, try to extract a sequence of six digits
        match_six_digits = re.search(r'_(\d{6})_', video_path)
        if match_six_digits:
            asset_id = match_six_digits.group(1)
        else:
            # If no six digits found, try to extract text between the first two underscores
            parts = filename.split('_', 2)
            if len(parts) > 2:
                asset_id = parts[1]
            else:
                # If neither condition is met, leave the asset_id blank
                asset_id = ''

        # Determine bitrate and aspect ratio based on resolution
        if width == 1920 and height == 1080:  # HD content
            video_bitrate = "8000000"
            bufsize = "8000000"
            maxrate = "8000000"
            additional_filters = ""
        elif width == 720 and height == 480 and display_aspect_ratio == '3:2':  # Specific SD widescreen content
            video_bitrate = "3500000"
            bufsize = "1750000"
            maxrate = "3500000"
            additional_filters = ",setdar=4/3"
        else:  # Other SD content
            video_bitrate = "3500000"
            bufsize = "1750000"
            maxrate = "3500000"
            additional_filters = ""

        ffmpeg_drawtext_cmd = [
            'ffmpeg', '-y', '-i', temp_output_path, '-c:v', 'libx264', '-movflags', 'faststart', '-b:v', video_bitrate, '-bufsize', bufsize, '-maxrate', maxrate, '-vf',
            f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=25:text='{asset_id}':x=10:y=10:fontcolor=white:enable='gte(t,{title_cards_duration})'," +
            f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=20:text='%{{pts\\:hms\\: - {title_cards_duration}}}':box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=h-th-10:fontcolor=white:enable='gte(t,{title_cards_duration})'{additional_filters},format=yuv420p",
            '-c:a', 'copy', output_path
        ]
        subprocess.check_output(ffmpeg_drawtext_cmd)
        os.remove(temp_output_path)
    else:
        output_path = base_name + '_with_title' + extension
        os.rename(temp_output_path, output_path)

    # Remove temporary files
    for file in image_video_files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {file} : {e.strerror}")

    # Remove the concat_list.txt file at the end
    try:
        os.remove(concat_list)
    except OSError as e:
        print(f"Error: {concat_list} : {e.strerror}")
    

def process_audio(audio_path, asset_flag):

    # Prepare output file path before any potential transcoding
    base_name, _ = os.path.splitext(audio_path)
    output_file = base_name + '_with_title.mp4'

    # Check audio file characteristics
    probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_fmt,sample_rate', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    probe_output = subprocess.run(probe_cmd, text=True, capture_output=True)
    sample_fmt, sample_rate = probe_output.stdout.strip().split('\n')

    temp_dir = None

    # Transcode digital audiotape files if necessary
    if sample_fmt == "s16" and (sample_rate == "48000" or sample_rate == "44100" or sample_rate == "44056"):
        temp_dir = tempfile.mkdtemp()
        base_name, _ = os.path.splitext(os.path.basename(audio_path))
        transcoded_audio_path = os.path.join(temp_dir, base_name + '.wav')
        transcode_cmd = ['ffmpeg', '-y', '-i', audio_path, '-c:a', 'pcm_s24le', '-ar', '96k', transcoded_audio_path]
        subprocess.run(transcode_cmd, check=True)
        audio_path = transcoded_audio_path


    # Extract prefix from filename
    filename = os.path.basename(audio_path)
    prefix = filename.split('_')[0]

    # Get the appropriate title cards based on the group
    title_cards = get_title_cards_for_group(prefix)

    # Start constructing the FFmpeg command
    ffmpeg_cmd = ['ffmpeg', '-y']

    # Add inputs for title card images
    for idx, image in enumerate(title_cards):
        ffmpeg_cmd.extend(['-loop', '1', '-t', '5', '-i', image])

    # Add the main audio input
    ffmpeg_cmd.extend(['-i', audio_path])

    # Calculate total duration for silent audio based on number of title cards
    silent_audio_duration = len(title_cards) * 5

    # Add silent audio input with calculated duration
    ffmpeg_cmd.extend(['-f', 'lavfi', '-t', str(silent_audio_duration), '-i', 'anullsrc'])

    # Construct the filter_complex command
    filter_complex_parts = []

    # Calculate the new height to maintain a 4:3 aspect ratio within a 1280x720 frame
    new_height = 720
    new_width = int(new_height * (4.0 / 3.0))  # Calculate width for 4:3 aspect ratio

    # Calculate padding (pillarboxing) to center the image in a 1280x720 frame
    pad_x = int((1280 - new_width) / 2)
    pad_y = 0  # No padding on top and bottom as the height is already 720

    # Logic for handling single and multiple title cards
    if len(title_cards) == 1:
        # For a single title card
        filter_complex_parts.append(
            f"[0:v]scale={new_width}:{new_height},pad=1280:720:{pad_x}:{pad_y}:black,"
            f"fade=t=in:st=0:d=2,fade=t=out:st=4:d=1,setpts=PTS-STARTPTS[v];"
        )
    else:
        # For multiple title cards
        for idx, _ in enumerate(title_cards):
            filter_complex_parts.append(
                f"[{idx}:v]scale={new_width}:{new_height},pad=1280:720:{pad_x}:{pad_y}:black,"
                f"fade=t=in:st=0:d=2,fade=t=out:st=4:d=1,setpts=PTS-STARTPTS[v{idx}];"
            )
        concat_v = "[" + "][".join(f"v{idx}" for idx in range(len(title_cards))) + "]"
        filter_complex_parts.append(
            f"{concat_v}concat=n={len(title_cards)}:v=1:a=0,format=yuv420p[v];"
        )

    # Audio visualization
    audio_idx = len(title_cards)  # The index of the main audio input
    filter_complex_parts.append(
        f"[{audio_idx}:a]showwaves=s=1280x720:mode=line:colors=blue,format=yuv420p[wave];"
    )

    # Apply text and timecode to the audio visualization, if enabled
    if asset_flag:
        title_cards_duration = len(title_cards) * 5  # Assuming each title card is 5 seconds
        
        # First, try to extract a sequence of six digits
        match_six_digits = re.search(r'_(\d{6})_', audio_path)
        if match_six_digits:
            asset_id = match_six_digits.group(1)
        else:
            # If no six digits found, try to extract text between the first two underscores
            parts = filename.split('_', 2)
            if len(parts) > 2:
                asset_id = parts[1]
                print(asset_id)
            else:
                # If neither condition is met, leave the asset_id blank
                asset_id = ''

        filter_complex_parts.append(
            f"[v][wave]concat=n=2:v=1:a=0,drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=25:text='{asset_id}':x=10:y=10:fontcolor=white:enable='gte(t,{title_cards_duration})',"
            f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize=20:text='%{{pts\\:hms\\: - {title_cards_duration}}}':box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=h-th-10:fontcolor=white:enable='gte(t,{title_cards_duration})'[vfinal];"
        )
    else:
        filter_complex_parts.append(
            "[v][wave]concat=n=2:v=1:a=0[vfinal];"
        )

    # Audio concatenation
    silent_audio_idx = audio_idx + 1  # The index of the silent audio input
    filter_complex_parts.append(
        f"[{silent_audio_idx}:a][{audio_idx}:a]concat=n=2:v=0:a=1[audiofinal]"
    )

    ffmpeg_cmd.extend(['-filter_complex', ''.join(filter_complex_parts)])
    ffmpeg_cmd.extend(['-map', '[vfinal]', '-map', '[audiofinal]', output_file])

    # Execute the ffmpeg command
    print(ffmpeg_cmd)
    returncode, _, stderr = run_ffmpeg_command(ffmpeg_cmd)
    if returncode != 0:
        print(f"Error processing audio: {stderr}")
        return

    # Remove temporary file and directory
    if temp_dir:
        shutil.rmtree(temp_dir)

    print(f"Processed audio file: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Prepend title card to a media file.")
    parser.add_argument('-f', '--file', help='Path to the video or audio file.')
    parser.add_argument('-d', '--directory', help='Path to a directory containing media files.')
    parser.add_argument('-a', '--asset', action='store_true', help='Extract and add asset ID from the filename + timdecode.')
    args = parser.parse_args()

    video_count = 0
    audio_count = 0
    error_count = 0
    error_files = []

    if args.directory:
        for media_file in sorted(glob.glob(os.path.join(args.directory, '*'))):
            try:
                if media_file.lower().endswith('.mp4'):
                    process_video(media_file, args.asset)
                    video_count += 1
                elif media_file.lower().endswith(('.wav', '.flac')):
                    process_audio(media_file, args.asset)
                    audio_count += 1
            except Exception as e:
                print(f"Error processing {media_file}: {e}")
                error_count += 1
                error_files.append(media_file)
    elif args.file:
        try:
            if args.file.lower().endswith('.mp4'):
                process_video(args.file, args.asset)
                video_count += 1
            elif args.file.lower().endswith(('.wav', '.flac')):
                process_audio(args.file, args.asset)
                audio_count += 1
            else:
                print("Error: Unsupported file format.")
        except Exception as e:
            print(f"Error processing {args.file}: {e}")
            error_count += 1
            error_files.append(args.file)
    else:
        print("Error: No file or directory specified.")
        parser.print_help()

    print(f"{video_count} video files processed, {audio_count} audio files processed")
    if error_count > 0:
        print(f"{error_count} files failed to process. The following files encountered errors:")
        for file in error_files:
            print(file)

if __name__ == "__main__":
    main()