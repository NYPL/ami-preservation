# AMI Production Scripts

This repository contains a set of Python scripts designed to streamline the handling, organization, and preparation of audio and video files for ingest into NYPL's Digital Repository. The primary goal of these scripts is to assist users in efficiently managing their multimedia files, generating accompanying JSON metadata, packaging all assets using the BagIt specification, and transferring access files to Amazon Web Services. The main functionalities of these scripts include:

1. Converting and organizing multimedia files in various formats and resolutions.
2. Preparing JSON metadata to accompany the media files.
3. Packaging assets following the BagIt specification for easy ingest into the Digital Repository.
4. Transferring access files to Amazon Web Services for storage and distribution.

These scripts aim to automate and simplify the management of multimedia files, ensuring a seamless integration with NYPL's Digital Repository system. For detailed instructions, dependencies, and examples of usage, please refer to the README.md file.

#### audio_processing.py

This script automates the process of transcoding WAV files to FLAC, organizing the files into appropriate directories, updating metadata in JSON files, and creating BagIt bags.

```python3 audio_processing.py -s /path/to/source_directory -d /path/to/destination_directory```

The script performs the following steps:

1. Transcodes WAV files to FLAC format with the highest compression level, preserving the modification time and verifying the output.
2. Organizes the transcoded FLAC files and JSON files into separate directories for Preservation Masters (PM) and Edit Masters (EM).
3. Updates the JSON files with the new technical metadata of the transcoded FLAC files.
4. Creates BagIt bags for each asset (identified by the ID folder).
5. Checks if all FLAC files have corresponding JSON files and if all PM and EM file pairs match.

Please note that this script requires Python 3.6 or higher.

#### clean_cms_export.py

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