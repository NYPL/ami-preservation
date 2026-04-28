#!/usr/bin/env python3

import os
import json
import hashlib
import logging
import argparse
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192

def fix_sc_json_filename(data_dir: Path) -> List[str]:
    """
    Finds *_sc.json files and appends '_sc' to the technical.filename field if missing.
    
    Args:
        data_dir: Path to the bag's 'data' directory.
        
    Returns:
        List of modified JSON file paths.
    """
    modified_files = []

    for json_file in data_dir.rglob('*_sc.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            technical = data.get("technical", {})
            current_filename = technical.get("filename", "")

            # Check if filename exists and doesn't already have the _sc suffix
            if current_filename and not current_filename.endswith("_sc"):
                technical["filename"] = f"{current_filename}_sc"
                
                # Write updated JSON back to file
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    f.write('\n') # Ensure newline at EOF

                modified_files.append(str(json_file))
                logger.info(f"Fixed filename in: {json_file.name}")

        except Exception as e:
            logger.error(f"Failed to process {json_file}: {e}")
            continue

    return modified_files

def calculate_md5(file_path: Path) -> str:
    """Calculate MD5 checksum for a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate MD5 for {file_path}: {e}")
        raise

def update_manifests(bag_path: Path, modified_paths: List[str]) -> None:
    """Update BagIt manifest-md5.txt with new checksums."""
    manifest_path = bag_path / 'manifest-md5.txt'

    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                parts = line.strip().split(' ', 1)
                if len(parts) != 2:
                    updated_lines.append(line)
                    continue
                    
                old_checksum, rel_path = parts
                rel_path = rel_path.strip()
                
                # If this file was modified, calculate new checksum
                if rel_path in modified_paths:
                    full_path = bag_path / rel_path
                    if full_path.is_file():
                        new_checksum = calculate_md5(full_path)
                        # BagIt spec requires double spaces or space-asterisk, standard is space-space for text
                        updated_lines.append(f"{new_checksum}  {rel_path}\n")
                    else:
                        logger.warning(f"File not found for manifest update: {full_path}")
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)

            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
                
            logger.info("Updated manifest-md5.txt")

        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
            raise

def update_payload_oxum(bag_path: Path) -> None:
    """Recalculate and update Payload-Oxum in bag-info.txt."""
    data_path = bag_path / 'data'
    bag_info_path = bag_path / 'bag-info.txt'

    if not data_path.exists() or not bag_info_path.exists():
        return

    total_size = 0
    total_files = 0

    for file_path in data_path.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            total_files += 1

    new_oxum = f"{total_size}.{total_files}"

    try:
        with open(bag_info_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated_lines = []
        oxum_found = False
        
        for line in lines:
            if line.startswith('Payload-Oxum:'):
                updated_lines.append(f'Payload-Oxum: {new_oxum}\n')
                oxum_found = True
            else:
                updated_lines.append(line)

        if not oxum_found:
            updated_lines.append(f'Payload-Oxum: {new_oxum}\n')

        with open(bag_info_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
            
        logger.info(f"Updated Payload-Oxum to {new_oxum}")
            
    except Exception as e:
        logger.error(f"Failed to update bag-info.txt: {e}")
        raise

def update_tagmanifest(bag_path: Path) -> None:
    """Update tagmanifest-md5.txt with new checksums for metadata files."""
    tag_manifest_path = bag_path / 'tagmanifest-md5.txt'
    bag_info_path = bag_path / 'bag-info.txt'
    manifest_path = bag_path / 'manifest-md5.txt'

    if not tag_manifest_path.exists():
        return

    try:
        with open(tag_manifest_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                updated_lines.append(line)
                continue
                
            old_checksum, filename = parts
            filename = filename.strip()

            if filename == 'manifest-md5.txt' and manifest_path.exists():
                new_checksum = calculate_md5(manifest_path)
                updated_lines.append(f"{new_checksum}  {filename}\n")
            elif filename == 'bag-info.txt' and bag_info_path.exists():
                new_checksum = calculate_md5(bag_info_path)
                updated_lines.append(f"{new_checksum}  {filename}\n")
            else:
                updated_lines.append(line)

        with open(tag_manifest_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
            
        logger.info("Updated tagmanifest-md5.txt")

    except Exception as e:
        logger.error(f"Failed to update tagmanifest: {e}")
        raise

def process_bag(bag_path: Path) -> None:
    """Orchestrate the processing of a single BagIt bag."""
    logger.info(f"--- Processing Bag: {bag_path.name} ---")
    data_dir = bag_path / 'data'
    
    if not data_dir.exists():
        logger.warning(f"No 'data' directory found in {bag_path}. Skipping.")
        return

    try:
        # Step 1: Fix the JSON files
        modified_absolute_paths = fix_sc_json_filename(data_dir)

        if not modified_absolute_paths:
            logger.info("No files needed updating.")
            return

        # Step 2: Convert to relative paths for BagIt manifest matching
        rel_modified = [
            os.path.relpath(path, start=bag_path).replace('\\', '/')
            for path in modified_absolute_paths
        ]

        # Step 3: Update all standard BagIt manifests
        update_manifests(bag_path, rel_modified)
        update_payload_oxum(bag_path)
        update_tagmanifest(bag_path)
        
        logger.info(f"Successfully finished processing {bag_path.name}\n")

    except Exception as e:
        logger.error(f"Failed during bag processing for {bag_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Fix missing '_sc' suffix in JSON sidecars and update BagIt manifests.")
    
    # Updated to require the -i / --input flag
    parser.add_argument(
        "-i", "--input", 
        dest="target_path", 
        type=Path, 
        required=True, 
        help="Path to a single BagIt bag or a directory containing multiple bags."
    )
    
    args = parser.parse_args()
    target = args.target_path

    if not target.exists():
        logger.error(f"Input path does not exist: {target}")
        return

    # Check if the target itself is a single bag
    if (target / "bagit.txt").exists():
        process_bag(target)
    else:
        # Assume it's a parent directory containing multiple bags
        logger.info(f"Searching for bags in directory: {target}")
        bags_found = 0
        for sub_dir in target.iterdir():
            if sub_dir.is_dir() and (sub_dir / "bagit.txt").exists():
                bags_found += 1
                process_bag(sub_dir)
        
        if bags_found == 0:
            logger.warning(f"No valid BagIt bags found in {target}. Make sure bags contain a 'bagit.txt' file.")

if __name__ == "__main__":
    main()