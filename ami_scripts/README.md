# AMI Production Scripts

This repository contains a set of Python scripts designed to streamline the handling, organization, and preparation of audio and video files for ingest into NYPL's Digital Repository. The primary goal of these scripts is to assist users in efficiently managing their multimedia files, generating accompanying JSON metadata, packaging all assets using the BagIt specification, and transferring access files to Amazon Web Services. The main functionalities of these scripts include:

1. Converting and organizing multimedia files in various formats and resolutions.
2. Preparing JSON metadata to accompany the media files.
3. Packaging assets following the BagIt specification for easy ingest into the Digital Repository.
4. Transferring access files to Amazon Web Services for storage and distribution.

These scripts aim to automate and simplify the management of multimedia files, ensuring a seamless integration with NYPL's Digital Repository system. For detailed instructions, dependencies, and examples of usage, please refer to the README.md file.

### audio_processing.py

This script automates the process of transcoding WAV files to FLAC, organizing the files into appropriate directories, updating metadata in JSON files, and creating BagIt bags.

```python3 audio_processing.py -s /path/to/source_directory -d /path/to/destination_directory```

The script performs the following steps:

1. Transcodes WAV files to FLAC format with the highest compression level, preserving the modification time and verifying the output.
2. Organizes the transcoded FLAC files and JSON files into separate directories for Preservation Masters (PM) and Edit Masters (EM).
3. Updates the JSON files with the new technical metadata of the transcoded FLAC files.
4. Creates BagIt bags for each asset (identified by the ID folder).
5. Checks if all FLAC files have corresponding JSON files and if all PM and EM file pairs match.

Please note that this script requires Python 3.6 or higher.

### clean_cms_export.py

This script automates the process of cleaning up an Excel file containing NYPL CMS/SPEC (inventory system) metadata for import into AMIDB (our working production database) or a similar vendor system. It performs character replacement, format fixes, and additional cleanup steps according to a provided configuration file (config.json).

```python3 clean_cms_export.py -s /path/to/source_excel.xlsx -w WORKORDER_ID -d /path/to/destination_directory -c /path/to/config.json [-v]```

This script performs the following steps:

1. Parse command-line arguments and read the configuration file.
2. Load the input data file (Excel) into a structured data format (DataFrame).
3. Perform data cleanup and transformations based on the configuration:
* Replace characters in specified columns.
*  Apply format fixes to map specific values to target values.
*  Apply custom cleanup steps for specific data types or conditions.
4. If the --vendor flag is not specified:
* Remove 'Filename (reference)' and 'MMS Collection ID' columns if present.
* Set 'asset.fileRole' to 'pm'.
5. Add any additional information to the dataset (e.g., work order ID).
6. Save the cleaned and transformed dataset as a new output data file (Excel) in the specified directory or the original file's directory. If the --vendor flag is specified, it will use the default pandas Excel writer and skip index saving.

### copy_to_s3.py

This script copies specific files (Service Copy Videos and Edit Master Audio) from a given directory of BagIt bags to an AWS S3 bucket.

```python3 copy_to_s3.py -d /path/to/directory/of/bags```

This script performs the following steps:

1. Parsing command-line arguments, specifically the path to the directory of bags.
2. Lists all the directories in the given directory, filtering out hidden or system directories.
3. For each directory (BagIt bag), the script walks through its contents and generates a list of files that have specific extensions (.sc.mp4, .sc.json, .em.wav, .em.flac, .em.json).
4. Copies each file in the list to the AWS S3 bucket using the aws s3 cp command.
5. The process is repeated for each BagIt bag in the directory.

* AWS CLI must be installed and configured with appropriate credentials.

### create_object_bags.py

This script moves files into object directories based on their CMS IDs, creates BagIt bags for these objects, and moves tag files into the appropriate 'tags' directory within the object bags. Empty directories in the source folder will be deleted at the end of the process.

```python3 bag_object_files.py -s /path/to/source_directory```

This script performs the following steps:

1. Parse command-line arguments to get the source directory path.
2. Traverse the source directory and generate a list of files to process.
3. Create object directories based on the CMS IDs extracted from the file names.
4. Move the files into their corresponding object directories.
5. Create BagIt bags for each object directory.
6. Move the tag files into the 'tags' directory within their corresponding object bags.
7. Update the tag manifests in the object bags.
8. Clean up any empty directories within the source directory.
9. Print any files that were not moved during the process.

### filemaker_to_json_validator.py

This script converts a FileMaker merge file to JSON files and validates them against JSON schema files.

```python3 filemaker_to_json_validator.py -s /path/to/source/filemaker_merge_file.mer -d /path/to/output/json_directory -m /path/to/schema_files_directory```

Upon completion, the script will generate JSON files in the specified output directory, count the JSON files by type, and validate the JSON files against the schema files, printing the validation results.

Steps performed by the script:

1. The script reads command line arguments for the source FileMaker merge file, destination directory for JSON files, and the directory of JSON schema files.
2. The FileMaker merge file is read using pandas, and empty columns and the 'asset.fileExt' column are dropped.
3. The output directory for JSON files is created if it doesn't already exist.
4. The script iterates through each row in the DataFrame, converting the flat dictionary to a nested dictionary using the convert_dotKeyToNestedDict() function.
5. The nested dictionary is saved as a JSON file in the specified output directory.
6. After processing all rows, the script prints the total number of JSON files created from the merge file.
7. The script then counts the JSON files by type and validates them against the JSON schema files using the get_info() function. The results are printed, including the total number of valid and invalid JSON files.

### film_processing.py

This script processes media files from motion picture film digitization. It automates the conversion of DPX image sequences to MKV files using RAWcooked, converts Mezzanine files (MOV) to MP4 files, and handles full coat mag audio film files by converting WAV files to FLAC files.

```python3 film_processing.py -d /path/to/input_directory```

This script performs the following steps:

1. The script iterates through the subfolders in the specified root directory.
2. For each subfolder, it checks for the existence of 'PreservationMasters' and 'Mezzanines' folders.
3. If a 'PreservationMasters' folder contains a WAV file, the script processes it as full coat mag audio film:
* Convert the WAV file to a FLAC file using the FLAC command-line tool.
* Delete the original WAV file.
* Create an 'EditMasters' folder (if it doesn't already exist).
* Copy the FLAC file to the 'EditMasters' folder and update the name from '_pm' to '_em'.
4. If both 'PreservationMasters' and 'Mezzanines' folders exist, the script processes the folder as a film with image and audio:
* Convert the DPX image sequence in the 'PreservationMasters' folder to an MKV file using RAWcooked.
* If the conversion is successful, move the MKV file to the 'PreservationMasters' folder and delete the DPX files.
* Create a 'ServiceCopies' folder (if it doesn't already exist).
* Convert the MOV file in the 'Mezzanines' folder to an MP4 file using FFmpeg and save it in the 'ServiceCopies' folder.
5. If an error occurs or required folders are missing, the script will print an error message describing the issue.

Note: Make sure you have RAWcooked, FFmpeg, and the FLAC command-line tool installed on your system and available in your PATH before running the script.

### json_updater.py

This script allows you to update JSON files within a specified directory. It has the ability to update media information using MediaInfo and change specific key values within the JSON files.

```python3 json_updater_new.py -s <source_directory> [-m] [-k <key_to_update>]```

This script performs the following steps:

1. Parse command-line arguments using argparse.
2. Validate and process the provided source directory path.
3. If the -m flag is provided, the script will:
* a. Get a list of media files and JSON files within the source directory.
* b. Run MediaInfo on each media file and extract relevant information.
* c. Update the corresponding JSON files with the extracted media information.
4. If the -k flag is provided along with a specific key, the script will:
* a. Get a list of JSON files within the source directory.
* b. For each JSON file, search for the specified key and retrieve its current value(s).
* c. If there's only one occurrence of the key within the JSON file, update the value without user input.
* d. If there are multiple occurrences of the key, prompt the user to choose the value they want to update and provide a new value.
* e. Update the selected JSON files with the new value.
5. Log the results of the process, including any warnings or errors encountered.


### mediainfo_extractor.py

This script extracts MediaInfo from a collection of video or audio files in a specified directory or a single file and saves the extracted data to a CSV file.

```python3 mediainfo_extractor.py [-d /path/to/media/directory] [-f /path/to/media/file] -o /path/to/output/csv```

Use the -d flag followed by the path to the directory containing the media files or the -f flag followed by the path to a single media file. The -o flag followed by the path to the output CSV file is required.

This script performs the following steps:

1. Parse the input arguments to obtain the directory, file, and output paths.
2. Determine the media files to examine based on the input directory or file.
3. For each media file, retrieve its MediaInfo using the pymediainfo library.
4. Extract the relevant track information from the MediaInfo.
5. Append the extracted information to a list of file data.
6. Write the file data to the output CSV file, including headers for each field.

The script processes video files with the following extensions: .mkv, .mov, .mp4, .dv, .iso and audio files with the following extensions: .wav, .flac.

* The pymediainfo library must be installed (install via pip install pymediainfo)

### rsync_validator.py

This script is designed to safely copy files from one directory to another using the rsync utility while performing various checks to ensure the integrity of the copied files. 

```python3 rsync_validator.py -s SOURCE_DIR -d DESTINATION_DIR [-c]```

This script performs the following steps:

1. A temporary subdirectory named temp_rsync is created within the destination directory to store the copied files during validation.
2. The source directory is copied to the temporary subdirectory using the rsync command with -rtv flags for recursive copying and showing progress.
3. The diff command is used to compare the contents of the source directory and the copied source directory in the temporary destination. If no differences are found, the script proceeds to the next step; otherwise, it prints the differences.
4. The script compares the sizes of the source and temporary destination directories. If they are the same, it proceeds to the next step; otherwise, it prints the size difference.
5. The script compares the number of files in the source and temporary destination directories. If the numbers are the same, it proceeds to the next step; otherwise, it prints the difference in file count.
6. If the checksum flag is enabled, the script compares the MD5 checksums of the files in the source and temporary destination directories. If all checksums match, it proceeds to the next step; otherwise, it prints a message indicating that some files have different checksums.
7. If all validations have passed, the script moves the files from the temporary subdirectory to the actual destination directory and removes the temporary subdirectory. If any validation fails, the script prints a message, and the files are not moved to the destination directory.

### unbag_objects.py

This script undoes object-level packaging and bagging by moving files to their respective subfolders (PreservationMasters, ServiceCopies, and EditMasters) and cleaning up empty directories.

```python3 unbag_objects.py -d /path/to/object/bags```

This script performs the following steps:

1. Parse command-line arguments to get the source directory containing the object bags.
2. Ensure that the provided source directory is valid and accessible.
3. Create the required subfolders (PreservationMasters, ServiceCopies, and EditMasters) in the source directory, if they do not already exist.
4. Iterate through the files in the source directory and its subdirectories.
5. Based on each file's extension, move the file to the appropriate subfolder (PreservationMasters, ServiceCopies, or EditMasters).
6. Iterate through the directories in the source directory to find any empty directories.
7. If an empty directory is found, delete it.


### video_processing.py

This script processes video and audio files in a specified directory. It converts .mkv and .dv files to .mp4, processes .mov files, generates .framemd5 files, renames files, moves files into appropriate subdirectories, transcribes audio to VTT format using the Whisper tool (optional), and extracts MediaInfo to save it in a CSV file (optional).

```python3 video_processing.py -d DIRECTORY [-t] [-o OUTPUT]```

This script performs the following steps:

1. Parse command-line arguments:
* Input directory containing video and audio files (-d or --directory)
* Flag to transcribe audio using the Whisper tool (-t or --transcribe, optional)
* Path to save extracted MediaInfo as CSV (-o or --output, optional)
2. Check if the input directory is valid. If not, exit with an error message.
3. Create subdirectories within the input directory: "AuxiliaryFiles", "V210", "PreservationMasters", and "ServiceCopies".
4. Convert .mkv and .dv files to .mp4 format.
5. Process .mov files by converting them to both FFV1 .mkv format and H.264 .mp4 format.
6. Generate .framemd5 files for .mkv files.
7. Rename files by removing the "_ffv1" substring from their names, if present.
8. Move files to their respective subdirectories based on their file extensions.
9. Move log files (.log) to the "AuxiliaryFiles" subdirectory and MediaInfo XML files (.xml.gz) to the "PreservationMasters" subdirectory.
10. If the -t flag is provided, transcribe the audio of .mkv files to VTT format using the Whisper tool.
11. Delete empty subdirectories among "AuxiliaryFiles", "V210", "PreservationMasters", and "ServiceCopies".
12. If the -o flag is provided, extract MediaInfo for each file in the input directory and save the extracted information in a CSV file at the specified output path.

* Whisper tool must be installed and available in your system's PATH (optional)