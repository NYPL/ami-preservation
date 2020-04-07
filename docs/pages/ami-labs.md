---
title: PAMI Labs
layout: default
nav_order: 4
---
Quick Resources:

[PAMI Digitization Scripts](https://github.com/NYPL/ami-preservation/tree/master/pami_scripts
)

[PAMI QC Scripts](https://github.com/NYPL/ami-preservation#pami-qc-scripts
)

[Packages and Software](https://github.com/NYPL/ami-preservation/wiki/resources#packages-and-software
)

[Scripts and Repos](https://github.com/NYPL/ami-preservation/wiki/resources#scripts-and-repos
)


# Audio

TBD

# Video

TBD

# Optical

## DVD Workflow

### Step 1: Make an ISO

Insert your DVD and unmount:
  * Open terminal, run `diskutil list`
  * Locate the disk identifier of your DVD (typically something like `disk1`)
  * Run `diskutil umount [DISK ID]`

Use ddrescue to create an ISO (`brew install ddrescue`) if needed:
  *  `ddrescue -b 2048 -r4 -v /dev/[DISK ID] [output ISO path] [output log
path]`

### Step 2: Make a single MP4 that represents all of the content on your ISO (a multi-step process, but safe and trustworthy for multi-title DVDs)
  * Open MakeMKV, and open your ISO
  * Select your output directory, and click `Make MKV`
  * Move all resulting MKVs into a single directory
  * Run dvd_concat.py on your directory `./dvd_concat.py -s [YOUR DIRECTORY] -d [output path for DVD]`
  * Rename MP4 according to NYPL convention, and delete all MKVs

# Post Digitization

## Metadata

### Import MediaInfo Metadata into Filemaker

Open the FilemakerPro 15 database:

  * Click the `Layout` dropdown menu at the top left and select `tbl_techinfo`

  * From the taskbar at top of the screen, go to **File > Import Records > File...**
  
  * A window will open, find the file path of the extractedMediaInfo.csv that you just created and click **Open**

  * The `Import File Mapping` menu will appear. To properly import select:

    * `Don't Import First Record...`

    * `Arrange by` dropdown > `Matching Names`

  * Click  **Import**

  * The `New Import Options` menu opens, then select `perform auto-enter…`

  * Click  **Import**.

A menu will appear that says the records are imported, click **Okay**. This will give you the data set of all the files that you just imported. (Note: you will still be in the `tbl_techinfo` layout.)

  * In the first column to the left titled `inhouse_bag_batch_id`, copy and paste the _workorderID_ into the first empty field.

  * While the cursor is still in that field, click `Command +` (Mac) or `Control +` (Windows) which autofills the ID into the remaining fields in that column for all the records that were just imported.

  * The window `Replace Field Contents` appears, click **Replace**.

Notes: The _workorderID_ you add to the `inhouse_bag_batch_id` column in the `tbl_techinfo` layout must match the _workorderID_ in the `Master::production data entry` layout (to find this layout, go to top left `Layout` dropdown menu).

  * For example: the `asset.referenceFilename` column that contains the _workorderID_ in the `tbl_techinfo` layout must be identical to `asset.referenceFilename` column in the `Master::production data entry` layout.

  * Make sure to include the `_pm` and remove the `_ffv1` from the filename!

In the `Master::production data entry` layout, the appropriate file extension (i.e., the `asset.fileExt` column) must be preselected for the fields to populate appropriately.

  * To confirm everything entered correctly and sycned, sceroll right to ensure that all of the columns with `technical` information (i.e., `technical.durationHuman`, etc.) see if the correct fields are populated
