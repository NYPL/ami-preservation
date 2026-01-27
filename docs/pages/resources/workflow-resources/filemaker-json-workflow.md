---
title: FileMaker and JSON Workflow
layout: default
nav_order: 7
parent: Workflow Resources
grand_parent: Resources
---

# FileMaker Integration and JSON Metadata Workflow
{: .no_toc }

This document outlines the Python-based workflow used by the NYPL AMI Preservation Lab for integrating FileMaker data, importing technical metadata, creating and validating JSON files, and duplicating records. 

- [FileMaker Integration and JSON Metadata Workflow](#filemaker-integration-and-json-metadata-workflow)
  - [Before You Begin: JDBC Setup Required](#before-you-begin-jdbc-setup-required)
  - [1. Digitize Preservation Master (PM) Files](#1-digitize-preservation-master-pm-files)
  - [2. Create Edit Master Files (Audio Only)](#2-create-edit-master-files-audio-only)
  - [3. Process Project Directory to Generate Derivatives](#3-process-project-directory-to-generate-derivatives)
  - [4. Duplicate FileMaker Records](#4-duplicate-filemaker-records)
  - [5. Extract and Import Technical Metadata](#5-extract-and-import-technical-metadata)
  - [6. Export and Validate JSON from FileMaker](#6-export-and-validate-json-from-filemaker)
  - [7. Organize, Package, and Bag Files](#7-organize-package-and-bag-files)

---

## Before You Begin: JDBC Setup Required

To use the FileMaker integration features described below, your environment must be properly configured to support JDBC. Please review and follow the setup instructions here:

👉 [Configuring Environmental Variables for Scripts](https://nypl.github.io/ami-preservation/pages/resources/computer-setup/configuring-env-variables.html)

This includes configuring your `.zshrc` and installing necessary Python packages like `jaydebeapi`.

For troubleshooting JDBC connectivity, including testing port access and restarting the FileMaker server if needed, see:

👉 [JDBC Connectivity Troubleshooting](https://nypl.github.io/ami-preservation/pages/resources/computer-setup/jdbc-connectivity-troubleshooting.html)

To confirm basic connectivity, use the [`test_jdbc.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/test_jdbc.py) script to quickly test both production and development servers before running the main workflow.

---

## 1. Digitize Preservation Master (PM) Files

- Complete digitization as usual.
- Ensure all required metadata fields are completed in FileMaker (use pink color coding per format to identify required fields).
- Make sure file extension is selected for each record in the database, as a complete asset.referenceFilename is required for the subsequent scripts to function properly.

## 2. Create Edit Master Files (Audio Only)

- For audio objects, generate Edit Masters before proceeding to the next step.

## 3. Process Project Directory to Generate Derivatives

- Use one of the following Python scripts depending on object type:
  - [`audio_processing.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/audio_processing.py)
  - [`film_processing.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/film_processing.py)
  - [`video_processing.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/video_processing.py)

These scripts will generate EM, MZ, or SC derivatives as appropriate.

## 4. Duplicate FileMaker Records

- Run [`duplicate_filemaker_records.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/duplicate_filemaker_records.py) on the project directory.
- This will create new FileMaker records for each derivative file based on the original PM record.

## 5. Extract and Import Technical Metadata

- Run [`mediainfo_extractor.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/mediainfo_extractor.py) on the project directory.
- This extracts technical metadata using MediaInfo or ffprobe and automatically inserts it into FileMaker.
- Note: This script still supports a `-o` flag to output CSV, primarily useful for vendor deliverables or as a backup method if JDBC issues arise.

## 6. Export and Validate JSON from FileMaker

- Run [`filemaker_to_json_validator.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/filemaker_to_json_validator.py) on the project directory.
- This uses JDBC to pull records from FileMaker and generate structured JSON files.
- The JSON output is automatically validated against the current schema.
- Note: The old version of this script has been renamed to `filemaker_to_json_validator_OLD.py` and moved to the `old_scripts` folder within `ami_scripts`.

## 7. Organize, Package, and Bag Files

- Run [`create_object_bags.py`](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/create_object_bags.py) on the project directory.  
- This script organizes files into object directories based on AMI IDs, applies BagIt structure, moves tag files into `tags/` subdirectories, updates manifests, and removes empty folders. Unmoved files are listed at the end.
