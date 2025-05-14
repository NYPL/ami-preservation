#!/usr/bin/env python3
"""
Process directories of CD WAV files using accompanying CUE files to concatenate tracks in the correct order using shntool.
If only one WAV is present, simply copy and rename instead of attempting to join.
Handles named tracks, diacritics, and falls back to alphabetical listing when necessary, ensuring unmatched tracks are filled.
* Default (join) mode  →  concatenate per‑track WAVs into a single master.
* Split mode (-s/--split) →  split a single master WAV/FLAC + CUE back into
    individual tracks (Track01.wav, Track02.wav, …).
"""
import argparse
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────
def strip_accents(txt: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn"
    ).casefold()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


# ── JOIN LOGIC (unchanged except for tidy refactor) ────────────────────────
def join_discs(root: Path, prefix: str) -> None:
    processed_dir = root / "Processed"
    pm_dir = root / "PreservationMasters"
    processed_dir.mkdir(exist_ok=True)
    pm_dir.mkdir(exist_ok=True)

    for disc_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if disc_dir.name in ("Processed", "PreservationMasters"):
            continue
        if not (disc_dir.name.isdigit() and len(disc_dir.name) == 6):
            print(f"Skipping {disc_dir.name}: not a six‑digit ID.")
            continue

        cue_files = list(disc_dir.glob("*.cue"))
        if not cue_files:
            print(f"No .cue file in {disc_dir.name}, skipping.")
            continue
        cue_path = cue_files[0]

        # ----- read TITLEs from CUE -----------------------------------------
        titles = []
        in_track = False
        for line in cue_path.read_text(encoding="utf‑8", errors="ignore").splitlines():
            if line.lstrip().startswith("TRACK"):
                in_track = True
            if in_track:
                m = re.match(r'^\s*TITLE\s+"(.+)"', line)
                if m:
                    titles.append(m.group(1))

        all_wavs = [p for p in disc_dir.glob("*.wav")]
        if not all_wavs:
            print(f"No WAVs in {disc_dir.name}, skipping.")
            continue

        def norm(p: Path) -> str:
            return strip_accents(p.stem)

        exact_map = {norm(w): w for w in all_wavs}
        used, ordered = set(), []

        if titles:
            for t in titles:
                nt = strip_accents(t)
                chosen = None
                # exact basename first
                if nt in exact_map and exact_map[nt] not in used:
                    chosen = exact_map[nt]
                else:
                    cands = [w for w in all_wavs if nt in norm(w) and w not in used]
                    if cands:
                        chosen = sorted(cands, key=lambda p: len(p.name))[0]

                if chosen:
                    ordered.append(chosen)
                    used.add(chosen)
                else:
                    ordered.append(None)
                    print(f"Warning: '{t}' unmatched in {disc_dir.name}")

            # fill gaps alphabetically
            remaining = [w for w in sorted(all_wavs) if w not in used]
            for i, v in enumerate(ordered):
                if v is None and remaining:
                    ordered[i] = remaining.pop(0)
        else:
            ordered = sorted(all_wavs)

        ordered = [p for p in ordered if p]

        out_base = f"{prefix}_{disc_dir.name}_v01_pm"
        out_wav = pm_dir / f"{out_base}.wav"
        out_cue = pm_dir / f"{out_base}.cue"

        if len(ordered) > 1:
            run(["shntool", "join", "-o", "wav", "-r", "none", *map(str, ordered), "-d", str(pm_dir)])
            joined = pm_dir / "joined.wav"
            if joined.exists():
                joined.rename(out_wav)
        else:
            shutil.copy2(ordered[0], out_wav)

        shutil.copy2(cue_path, out_cue)
        shutil.move(str(disc_dir), processed_dir)
        print(f"Finished {disc_dir.name}: {out_wav.name}")

    print("All done (join mode).")


# ── SPLIT LOGIC ────────────────────────────────────────────────────────────
def split_masters(pm_dir: Path) -> None:
    """
    Walk a PreservationMasters directory, split each master WAV/FLAC by its CUE.
    Masters that contain only a single track (one TRACK entry in the CUE) are
    handled by copying the whole file to Track01.ext.
    """
    parent   = pm_dir.parent
    out_root = parent / "Processed_Split"
    out_root.mkdir(exist_ok=True)

    masters = sorted(p for p in pm_dir.iterdir()
                     if p.suffix.lower() in (".wav", ".flac"))

    for master in masters:
        m = re.search(r"(\d{6})", master.stem)
        if not m:
            print(f"Skipping {master.name}: no 6‑digit ID in filename.")
            continue
        disc_id   = m.group(1)
        cue_path  = master.with_suffix(".cue")
        if not cue_path.exists():
            print(f"Missing CUE for {master.name}, skipping.")
            continue

        # Count TRACK lines in the cue file
        track_count = sum(1 for line in cue_path.read_text(
                          encoding="utf‑8", errors="ignore").splitlines()
                          if re.match(r"^\s*TRACK", line))

        dest = out_root / disc_id
        dest.mkdir(exist_ok=True)

        # Single‑track disc ➜ copy & rename to Track01
        if track_count <= 1:
            new_name = f"Track01{master.suffix.lower()}"
            shutil.copy2(master, dest / new_name)
            shutil.copy2(cue_path, dest)
            print(f"Copied single‑track {master.name} → {dest/new_name}")
            continue

        # Multi‑track ➜ split with shnsplit
        fmt_out = "flac" if master.suffix.lower() == ".flac" else "wav"
        try:
            run(["shnsplit", "-f", str(cue_path), "-o", fmt_out,
                 "-t", "Track%n", "-d", str(dest), str(master)])
            shutil.copy2(cue_path, dest)
            print(f"Split {master.name} → {dest}")
        except subprocess.CalledProcessError as e:
            print(f"shnsplit failed on {master.name}: {e}")

    print("All done (split mode).")


# ── CLI / main ─────────────────────────────────────────────────────────────
def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True,
                    help="Root folder of disc subdirs (join) OR PreservationMasters dir (split)")
    ap.add_argument("-p", "--prefix", default="xxx",
                    help="Three‑letter prefix for joined masters (join mode only)")
    ap.add_argument("-s", "--split", action="store_true",
                    help="Activate split mode (default is join)")
    args = ap.parse_args()

    path = Path(args.input).expanduser().resolve()
    if args.split:
        split_masters(path)
    else:
        join_discs(path, args.prefix)


if __name__ == "__main__":
    cli()
