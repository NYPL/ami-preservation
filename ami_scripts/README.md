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

This script automates the process of cleaning up an Excel file containing NYPL CMS/SPEC (inventory system) metadata for import into AMIDB (our working production database). It performs character replacement, format fixes, and additional cleanup steps according to a provided configuration file (config.json).

```python3 clean_cms_export.py -s /path/to/source_excel.xlsx -w WORKORDER_ID -d /path/to/destination_directory -c /path/to/config.json```

This script performs the following steps:

1. Parse command-line arguments and read the configuration file.
2. Load the input data file (Excel) into a structured data format (DataFrame).
3. Perform data cleanup and transformations based on the configuration:
* Replace characters in specified columns.
*  Apply format fixes to map specific values to target values.
*  Apply custom cleanup steps for specific data types or conditions.
4. Add any additional information to the dataset (e.g., work order ID).
5. Save the cleaned and transformed dataset as a new output data file (Excel) in the specified directory or the original file's directory.

### cp2s3.py

This script copies specific files (Service Copy Videos and Edit Master Audio) from a given directory of BagIt bags to an AWS S3 bucket.

```python3 cp2s3.py -d /path/to/directory/of/bags```

This script performs the following steps:

1. Parsing command-line arguments, specifically the path to the directory of bags.
2. Lists all the directories in the given directory, filtering out hidden or system directories.
3. For each directory (BagIt bag), the script walks through its contents and generates a list of files that have specific extensions (.sc.mp4, .sc.json, .em.wav, .em.flac, .em.json).
4. Copies each file in the list to the AWS S3 bucket using the aws s3 cp command.
5. The process is repeated for each BagIt bag in the directory.

* AWS CLI must be installed and configured with appropriate credentials.

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

### video_processing.py

This script processes video files in a specified directory by converting and organizing them into different formats and categories.

```python3 video_processing.py -d /path/to/input/directory [-t]```

This script performs the following steps:

1. Rename files in the input directory, removing "_ffv1" from their names.
2. Convert .mkv and .dv files to .mp4 format.
3. Process .mov files by converting them to FFV1 (.mkv) and H.264 (.mp4) formats.
4. Generate .framemd5 files for .mkv files.
5. Transcribe the audio of .mkv files to VTT format using the Whisper tool (optional).
6. Create directories: PreservationMasters, ServiceCopies, V210, and AuxiliaryFiles.
7. Move processed files (.mp4, .mov, .mkv, .framemd5, .vtt) to their respective directories.
8. Move .log files to the AuxiliaryFiles directory and .xml.gz files to the PreservationMasters directory.
9. Delete empty directories: AuxiliaryFiles and V210.

* Whisper tool must be installed and available in your system's PATH (optional)