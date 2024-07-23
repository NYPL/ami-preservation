
# AMI Production Scripts

- [AMI Production Scripts](#ami-production-scripts)
    - [Overview](#overview)
    - [ami\_file\_sync.py](#ami_file_syncpy)
    - [ami\_record\_exporter\_and\_analyzer.py](#ami_record_exporter_and_analyzerpy)
    - [audio\_processing.py](#audio_processingpy)
    - [clean\_spec\_csv\_to\_excel.py](#clean_spec_csv_to_excelpy)
    - [copy\_from\_s3.py](#copy_from_s3py)
    - [copy\_to\_s3.py](#copy_to_s3py)
    - [create\_media\_json.py](#create_media_jsonpy)
    - [create\_object\_bags.py](#create_object_bagspy)
    - [digitization\_performance\_tracker.py](#digitization_performance_trackerpy)
    - [filemaker\_to\_json\_validator.py](#filemaker_to_json_validatorpy)
    - [film\_processing.py](#film_processingpy)
    - [generate\_test\_media.py](#generate_test_mediapy)
    - [hflip\_film\_packages.py](#hflip_film_packagespy)
    - [iso\_transcoder.py](#iso_transcoderpy)
    - [json\_to\_csv.py](#json_to_csvpy)
    - [json\_updater.py](#json_updaterpy)
    - [json\_validator.py](#json_validatorpy)
    - [make\_anamorphic\_scs.py](#make_anamorphic_scspy)
    - [media\_metrics\_aggregator.py](#media_metrics_aggregatorpy)
    - [media\_production\_stats.py](#media_production_statspy)
    - [mediaconch\_checker.py](#mediaconch_checkerpy)
    - [mediainfo\_extractor.py](#mediainfo_extractorpy)
    - [migrated\_media\_file\_checker.py](#migrated_media_file_checkerpy)
    - [migration\_status\_reporter.py](#migration_status_reporterpy)
    - [prepend\_title\_cards.py](#prepend_title_cardspy)
    - [rawcooked\_check\_mkv.py](#rawcooked_check_mkvpy)
    - [remake\_anamorphic\_bags.py](#remake_anamorphic_bagspy)
    - [rsync\_and\_organize\_json.py](#rsync_and_organize_jsonpy)
    - [rsync\_validator.py](#rsync_validatorpy)
    - [spec\_csv\_summary\_to\_excel.py](#spec_csv_summary_to_excelpy)
    - [trello\_engineer\_notifier.py](#trello_engineer_notifierpy)
    - [trello\_list\_ids.py](#trello_list_idspy)
    - [trello\_qcqueue\_mover.py](#trello_qcqueue_moverpy)
    - [trim\_and\_transcode.py](#trim_and_transcodepy)
    - [unbag\_objects.py](#unbag_objectspy)
    - [video\_processing.py](#video_processingpy)


### Overview

This repository contains a set of Python scripts designed to streamline the handling, organization, and preparation of audio and video files for ingest into NYPL's Digital Repository. The primary goal of these scripts is to assist users in efficiently managing their multimedia files, generating accompanying JSON metadata, packaging all assets using the BagIt specification, and transferring access files to Amazon Web Services. The main functionalities of these scripts include:

1. Converting and organizing multimedia files in various formats and resolutions.
2. Preparing JSON metadata to accompany the media files.
3. Packaging assets following the BagIt specification for easy ingest into the Digital Repository.
4. Transferring access files to Amazon Web Services for storage and distribution.

These scripts aim to automate and simplify the management of multimedia files, ensuring a seamless integration with NYPL's Digital Repository system. For detailed instructions, dependencies, and examples of usage, please refer to the README.md file.


### ami_file_sync.py

This script facilitates the synchronization of files based on AMI IDs from a given CSV file. It supports two main operations: checking for the presence of AMI IDs in specified file paths and rsyncing the files to a designated destination. The script is designed to work with two CSV files: one containing SPEC AMI Export data (including AMI IDs and migration status) and another listing the file paths of interest. It filters AMI IDs marked as 'Migrated' and performs operations based on the mode selected ('check' or 'rsync').

```python3 ami_file_sync.py -s /path/to/spec_ami_export.csv -p /path/to/path_list.csv -d /path/to/destination_directory -m [check|rsync]```

The script performs the following steps:

1. Parse Command-Line Arguments: Reads the paths to the SPEC AMI Export CSV, the file paths CSV, the destination directory, and the operation mode.
2. Read AMI IDs: Extracts AMI IDs marked as 'Migrated' from the SPEC AMI Export CSV.
3. Search for AMI IDs in File Paths: Utilizes regular expressions to identify files in the provided list of paths that correspond to the AMI IDs.
4. Rsync Files (if in 'rsync' mode): For files ending with '.em.flac' or '.pm.iso', rsyncs the files to the specified destination directory, preserving timestamps and showing progress.
5. Check Mode: If in 'check' mode, the script outputs the number of found and not found AMI IDs, listing any AMI IDs that were not found in the file paths.

### ami_record_exporter_and_analyzer.py

This script extracts and exports details and summary information about AMI IDs from a FileMaker database, using input data provided in CSV or Excel format. It generates two primary outputs: a detailed list of AMI IDs with associated data and a summarized view of box information with a breakdown of formats.

```python3 ami_record_exporter_and_analyzer.py -u USERNAME -p PASSWORD -i /path/to/input_file -o /path/to/output.xlsx```

This script performs the following steps:

1. Connect to FileMaker Database: Utilizes environment variables to configure the connection to the FileMaker database. It attempts to log in using the provided credentials and prints the connection status.
2. Read AMI IDs: Depending on the file type (.csv or .xlsx), the script parses the input file to extract AMI IDs. It skips headers and checks for numeric values in the designated 'SPEC_AMI_ID' column.
3. Query Database: For each AMI ID, the script queries the FileMaker database to retrieve associated data such as barcode, migration status, item location, box name, box barcode, box location, and format type.
4. Query Sierra API: The script fetches additional item information from the Sierra API, including item locations.
5. Query SCSB API: The script retrieves item availability from the SCSB API.
6. Data Organization: Organizes retrieved data into two structures:
* AMI ID Details: Contains detailed information per AMI ID.
* Box Summary: Aggregates data by box name, counting items and categorizing them by format type.
7. Export to Excel: Outputs the organized data into an Excel file with two sheets:
* 'AMI ID Details': Detailed view for each AMI ID.
* 'Box Summary': Summarized box information and format breakdown, presented in two sections within the same sheet.

The script requires the following environment variables to be set:

* FM_SERVER: URL of the FileMaker server.
* FM_DATABASE: Name of the FileMaker database.
* FM_LAYOUT: Database layout to be used for queries.
* OAUTH_CLIENT_ID: Client ID for OAuth authentication.
* OAUTH_CLIENT_SECRET: Client secret for OAuth authentication.
* OAUTH_SERVER: URL of the OAuth server.
* SCSB_API_KEY: API key for accessing the SCSB API.
* SCSB_API_URL: URL of the SCSB API endpoint.

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


### clean_spec_csv_to_excel.py

This script prepares and cleans a SPEC CSV file for import into AMIDB by performing various data transformation and cleanup operations. It allows for adding work order and project code to the new Excel file, offers a vendor mode for specific processing, and can optionally interact with Trello for project management purposes.

```python3 clean_cms_export.py -s /path/to/source_excel.xlsx -w WORKORDER_ID -d /path/to/destination_directory -c /path/to/config.json [-v]```

This script performs the following steps:

1. Parse Command-Line Arguments: Collects paths to the source CSV, the destination directory, the config file, and flags for vendor mode and Trello interaction.
2. Detect File Encoding: Automatically detects and uses the correct encoding for reading the source CSV.
3. Read and Clean Data: Loads the source CSV into a DataFrame, applying transformations based on a configuration file and additional parameters (work order ID, project code).
4. Trello Card Creation (Optional): If enabled, creates a Trello card for each unique Archival Box Barcode or a single card for the batch, requiring TRELLO_API_KEY and TRELLO_TOKEN environment variables.
5. Data Transformation: Maps CSV columns to their corresponding Excel columns, replaces characters, applies format fixes, and adds project-specific information.
6. Output: Saves the cleaned and transformed dataset as a new Excel file in the specified directory, with special handling if the vendor mode is activated.

Key Features:

* Vendor Mode: Skips certain cleanup steps and uses the default pandas Excel writer, useful for preparing data for vendors.
* Trello Integration: Automates the creation of Trello cards for project management, supporting both individual and batch processing modes.
* Configurable Transformations: Uses an external configuration file (config.json) for flexible data cleanup rules.


### copy_from_s3.py

This script is designed for managing file operations with an AWS S3 bucket, specifically focusing on copying files to a local destination or initiating a Glacier restore process for them. It uses a CSV file containing specific numbers to identify and filter files by extension within an AWS S3 bucket for either copying or restoration.

```python3 copy_from_s3.py -n /path/to/numbers.csv -i /path/to/input.csv -d /path/to/destination -b S3_BUCKET_NAME -e FILE_EXTENSION -m [copy|restore]```

This script performs the following steps:

1. Argument Parsing: It starts by collecting the CSV file with numbers, the input CSV file to search within, the local destination path, the AWS S3 bucket name, the file extension to filter by, and the operation mode.
2. ID Extraction: Identifies files by extracting a specific pattern (six consecutive digits) from filenames listed in the input CSV file.
3. File Filtering: Filters files based on the specified extension and numbers provided, identifying which files need to be copied or restored.
Copying or Restoring Files:
4. In copy mode, the script copies the filtered files from the S3 bucket to the specified local destination.
In restore mode, it initiates a Glacier restore process for each filtered file, setting the restoration period for 5 days.
5. Reporting: Provides feedback on the process, including the number of files processed and any numbers from the CSV file not found in the input CSV.

Key Features:

* Dual Mode Operation: Offers flexibility with a copy mode for immediate file copying and a restore mode for Glacier restore requests.
* Efficient File Filtering: Employs regular expressions for precise identification and filtering of files based on the provided CSV of numbers and desired file extension.
* Feedback and Error Handling: Outputs helpful information throughout the process, including missing numbers and errors encountered during file operations.


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


### create_media_json.py

This script automates the creation of NYPL JSON files by fetching metadata from a FileMaker database and analyzing a user-supplied directory of media files. It aims to streamline the metadata generation process, ensuring that media files are accurately described and ready for integration into NYPL's digital repository.

```python3 create_media_json.py -u <username> -p <password> -m /path/to/media_files -c /path/to/config.json -o /path/to/output_json_files [-d [Media Preserve|NYPL|Memnon]]```

This script performs the following steps:

1. Configuration and Input Parsing: The script starts by parsing command-line arguments to determine the media directory, FileMaker credentials, digitizer information, and output location for the JSON files.
2. FileMaker Database Connection: Establishes a connection to the specified FileMaker database to fetch bibliographic metadata associated with each media file based on its unique identifier.
3. Media File Analysis: Scans the specified directory for media files (filtering by supported extensions such as .mov, .wav, etc.), extracting relevant metadata using the mediainfo tool.
4. JSON File Creation: For each media file, generates a comprehensive JSON file containing both bibliographic and technical metadata. The JSON structure is tailored to NYPL's specifications, incorporating data from both the FileMaker database and media file analysis.


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


### digitization_performance_tracker.py

This script generates production statistics and visualizations from the AMIDB. It fetches data, processes it, and creates various plots to summarize the digitization performance, compiling all results into a comprehensive PDF report.

```python3 digitization_performance_tracker.py -s <source_directory> [-f] [-e <engineer_names>] [-H]```

Options:

* -f, --fiscal: Optional. Organize statistics and visualizations by fiscal year instead of the default calendar year.
* -e, --engineer: Optional. Filter the output to include only specific engineers. This should be followed by one or more last names.
* -H, --historical: Optional. Analyze data from all available years instead of just the current year.
* -p, --previous-fiscal: Optional. Analyze data from the previous fiscal year.

This script performs the following steps:

1. Command-Line Argument Parsing: The script uses argparse to handle command-line options. Each option adjusts the scope and output of the data processing.
2. Database Connection and Data Fetching:
* Establishes a JDBC connection to the AMIDB using credentials stored in environment variables.
* Executes a SQL query to fetch relevant digitization data, including details like the primary ID, file format, file size, and engineer details.
3. Data Processing:
* Converts date strings to datetime objects for better manipulation.
* Filters data based on user input for specific engineers and/or date ranges (fiscal/calendar year).
* Prepares the data for visualization by aggregating unique digitization entries per month and engineer.
4. Data Visualization:
* Generates line plots to display monthly output by each specified engineer, using Seaborn and Matplotlib for plotting.
* Optionally adjusts the display settings for historical data to ensure clarity and readability.
5. PDF Report Generation:
* Compiles all visualizations and summaries into a single PDF report.
* Dynamically adjusts plot sizes and layout based on the amount of historical data.
* Includes detailed annotations and formatting to enhance report utility.
6. Error Handling and Logging:
* Provides feedback on the success of data fetching and connection issues.
* Logs and displays errors related to data processing or file generation.

### filemaker_to_json_validator.py

This script converts a FileMaker merge file to JSON files and validates them against JSON schema files.

```python3 filemaker_to_json_validator.py -s /path/to/source/filemaker_merge_file.mer -d /path/to/output/json_directory -m /path/to/schema_files_directory```

Upon completion, the script will generate JSON files in the specified output directory, count the JSON files by type, and validate the JSON files against the schema files, printing the validation results.

This script performs the following steps:

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


### generate_test_media.py

This utility script is crafted to facilitate the generation of test media files in a specified directory. These test files cover a range of formats and codecs for both video and audio, allowing for comprehensive testing of media processing workflows.

```python3 generate_test_media.py -d /path/to/destination [-r ntsc|pal]```

This script performs the following steps:

1. Argument Setup: Processes command-line arguments to define the destination directory for the test media files and the video standard region (NTSC or PAL).
2. Test File Specification: Based on the specified region, the script prepares a list of test media file configurations covering various video and audio formats, resolutions, frame rates, and codecs.
3. File Generation: Iteratively generates each test file using ffmpeg and, for certain types, rawcooked for DPX sequences, placing them in the defined destination directory.
4. Logging and Progress Indication: Provides console output to inform the user of the ongoing file generation processes and any errors encountered.

Key Features:

* Wide Range of Test Files: Generates multiple types of test files, including different video codecs (e.g., v210, ffv1, dvvideo), audio codecs (e.g., pcm, flac), and resolutions.
* Customizable Video Standards: Supports the generation of video files conforming to either the NTSC or PAL standard, affecting the resolution and frame rate of the generated files.
* Advanced File Types: Produces not only standard video and audio files but also more complex types like DPX image sequences, accommodating a broad spectrum of testing needs.


### hflip_film_packages.py

This script is specifically designed for processing BagIt packages, flipping the horizontal orientation of video files and updating corresponding JSON metadata to reflect changes. It targets 'mz.mov' and 'sc.mp4' files for flipping, leaves 'pm' files untouched, and adjusts metadata in JSON files accordingly.

```python3 hflip_film_packages.py -d /path/to/BagIt_directories```

This script performs the following steps:

1. Identify BagIt Packages: Determines which directories adhere to the BagIt specification by looking for essential BagIt files.
2. Horizontal Flip Processing: Utilizes ffmpeg to horizontally flip 'mz.mov' and 'sc.mp4' files within each package, re-encoding them appropriately.
3. Metadata Update: Edits associated JSON metadata files to document the horizontal flip and update technical details like dateCreated and fileSize based on the modified media files.
4. Unbagging and Rebagging: Following modifications, the script temporarily removes BagIt structure for processing and then reapplies it, ensuring the package remains compliant with BagIt specifications.


### iso_transcoder.py

This script facilitates the transcoding of video object (VOB) files extracted from ISO images into H.264 MP4 format, ensuring compatibility and ease of access for video content. It mounts the ISO, identifies relevant VOB files, and employs FFmpeg for transcoding, with optional settings for splitting and concatenation.

```python3 iso_transcoder.py -i /path/to/input -o /path/to/output [-s] [-f]```

This script performs the following steps:

1. Pre-Check: Verifies the installation of necessary tools (mkvmerge from MKVToolNix and FFmpeg) on the system.
2. Mount ISO Image: Automatically mounts the ISO image to access the VOB files within.
3. Identify VOB Files: Scans the mounted ISO for VOB files, specifically targeting those relevant for transcoding.
4. Transcode VOB to MP4: Utilizes FFmpeg to transcode identified VOB files to the H.264 MP4 format, with options for resolution scaling and audio channel mapping as necessary.
5. Unmount ISO Image: Safely unmounts the ISO image post-processing.
6. Verification: Optionally, verifies the success of the transcoding process by checking for the expected output files.

Key Features:

* Flexible File Handling: Supports both individual ISO files and directories containing multiple ISO images.
* Splitting and Concatenation Options: Offers the ability to split each VOB file into separate MP4 files or concatenate all VOBs from an ISO into a single MP4, based on user preference.
* Resolution and Audio Channel Adjustment: Automatically adjusts the resolution of the output MP4 files and maps audio channels to ensure compatibility and quality.
* Robust Error Handling and Logging: Provides detailed logging throughout the process and implements error handling for common issues, such as mounting failures or transcoding errors.

### json_to_csv.py

This script is designed to efficiently process multiple JSON files within a specified directory, converting and consolidating them into a single CSV file. It leverages multiprocessing for enhanced performance, making it suitable for handling large volumes of data.

```python3 json_to_csv.py -s /path/to/source_directory -d /path/to/destination_file.csv```

This script performs the following steps:

1. Argument Parsing: Captures user input for the source directory of JSON files and the destination CSV file path.
2. Multiprocessing: Utilizes Python's multiprocessing capabilities to parallelize the reading and processing of JSON files, optimizing performance on multi-core systems.
JSON to DataFrame Conversion: Each JSON file is read and converted into a pandas DataFrame, with nested structures flattened for CSV compatibility.
3. Data Consolidation: All individual DataFrames are concatenated into a single DataFrame, ensuring that data from all JSON files are merged.
4. CSV Export: The consolidated DataFrame is exported to a CSV file at the specified destination, with an option to exclude the index.

### json_updater.py

This script provides functionalities to update JSON files within a specified directory, update media information using MediaInfo, change specific key values within the JSON files, and maintain checksums for BagIt compliance.

```python3 json_updater.py -s <source_directory> [-m] [-k <key_to_update>] [-c]```

Options

* -s, --source: Required. The path to the source directory containing JSON files.
* -m, --mediainfo: Optional. Update JSON files with media information extracted using MediaInfo.
* -k, --key: Optional. The dot-separated path to a specific key within the JSON files that should be updated.
* -c, --checksum: Optional. Update the checksums in the manifest file and payload oxum for BagIt compliance.
  
This script performs the following steps:

1. Parse Command-Line Arguments: The script uses argparse to handle command-line inputs.
2. Process Source Directory:
* Validate and process the provided source directory path.
* Remove unwanted files like .DS_Store and others starting with ._.
3. Media Information Update (-m flag):
* Retrieve a list of media and JSON files within the source directory.
* Use MediaInfo to extract media information from each media file.
* Update the corresponding JSON files with the extracted information, such as filename, fileSize, and videoCodec.
4. JSON Key Value Update (-k flag):
* Retrieve the list of JSON files within the source directory.
* For each JSON file, search for the specified nested key using a dot-separated path (e.g., digitizationProcess.playbackDevice.speed.unit) and retrieve its current value.
5. Checksum Update (-c flag):
* After updating JSON files or if the -c flag is used independently, the script updates the checksums in the manifest and tag manifest files.
6. Logging:
* The script logs all significant actions, warnings, or errors encountered during execution.


### json_validator.py

This script offers a robust solution for validating a directory of JSON files against predefined JSON schemas. It ensures that each JSON file adheres to the expected structure and data types specified by the schema, identifying and reporting any discrepancies.

```python3 json_validator.py -m /path/to/json_schemas -d /path/to/json_directory```

This script performs the following steps:

1. Argument Configuration: Collects command-line inputs specifying the paths to the directories containing the JSON schema files and the JSON files to be validated.
2. Directory Validation: Confirms the existence and accessibility of both the JSON and schema directories.
3. Schema Association: Dynamically matches each JSON file to the appropriate schema based on its content, particularly the type of media or format described within.
4. Validation Execution: Utilizes the ajv command-line tool for schema validation, applying the matched schema to each JSON file and outputting validation results.
5. Results Summary: Provides a concise summary of validation outcomes, including counts by type and detailed reports on any errors or issues detected in the JSON files.


### make_anamorphic_scs.py
This script processes MKV videos to create anamorphic service copies using FFmpeg. The script can handle a single MKV file or all MKV files in a specified directory, outputting the processed files in a specified directory or the same directory as the input files.

```python3 make_anamorphic_scs.py [-f <input_file>] [-d <input_directory>] [-o <output_directory>]```

This script performs the following steps:
1. Uses argparse to handle command-line options for specifying a single input file or a directory of files to process and an optional output directory.
2. Constructs the output file name based on the input file name, appending _sc.mp4 to the base name, andBuilds the FFmpeg command to process the video.


### media_metrics_aggregator.py

This script processes a CSV containing detailed metrics for media files (from AMIDB), such as duration and file size, to compute and report aggregate statistics. It groups files by their physical object origin and media format, calculates average durations and file sizes, and outputs a summary CSV with these averages.

```python3 media_metrics_aggregator.py -i /path/to/input.csv -o /path/to/output.csv```

This script performs the following steps:

1. Input and Output Configuration: Takes user-defined paths for the source CSV containing media file metrics and the destination CSV for the aggregate statistics.
2. CSV Processing: Reads the source CSV into a pandas DataFrame, ensuring that essential columns for analysis are present.
3. Data Aggregation: Groups media files by their physical object and format, computing the average duration and file size for each group.
4. Conversion and Formatting: Converts metrics like duration from milliseconds to a human-readable format and file size to both base 1024 (e.g., KiB, MiB) and base 1000 (e.g., GB) human-readable formats.
5. Output Generation: Produces a summary CSV file containing the calculated averages for duration and file size by media format, alongside their human-readable representations.


### media_production_stats.py

This script leverages Python to parse, analyze, and visualize media production statistics derived from AMIDB MER files (FileMaker CSV w/ header row). It offers insights into the volume of production, categorizing stats by fiscal or calendar year, and generates comprehensive visualizations to illustrate trends over time.

```python3 media_production_stats.py -s /path/to/MER_file.csv [-f]```

This script performs the following steps:

1. Data Parsing and Preparation: Loads the MER file into a pandas DataFrame, parsing dates and categorizing entries by either calendar or fiscal year based on the user's selection.
2. Statistical Analysis: Calculates summary statistics including the count of unique media objects, average file sizes, and total durations, organized by media type and year.
3. Visualizations: Generates a series of plots using seaborn and matplotlib, including:

* Annual digitization output trends over time.
* Monthly digitization output distribution.
* Operator-specific production volumes highlighting top contributors.
* Distribution of objects digitized by division code.

Count of the top source object formats.
4. Interactive Reporting: Presents interactive visualizations and tables directly to the user for exploration and analysis.


### mediaconch_checker.py

This script facilitates the automated validation of media files within a specified directory against a set of predefined MediaConch policies. It aims to streamline the quality control process for digital preservation efforts, ensuring that media files conform to technical standards and best practices.

```python3 mediaconch_checker.py -d /path/to/AMI_bags -p /path/to/MediaConch_policies [-ff] [-fs] [-pf] [-ps] [-rf] [-rs] [-ua] [-ud]```

This script performs the following steps:

1. Argument Parsing: Collects user-defined paths for the directory containing media files (AMI bags) and the directory where MediaConch policies are stored.
2. File Identification: Scans the specified directory for media files, excluding non-media files based on file extension criteria.
3. Policy Matching: Utilizes metadata from corresponding JSON files to classify each media file and assign an appropriate MediaConch policy for validation.
4. MediaConch Execution: Invokes MediaConch with the specified policy on each eligible media file, capturing the validation outcome.
5. Result Reporting: Outputs the validation results to the terminal, with options for detailed or summary views, and the ability to group results by type/format/role.

Key Features:

* Comprehensive Media Classification: Automatically classifies media files based on their metadata, ensuring that the correct MediaConch policy is applied.
* Flexible Output Formatting: Provides options to customize the verbosity of pass/fail results and to choose between flat or sorted result presentation.
* Error Handling: Reports issues encountered during the process, such as missing JSON metadata files or invalid metadata content, ensuring transparency in the validation process.
* U-matic PCM Exception: Offers a command-line option to treat U-matic/PCM audio as either analog or digital, based on project-specific standards.


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


### migrated_media_file_checker.py

This utility script cross-references a CSV list of media file specifications (spec) against a CSV list of actual media files to identify any discrepancies. Specifically, it checks for migrated media files that are specified as "Migrated" in the spec list but do not appear in the file list, outputting a list of missing IDs.

```python3 migrated_media_file_checker.py -f /path/to/files.csv -s /path/to/spec.csv -o /path/to/output_missing_ids.csv```

This script performs the following steps:

1. Argument Parsing: Gathers paths for the spec CSV, the file list CSV, and the output CSV file for missing IDs as input from the user.
2. SPEC CSV Processing: Reads the spec CSV to extract a list of IDs marked as 'Migrated'.
3. File List Processing: Reads the file list CSV and extracts IDs from filenames based on a predefined pattern.
4. Comparison and Analysis: Identifies IDs from the 'Migrated' list that do not appear in the file list, indicating missing files.
5. Output Generation: Writes the list of missing IDs to the specified output CSV file.


### migration_status_reporter.py
This script fetches and processes migration status issues from the AMIDB, filtering the output by specific engineers if specified, and exports the data to a CSV file.

```python3 migration_status_reporter.py [-e <engineer_names>]```

This script performs the following steps:
1. Uses argparse to handle command-line options for specifying specific engineers to filter the output.
2. Establishes a JDBC connection to the AMIDB using credentials stored in environment variables.
3. Executes a SQL query to fetch relevant data, including details like primary ID, migration exceptions, capture issue notes, issue types, and engineer details.
4. Data Cleaning and Processing:
* Cleans fields that may contain special characters or formatting issues.
* Splits and concatenates the __captureIssueCategory field to handle multiple categories properly.
* Removes duplicates and aggregates issues to ensure consistent ordering.
* Filters out records where all specified fields are effectively blank.
5. Data Export:
* Reorders the DataFrame columns to a predefined order.
* Sorts the DataFrame first by __migrationExceptions and then by issue.Type.
* Exports the cleaned and processed data to a CSV file named migration_status_<today's_date>.csv on the Desktop.


### prepend_title_cards.py

This script automates the process of prepending title cards to video or audio files. It selects title cards based on predefined criteria related to the file's content and, if specified, appends asset IDs and timecodes directly to the media file.

```python3 prepend_title_cards.py [-f FILE] [-d DIRECTORY] [-a]```

Arguments:

* -f, --file: Path to a single video or audio file.
* -d, --directory: Path to a directory containing multiple media files.
* -a, --asset: Extract and add asset ID from the filename, along with a timecode overlay to the final video.

This script performs the following steps:

1. Title Card Selection: Dynamically selects appropriate title cards based on the media file's naming conventions and grouping criteria.
2. Media Processing: Handles both video and audio files, transcoding them if necessary to ensure compatibility with title card resolutions and formats.
3. Custom Overlays: Optionally adds asset ID and timecode overlays to videos for enhanced identification and tracking.
4. Broad Compatibility: Supports a wide range of video and audio formats, including .mp4, .wav, and .flac.
5. Batch Processing: Capable of processing an entire directory of media files, streamlining operations for large collections.


### rawcooked_check_mkv.py

This script facilitates the batch verification of MKV files using RAWcooked. It is designed to randomly select a specified percentage of MKV files within a directory for processing, offering a practical approach for quality assurance over large collections.

```python3 rawcooked_check_mkv.py -d <directory> [-p <percentage>]```

This script performs the following steps:

1. RAWcooked Integration: Leverages RAWcooked to verify the integrity and compliance of MKV files.
2. Selective Processing: Randomly selects a user-defined percentage of files for checking, optimizing resource usage.
3. Batch Processing: Allows for the processing of large numbers of files with minimal manual intervention.
4. Reporting: Provides a concise report detailing the success or failure of RAWcooked checks.

### remake_anamorphic_bags.py
This script processes BagIt packages to remake anamorphic service copies, update associated metadata files, and ensure the integrity of the BagIt package by updating the manifests and checksums.

```python3 remake_anamorphic_bags.py -d <directory>```

This script performs the following steps:

1. BagIt Package Validation:
* Verifies the presence of essential BagIt files (bag-info.txt, bagit.txt, manifest-md5.txt, tagmanifest-md5.txt) in each directory to ensure it is a valid BagIt package.
2. Remake Anamorphic Service Copies:
* Processes each service copy (*_sc.mp4 files) in the ServiceCopies directory by re-transcoding them using FFmpeg with specific settings to ensure they are anamorphic.
* The original file is replaced with the newly transcoded file.
3. Update JSON Metadata:
* Updates the JSON metadata files (*_sc.json) to reflect the latest file modification date and file size.
* Uses pymediainfo to extract the necessary metadata from the newly transcoded video files.
4. Update Manifests:
* Re-calculates the MD5 checksums for the modified files and updates the manifest-md5.txt and tagmanifest-md5.txt files accordingly.
* Ensures the new checksums are accurately recorded to maintain the integrity of the BagIt package.
5. Update Payload-Oxum:
* Calculates the new Payload-Oxum (total size and file count of all files in the data directory) and updates this information in the bag-info.txt.


### rsync_and_organize_json.py

This script streamlines the synchronization and organization of JSON files. It rsyncs JSON files from a specified source directory to a target destination directory. To enhance file management, it organizes these files into subdirectories derived from the filenames.

```python3 rsync_and_organize_json.py -s <source_directory> -d <destination_directory>```

This script performs the following steps:

1. Scans the source directory for JSON files, including any files within nested subdirectories.
2. For each JSON file, it parses the filename to determine the appropriate subdirectory within the destination directory.
3. Creates the subdirectory if it doesn't already exist.
4. The JSON file is then rsynced to the designated subdirectory within the destination directory.


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


### spec_csv_summary_to_excel.py

This script is designed to process a specified CSV file to generate an Excel file that includes both the original dataset and various summary statistics and information derived from the data. The Excel file will contain two sheets: one with the original CSV data and another with summary statistics and box-related information.

```python3 spec_csv_summary_to_excel.py -s <source_csv_file> -d <destination_excel_file>```

This script performs the following steps:

1. Encoding Detection: Determines the encoding of the source CSV file to ensure accurate data reading.
2. Data Loading: Reads the CSV file into a Pandas DataFrame, applying necessary data type specifications.
3. Data Cleaning: Trims whitespace from specific columns to standardize the data.
Excel Exportation:
4. Exports the entire dataset to the first sheet of the Excel file named 'Original CSV'.
Constructs a summary DataFrame containing overall statistics such as the total number of objects and unique boxes.
5. Calculates the breakdown of objects by format and presents it alongside the summary statistics in the 'Summary' sheet.
6. Prepares and exports detailed box-related information to the 'Summary' sheet, providing insights into barcode counts per box and their respective locations.
7. Output Generation: The script then compiles all the gathered information into a well-organized Excel file with two sheets, facilitating easy access and analysis of the data.

### trello_engineer_notifier.py

This script facilitates task management in Trello by automatically moving specified cards to engineer-specific lists, notifying engineers via card comments, and assigning them to the cards. It utilizes Trello's API to interact with cards based on command line inputs and environmental configurations.

```python3 trello_engineer_notifier.py -c CARD_ID -e ENGINEER_NAME```

This script performs the following steps:

1. Card Retrieval: Fetches the specified card from a Trello board using the provided card ID and a board ID sourced from environment variables.
2. List Assignment: Moves the card to a list specified by the engineer's name, which corresponds to a list ID defined in environment variables.
3. Notification: Adds a comment tagging the engineer on the moved card to notify them of the new task assignment.
4. Member Assignment: Assigns the engineer as a member of the card to indicate their responsibility for the task.
5. Environment Variable Dependencies:
   
* TRELLO_API_KEY: Your Trello API key.
* TRELLO_TOKEN: Your Trello authorization token.
* NYPL_MPL_BOARD_ID: The ID of the Trello board from which the card will be moved.
* Engineer-specific variables such as TRELLO_ENGINEERNAME_USERNAME and TRELLO_ENGINEERNAME_LIST_ID for each engineer (replace ENGINEERNAME with the actual engineer's name).

### trello_list_ids.py

This script is designed to provide a quick overview of all the lists and members associated with a specific Trello board. It utilizes the Trello API to fetch and display list names and IDs, as well as member names, usernames, and IDs from a specified board.

```python3 trello_list_ids.py```

You will be prompted to enter the board ID:

```Enter the Trello board ID:```

This script performs the following steps:

1. List Information Retrieval: Fetches and displays all lists from the specified Trello board, including their names and unique IDs.
2. Member Information Retrieval: Fetches and displays all members of the specified Trello board, including their full names, usernames, and unique IDs.

### trello_qcqueue_mover.py

This script is designed to automate the transfer of Trello cards from one list to another across different boards. It is particularly useful for workflows where tasks need to be moved systematically from one project phase to another, which might be tracked on separate Trello boards.

```python3 trello_qcqueue_mover.py```

Before running the script, ensure that the environment variables for the source list ID, target list ID, and Trello API credentials are set.

Key Functionalities:

1. Card Transfer: Transfers all cards from a specified source list to a target list on potentially different Trello boards.
2. Dynamic Board Handling: Automatically fetches and uses the correct board ID associated with the target list, ensuring cards are moved accurately across boards.
3. Error Handling: Provides detailed error responses from the Trello API to assist with troubleshooting issues related to card movements.

### trim_and_transcode.py

This script facilitates the trimming and transcoding of media files. Users can specify start and end times for the desired output, along with input and output files. The script leverages ffmpeg to perform these tasks efficiently.

```python3 trim_and_transcode.py -f <input_file> -o <output_directory> -t <start_time> <end_time>```

This script performs the following steps:

1. Read Input Parameters: Parses command-line arguments for the input file, output directory, and start/end timestamps.
2. Timestamp Conversion: Converts timestamps from HH:MM:SS to seconds to accurately specify the trimming points.
3. Construct Output Filename: Generates an output filename based on the input file name with a "_trim" suffix.
4. Transcoding Command: Constructs and executes an ffmpeg command that:
5. Execute Transcoding: Runs the ffmpeg command to generate the trimmed and transcoded output file in the specified output directory.


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