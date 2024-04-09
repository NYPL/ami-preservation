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

## Shipment Intake
 **(vendor only)**
* Enter all drives and associated invoice IDs ("shipments" / "work orders") received into the [Vendor Project Tracking sheet](https://docs.google.com/spreadsheets/d/1ZeF6vGE1TqLnKaNjZFSIvjyKhYBt38nBcZDHyD_saPo/edit#gid=1973090513). Complete all fields (some are formulas - highlighted gray if so).

* Copy the "work order ID" that is automatically generated in the Vendor Project Tracking sheet (column A).

## Cards & Logs

### Trello Card
* Use the appropriate template (In-House/Vendor) to create a Trello card on the [MPS Quality Control board](https://trello.com/b/CBLrQvG1/mps-quality-control) for each project directory (In-House) or hard drive (Vendor)

### ICA Log
* Create an ICA Log directory in ica.repo.nypl.org/pami named with the work order ID

### QC Log 
* Create a QC log in the Team Drive QC Folder for each hard drive:
  * make a copy of the [QC Log Template](https://docs.google.com/spreadsheets/d/1OKlFNGR27H6Ey9v2EyAjqe6MzOsPrVl_5X4PDV-elsU/edit?usp=sharing) & rename the copy using the same work order ID, (follow the QC log template naming convention).
  * Attach QC log to the associated Trello card (using the Attachments button in the card, drop in the URL of the QC log).

## Content Inspection

  * Software requirements:
    * Text editor (Atom / Notepad / Text Edit etc.) to open and inspect JSON files. 
    * VLC to open and inspect media files. 

  * Content inspection can be completed either on ICC or on the drive.
    * **On ICC**: make sure your machine is not going to create DS_Store files or Thumbs.db files inside bags.
    * Locate the directory that contains batch to QC in the 3_Ready_To_QC folder, if assigned by MPA.
    * Follow the below instructions (skip “Mount Read Only” section)
    * **On Hard Drive**: Mount Drive Read Only before opening any directories, and follow the below instructions

  * Open and inspect JSON file using a text-editor (Atom / Notepad / Text Edit etc.) to ensure that:
    * There is one JSON file for each digital asset created from a physical object
    * JSON files are named properly
    * All elements are properly structured
    * All fields contain values (except “bibliographic date”, which is allowed to be left empty).
    * Technical characteristics/configurations noted in JSON make sense for what you are hearing / seeing. Note: if content quality is questionable, make sure to check whether item was cleaned/baked/in poor condition. This will give perspective on the quality of the file.
  * Check files for anomalies
    * Manually check 30sec sections at beginning, middle, end of each file.
      * Things to consider when working with audio files:
        * No 5 second overlap between heads and tails of Parts or Regions
        * Reversed content that was not transferred as a separate region
        * Tip: For a quick check of the entire drive for objects with Regions, grep the directory for “p01” or “r01”
      * Things to consider when working with video files:
        * Service Copy plays and does not contain transcoding errors / is not corrupt.

  * **MOUNT DRIVE READ-ONLY** 
    * **Be sure to mount your drive [Read-Only](https://github.com/NYPL/ami-preservation/wiki/Resources#mounting-drives-read-only) before you begin QC** 
    * Open Disk Utility and check the Device name listed in the lower right corner

    * Mount drive read-only using the following command: 

    ```
      diskutil mount readOnly device name as listed in Disk Utility
    ```
## Logging QC Failures & Flags
  * Use the Definitions below to review and mark-off the items listed in the QC log.
    * **Be as concise as possible when noting questions and errors, so MPA does not have to double-check or clarify with you before compiling notes for Vendors.** 
    * Feel free to add rows for additional assets if you encounter more errors when troubleshooting. Rows are ‘per bag’.
    * When QC is complete, send an email to notify MPA / Asst Mgr. that there are some items to review. They will compile all notes for a shipment into a single email and communicate to the vendor. Note: Try to troubleshoot errors to make sure you’re not missing something about the nature of the tape that would impact the quality or structure of the file or metadata, e.g. if it was a very poor quality tape and they baked it twice and cleaned it and tried it on multiple machines.

    * Definitions
      * Question: A question which will help determine whether an item should be reworked or not. Example:
        * Freeze frame at the head of the Preservation Master, not noted in the JSON signalNotes. Is this freeze-frame recorded in on-tape?
      * *Flag*: A moderate or minor error that is concerning but that DOES NOT require rework, but does require. Examples:
        * An audio Edit Master was not levelled-out. The volume level is the same as the Preservation Master, which is lower than the ideal listening volume.
        * Audio channels in a video Service Copy were not mixed down the audio from the single channel audible in the Preservation Master, so Service Copy only has one channel of audible content.
      * *Fail*: A severe, systematic, or critical error that you think will most likely require retransfer, updating of metadata, and/or rebagging. Examples:
        * The metadata for a video asset describes audible content, but the Preservation Master and Service Copy do not have audio.
        * An audio asset appears to sound entirely backwards (reversed content on a single face -f01 -was not split out into a separate Face -f02-)
      * Pass No errors, or any errors listed in the notes are inconsequential, inherent to tape, or only included as supplemental information for future cataloger inquiries.
      * Urgent / Systematic errors
        * If you notice that there is something consistently and terribly wrong with many files in a row, please notify MPA / Asst. Mgr immediately so we can notify vendor and avoid replicating the error in future deliverables ASAP. (e.g. the ’barcode’ field in the JSON files is consistently “000000000”, or the ‘duration’ values are all wrong, or every value for ‘filename’ is the same across an entire batch.)

## Bag Validation

  * Use ```validate_ami_bags.py``` in ami-tools to check Check bag Oxums, bag completeness, bag hashes, directory structure, filenames, and metadata. 
  * Due to the time required to validate a directory of Vendor bags, its best to let validate_ami_bags.py run overnight.  

```
python3 /path/to/ami-tools/bin/validate_ami_bags.py -d /Volumes/driveID/ --metadata --slow
```
  * Review any Bags that report as "not ready for ingest"

or...just validate JSON using one of two options:

## JSON Validation

  * Use ```json_validator.py``` in ami-scripts to confirm JSON files comply with [NYPL metadata specifications](https://nypl.github.io/ami-preservation/pages/ami-metadata.html). 

```
/path/to/ami-preservation/ami-scripts/json_validator.py -m /path/to/ami-metadata -d /Volumes/DRIVE-ID
```
or

```
ajv validate --all-errors --multiple-of-precision=2 --verbose -s /path/to/ami-metadata/versions/2.0/schema/digitized.json -r "/path/to/ami-metadata/versions/2.0/schema/*.json" -d "/Volumes/DRIVE-ID/*/*/data/*/*.json"
```

## Digital Asset Conformance

  * Use ```mediaconch_checker.py``` in ami_scripts to confirm media files comply with [NYPL digital asset specifications](https://nypl.github.io/ami-preservation/pages/ami-specifications.html).

The ami-preservation repo contains a directory, [qc_utilities](https://github.com/NYPL/ami-preservation/tree/master/qc_utilities). Within this are various scripts and tools, including the mediaconch scripts listed below which will generate 'pass/fail' logs in your home directory when run against a directory of media files.
```
python3 /path/to/ami-preservation/ami-scripts/mediaconch_checker.py -p /path/to/ami-preservation/qc_utilities/MediaconchPolicies -d /Volumes/DRIVE-ID
```
## Additional Checks 
  
### BEXT Check
  * **AUDIO ONLY**: Check a selection of FLAC for embedded metadata
  * Copy 5 .flac files delivered to Desktop and decode these new copies back to wav.
```
flac --decode --keep-foreign-metadata --preserve-modtime --verify input.flac
```
  * Check BEXT in newly decoded .wavs using BWF MetaEdit. **Discard .wavs and .flac copies after use.**
  
### RAWCooked Check
  * **FILM PMs ONLY**:
  * Check a selection of PMs for RAWCooked reversability:
  ```
  /path/to/ami-preservation/ami-scripts/rawcooked_check_mkv.py -d /Volumes/DRIVE-ID -p 20
  ```

## Wrap Up...
  
  * **IF APPROVED**:
    * Move the Trello Card to the proper list (passed / failed etc.)

## Pull MediaInfo
  * After manual QC is complete and all assets are approved, run mediainfo_extractor.py
  ```
  python3 /path/to/ami-preservation/ami_scripts/mediainfo_extractor.py -d /Volumes/DRIVE-ID -o /path/to/destination/folder/WorkOrderID.csv
  ```
  * For Vendor deliverables, fill out the projectID and workOrderID columns and copy the entire CSV log into the "mediaInfo" tab in the project sheet
   * Update QC status and check Due date in Trello Card; Move the Trello Card to the passed list
 
  * **IF NOT APPROVED**:
    * Mention MPC in Trello card for follow-up OR email vendor with QC feedback / issues (or send feedback to Manager to relay to vendor); include relevant CMS IDs or filenames.
&
    * Move Trello card to "Vendor: QC Review" or "IN-HOUSE: QC Review" list in Trello.
    * Vendor: MPC follow up with vendor about errors and resolve before approving shipments. 
    * In-house: Tag relevant engineer and MPC, and Manager on Trello Card. 

## Media Ingest Preparation

### Vendor 
  * Once QC is complete and approved, notify Digital Preservation and make arrangements to hand off hard drives so media files can be uploaded to EAVie. 


### In-House

[Need to complete]


  * Generating a QC list
Use Terminal to generate a QC list for each drive you are QCing by following the steps outlined [here](https://github.com/NYPL/ami-preservation/wiki/Resources#generating-a-qc-list).


  * Locate & Open QC log

**Each QC log should be easily found linked in Google Drive as an** _attachment in the Trello Card for the batch you are inspecting._ **If not, check with MPA.** _Tip: you can search for the drive ID / work order ID in the Trello search box._

  * Use the list of files that appears in the Google Sheet QC log (in the QClog tab) as your list of files to check.
  * Drop down menus are available for noting specific identifiable errors, and there is a free-text field for general notes.

# Tools
See our [Command Line Resources ](https://nypl.github.io/ami-preservation/pages/resources.html)for descriptions, usage, and installation instructions of various tools we use in this workflow.
