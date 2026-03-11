#!/usr/bin/env python3

import argparse
from pathlib import Path
import bagit
import re
import shutil
import logging
import json

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
    '.aea', '.csv', '.wav', '.mka', '.tar'
}

# Pre-compiled regex patterns
AMI_ID_RE = re.compile(r'_(\d{6})_')
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
    # CHANGED: -s/--source to -d/--directory
    parser.add_argument('-d', '--directory',
                        help='path to the directory of object files', required=True)
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


def classify_ami_ids(source_directory: Path, file_list: list[Path]) -> dict[str, str]:
    """
    Classifies each AMI ID into a media type (video, film, audio, data) 
    based on JSON metadata or file extensions/roles.
    """
    media_mapping = {}
    ami_files = {}

    for file_path in file_list:
        try:
            ami_id = AMI_ID_RE.search(str(file_path)).group(1)
            if ami_id not in ami_files:
                ami_files[ami_id] = []
            ami_files[ami_id].append(file_path)
        except AttributeError:
            continue

    for ami_id, files in ami_files.items():
        media_type = None
        
        # 1. Try to find and parse JSON
        json_files = [f for f in files if f.suffix.lower() == '.json']
        for jf in json_files:
            json_path = source_directory / jf
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Try to extract source.object.type
                obj_type = data.get('source', {}).get('object', {}).get('type', '')
                if isinstance(obj_type, list) and len(obj_type) > 0:
                    obj_type = obj_type[0]
                obj_type = str(obj_type).lower()
                
                if 'video' in obj_type: media_type = 'Video'
                elif 'film' in obj_type: media_type = 'Film'
                elif 'audio' in obj_type: media_type = 'Audio'
                elif 'data' in obj_type: media_type = 'Data'
                else:
                    # Fallback to searching the whole json file string
                    content = json_path.read_text(encoding='utf-8').lower()
                    if re.search(r'\bvideo\b', content): media_type = 'Video'
                    elif re.search(r'\bfilm\b', content): media_type = 'Film'
                    elif re.search(r'\baudio\b', content): media_type = 'Audio'
                    elif re.search(r'\bdata\b', content): media_type = 'Data'
            except Exception as e:
                logging.warning(f"Error reading JSON for {ami_id}: {e}")
                # Fallback to pure string search if JSON parsing failed entirely
                try:
                    content = json_path.read_text(encoding='utf-8').lower()
                    if re.search(r'\bvideo\b', content): media_type = 'Video'
                    elif re.search(r'\bfilm\b', content): media_type = 'Film'
                    elif re.search(r'\baudio\b', content): media_type = 'Audio'
                    elif re.search(r'\bdata\b', content): media_type = 'Data'
                except Exception as e2:
                    logging.warning(f"Could not read content of {json_path}: {e2}")

            if media_type:
                break

        # 2. Fallback to file extensions/roles derived from ami_bag_constants
        if not media_type:
            extensions = {f.suffix.lower() for f in files}
            roles = {ROLE_RE.search(f.name).group(1).lower() for f in files if ROLE_RE.search(f.name)}
            
            if '_em' in roles or '.wav' in extensions or '.flac' in extensions or '.aea' in extensions:
                media_type = 'Audio'
            elif '_mz' in roles or '.mov' in extensions:
                media_type = 'Film'
            elif '.mkv' in extensions or '.dv' in extensions or '.mp4' in extensions:
                media_type = 'Video'
            elif '.iso' in extensions or '.tar' in extensions:
                media_type = 'Data'

        logging.info(f"Classified AMI ID {ami_id} as {media_type or 'Unknown'}")
        media_mapping[ami_id] = media_type or 'Unknown'

    return media_mapping


def make_object_dirs(source_directory: Path, file_list: list[Path], media_mapping: dict[str, str]) -> tuple[set[str], list[Path], list[Path], int]:
    """
    Sorts files into AMI ID and role-based directories under their media type.

    Returns:
        A tuple containing:
        - A set of all AMI IDs found.
        - A list of relative paths for files that were not moved.
        - A list of absolute paths for files identified as tags.
        - An integer count of data files successfully moved.
    """
    ami_ids = set()
    unmoved = []
    tags = []
    data_files_moved_count = 0

    for file_path in file_list:
        try:
            ami_id = AMI_ID_RE.search(str(file_path)).group(1)
            ami_ids.add(ami_id)
        except AttributeError:
            logging.warning(f'Unrecognized file (no AMI ID): {file_path}')
            unmoved.append(file_path)
            continue

        old_file_path = source_directory / file_path
        media_type = media_mapping.get(ami_id, 'Unknown')
        
        if old_file_path.suffix.lower() in DATA_EXTENSIONS:
            role_match = ROLE_RE.search(file_path.name)
            
            if role_match:
                role_key = role_match.group(1).lower()
                role_directory = ROLE_MAP.get(role_key)
                
                new_file_path = source_directory / media_type / ami_id / role_directory / file_path.name
                new_file_path.parent.mkdir(parents=True, exist_ok=True)

                if new_file_path.exists():
                    if old_file_path.resolve() == new_file_path.resolve():
                        pass # already correctly placed
                    else:
                        logging.error(f'File collision detected! Not moving: {old_file_path}')
                        logging.error(f'File already exists at: {new_file_path}')
                        unmoved.append(file_path)
                else:
                    shutil.move(str(old_file_path), str(new_file_path))
                    logging.info(f'Moved: {file_path.name} -> {media_type}/{ami_id}/{role_directory}')
                    data_files_moved_count += 1
            else:
                logging.warning(f'Data file has no role, skipping: {file_path}')
                unmoved.append(file_path)
                
        else:
            logging.debug(f'Identified as tag file: {old_file_path}')
            tags.append(old_file_path)

    return ami_ids, unmoved, tags, data_files_moved_count


def make_object_bags(source_directory: Path, ami_objects: set[str], media_mapping: dict[str, str]) -> tuple[int, int]:
    """
    Creates BagIt bags for each AMI ID directory inside the media type directory.

    Returns:
        A tuple of (success_count, failure_count).
    """
    success_count = 0
    failure_count = 0
    
    for ami_id in ami_objects:
        media_type = media_mapping.get(ami_id, 'Unknown')
        bag_path = source_directory / media_type / ami_id
        logging.info(f'Starting bagging for: {ami_id} in {media_type}')
        try:
            bagit.make_bag(str(bag_path), checksums=['md5'])
            logging.info(f'Finished bagging object: {ami_id}')
            success_count += 1
        except bagit.BagError as e:
            logging.error(f'Failed to create bag for {ami_id}: {e}')
            failure_count += 1
        except Exception as e:
            logging.error(f'An unexpected error occurred while bagging {ami_id}: {e}')
            failure_count += 1
            
    return success_count, failure_count


def move_tag_files(source_directory: Path, tags: list[Path], media_mapping: dict[str, str]) -> int:
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
            ami_id = AMI_ID_RE.search(str(tag_file.name)).group(1)
        except AttributeError:
            logging.warning(f'Could not find AMI ID for tag file: {tag_file}')
            continue
            
        media_type = media_mapping.get(ami_id, 'Unknown')
        object_bag = source_directory / media_type / ami_id

        if not object_bag.exists() or not (object_bag / 'bagit.txt').exists():
            logging.warning(f'No bag found for object {ami_id} (tag file: {tag_file})')
            continue

        tag_dir = object_bag / 'tags'
        tag_dir.mkdir(exist_ok=True)
        
        new_tag_path = tag_dir / tag_file.name
        
        if new_tag_path.exists():
            if tag_file.resolve() == new_tag_path.resolve():
                pass # Already correctly placed
            else:
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
                logging.error(f'Failed to update bag {ami_id} after moving tag file: {e}')
                
    return moved_count


def clean_up(source_directory: Path) -> int:
    """
    Deletes any empty subdirectories left in the source directory.

    Returns:
        An integer count of deleted directories.
    """
    deleted_count = 0
    logging.info('Starting cleanup of empty directories...')
    
    # CHANGED: Reverted to rglob and sorting by len(parts) for a true bottom-up traversal
    for directory in sorted(source_directory.rglob('*'), key=lambda p: len(p.parts), reverse=True):
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
        # CHANGED: arguments.source to arguments.directory
        source_directory = Path(arguments.directory)
        if not source_directory.is_dir():
            logging.critical(f'Source directory not found: {source_directory}')
            return

        file_list = get_files(source_directory)
        
        if not file_list:
            logging.info('No files found to process. Exiting.')
            return
            
        media_mapping = classify_ami_ids(source_directory, file_list)
        
        # --- Capture return values ---
        ami_objects, unmoved, tags, data_files_moved = make_object_dirs(source_directory, file_list, media_mapping)
        bags_created, bags_failed = make_object_bags(source_directory, ami_objects, media_mapping)
        tags_moved = move_tag_files(source_directory, tags, media_mapping)
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