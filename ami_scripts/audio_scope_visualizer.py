#!/usr/bin/env python3

import subprocess
import json
import sys

def get_audio_stream_count(file_path):
    ffprobe_cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 'a',
        file_path
    ]
    
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    streams = json.loads(result.stdout)['streams']
    return len(streams)

def generate_mpv_command(file_path, audio_stream_count):
    base_cmd = [
        'mpv',
        '--autofit=75%',
        '--geometry=+0+0',
        file_path,
        '--lavfi-complex='
    ]
    
    if audio_stream_count == 1:
        # Single audio stream: Video + one vectorscope
        filter_complex = (
            '[aid1]asplit=2[ao][a1];'
            '[a1]avectorscope=s=486x486,format=yuv420p[vec];'
            '[vid1]scale=-1:486[vid];'
            '[vid][vec]hstack=inputs=2[vo]'
        )
    elif audio_stream_count >= 2:
        # Dual audio streams: Video + vectorscope (Ch 1+2 in the middle, Ch 3+4 on the right)
        filter_complex = (
            '[aid1][aid2]amerge=inputs=2[amerged12];'
            '[amerged12]asplit=3[a12][a34][ao];'  # Split into audio for playback (ao) and two for visualization
            '[a12]avectorscope=s=486x486,format=yuv420p[vec1];'
            '[a34]avectorscope=s=486x486,format=yuv420p[vec2];'
            '[vid1]scale=-1:486[vid];'
            '[vid][vec1][vec2]hstack=inputs=3[vo]'
        )
    
    base_cmd[-1] += filter_complex
    return base_cmd


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_video_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    audio_stream_count = get_audio_stream_count(file_path)
    mpv_command = generate_mpv_command(file_path, audio_stream_count)
    
    print("Executing command:")
    print(" ".join(mpv_command))
    subprocess.run(mpv_command)

if __name__ == "__main__":
    main()
