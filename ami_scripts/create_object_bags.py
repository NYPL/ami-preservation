#!/usr/bin/env python3

import argparse
from pathlib import Path
import bagit
import re
import shutil
import logging

# --- Constants ---

# Maps file role suffixes to their target directory names
ROLE_MAP = {
    '_pm': 'PreservationMasters',
    '_em': 'EditMasters',
    '_mz': 'Mezzanines',
    '_sc': 'ServiceCopies',
}

# Set of file extensions to be treated as 'data' and sorted into role directories
DATA_EXTENSIONS = {
    '.mkv', '.json', '.mp4', '.dv', '.flac', 
    '.iso', '.cue', '.mov', '.jpg', '.tif', 
    '.aea', '.csv'
}

# Pre-compiled regex patterns
CMS_ID_RE = re.compile(r'_(\d{6})_')
ROLE_RE = re.compile(r'(_pm|_em|_mz|_sc)', re.IGNORECASE)

# --- End Constants ---


def setup_logging():
    """Configure basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Move files into object dirs and bag')
    parser.add_argument('-s', '--source',
                        help='path to the source directory files', required=True)
    args = parser.parse_args()
    return args


def get_files(source_directory: Path) -> list[Path]:
    """
    Recursively find all non-hidden files in the source directory.

    Args:
        source_directory: The Path object for the source directory.

    Returns:
        A list of Path objects, relative to the source directory.
    """
    file_paths = []
    logging.info(f'Scanning for files in: {source_directory}')
    for path in source_directory.glob('**/*'):
        if path.is_file():
            if not path.name.startswith('.') and not path.name.startswith('._'):
                file_paths.append(path.relative_to(source_directory))
    logging.info(f'Found {len(file_paths)} files to process.')
    return file_paths


def make_object_dirs(source_directory: Path, file_list: list[Path]) -> tuple[set[str], list[Path], list[Path], int]:
    """
    Sorts files into CMS ID and role-based directories.

    Returns:
        A tuple containing:
        - A set of all CMS IDs found.
        - A list of relative paths for files that were not moved.
        - A list of absolute paths for files identified as tags.
        - An integer count of data files successfully moved.
    """
    cms_ids = set()
    unmoved = []
    tags = []
    data_files_moved_count = 0

    for file_path in file_list:
        try:
            cms_id = CMS_ID_RE.search(str(file_path)).group(1)
            cms_ids.add(cms_id)
        except AttributeError:
            logging.warning(f'Unrecognized file (no CMS ID): {file_path}')
            unmoved.append(file_path)
            continue

        old_file_path = source_directory / file_path
        
        if old_file_path.suffix.lower() in DATA_EXTENSIONS:
            role_match = ROLE_RE.search(file_path.name)
            
            if role_match:
                role_key = role_match.group(1).lower()
                role_directory = ROLE_MAP.get(role_key)
                
                new_file_path = source_directory / cms_id / role_directory / file_path.name
                new_file_path.parent.mkdir(parents=True, exist_ok=True)

                if new_file_path.exists():
                    logging.error(f'File collision detected! Not moving: {old_file_path}')
                    logging.error(f'File already exists at: {new_file_path}')
                    unmoved.append(file_path)
                else:
                    shutil.move(str(old_file_path), str(new_file_path))
                    logging.info(f'Moved: {file_path.name} -> {cms_id}/{role_directory}')
                    data_files_moved_count += 1
            else:
                logging.warning(f'Data file has no role, skipping: {file_path}')
                unmoved.append(file_path)
                
        else:
            logging.debug(f'Identified as tag file: {old_file_path}')
            tags.append(old_file_path)

    return cms_ids, unmoved, tags, data_files_moved_count


def make_object_bags(source_directory: Path, cms_objects: set[str]) -> tuple[int, int]:
    """
    Creates BagIt bags for each CMS ID directory.

    Returns:
        A tuple of (success_count, failure_count).
    """
    success_count = 0
    failure_count = 0
    
    for cms_id in cms_objects:
        bag_path = source_directory / cms_id
        logging.info(f'Starting bagging for: {cms_id}')
        try:
            bagit.make_bag(str(bag_path), checksums=['md5'])
            logging.info(f'Finished bagging object: {cms_id}')
            success_count += 1
        except bagit.BagError as e:
            logging.error(f'Failed to create bag for {cms_id}: {e}')
            failure_count += 1
        except Exception as e:
            logging.error(f'An unexpected error occurred while bagging {cms_id}: {e}')
            failure_count += 1
            
    return success_count, failure_count


def move_tag_files(source_directory: Path, tags: list[Path]) -> int:
    """
    Moves identified tag files into the 'tags' directory of their
    corresponding object bag and updates the bag manifests.

    Returns:
        An integer count of tag files successfully moved.
    """
    moved_count = 0
    
    for tag_file in tags:
        logging.debug(f'Processing tag file: {tag_file}')
        try:
            cms_id = CMS_ID_RE.search(str(tag_file.name)).group(1)
        except AttributeError:
            logging.warning(f'Could not find CMS ID for tag file: {tag_file}')
            continue
            
        object_bag = source_directory / cms_id

        if not object_bag.exists() or not (object_bag / 'bagit.txt').exists():
            logging.warning(f'No bag found for object {cms_id} (tag file: {tag_file})')
            continue

        tag_dir = object_bag / 'tags'
        tag_dir.mkdir(exist_ok=True)
        
        new_tag_path = tag_dir / tag_file.name
        
        if new_tag_path.exists():
            logging.error(f'Tag file collision! Not moving: {tag_file}')
            logging.error(f'File already exists at: {new_tag_path}')
        else:
            shutil.move(str(tag_file), str(new_tag_path))
            try:
                bag = bagit.Bag(str(object_bag))
                bag.save(manifests=True)
                logging.info(f'Moved tag file {tag_file.name} to {tag_dir} and updated bag.')
                moved_count += 1
            except Exception as e:
                logging.error(f'Failed to update bag {cms_id} after moving tag file: {e}')
                
    return moved_count


def clean_up(source_directory: Path) -> int:
    """
    Deletes any empty subdirectories left in the source directory.

    Returns:
        An integer count of deleted directories.
    """
    deleted_count = 0
    logging.info('Starting cleanup of empty directories...')
    
    for directory in sorted(source_directory.glob('**/*'), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            try:
                logging.info(f'Deleting empty directory: {directory}')
                directory.rmdir()
                deleted_count += 1
            except OSError as e:
                logging.warning(f'Could not delete {directory}: {e}')
                
    return deleted_count


def main():
    """Main execution function."""
    setup_logging()
    arguments = get_args()
    
    try:
        source_directory = Path(arguments.source)
        if not source_directory.is_dir():
            logging.critical(f'Source directory not found: {source_directory}')
            return

        file_list = get_files(source_directory)
        
        if not file_list:
            logging.info('No files found to process. Exiting.')
            return
            
        # --- Capture return values ---
        cms_objects, unmoved, tags, data_files_moved = make_object_dirs(source_directory, file_list)
        bags_created, bags_failed = make_object_bags(source_directory, cms_objects)
        tags_moved = move_tag_files(source_directory, tags)
        clean_up(source_directory) # Runs but is not reported in summary
        
        # --- Calculate final stats ---
        tags_identified = len(tags)
        tags_not_moved = tags_identified - tags_moved
        files_not_moved_count = len(unmoved)

        # --- Display PARED DOWN Summary Report ---
        logging.info("--- 📊 Summary Report ---")
        logging.info(f"Bags created successfully:  {bags_created}")
        logging.info(f"Bags failed to create:      {bags_failed}")
        
        # --- Still log warnings if there were other issues ---
        if files_not_moved_count > 0 or tags_not_moved > 0:
            logging.warning("--- ⚠️ Other Issues Detected ---")
            if files_not_moved_count > 0:
                logging.warning(f"Data files not moved:       {files_not_moved_count}")
                logging.warning("Unmoved data/role files:")
                for f in unmoved:
                    logging.warning(f"  - {f}")
            if tags_not_moved > 0:
                logging.warning(f"Tag files not moved:        {tags_not_moved}")
            logging.warning("Review log above for details on collisions or errors.")

        elif bags_created > 0 and bags_failed == 0:
             logging.info("--- ✅ All operations successful. ---")

    except Exception as e:
        logging.critical(f'An unhandled error occurred: {e}', exc_info=True)


if __name__ == '__main__':
    main()