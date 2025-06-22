#!/usr/bin/env python3
"""
Compare durations of corresponding preservation master (PM) and edit master (EM)
audio files under a directory tree. Outputs a CSV with base name, paths,
durations, and their difference, with a progress bar.

Usage:
    python compare_pm_em_durations.py -i /path/to/input_dir [-o durations.csv]

Requirements:
    - Python 3.6+
    - ffprobe (part of FFmpeg) must be in your PATH.
"""

import argparse
import csv
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from tqdm import tqdm


def get_args():
    parser = argparse.ArgumentParser(
        description=(
            "Recursively look for *_pm.wav, *_pm.flac, *_em.wav, *_em.flac under "
            "the input directory, compute each file's duration via ffprobe, and "
            "write a CSV comparing PM vs. EM durations."
        )
    )
    parser.add_argument(
        "-i", "--input", required=True,
        help="Path to the root directory to search"
    )
    parser.add_argument(
        "-o", "--output", default="durations.csv",
        help="Output CSV file (default: durations.csv)"
    )
    parser.add_argument(
        "--log-file", default=None,
        help="Optional file to write logs to (default: stderr)"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    return parser.parse_args()


def get_duration(path: Path) -> float:
    """
    Run ffprobe to get the duration (in seconds) of an audio file.
    Returns a float (seconds) on success, or None on failure.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = completed.stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError) as e:
        tqdm.write(f"WARNING: Failed to get duration for {path}: {e}")
        return None


def main():
    args = get_args()

    # Configure logging
    log_handlers = []
    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))
    else:
        log_handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=log_handlers
    )

    input_dir = Path(args.input).resolve()
    output_csv = Path(args.output)

    if not input_dir.is_dir():
        logging.error(f"'{input_dir}' is not a directory or does not exist.")
        sys.exit(1)

    logging.info(f"Starting comparison in directory: {input_dir}")

    # Patterns to match "*_pm.wav", "*_pm.flac", "*_em.wav", "*_em.flac"
    pm_pattern = re.compile(r"^(?P<base>.+)_pm\.(wav|flac)$", re.IGNORECASE)
    em_pattern = re.compile(r"^(?P<base>.+)_em\.(wav|flac)$", re.IGNORECASE)

    pm_files = {}
    em_files = {}

    # Discover files
    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            fullpath = Path(root) / fname
            if pm_match := pm_pattern.match(fname):
                pm_files[pm_match.group('base')] = fullpath
                logging.debug(f"Found PM: {fullpath}")
            elif em_match := em_pattern.match(fname):
                em_files[em_match.group('base')] = fullpath
                logging.debug(f"Found EM: {fullpath}")

    common_bases = sorted(pm_files.keys() & em_files.keys())
    if not common_bases:
        logging.error("No matching PM/EM pairs were found.")
        sys.exit(1)

    # Open CSV and progress bar
    with output_csv.open("w", newline='', encoding="utf-8") as csvfile, tqdm(total=len(common_bases), unit="file") as pbar:
        writer = csv.writer(csvfile)
        writer.writerow([
            "base",
            "pm_path", "pm_duration_seconds",
            "em_path", "em_duration_seconds",
            "duration_diff_seconds"
        ])

        for idx, base in enumerate(common_bases, start=1):
            pm_path = pm_files[base]
            em_path = em_files[base]

            # Update progress bar description and log
            pbar.set_description(f"{idx}/{len(common_bases)}: {base}")
            logging.info(f"Processing base ({idx}/{len(common_bases)}): {base}")

            pm_dur = get_duration(pm_path)
            em_dur = get_duration(em_path)

            if pm_dur is None or em_dur is None:
                pm_str = f"{pm_dur:.3f}" if pm_dur is not None else ""
                em_str = f"{em_dur:.3f}" if em_dur is not None else ""
                diff_str = ""
                logging.warning(
                    f"Could not read duration for {base}: pm_dur={pm_dur}, em_dur={em_dur}"
                )
            else:
                pm_str = f"{pm_dur:.3f}"
                em_str = f"{em_dur:.3f}"
                diff = em_dur - pm_dur
                diff_str = f"{diff:.3f}"
                logging.info(f"  Durations -> PM: {pm_str}s, EM: {em_str}s, Diff: {diff_str}s")

            writer.writerow([
                base,
                pm_path, pm_str,
                em_path, em_str,
                diff_str
            ])
            pbar.update(1)

    logging.info(f"Done. CSV written to: {output_csv}")


if __name__ == "__main__":
    main()
