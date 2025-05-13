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
    p = argparse.ArgumentParser(
        description="Concatenate/copy CD WAVs according to CUE track order"
    )
    p.add_argument(
        "-i", "--input", required=True,
        help="Directory with one sub‑folder per disc (named by six‑digit ID)"
    )
    p.add_argument(
        "-p", "--prefix", required=True,
        help="Three‑letter prefix for output filenames"
    )
    return p.parse_args()


def strip_accents(text: str) -> str:
    """Remove diacritics; return lower‑cased, accent‑free string."""
    return ''.join(
        ch for ch in unicodedata.normalize('NFD', text)
        if unicodedata.category(ch) != 'Mn'
    ).casefold()


def process_disc(disc_path: str, disc_id: str, prefix: str,
                 processed_dir: str, preservation_dir: str) -> None:

    cue_files = [f for f in os.listdir(disc_path) if f.lower().endswith(".cue")]
    if not cue_files:
        print(f"No .cue file found in {disc_id}, skipping.")
        return
    cue_path = os.path.join(disc_path, cue_files[0])

    # --- extract TITLE lines from CUE ---------------------------------------
    track_titles = []
    in_track = False
    with open(cue_path, encoding="utf‑8", errors="ignore") as fh:
        for line in fh:
            if re.match(r"^\s*TRACK", line):
                in_track = True
            if in_track:
                m = re.match(r'^\s*TITLE\s+"(.+)"', line)
                if m:
                    track_titles.append(m.group(1))

    all_wavs = [f for f in os.listdir(disc_path) if f.lower().endswith(".wav")]
    if not all_wavs:
        print(f"No WAV files found in {disc_id}, skipping.")
        return

    noext = lambda p: os.path.splitext(p)[0]
    norm   = lambda p: strip_accents(noext(p))

    exact_map = {norm(w): w for w in all_wavs}
    used: set[str] = set()
    wav_paths: list[str | None] = []

    if track_titles:                     #  ❯❯❯  TITLE‑driven ordering
        for title in track_titles:
            n_title = strip_accents(title)

            chosen = None
            # 1) exact basename match (unused)
            if n_title in exact_map and exact_map[n_title] not in used:
                chosen = exact_map[n_title]
            else:
                # 2) substring match (unused)
                cands = [w for w in all_wavs
                         if n_title in norm(w) and w not in used]
                if cands:
                    # prefer the shortest candidate (avoids hcbb vs hcbbng)
                    chosen = sorted(cands, key=len)[0]

            if chosen:
                wav_paths.append(os.path.join(disc_path, chosen))
                used.add(chosen)
            else:
                wav_paths.append(None)
                print(f"Warning: no WAV matching '{title}' in {disc_id}")

        # Fill any gaps with remaining unused WAVs alphabetically
        remaining = [w for w in sorted(all_wavs) if w not in used]
        for idx, val in enumerate(wav_paths):
            if val is None and remaining:
                fill = remaining.pop(0)
                wav_paths[idx] = os.path.join(disc_path, fill)
                used.add(fill)
                print(f"Filled missing track {idx+1} with '{fill}'")
    else:                               #  ❯❯❯  Alphabetical fallback
        print(f"No TITLE lines in {disc_id}; using alphabetical WAV order")
        wav_paths = [os.path.join(disc_path, w) for w in sorted(all_wavs)]

    # ── output names ---------------------------------------------------------
    base = f"{prefix}_{disc_id}_v01_pm"
    out_wav = os.path.join(preservation_dir, base + ".wav")
    out_cue = os.path.join(preservation_dir, base + ".cue")

    # ── join or copy ---------------------------------------------------------
    if len(wav_paths) > 1:
        try:
            subprocess.run(
                ["shntool", "join", "-o", "wav", "-r", "none"] + wav_paths,
                cwd=preservation_dir,
                check=True
            )
            joined = os.path.join(preservation_dir, "joined.wav")
            if os.path.exists(joined):
                os.rename(joined, out_wav)
            else:
                print(f"Expected 'joined.wav' not found for {disc_id}")
                return
        except subprocess.CalledProcessError as e:
            print(f"shntool error on {disc_id}: {e}")
            return
    else:
        shutil.copy2(wav_paths[0], out_wav)

    # copy/rename CUE, move source dir to “Processed”
    shutil.copy2(cue_path, out_cue)
    shutil.move(disc_path, processed_dir)

    print(f"Finished {disc_id}: {os.path.basename(out_wav)}")


def main():
    args = parse_args()
    input_dir = os.path.abspath(args.input)
    prefix = args.prefix

    processed_dir     = os.path.join(input_dir, "Processed")
    preservation_dir  = os.path.join(input_dir, "PreservationMasters")
    os.makedirs(processed_dir,    exist_ok=True)
    os.makedirs(preservation_dir, exist_ok=True)

    for entry in sorted(os.listdir(input_dir)):
        disc_path = os.path.join(input_dir, entry)
        if (not os.path.isdir(disc_path)
                or entry in ("Processed", "PreservationMasters")):
            continue
        if not (entry.isdigit() and len(entry) == 6):
            print(f"Skipping {entry}: not a six‑digit ID.")
            continue

        print(f"Processing CD {entry} …")
        process_disc(disc_path, entry, prefix, processed_dir, preservation_dir)

    print("All done.")


if __name__ == "__main__":
    main()