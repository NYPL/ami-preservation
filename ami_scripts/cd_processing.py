#!/usr/bin/env python3
"""
Process directories of CD WAV files using accompanying CUE files to concatenate tracks in the correct order using shntool.
If only one WAV is present, simply copy and rename instead of attempting to join.
Handles named tracks, diacritics, and falls back to alphabetical listing when necessary, ensuring unmatched tracks are filled.
"""
import argparse
import os
import re
import subprocess
import shutil
import unicodedata

def parse_args():
    parser = argparse.ArgumentParser(
        description="Process directories of CD WAV files using cues and shntool."
    )
    parser.add_argument(
        "-i", "--input", required=True,
        help="Input directory containing subdirectories for each CD (named by six-digit ID)."
    )
    parser.add_argument(
        "-p", "--prefix", required=True,
        help="Three-letter prefix for output filenames."
    )
    return parser.parse_args()

def strip_accents(text):
    """Strip accents from string using Unicode NFD normalization."""
    return ''.join(
        ch for ch in unicodedata.normalize('NFD', text)
        if unicodedata.category(ch) != 'Mn'
    )

def main():
    args = parse_args()
    input_dir = os.path.abspath(args.input)
    prefix = args.prefix

    processed_dir = os.path.join(input_dir, "Processed")
    preservation_dir = os.path.join(input_dir, "PreservationMasters")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(preservation_dir, exist_ok=True)

    for entry in sorted(os.listdir(input_dir)):
        entry_path = os.path.join(input_dir, entry)
        if not os.path.isdir(entry_path) or entry in ("Processed", "PreservationMasters"):
            continue
        if not (entry.isdigit() and len(entry) == 6):
            print(f"Skipping {entry}: not a six-digit ID.")
            continue

        print(f"Processing CD {entry}...")
        # Find the CUE file
        cue_files = [f for f in os.listdir(entry_path) if f.lower().endswith('.cue')]
        if not cue_files:
            print(f"No .cue file found in {entry}, skipping.")
            continue
        cue_path = os.path.join(entry_path, cue_files[0])

        # Read track-level titles from CUE
        track_titles = []
        in_track = False
        with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if re.match(r"^\s*TRACK", line):
                    in_track = True
                if in_track:
                    m = re.match(r'^\s*TITLE\s+"(.+)"', line)
                    if m:
                        track_titles.append(m.group(1))

        # List WAV files and build normalized map
        all_wavs = [f for f in os.listdir(entry_path) if f.lower().endswith('.wav')]
        norm_map = {wav: strip_accents(wav).casefold() for wav in all_wavs}

        # Determine WAV order
        if track_titles:
            # Pre-allocate slots
            wav_paths = [None] * len(track_titles)
            # Match titles to files
            for idx, title in enumerate(track_titles):
                norm_title = strip_accents(title).casefold()
                matches = [wav for wav, norm in norm_map.items() if norm_title in norm]
                if matches:
                    if len(matches) > 1:
                        print(f"Multiple matches for '{title}' in {entry}: using '{matches[0]}'")
                    wav_paths[idx] = os.path.join(entry_path, matches[0])
                else:
                    print(f"Warning: no WAV matching title '{title}' in {entry}")
            # Fill unmatched slots
            remaining = [wav for wav in all_wavs if os.path.join(entry_path, wav) not in wav_paths]
            for i in range(len(wav_paths)):
                if wav_paths[i] is None and remaining:
                    fill = remaining.pop(0)
                    wav_paths[i] = os.path.join(entry_path, fill)
                    print(f"Filled missing track {i+1} with '{fill}'")
        else:
            # No titles: alphabetical fallback
            wav_paths = [os.path.join(entry_path, wav) for wav in sorted(all_wavs)]
            if not wav_paths:
                print(f"No WAV files found in {entry}, skipping.")
                continue
            else:
                print(f"No track titles in {entry}: using alphabetical WAV listing")

        # Remove any None entries
        wav_paths = [p for p in wav_paths if p]
        if not wav_paths:
            print(f"No valid WAVs to process for {entry}, skipping.")
            continue

        # Prepare output names
        base = f"{prefix}_{entry}_v01_pm"
        out_wav = os.path.join(preservation_dir, base + '.wav')
        out_cue = os.path.join(preservation_dir, base + '.cue')

        # Join or copy
        if len(wav_paths) > 1:
            try:
                subprocess.run(
                    ['shntool', 'join', '-o', 'wav', '-r', 'none'] + wav_paths,
                    cwd=preservation_dir,
                    check=True
                )
                default_join = os.path.join(preservation_dir, 'joined.wav')
                if os.path.exists(default_join):
                    os.rename(default_join, out_wav)
                else:
                    print(f"Expected 'joined.wav' not found for {entry}.")
            except subprocess.CalledProcessError as e:
                print(f"Error joining WAVs for {entry}: {e}")
                continue
        else:
            print(f"Only one WAV in {entry}; copying to '{out_wav}'")
            shutil.copy2(wav_paths[0], out_wav)

        # Copy and rename CUE
        shutil.copy2(cue_path, out_cue)
        # Move processed folder
        shutil.move(entry_path, processed_dir)
        print(f"Finished processing {entry}: {os.path.basename(out_wav)}, {os.path.basename(out_cue)}")

    print("All done.")

if __name__ == '__main__':
    main()
