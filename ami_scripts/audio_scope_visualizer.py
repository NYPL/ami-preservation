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
    
    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        streams = json.loads(result.stdout).get('streams', [])
        return len(streams)
    except subprocess.CalledProcessError:
        print("Error: Failed to execute ffprobe. Please ensure it is installed and available in your PATH.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Failed to parse ffprobe output.")
        sys.exit(1)

def generate_mpv_command(file_path, audio_stream_count):
    base_cmd = [
        'mpv',
        '--autofit=75%',
        '--geometry=+0+0',
        file_path,
        '--lavfi-complex='
    ]
    
    if audio_stream_count == 1:
        filter_complex = (
            '[aid1]asplit=3[ao][a1][a2];'
            '[a1]avectorscope=s=324x324,format=yuv420p[vec];'
            '[vec]drawbox=x=0:y=0:w=iw:h=ih:color=green:t=2[vec_b];'
            '[vec_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'CH 1 + 2\'[vec_t];'
            '[a2]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40[vol];'
            '[vid1]format=yuv420p,split=2[vid][vid_wave];'
            '[vid]scale=480:324,setsar=1,format=yuv420p[vid_scaled];'
            '[vid_wave]scale=960:162,setsar=1,waveform=filter=lowpass:scale=ire:graticule=green:flags=numbers+dots[wave];'
            '[vec_t][vol]overlay=x=10:y=H-h-10[vec_ov];'
            '[vec_ov]scale=480:324[vec_scaled];'
            '[vid_scaled][vec_scaled]hstack=inputs=2[video_and_scope];'
            '[video_and_scope][wave]vstack=inputs=2[vo]'
        )
    elif audio_stream_count >= 2:
        filter_complex = '[vid1]format=yuv420p,split=2[vid][vid_wave];[vid]scale=480:324,setsar=1,format=yuv420p[vid_scaled];'
        
        colors = ['green', 'blue', 'red', 'magenta', 'cyan']
        
        for i in range(1, audio_stream_count + 1):
            color = colors[(i-1) % len(colors)]
            channel_text = f'CH {2*i-1} + {2*i}'
            
            filter_complex += f'[aid{i}]asplit=3[ao{i}][a{i}][av{i}];'
            filter_complex += f'[a{i}]avectorscope=s=324x324,format=yuv420p[vec{i}];'
            filter_complex += f'[vec{i}]drawbox=x=0:y=0:w=iw:h=ih:color={color}:t=2[vec{i}_b];'
            filter_complex += f'[vec{i}_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'{channel_text}\'[vec{i}_t];'
            filter_complex += f'[av{i}]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40[vol{i}];'
            filter_complex += f'[vec{i}_t][vol{i}]overlay=x=10:y=H-h-10[vec{i}_ov];'
        
        total_width = 480 + 2 * 324  # Video + two vectorscopes
        filter_complex += f'[vid_wave]format=yuv420p,scale={total_width}:162,setsar=1,waveform=filter=lowpass:scale=ire:graticule=green:flags=numbers+dots[wave];'  # Reduced height of waveform
        filter_complex += f'{"".join([f"[ao{i}]" for i in range(1, audio_stream_count + 1)])}amix=inputs={audio_stream_count}[ao];'
        filter_complex += f'[vid_scaled]{" ".join([f"[vec{i}_ov]" for i in range(1, audio_stream_count + 1)])}hstack=inputs={audio_stream_count + 1}[video_and_scope];'
        filter_complex += f'[video_and_scope][wave]vstack=inputs=2[vo]'
    
    base_cmd[-1] += filter_complex
    return base_cmd


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_video_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    audio_stream_count = get_audio_stream_count(file_path)
    if audio_stream_count == 0:
        print("Error: No audio streams found in the provided file.")
        sys.exit(1)
    
    mpv_command = generate_mpv_command(file_path, audio_stream_count)
    
    print("Executing command:")
    print(" ".join(mpv_command))
    try:
        subprocess.run(mpv_command, check=True)
    except subprocess.CalledProcessError:
        print("Error: Failed to execute mpv. Please ensure it is installed and available in your PATH.")
        sys.exit(1)

if __name__ == "__main__":
    main()
