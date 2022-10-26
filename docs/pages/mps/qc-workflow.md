---
title: QC Workflow
layout: default
nav_order: 1
parent: Quality Control
---

# Quality Control Workflow
{: .no_toc }
Internal workflow for carrying out QC on digital assets.

| **Activity** | **Staff Responsible** |
|   -----          |     -----      |  
|   Transfer packages to ICA     |  AMI Labs |
|   Update database work order (from in progress to quality control)  | AMI Labs |
|   Update and move Trello cards from *AMI Labs Board* to *Quality Control and Ingest Board* | AMI Labs  |
|   Create Quality Control Spreadsheet   | AMI Labs QC |
|   Validate and spot check JSON, bag structure, and file conformance  | AMI Labs QC |
|   Perform manual QC of digital audio and moving image assets and metadata files | AMI Labs QC |  
|   Once manual QC is complete Trello cards are updated | AMI Labs QC |
|   Update database work order from *Quality Control* to *Ready for Ingest* and enter completion date)  | AMI Labs Asst. Manager  |   
|   Update completed Trello cards to *Ready for Migration*    | AMI Labs QC |
|   Move completed packages to staging area for ingest   | Media Preservation Coordinator  |
|   Create and submit Mediainfo report for completed work order to PAMI Manager | Media Preservation Coordinator  |
|   Repack physical media for outgoing pickup | AMI labs  |
|   Update AMI batch status in CMS  | AMI Labs Asst. Manager  |
|   Share DNC spreadsheet with SFP  | AMI Labs Asst. Manager  |
|   Update shipping register and arrange for return shipment of media to LSC  | AMI Labs Asst. Manager  |



## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Shipment Intake & QC Cheat-Sheet

* Enter all drives and associated invoice IDs ("shipments" / "work orders") received into the [Vendor Project Tracking sheet](https://docs.google.com/spreadsheets/d/1ZeF6vGE1TqLnKaNjZFSIvjyKhYBt38nBcZDHyD_saPo/edit#gid=1973090513). Complete all fields (some are formulas - highlighted gray if so).

* Copy the "work order ID" that is automatically generated in the Vendor Project Tracking sheet (column A).

* Create an ICC/Logs directory named with the work order ID

* Create a Trello Card on the [Vendor QC Trello Board](https://trello.com/b/CBLrQvG1/nypl-ami-quality-control-and-ingest) and paste the work order ID into the Title of the card.

* Create a QC log in the Team Drive QC Folder for each hard drive:
  * make a copy of the [QC Log Template](https://docs.google.com/spreadsheets/d/17VKQiZGwC2JpTYHjHBcdwMBNU29S1_Op6WhP-oUjaxg/edit?usp=sharing) & rename the copy using the same work order ID, (follow the QC log template naming convention).

* Attach the QC log to the associated Trello card (using the Attachments button in the card, drop in the URL of the QC log).

* **Mount drive read-only.**

* Validate Packages:
Use ```validate_ami_bags.py``` in ami-tools (Run ```/path/to/validate_ami_bags.py -h``` for additional usage)
```
python3 /path/to/ami-tools/bin/validate_ami_bags.py -d /Volumes/driveID/ --metadata --quiet
```
* Review any Bags that report as "not ready for ingest"

or...
just validate JSON:
```
ajv validate --all-errors --multiple-of-precision=2 --verbose -s /path/to/ami-metadata/versions/2.0/schema/digitized.json -r "/path/to/ami-metadata/versions/2.0/schema/*.json" -d "/Volumes/DRIVE-ID/*/*/data/*/*.json"
```


* Run MediaConch:
The ami-preservation repo contains a directory, [qc_utilities](https://github.com/NYPL/ami-preservation/tree/master/qc_utilities). Within this are various scripts and tools, including the mediaconch scripts listed below which will generate 'pass/fail' logs in your home directory when run against a directory of media files.
```
cd /Volumes/DRIVE-ID/
```
*then...*
  * For analog VIDEO:
```
/path/to/qc_utilities/mediaconch_videoFFv1.sh && /path/to/qc_utilities/mediaconch_videoAnalogSC.sh
```

  * For analog AUDIO:
```
/path/to/qc_utilities/mediaconch_audioAnalog.sh
```
  * For FILM:
  ```
  /path/to/qc_utilities/mediaconch_filmPM.sh && /path/to/qc_utilities/mediaconch_videoAnalogSC.sh
  ```

Note: the video service copy mediaconch policy works for all video/film deliverables.


* Validate Bags:
```
cd path/to/dir/of/bags
path/to/validate_bags.sh
```
* Log destination is home/user directory. Check Bag validation logs for errors. Resolve / log any errors (in QC log) and continue.

* AUDIO ONLY: Check a selection of FLAC for embedded metadata
  * Copy 5 .flac files delivered to Desktop and decode these new copies back to wav.
```
flac --decode --keep-foreign-metadata --preserve-modtime --verify input.flac
```
  * Check BEXT in newly decoded .wavs using BWF MetaEdit. **Discard .wavs and .flac copies after use.**

* Film PMs only:
Check a selection of PMs for RAWCooked reversability:
```
rawcooked /path/to/mkv --check
```

* Perform Manual QC ...
  * Perform manual QC using Google Sheet list of Bags to check (in Trello card) (1min @ beginning, middle, end of each file)
  * Note any errors / observations in the Google Sheet log. Use the categories/menus provided as much as possible.

* After manual QC, **if all bags are valid**...Then:

  * Move JSON to ICC (must be connected to ICC):
```
find /Volumes/DRIVE-ID/ -name '*.json' -exec cp {} /Volumes/video_repository/Working_Storage/JSON_and_Images/VendorJSON ';'
```

  * Move IMAGES to ICC, if received (must be connected to ICC):

```
find /Volumes/DRIVE-ID/ -name '*.JPG' -exec cp {} /Volumes/video_repository/Working_Storage/JSON_and_Images/AssetImages ';'
```
&
```
find /Volumes/DRIVE-ID/ -name '*.jpg' -exec cp {} /Volumes/video_repository/Working_Storage/JSON_and_Images/Asset_Images ';'
```

* Pull MediaInfo & output the resulting mediainfo.csv log to the MediaInfo folder for your project on ICC

```
python3 /path/to/ami-preservation/pami_scripts/pull_mediainfo.py -d /Volumes/DRIVE-ID -o /path/to/destination/folder/WorkOrderID.csv
```

* Wrap Up...
  * Move the Trello Card to the proper list (passed / failed etc.)
  * IF APPROVED:
    * email vendor to confirm QC approval of designated shipment & invoice number; CC Rebecca to approve invoice
    * Database: update database for approved shipments

  * IF NOT APPROVED
    * Mention MPC in Trello card for follow-up OR email vendor with QC feedback / issues (or send feedback to Manager to relay to vendor); include relevant CMS IDs or filenames.
&
    * Move Trello card to "Flags & Failures To Review" list in Trello.
    * MPC: Follow up with vendor about errors and resolve before approving shipments with errors and moving Trello card to the 'Passed QC' list.


# Quality Control Overview
Quality control (QC) is conducted in accordance with best practices to ensure that deliverables generated for preservation and access meet our technical specifications, metadata requirements, and adhere to best practices for handling and digitization of NYPL’s audiovisual collections.

Our QC workflow is currently comprised of the following processes:

  * Fixity check: custom scripts that incorporate Bagit.py
  * JSON validation using ajv
  * MediaConch specification conformance check
  * Manual bag, content, & metadata inspection

Our QC workflows vary slightly between Vendor and In-House deliverables, so the following handbook is divided to reflect that. The following sections will provide step-by-step instructions for carrying out our QC processes.

## Vendor Deliverables
For Vendor deliverables, QC is primarily performed directly on hard-drives.

### Mounting Drives Read-Only
   The most important step during QC is to mount your drive(s) [Read-Only](https://github.com/NYPL/ami-preservation/wiki/Resources#mounting-drives-read-only).

### JSON Validation
Run the following in Terminal to check if JSON is valid against the appropriate schema:
```
ajv validate --all-errors --multiple-of-precision=2 --verbose -s /path/to/ami-metadata/versions/2.0/schema/digitized.json -r "/path/to/ami-metadata/versions/2.0/schema/*.json" -d "/Volumes/DRIVE-ID/*/*/data/*/*.json"
```

### Media specification validation (MediaConch)
Use either [MediaConch CLI](https://github.com/NYPL/ami-preservation/wiki/Resources#mediaconch) or [MediaConch GUI](https://github.com/NYPL/ami-preservation/wiki/Resources#mediaconch) to make sure files meet NYPL specifications.

### Generating a QC list
Use Terminal to generate a QC list for each drive you are QCing by following the steps outlined [here](https://github.com/NYPL/ami-preservation/wiki/Resources#generating-a-qc-list).

### Content Inspection
Content inspection can be completed either on ICC or on the drive by following the steps outlined [here](https://github.com/NYPL/ami-preservation/wiki/Resources#content-inspection).  

#### Locate & Open QC log

**Each QC log should be easily found linked in Google Drive as an** _attachment in the Trello Card for the batch you are inspecting._ **If not, check with MPA.** _Tip: you can search for the drive ID / work order ID in the Trello search box._

  * Use the list of files that appears in the Google Sheet QC log (in the QClog tab) as your list of files to check.
  * Drop down menus are available for noting specific identifiable errors, and there is a free-text field for general notes.

#### Spot Checking Content & JSON
Use a text-editor (Atom / Notepad / Text Edit etc.) to [open and inspect](https://github.com/NYPL/ami-preservation/wiki/Resources#spot-checking-content--json) JSON files.

#### Logging QC Failures & Flags
Use [this](https://github.com/NYPL/ami-preservation/wiki/Resources#logging-qc-failures--flags) list of definitions to review and mark-off the items listed in the QC log.

#### Media Ingest Preparation
Follow these [steps](https://github.com/NYPL/ami-preservation/wiki/Resources#media-ingest-preparation) to prepare media for ingest.

## Tools
See our [Command Line Resources ](https://nypl.github.io/ami-preservation/pages/resources.html)for descriptions, usage, and installation instructions of various tools we use in this workflow.
