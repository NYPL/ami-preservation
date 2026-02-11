#!/usr/bin/env python3

import argparse
import re
import os

def get_core_name(basename):
    # Strips trailing suffixes to find the "Asset ID"
    # Now includes: _mz (Mezzanine) and _pm (Preservation Master)
    # Example: 'myd_493093_v01_pm' -> 'myd_493093_v01'
    return re.sub(r'_((talk|wide|close)_)?(sc|em|mz|pm)$', '', basename)

def analyze_csv(file_path):
    # Regex for old style: Date, Time, Size, Filename
    old_style_regex = re.compile(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\d+\s+(?P<filename>.*)$')
    
    # Regex for conforming ID: [prefix]_[6-digits]_
    id_pattern = re.compile(r'^([a-zA-Z0-9]+)_(?P<id>\d{6})_')

    # Define what counts as "Media"
    media_extensions = {'.mp4', '.flac', '.wav', '.mov', '.mkv', '.avi', '.mp3', '.m4a'}

    stats = {
        "unique_ids": set(),
        "flac_count": 0,
        "mp4_count": 0,
        "json_count": 0,
        "total_media": 0,
        "non_conforming_count": 0,
        "flac_basenames": set(),
        "mp4_basenames": set(),
        "json_basenames": set()
    }

    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print(f"Analyzing {os.path.basename(file_path)}...")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines or the literal header "filePath"
            if not line or line.lower() == 'filepath':
                continue
            
            # 1. Try to parse as Old Style (Timestamp + Size + Name)
            match = old_style_regex.match(line)
            
            if match:
                filename = match.group('filename')
            else:
                # 2. Fallback: Treat line as a File Path (New Style)
                # os.path.basename works on both "/path/to/file.mp4" and just "file.mp4"
                filename = os.path.basename(line)

            # Skip Mac OS hidden files
            if filename.startswith('._'):
                continue

            # --- DATA COLLECTION ---

            # ID Validation
            id_match = id_pattern.match(filename)
            if id_match:
                stats["unique_ids"].add(id_match.group('id'))
            else:
                stats["non_conforming_count"] += 1

            # Extension Handling
            basename, ext = os.path.splitext(filename)
            ext = ext.lower()

            if ext == '.flac':
                stats["flac_count"] += 1
                stats["total_media"] += 1
                stats["flac_basenames"].add(basename)
            elif ext == '.mp4':
                stats["mp4_count"] += 1
                stats["total_media"] += 1
                stats["mp4_basenames"].add(basename)
            elif ext == '.json':
                stats["json_count"] += 1
                stats["json_basenames"].add(basename)
            elif ext in media_extensions:
                stats["total_media"] += 1

    # --- CROSS REFERENCING ---

    # Generate "core" names (stripped of _sc, _pm, etc)
    json_cores = {get_core_name(b) for b in stats["json_basenames"]}
    mp4_cores = {get_core_name(b) for b in stats["mp4_basenames"]}

    # Identify Orphans
    flac_no_mp4 = [b for b in stats["flac_basenames"] if get_core_name(b) not in mp4_cores]
    mp4_no_json = [b for b in stats["mp4_basenames"] if get_core_name(b) not in json_cores]
    json_no_mp4 = [b for b in stats["json_basenames"] if get_core_name(b) not in mp4_cores]

    # Print Results
    print(f"\n--- Analysis Results ---")
    print(f"(1) Unique 6-digit IDs:          {len(stats['unique_ids'])}")
    print(f"(2) Total FLAC files:           {stats['flac_count']}")
    print(f"(3) FLAC without matching MP4:  {len(flac_no_mp4)}")
    print(f"(4) Total MP4 files:            {stats['mp4_count']}")
    print(f"(5) Total JSON files:           {stats['json_count']}")
    print(f"(6) Non-conforming filenames:   {stats['non_conforming_count']}")
    print(f"(*) TOTAL MEDIA FILES:          {stats['total_media']} (MP4 + FLAC + MKV/MOV/etc)")
    
    print("\n--- Discrepancy Analysis ---")
    print(f"(A) MP4s without matching JSON: {len(mp4_no_json)}")
    print(f"(B) JSONs without matching MP4: {len(json_no_mp4)}")

    if mp4_no_json:
        print("\nFirst 5 MP4s missing JSON (examples):")
        for name in list(mp4_no_json)[:5]:
            print(f"  - {name}.mp4")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, help="Path to input CSV/TXT")
    args = parser.parse_args()
    analyze_csv(args.input)