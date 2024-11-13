#!/usr/bin/env python3

import argparse
import os
import csv
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _make_parser():
    parser = argparse.ArgumentParser(description="Pull MediaInfo from a bunch of video or audio files")
    parser.add_argument("-d", "--directory",
                        help="Path to folder full of media files",
                        required=True)
    parser.add_argument("-o", "--output",
                        help="Path to save CSV",
                        required=True)
    parser.add_argument("-c", "--checkpoint",
                        help="Path to a checkpoint file for resuming progress",
                        required=False)
    return parser

def load_checkpoint(checkpoint_file):
    if checkpoint_file and os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            processed_files = {line.strip() for line in f}
        LOGGER.info(f"Loaded {len(processed_files)} entries from checkpoint.")
        return processed_files
    return set()

def save_checkpoint(checkpoint_file, processed_files):
    if checkpoint_file:
        with open(checkpoint_file, 'w') as f:
            f.writelines(f"{file}\n" for file in processed_files)
        LOGGER.info(f"Checkpoint saved with {len(processed_files)} entries.")

def gather_files(directory, extensions, processed_files):
    LOGGER.info("Gathering files...")
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                if file_path not in processed_files:
                    yield file_path

def main():
    parser = _make_parser()
    args = parser.parse_args()

    directory = args.directory
    output_file = args.output
    checkpoint_file = args.checkpoint
    extensions = ['.mkv', '.mov', '.json', '.wav', '.mp4', '.dv', '.iso', '.flac']

    if not os.path.isdir(directory):
        LOGGER.error("The specified directory does not exist.")
        return

    # Load checkpoint if available
    processed_files = load_checkpoint(checkpoint_file)

    # Open output file in append mode
    with open(output_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if os.path.getsize(output_file) == 0:  # Write header if file is empty
            writer.writerow(['filePath'])

        try:
            # Iterate over files and write to CSV
            for file_path in gather_files(directory, extensions, processed_files):
                writer.writerow([file_path])
                processed_files.add(file_path)

                # Save checkpoint periodically
                if len(processed_files) % 1000 == 0:
                    save_checkpoint(checkpoint_file, processed_files)
                    LOGGER.info(f"Processed {len(processed_files)} files so far.")
        except KeyboardInterrupt:
            LOGGER.warning("Process interrupted. Saving progress...")
            save_checkpoint(checkpoint_file, processed_files)

    # Final checkpoint save
    save_checkpoint(checkpoint_file, processed_files)
    LOGGER.info(f"Processing complete. Total files processed: {len(processed_files)}")

if __name__ == "__main__":
    main()
