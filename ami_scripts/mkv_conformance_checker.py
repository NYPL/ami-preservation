#!/usr/bin/env python3

import argparse
import subprocess
import os
import re
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
    extracted = {"Compliance details": []}

    for line in lines:
        if line.startswith("IsTruncated"):
            extracted["IsTruncated"] = line.split(":", 1)[1].strip()
        elif line.startswith("Conformance errors"):
            extracted["Conformance errors"] = line.split(":", 1)[1].strip()
        elif "General compliance" in line:
            extracted["Compliance details"].append(line.strip())

    # default to not truncated if key missing
    extracted.setdefault("IsTruncated", "No")
    return extracted

def process_directories(input_paths):
    passed_ids = []
    truncated_info = {}

    for input_path in input_paths:
        for mkv_file in Path(input_path).rglob("*.mkv"):
            # extract six-digit bag ID from filename (fallback to stem)
            m = re.search(r"(\d{6})", mkv_file.name)
            bag_id = m.group(1) if m else mkv_file.stem

            print(f"\n[INFO] Checking file: {mkv_file}")
            output = run_mediainfo(mkv_file)
            if not output:
                continue

            data = extract_attributes(output)
            if data["IsTruncated"] == "Yes":
                # find the first general compliance message
                msg = data["Compliance details"][0] if data["Compliance details"] else "No compliance detail found"
                print(f"  {bag_id}: Truncated – {msg}")
                truncated_info[bag_id] = msg
            else:
                print(f"  {bag_id}: Pass")
                passed_ids.append(bag_id)

    return passed_ids, truncated_info

def main():
    parser = argparse.ArgumentParser(
        description="Check MKV files for Mediainfo conformance issues."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        nargs="+",
        help="One or more paths to input directories"
    )
    args = parser.parse_args()

    passed, truncated = process_directories(args.input)

    # summary report
    print("\n=== Summary Report ===")
    print(f"Passed bags    : {len(passed)}", end="")
    if passed:
        print(f" (IDs: {', '.join(passed)})")
    else:
        print()
    print(f"Truncated bags : {len(truncated)}")
    if truncated:
        print("Details:")
        for bag_id, msg in truncated.items():
            print(f"  • {bag_id}: {msg}")

if __name__ == "__main__":
    main()
