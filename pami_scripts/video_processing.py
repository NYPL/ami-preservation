#!/usr/bin/env python3

import argparse
import subprocess
import os
import shutil
import pathlib
import itertools


def rename_files(input_directory, extensions):
    files = set(itertools.chain.from_iterable(input_directory.glob(ext) for ext in extensions))
    for file in files:
        new_file_name = file.name.replace("_ffv1", "")
        new_file = file.with_name(new_file_name)
        shutil.move(file, new_file)


def convert_mkv_dv_to_mp4(input_directory):
    for file in itertools.chain(input_directory.glob("*.mkv"), input_directory.glob("*.dv")):
        convert_to_mp4(file, input_directory)


def process_mov_files(input_directory):
    for file in input_directory.glob("*.mov"):
        convert_mov_file(file, input_directory)


def generate_framemd5_files(input_directory):
    for file in input_directory.glob("*.mkv"):
        output_file = input_directory / f"{file.stem}.framemd5"
        if not output_file.exists():
            command = [
                "ffmpeg",
                "-i", str(file),
                "-f", "framemd5", "-an", str(output_file)
            ]
            subprocess.run(command)


def transcribe_files(input_directory):
    os.chdir(input_directory)
    for file in input_directory.glob("*.mkv"):
        print(f"Transcribing file: {file}")
        command = ['whisper', file, '--model' , 'medium', '--output_format', 'vtt']
        subprocess.run(command)


def convert_to_mp4(input_file, input_directory):
    output_file_name = f"{input_file.stem.replace('_pm', '')}_sc.mp4"
    output_file = input_directory / output_file_name
    command = [
        "ffmpeg",
        "-i", str(input_file),
        "-map", "0:v", "-map", "0:a",
        "-c:v", "libx264",
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        "-b:v", "3500000", "-bufsize", "1750000", "-maxrate", "3500000",
        "-vf", "yadif",
        "-c:a", "aac", "-b:a", "320000", "-ar", "48000", str(output_file)
    ]
    subprocess.check_call(command)

    return output_file

    
def convert_mov_file(input_file, input_directory):
    """Convert a MOV file to FFV1 and MP4 formats using FFmpeg"""    
    output_file1 = input_directory / f"{pathlib.Path(input_file).stem}.mkv"
    output_file2 = input_directory / f"{input_file.stem.replace('_pm', '')}_sc.mp4"
    command1 = [
        "ffmpeg",
        "-i", input_file,
        "-map", "0", "-dn", "-c:v", "ffv1", "-level", "3", "-g", "1", "-slicecrc", "1",
        "-slices", "24", "-field_order", "bt", "-vf", "setfield=bff,setdar=4/3",
        "-color_primaries", "smpte170m", "-color_range", "tv", "-color_trc", "bt709",
        "-colorspace", "smpte170m", "-c:a", "copy", str(output_file1)
    ]
    subprocess.run(command1)
    command2 = [
        "ffmpeg",
        "-i", input_file,
        "-map", "0", "-dn", "-c:v", "libx264", "-movflags", "faststart", "-pix_fmt", "yuv420p",
        "-b:v", "3500000", "-bufsize", "1750000", "-maxrate", "3500000", "-vf", "yadif",
        "-c:a", "aac", "-b:a", "320000", "-ar", "48000", str(output_file2)
    ]
    subprocess.run(command2)


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


def delete_empty_directories(input_directory, directories):
    for directory in directories:
        dir_path = input_directory / directory
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
        except FileNotFoundError:
            pass


def main(input_directory, transcribe):
    extensions = ("*.mov", "*.mkv", "*.xml.gz", "*.framemd5")
    rename_files(input_directory, extensions)
    convert_mkv_dv_to_mp4(input_directory)
        
    process_mov_files(input_directory)
    generate_framemd5_files(input_directory)

    if transcribe:
        transcribe_files(input_directory)
    
    directories = ["PreservationMasters", "ServiceCopies", "V210", "AuxiliaryFiles"]
    create_directories(input_directory, directories)

    move_files(input_directory)
    move_log_files_to_auxiliary_files(input_directory)
    
    delete_empty_directories(input_directory, ["AuxiliaryFiles", "V210"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process video files in a specified directory.")
    parser.add_argument("-d", "--directory", type=str, required=True, help="Input directory containing video files.")
    parser.add_argument("-t", "--transcribe", action="store_true", help="Transcribe the audio of the MKV files to VTT format using the Whisper tool.")
    
    args = parser.parse_args()
    
    input_dir = pathlib.Path(args.directory)
    
    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a valid directory.")
        exit(1)
    
    main(input_dir, args.transcribe)
