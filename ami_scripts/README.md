
# AMI Production Scripts

- [AMI Production Scripts](#ami-production-scripts)
    - [Overview](#overview)
    - [ami\_collections\_digitization\_reporter.py](#ami_collections_digitization_reporterpy)
    - [ami\_file\_sync.py](#ami_file_syncpy)
    - [ami\_record\_exporter\_and\_analyzer.py](#ami_record_exporter_and_analyzerpy)
    - [append\_eoy\_report\_intro.py](#append_eoy_report_intropy)
    - [audio\_concat\_and\_bag.py](#audio_concat_and_bagpy)
    - [audio\_processing.py](#audio_processingpy)
    - [audio\_to\_mp4\_converter.py](#audio_to_mp4_converterpy)
    - [clean\_spec\_csv\_to\_excel.py](#clean_spec_csv_to_excelpy)
    - [copy\_from\_s3.py](#copy_from_s3py)
    - [copy\_to\_s3.py](#copy_to_s3py)
    - [cover\_video\_lines.py](#cover_video_linespy)
    - [create\_media\_json.py](#create_media_jsonpy)
    - [create\_object\_bags.py](#create_object_bagspy)
    - [digitization\_performance\_tracker.py](#digitization_performance_trackerpy)
    - [duplicate\_filemaker\_records.py](#duplicate_filemaker_recordspy)
    - [export\_s3\_to\_csv.py](#export_s3_to_csvpy)
    - [filemaker\_to\_json\_validator.py](#filemaker_to_json_validatorpy)
    - [film\_processing.py](#film_processingpy)
    - [generate\_test\_media.py](#generate_test_mediapy)
    - [hflip\_film\_packages.py](#hflip_film_packagespy)
    - [iso\_checker.py](#iso_checkerpy)
    - [iso\_creator.py](#iso_creatorpy)
    - [iso\_transcoder\_cat\_mkvmerge.py](#iso_transcoder_cat_mkvmergepy)
    - [iso\_transcoder\_makemkv.py](#iso_transcoder_makemkvpy)
    - [json\_to\_csv.py](#json_to_csvpy)
    - [json\_updater.py](#json_updaterpy)
    - [json\_validator.py](#json_validatorpy)
    - [make\_anamorphic\_scs.py](#make_anamorphic_scspy)
    - [media\_metrics\_aggregator.py](#media_metrics_aggregatorpy)
    - [mediaconch\_checker.py](#mediaconch_checkerpy)
    - [mediainfo\_extractor.py](#mediainfo_extractorpy)
    - [migrated\_media\_file\_checker.py](#migrated_media_file_checkerpy)
    - [migration\_status\_reporter.py](#migration_status_reporterpy)
    - [prepend\_title\_cards.py](#prepend_title_cardspy)
    - [qc\_scope\_visualizer.py](#qc_scope_visualizerpy)
    - [rawcooked\_check\_mkv.py](#rawcooked_check_mkvpy)
    - [remake\_anamorphic\_bags.py](#remake_anamorphic_bagspy)
    - [rsync\_and\_organize\_json.py](#rsync_and_organize_jsonpy)
    - [rsync\_validator.py](#rsync_validatorpy)
    - [spec\_csv\_summary\_to\_excel.py](#spec_csv_summary_to_excelpy)
    - [test\_jdbc.py](#test_jdbcpy)
    - [trello\_engineer\_notifier.py](#trello_engineer_notifierpy)
    - [trello\_list\_ids.py](#trello_list_idspy)
    - [trello\_qcqueue\_mover.py](#trello_qcqueue_moverpy)
    - [trim\_and\_transcode.py](#trim_and_transcodepy)
    - [unbag\_objects.py](#unbag_objectspy)
    - [validate\_ami\_bags.py](#validate_ami_bagspy)
    - [video\_processing.py](#video_processingpy)


### Overview

This repository contains a set of Python scripts designed to streamline the handling, organization, and preparation of audio and video files for ingest into NYPL's Digital Repository. The primary goal of these scripts is to assist users in efficiently managing their multimedia files, generating accompanying JSON metadata, packaging all assets using the BagIt specification, and transferring access files to Amazon Web Services. The main functionalities of these scripts include:

1. Converting and organizing multimedia files in various formats and resolutions.
2. Preparing JSON metadata to accompany the media files.
3. Packaging assets following the BagIt specification for easy ingest into the Digital Repository.
4. Transferring access files to Amazon Web Services for storage and distribution.

These scripts aim to automate and simplify the management of multimedia files, ensuring a seamless integration with NYPL's Digital Repository system. For detailed instructions, dependencies, and examples of usage, please refer to the README.md file.


### ami_collections_digitization_reporter.py

This script is designed to generate a PDF report summarizing the digitization activity of AMI (Audio and Moving Image) items in SPEC collections over the past 18 months. It connects to a FileMaker database via JDBC to retrieve digitization data, processes it to generate summary statistics, and visualizes recent digitization trends, focusing on the last three months.

```python3 ami_collections_digitization_reporter.py```

The script performs the following steps:

1. Database Connection and Data Retrieval:
    * The script uses jaydebeapi to connect to the AMI FileMaker database. Environment variables for the database server, database name, username, and password are required.
    * Queries data from two tables (tbl_vendor_mediainfo and tbl_metadata) containing digitized AMI item records. The data is then loaded into a Pandas DataFrame for processing.
2. Data Processing:
    * Converts the dateCreated field into a datetime object and filters records to include only those from the last 18 months.
    * Aggregates data by SPEC collection and counts the unique items digitized per collection.
    * Generates a month-by-month breakdown of digitization activity, with a focus on the last three months. Collections with fewer than 5 items digitized over this period are excluded for better clarity.
3. PDF Report Generation:
    * Title Page: Creates an introductory title page summarizing the date range of the report.
    * Trend Visualization: A bar chart visualizing digitization trends across SPEC collections for the last three months, using a custom color palette.
    * Paginated Table: Displays a table ranking SPEC collections by the number of unique items digitized over the last 18 months, split across multiple pages if necessary.


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

### append_eoy_report_intro.py

This script is designed to append an introductory PDF (e.g., a cover letter or executive summary) to an existing statistics PDF report, merging the two into a single document. The resulting file is saved to the user's desktop or to a specified output path.

```python3 append_eoy_report_intro.py -i <intro_pdf> -s <stats_pdf> -o <output_pdf>```

Script Functionality:

1. PDF Merging:
    * The script uses the PyPDF2 library to read and merge two PDF files: an introductory PDF and a statistics report PDF.
    * All pages from the introductory PDF are added first, followed by all pages from the statistics PDF.
    * The merged result is written to a new output PDF file.

2. Arguments:
    * -i or --intro: Path to the introductory PDF file.
    * -s or --stats: Path to the existing statistics PDF report.
    * -o or --output: (Optional) Path to the output PDF file. If not provided, the script will save the merged PDF to the desktop with a default filename.

### audio_concat_and_bag.py

This script processes audio files within a directory, concatenates FLAC files, updates associated JSON metadata, and creates BagIt-compliant directories for repackaging. It supports both single and multiple bag directories as input.

```python3 audio_concat_and_bag.py -b /path/to/bag -o /path/to/output_directory```

```python3 audio_concat_and_bag.py -d /path/to/directory_of_bags -o /path/to/output_directory```

Usage:

Required Arguments:
* -o, --output: Output directory where processed files and bags will be stored.

Mutually Exclusive Options:
* -b, --bag: Path to a single bag directory to process.
* -d, --directory: Path to a directory containing multiple bags to process.

The script performs the following steps:

1. Input Validation:
    * Checks the input directory structure for required subdirectories and files.
    * Ensures the output directory exists or creates it.
2. FLAC File Concatenation:
    * Generates a concatenated .flac file in EditMasters or PreservationMasters based on the file type.
3. JSON Metadata Update:
    * Copies JSON metadata files and updates fields to match the new concatenated audio file.
4. Image File Handling:
    * Copies .JPG files from the input Images directory to the corresponding output directory.
5. BagIt Bag Creation:
    * Generates a BagIt bag for each processed directory with manifest files for integrity checks.

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

### audio_to_mp4_converter.py

This script converts .wav or .flac audio files to .mp4 or .mp3 formats using FFmpeg. It processes all audio files within a specified directory, converting them to the desired output format with appropriate audio encoding settings.

```python3 audio_to_mp4_converter.py -d <directory_path> -f <output_format>```

Script Functionality:

1. Audio Conversion:
    * The script uses FFmpeg to convert .wav or .flac files to either .mp4 (AAC audio) or .mp3 formats.
    * For .mp4:
        * The audio is encoded using AAC codec at a bitrate of 320 kbps and a sample rate of 44.1 kHz.
        * Rectangular dithering is applied during the conversion process.
    * For .mp3:
        * The script writes ID3v1 and ID3v2 tags, applies triangular dithering, and encodes the audio at a sample rate of 48 kHz with high-quality settings.

### clean_spec_csv_to_excel.py

This script prepares and cleans a SPEC CSV file for import into AMIDB by performing various data transformation and cleanup operations. It allows for adding work order and project code to the new Excel file, offers a vendor mode for specific processing, and can optionally interact with Trello for project management purposes.

```python3 clean_spec_csv_to_excel.py -s /path/to/source_csv.csv -w WORKORDER_ID -p PROJECT_CODE -d /path/to/destination_directory -c /path/to/config.json -pt PROJECT_TYPE [-v] [-t] [--single-card]```

Updated Features:
1. Improved Command-Line Arguments:
* -p, --projectcode: Mandatory project code for identifying the project in AMIDB.
* -pt, --project-type: Adds a descriptive project type, now required unless vendor mode is enabled. Supported types:
    * exhibition
    * programmatic
    * priority
    * public
    * researcher

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

```python3 copy_to_s3.py -d /path/to/directory/of/bags OR additional /path/to/directory/of/bags```

This script performs the following steps:

1. Parsing command-line arguments, specifically the path to the directory of bags.
2. Lists all the directories in the given directory, filtering out hidden or system directories.
3. For each directory (BagIt bag), the script walks through its contents and generates a list of files that have specific extensions (.sc.mp4, .sc.json, .em.wav, .em.flac, .em.json).
4. Copies each file in the list to the AWS S3 bucket using the aws s3 cp command.
5. The process is repeated for each BagIt bag in the directory.

* AWS CLI must be installed and configured with appropriate credentials.


### cover_video_lines.py

This script allows users to cover specified numbers of lines at the top or bottom of a video with a black bar using FFmpeg. The script can either preview the changes in real time using FFplay or save the processed video to a file.

```python3 cover_video_lines.py [-d <directory_path> | -f <video_file>] [-t <top_lines>] [-b <bottom_lines>] [-p] [-s]```

Script Functionality:

1. Covering Video Lines:
    * The script uses FFmpeg to cover a specified number of lines at the top (-t) and/or bottom (-b) of the video with black.
    * The user can choose to preview the result using FFplay (-p) or save the processed video as a new file (-s).
2. Processing Options:
    * Preview Mode: If --preview is specified, the script uses FFplay to preview the video with the black bars applied but does not save any changes.
    * Save Mode: If --save is specified, the script saves a new video file with the processed changes. The saved file will have _processed appended to the original filename (e.g., video_processed.mp4).
    * Users must choose either the --preview or --save option.
3. Video Input:
    * The script can process either a single video file (-f) or all video files in a directory (-d). Supported video formats include .mp4, .mov, .avi, and .mkv.
4. Video Filters:
    * The script applies the drawbox filter to cover the specified number of lines at the top or bottom of the video.
    * It also includes the Yadif deinterlacing filter (yadif) to improve video quality during conversion.
5. Output Video:
    * When saving a file, the script generates a new video file using H.264 video encoding and AAC audio encoding. The output video is optimized for fast playback (-movflags faststart) and uses a video bitrate of 3.5 Mbps.

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
* -p, --previous-fiscal: Focuses on the previous fiscal year or a specified calendar year (e.g., -p FY23 or -p 2020).
* --vendor: Pulls data exclusively from the vendor table.
* --c, -combined: Combines data from both vendor and in-house sources.


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

### duplicate_filemaker_records.py

This script duplicates FileMaker database records for MP4 derivatives based on corresponding ISO records. It identifies and processes files in a specified directory, extracts metadata from the original ISO records, and inserts new records for the MP4 derivatives.

```python3 duplicate_filemaker_records.py -d <directory_path> [--dev-server]```

Arguments:
* -d, --directory: (Required) Path to the directory containing ISO and MP4 files.
* --dev-server: (Optional) Connect to the DEV server instead of the production server.

This script performs the following steps:

1. Connect to Database:
    * Establishes a JDBC connection to the FileMaker database.
2. Crawl Directory:
    * Scans the specified directory for ISO and MP4 files.
    * Maps ISO files to their associated MP4 derivatives.
3. Fetch Original Record:
    * Retrieves the database record for each ISO file using its reference filename.
4. Insert New Records:
    * Creates new records in the database for each MP4 file with:
    * Updated metadata from the original ISO record.
    * Additional fields specific to the MP4 derivatives.
5. Close Connection:
    * Ensures the database connection is closed after processing.

### export_s3_to_csv.py

This script exports the contents of an Amazon S3 bucket to a CSV file, listing each object's key, last modified date, and size.

```python3 export_s3_to_csv.py -b <bucket_name> -o <output_file>```

Arguments:
* -b, --bucket: (Required) Name of the S3 bucket to export.
* -o, --out: (Required) Path and filename for the output CSV file.

This script performs the following steps:

1. Initialize S3 Client:
    * Uses the AWS SDK (boto3) to interact with S3.
2. Fetch Object Metadata:
    * Retrieves object details using the list_objects_v2 API.
    * Handles pagination to fetch all objects in the bucket.
3. Write to CSV:
    * Creates a CSV file and writes the object details to it.
    * Includes headers for better readability.
4. Print Summary:
    * Displays the total number of files exported to the console.

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

### iso_checker.py

This script processes .iso files using Isolyzer, a tool for validating ISO images. It analyzes the file system types, checks the image size consistency, and generates a detailed report of the findings.

```python3 iso_checker.py -d /path/to/iso/files```

This script performs the following steps:

1. Recursive Directory Search:
    * Automatically detects all .iso files in the specified directory and its subdirectories.
2. File System Detection:
    * Extracts and lists file system types (e.g., ISO 9660, UDF) from each ISO image.
3. Validation:
    * Checks if the ISO file's size matches the expected size:
    * Reports ISO files with "unexpected" sizes or errors.
4. Error Handling:
    * Catches and displays errors for ISO files that fail validation or processing.
5. Summary Report that Provides:
    * Total number of ISO files processed.
    * Counts of images with expected and unexpected sizes.
    * A breakdown of detected file system types.

### iso_creator.py

This script facilitates the creation of ISO image backups from DVDs using ddrescue. It includes functionality for opening and closing the disc tray, unmounting and remounting DVDs, and handling errors during the backup process.

```python3 iso_creator.py```

This script performs the following steps:

1. Start the Script:
    * Opens the disc tray and prompts the user to insert a DVD.
2. Prepare the Backup:
    * Asks the user to specify a destination directory and filename for the ISO file.
3. Run ddrescue:
    * Backs up the DVD to an ISO file and logs progress in real time.
    * Runs up to 4 rescue passes (-r4) with a block size of 2048 bytes (-b 2048).
4. Post-Backup Actions:
    * Remounts and ejects the DVD after backup.
    * Logs failed attempts for troubleshooting.
5. Repeat or Exit:
    * Asks the user if they want to back up another DVD.
    * Provides a summary of the session upon exit.


### iso_transcoder_cat_mkvmerge.py

This script processes ISO images to transcode their VOB files into H.264 MP4 format, with an emphasis on handling complex DVD structures. It prioritizes cat for concatenation and uses mkvmerge as a fallback if cat fails.

```python3 iso_transcoder_cat_mkvmerge.py -i /path/to/input -o /path/to/output [-s] [-f]```

Arguments

* -i, --input	Required. Path to the directory containing ISO files or individual ISO file paths.
* -o, --output	Optional. Path to the directory where the output MP4 files will be saved (default: input).
* -s, --split	Optional. Split each VOB file into separate MP4 files (default: concatenate VOB files).
* -f, --force-concat	Optional. Force concatenation of all VOB files into one MP4 file.

This script performs the following steps:

1. Tries cat first for VOB concatenation.
2. Falls back to mkvmerge if cat fails to concatenate the files.
3. Flexible Transcoding Options:
    * Split Mode (-s): Creates individual MP4 files for each VOB.
    * Concatenation Mode:
    * Combines all VOB files into a single MP4, prioritizing cat and using mkvmerge as fallback.
    * Robust Error Handling:
    * Handles mounting/unmounting errors and fallback scenarios for concatenation and transcoding.
4. Detailed Logging:
    * Provides comprehensive logs for each step, including errors and processing summaries.
5. Post-Processing Verification:
    * Confirms successful creation of expected MP4 files and logs any failures.
6. Automatic Cleanup:
    * Cleans up temporary files and mount points after processing.

### iso_transcoder_makemkv.py

This script facilitates the transcoding of video object (VOB) files extracted from ISO images into H.264 MP4 format using MakeMKV for initial ISO processing and FFmpeg for transcoding. It provides enhanced compatibility, better video quality, and ease of access for archived video content.

```python3 iso_transcoder_makemkv.py -i /path/to/input -o /path/to/output [-f]```

This script performs the following steps:

1. Pre-Check:
    * Verifies that makemkvcon (MakeMKV) and ffmpeg are installed and accessible in the system's PATH.
2. ISO Processing:
    * MakeMKV extracts MKV files from ISO images.
    * Handles failures by logging errors and skipping problematic ISOs.
3. MKV Transcoding:
    * Uses FFmpeg to transcode MKV files into H.264 MP4 format with optimal settings:
    * Video: H.264 codec, 3.5 Mbps bitrate, deinterlacing (yadif), and pixel format yuv420p.
    * Audio: AAC codec, 320 kbps bitrate, and 48 kHz sampling rate.
4. Concatenation (Optional):
    * Combines multiple MKV files into a single MKV using mkvmerge before transcoding, if requested.
5. Verification:
    * Ensures all expected MP4 files are created and categorizes them based on resolution, aspect ratio, and frame rate.
6. Post-Processing Check:
    * Classifies MP4 files using predefined categories (e.g., NTSC DVD SD, PAL Widescreen).
    * Identifies and logs outliers that do not match any category.
7. Cleanup:
    * Removes temporary files and directories created during the process.

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

This script extracts MediaInfo from a collection of video or audio files in a specified directory or a single file and saves the extracted data to a CSV file. It also supports processing BagIt packages with sidecar JSON metadata.

```python3 mediainfo_extractor.py [-d /path/to/media/directory] [-f /path/to/media/file] -o /path/to/output/csv [-v]```

Options:

* -d, --directory: Path to the directory containing media files. This can include BagIt packages if the -v flag is used.
* -f, --file: Path to a single media file.
* -o, --output: Path to save the output CSV file. This is a required argument.
* -v, --vendor: Optional. Process files as BagIt packages with sidecar JSON metadata.

This script performs the following steps:

1. Parse the input arguments to obtain the directory, file, and output paths.
2. Determine the media files to examine based on the input directory or file.
3. For each media file, retrieve its MediaInfo using the pymediainfo library.
4. Extract the relevant track information from the MediaInfo.
5. Append the extracted information to a list of file data.
6. JSON Metadata Handling (optional):
* Reads sidecar JSON files (if present) to extract additional metadata (collectionID, objectType, objectFormat).
7. Write the file data to the output CSV file, including headers for each field.

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

### qc_scope_visualizer.py

This script is designed to provide a detailed audio and video visualization for media files using MPV and FFmpeg filters. It supports both video and audio files, and offers customizable spectrum visualizations. The script automatically detects the number of audio and video streams in the media file, configures appropriate visualizations, and processes the file for quality control (QC) review.

```python3 qc_scope_visualizer.py -f <media_file> --showspectrum-stop <upper_frequency_limit>```

This script performs the following steps:

1. MPV Installation Check: Verifies that MPV is installed on the system. If MPV is missing, it suggests installing it via brew install mpv on macOS.
2. Audio Stream Detection: Uses ffprobe to detect the number of audio streams in the provided media file.
3. Video Stream Detection: Uses ffprobe to detect the number of video streams in the file.
4. Audio-Only Mode: If no video streams are present, the script switches to audio-only mode, adjusting the layout to accommodate audio visualizations like avectorscope, showspectrum, and ebur128.
5. Complex MPV Command Generation: Constructs a dynamic mpv command using FFmpeg filters based on the detected media streams. Visualizations are generated for:
    * Audio-Only: Avectorscope, showspectrum, ebur128 loudness meter, and showvolume.
    * Audio with Video: Video waveform monitor, avectorscope, and showvolume.
6. Customizable Showspectrum Visualization: The --showspectrum-stop argument allows the user to define the upper frequency limit for the showspectrum filter, offering flexibility for different audio content.

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

### test_jdbc.py

This script is a utility for testing JDBC connections to a FileMaker server. It dynamically determines whether to connect to the production server or the development server based on command-line arguments.

```python3 test_jdbc.py [--use-dev]```

1. Load Environment Variables:
2. Retrieves connection details such as server IP, database name, username, and password from the environment variables:
    * FM_SERVER (Production Server IP)
    * FM_DEV_SERVER (Development Server IP)
    * AMI_DATABASE (Database Name)
    * AMI_DATABASE_USERNAME (Username)
    * AMI_DATABASE_PASSWORD (Password)
2. Dynamic JDBC Path:
3. Uses the JDBC driver located at ~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar.
4. Print Connection Details:
    * Prints the selected server, database, and username for transparency.
5. Attempt Connection:
    * Attempts to connect to the specified server using the JayDeBeApi library.

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

### validate_ami_bags.py

This script is a tool for validating AMI (Audio/Moving Image) bags. These bags contain JSON metadata and various types of media files, organized into a structured BagIt format. The script ensures that the bags conform to specific structural, content, and metadata requirements.

```python3 validate_ami_bags.py -d /path/to/bag_directory OR -b /path/to/bag [--metadata] [--slow] [-log]

1. Validation of Bag Structure:
    * Checks for the presence of required directories and files.
    * Ensures compliance with BagIt specifications, including Oxum and checksum validation.
2. Media File Validation:
    * Ensures media files have valid formats (e.g., .mov, .wav, .flac).
    * Verifies preservation master files (_pm) are present and correctly located.
3. JSON Metadata Validation:
    * Ensures JSON metadata files match the associated media files.
    * Validates the structure, required fields, and values of JSON metadata files.
4. Customizable Checks:
    * Includes options for fast validation (skipping checksum recalculation) and deep metadata checks.
5. Logging and Summaries:
    * Provides detailed logs and summaries, including warnings and errors, for each bag.
    * Tracks and aggregates specific issues across multiple bags.

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