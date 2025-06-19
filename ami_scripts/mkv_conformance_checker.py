#!/usr/bin/env python3

import argparse
import subprocess
import os
from pathlib import Path

def run_mediainfo(file_path):
    try:
        result = subprocess.run(
            ["mediainfo", "-F", "-Language=raw", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to run mediainfo on {file_path}:\n{e.stderr}")
        return None

def extract_attributes(output):
    lines = output.splitlines()
    extracted = {}
    capture_lines = []

    for line in lines:
        if line.startswith("IsTruncated"):
            extracted["IsTruncated"] = line.split(":", 1)[1].strip()
        elif line.startswith("Conformance errors"):
            extracted["Conformance errors"] = line.split(":", 1)[1].strip()
        elif "General compliance" in line or "Matroska" in line or line.strip().startswith("0x"):
            capture_lines.append(line.strip())

    extracted["Compliance details"] = capture_lines
    return extracted

def process_directory(input_path):
    for mkv_file in Path(input_path).rglob("*.mkv"):
        print(f"\n[INFO] Checking file: {mkv_file}")
        output = run_mediainfo(mkv_file)
        if output:
            data = extract_attributes(output)
            for key, value in data.items():
                if isinstance(value, list):
                    for v in value:
                        print(f"  {v}")
                else:
                    print(f"  {key}: {value}")

def main():
    parser = argparse.ArgumentParser(description="Check MKV files for Mediainfo conformance issues.")
    parser.add_argument("-i", "--input", required=True, help="Path to input directory")
    args = parser.parse_args()
    process_directory(args.input)

if __name__ == "__main__":
    main()
