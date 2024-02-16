---
title: QC Workflow
layout: default
nav_order: 1
parent: Quality Control
---

# Quality Control Workflow
{: .no_toc }
Internal workflow for carrying out QC on digital assets.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

# Quality Control Overview
Quality control (QC) is conducted in accordance with best practices to ensure that deliverables generated for preservation and access meet our technical specifications, metadata requirements, and adhere to best practices for handling and digitization of NYPL’s audiovisual collections.

Our QC workflow is currently comprised of the following processes:

  * Fixity check: custom scripts that incorporate Bagit.py
  * JSON validation using ajv
  * MediaConch specification conformance check
  * Manual bag, content, & metadata inspection

The following handbook will provide step-by-step instructions for carrying out our QC processes on Vendor and In-House projects. Our QC workflows vary slightly between Vendor and In-House deliverables, so steps applicable to Vendor projects only are marked **(vendor only)**. Vendor QC is primarily performed directly on hard-drives.

# Shipment Intake
 **(vendor only)**

* Enter all drives and associated invoice IDs ("shipments" / "work orders") received into the [Vendor Project Tracking sheet](https://docs.google.com/spreadsheets/d/1ZeF6vGE1TqLnKaNjZFSIvjyKhYBt38nBcZDHyD_saPo/edit#gid=1973090513). Complete all fields (some are formulas - highlighted gray if so).

* Copy the "work order ID" that is automatically generated in the Vendor Project Tracking sheet (column A).

* Create an ICC/Logs directory named with the work order ID

* Create a Trello Card on the [MPS Quality Control Trello Board](https://trello.com/b/CBLrQvG1/nypl-ami-quality-control-and-ingest) and paste the work order ID into the Title of the card.

* Create a QC log in the Team Drive QC Folder for each hard drive:
  * make a copy of the [QC Log Template](https://docs.google.com/spreadsheets/d/1OKlFNGR27H6Ey9v2EyAjqe6MzOsPrVl_5X4PDV-elsU/edit?usp=sharing) & rename the copy using the same work order ID, (follow the QC log template naming convention).

* Attach the QC log to the associated Trello card (using the Attachments button in the card, drop in the URL of the QC log).

* **Mount Drive Read-Only** 
**(vendor only)**

The most important step during QC is to mount your drive(s) [Read-Only](https://github.com/NYPL/ami-preservation/wiki/Resources#mounting-drives-read-only).
   * Open Disk Utility and check the Device name listed in the lower right corner

   * Mount a drive read-only using the following command: 
   ```
   diskutil mount readOnly device name as listed in Disk Utility
   ```

# Bag Validation

  * Use ```validate_ami_bags.py``` in ami-tools to check Check bag Oxums, bag completeness, bag hashes, directory structure, filenames, and metadata. 
  * Due to the time required to validate a directory of Vendor bags, its best to let validate_ami_bags.py run overnight.  

```
python3 /path/to/ami-tools/bin/validate_ami_bags.py -d /Volumes/driveID/ --metadata --slow
```
  * Review any Bags that report as "not ready for ingest"

or...just validate JSON using one of two options:

# JSON Validation

  * Use ```json_validator.py``` in ami-scripts to confirm JSON files comply with [NYPL metadata specifications](https://nypl.github.io/ami-preservation/pages/ami-metadata.html). 

```
/path/to/ami-preservation/ami-scripts/json_validator.py -m /path/to/ami-metadata -d /Volumes/DRIVE-ID
```
or

```
ajv validate --all-errors --multiple-of-precision=2 --verbose -s /path/to/ami-metadata/versions/2.0/schema/digitized.json -r "/path/to/ami-metadata/versions/2.0/schema/*.json" -d "/Volumes/DRIVE-ID/*/*/data/*/*.json"
```

# Digital Asset Specification Check

  * Use ```mediaconch_checker.py``` in ami_scripts to confirm media files comply with [NYPL digital asset specifications](https://nypl.github.io/ami-preservation/pages/ami-specifications.html).

The ami-preservation repo contains a directory, [qc_utilities](https://github.com/NYPL/ami-preservation/tree/master/qc_utilities). Within this are various scripts and tools, including the mediaconch scripts listed below which will generate 'pass/fail' logs in your home directory when run against a directory of media files.
```
python3 /path/to/ami-preservation/ami-scripts/mediaconch_checker.py -p /path/to/ami-preservation/qc_utilities/MediaconchPolicies -d /Volumes/DRIVE-ID
```
# Additional Checks 

* **AUDIO ONLY**: Check a selection of FLAC for embedded metadata
  * Copy 5 .flac files delivered to Desktop and decode these new copies back to wav.
```
flac --decode --keep-foreign-metadata --preserve-modtime --verify input.flac
```
  * Check BEXT in newly decoded .wavs using BWF MetaEdit. **Discard .wavs and .flac copies after use.**

* **FILM PMs ONLY**:
  * Check a selection of PMs for RAWCooked reversability:
```
/path/to/ami-preservation/ami-scripts/rawcooked_check_mkv.py -d /Volumes/DRIVE-ID -p 20
```

# Perform Manual QC 
  * Perform manual QC using Google Sheet list of Bags to check (in Trello card) (1min @ beginning, middle, end of each file)
  * Note any errors / observations in the Google Sheet log. Use the categories/menus provided as much as possible.
  * Use [this](https://github.com/NYPL/ami-preservation/wiki/Resources#logging-qc-failures--flags) list of definitions to review and mark-off the items listed in the QC log.
  * Content Inspection of In-House deliverables can be completed either on ICC or on the drive by following the steps outlined [here](https://github.com/NYPL/ami-preservation/wiki/Resources#content-inspection).  
  * Use a text-editor (Atom / Notepad / Text Edit etc.) to [open and inspect](https://github.com/NYPL/ami-preservation/wiki/Resources#spot-checking-content--json) JSON files.

* After manual QC, **if all bags are valid**...Then:

  * Pull MediaInfo & output the resulting mediainfo.csv log to the directory for your project or HD on ICA

```
python3 /path/to/ami-preservation/ami_scripts/mediainfo_extractor.py -d /Volumes/DRIVE-ID -o /path/to/destination/folder/WorkOrderID.csv
```

# Wrap Up...
  * Move the Trello Card to the proper list (passed / failed etc.)
  * **IF APPROVED**:
    * Update QC status and check Due date in Trello Card; Move the Trello Card to the passed list; stage HD for delivery to Digital Preservation
    * Database: update database for approved shipments

  * **IF NOT APPROVED**:
    * Mention MPC in Trello card for follow-up OR email vendor with QC feedback / issues (or send feedback to Manager to relay to vendor); include relevant CMS IDs or filenames.
&
    * Move Trello card to "Vendor: QC Review" or "IN-HOUSE: QC Review" list in Trello.
    * Vendor: MPC follow up with vendor about errors and resolve before approving shipments. 
    * In-house: Tag relevant engineer and MPC, and Manager on Trello Card. 

  * Media Ingest Preparation
Follow these [steps](https://github.com/NYPL/ami-preservation/wiki/Resources#media-ingest-preparation) to prepare media for ingest.

  * Generating a QC list
Use Terminal to generate a QC list for each drive you are QCing by following the steps outlined [here](https://github.com/NYPL/ami-preservation/wiki/Resources#generating-a-qc-list).


  * Locate & Open QC log

**Each QC log should be easily found linked in Google Drive as an** _attachment in the Trello Card for the batch you are inspecting._ **If not, check with MPA.** _Tip: you can search for the drive ID / work order ID in the Trello search box._

  * Use the list of files that appears in the Google Sheet QC log (in the QClog tab) as your list of files to check.
  * Drop down menus are available for noting specific identifiable errors, and there is a free-text field for general notes.

# Tools
See our [Command Line Resources ](https://nypl.github.io/ami-preservation/pages/resources.html)for descriptions, usage, and installation instructions of various tools we use in this workflow.
