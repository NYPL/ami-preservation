---
title: Command Line Resources
layout: default
nav_order: 9
---
# Resources
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Packages and Software

**NOTE: Be aware of where on your computer you are installing scripts. If you are not familiar with command line tools and usage, please ask for help before installing anything.**

* Download Microsoft Office / Open Office
* Applications:
   * Atom
   * Firefox
   * Chrome
   * [Homebrew](https://brew.sh/)

* MediaInfo:
   ```
   brew install mediainfo
   ```
* Git:
   ```
   brew install git
   ```
* ffmpeg - install with flags listed below:
   ```
   brew install ffmpeg --with-sdl2 --with-freetype --with-openjpeg --with-x265 --with-rubberband --with-tesseract
   ```
   * Good instructions on Reto Kramer's [website.](https://avpres.net/FFmpeg/)

* Pip:
   * First, check that you have pip installed:
      ```
      pip --version
      ```
   * If you get a version number, you can install BagIt Python (skip the pip instructions below and move on to installing bagit). If you get a message that pip isn’t installed, install pip:
      * Go to https://pip.pypa.io/en/stable/installing/
      * Click on the hyperlinked “get-pip.py”.
      * A tab should open that looks like a text file – save the page (Command-S) to a specific place on your computer (Desktop / Downloads / Home folder etc.).
      * In Terminal, `cd` into the directory where you downloaded the script.
      * Run the script:
        ```
        python path/to/get-pip.py
        ```
      * Pip should now be installed.

* Python 2.7.12 (for bagit) & python3 (for other things)
   * Go to https://www.python.org/downloads/mac-osx/ and install Python 2.7.12.
   * Then install:
     ```
     Brew install python3
     ```
   * Note: this also installs pip3, which you need in order to install python3 scripts below)

* Bagit Python (install both)
   ```
   pip install bagit
   ```
   ```
   pip3 install bagit
   ```

* Pymediainfo
   ```
   pip3 install pymediainfo
   ```

* Mediaconch & Mediaconch CLI
   * Install the [Media Conch GUI](https://mediaarea.net/MediaConch/) then:
      ```
      brew install mediaconch
      ```

* QC Tools
   * Go to https://bavc.org/preserve-media/preservation-tools
   * QCtools reports / QCparse - not in use yet, but have been tested; are installed on c03 corner Mac
      ```
      brew install qcli
      ```
=======

## Scripts and Repos

### Github Repos

#### **[ami-metadata](https://github.com/NYPL/ami-metadata)**
* Dependencies:
   * Npm & ajv:
     ```
     brew install npm
     ```
   * Then, in Terminal:
     ```
     npm install -g ajv-cli
     ```
* For json schema validation & development. See usage instructions on GitHub.

#### **[ami-tools](https://github.com/NYPL/ami-tools)**
   _Many different scripts, mostly for bagit-related repair & validation tasks_
   * `pip3 install .` (Be sure to include the ".")
   This should automatically install the following dependencies (but here they are just in case):
      * `tqdm`
      * `xlrd`
      * `Openpyxl`
   * `Survey_drive.py`
   This will create a series of reports on a specified drive:
      * Mount drive
      * Open Terminal
      * `cd ami-tools`
      * `python3 path/to/survey_drive.py -d path/to/Volume -o path/to/location_for_Reports`

#### **make_bags.sh**

   For making a lot of directories into bags overnight.

   * https://github.com/genfhk/ghk-sandbox/tree/master/make_bags
   * Usage:
      * `cd path/to/dir/of/bags`
      * `/path/to/script (enter)`
   * _Note: Be sure to update the log-drop location in this script for your own machine, or it won’t work (until new version merged in ami-tools repo)._

#### **check_mediainfo.py**
   * Usage:

      ```
      python3 /path/to/check_mediainfo.py -d /path/to/dir/with/bags -f _filename.mp4
      ```
   * Currently this script is set to check files that have fewer than 2 audio channels (as reported by mediainfo), but this may be changed, enhanced for other fields / values, etc.

#### **repair_bag.py / Fix_baginfo.py**

   Use Case: Adding metadata file to a single Bag and repairing the manifests

   1. Add completed metadata file to the bag in the appropriate directory
   1. *Optional*

      ```
      Python3 path/to/repair_bags.py -b /path/to/bag --deletefiles
      ```
   1.  (this will delete the .DS_Store 's)
   1. Run `repair_bags.py`:

      ```
      Python3 path/to/repair_bags.py -b /path/to/bag --addfiles
      ```

      (this will update the manifest with any new files)
   1. Check if bag is complete using bagger or `validate_bags.py` (only checks bag ‘completeness’  - not checksum validation, but theoretically should be good enough):

      ```
      Python3 path/to/validate_ami_bags.py -b /path/to/bag
      ```
   *Note: The above scripts can be used for checking directories of bags or single bags, by using `-d` for directories and specifying the parent directory containing the bags, or `-b` for bag and specifying just the bag directory.*

### ffmpeg

#### **Audio**

   * In-house Audio Edit Master > AWS Audio Edit Master / Service Copy (audio as mp4):
     * *[individual file version]*:
       ```
       ffmpeg -i path/to/input_em.wav -c:a aac -b:a 320k -dither_method rectangular -ar 44100 path/to/name-of-output_em.mp4
       ```

     * *[directory of files version]*:
       ```
       for file in *wav ; do ffmpeg -i "$file" -c:a aac -b:a 320k -dither_method rectangular -ar 44100 "${file%.*}.mp4" ; done
       ```

### MediaConch

- **Option A (Mac only):** Use MediaConch CLI to ensure that files meet NYPL specifications
    - Check that MediaConch CLI is installed. If it is not, install it.
    - If you’ve cloned the ami-tools Github repo, you can find all of NYPL’s MediaConch Policies within the ami-files directory. Otherwise, they can be found on ICC.
    - Basic terminology is to use the “find” command to locate the type of file you’ll be cross-checking against the policy (.mkv, .wav, etc.), and then applying the relevant MediaConch policy. Open Terminal to run the following commands for the specific media type & file roles you are inspecting.
    - The CLI report is output as a .csv file. Move this file into the log folder for the batch you are reviewing.
   * The MediaConch GUI should be downloaded for checking individual files and for general purposes.

#### MediaConch Command-line

   | Media Type | File Role | Commands |
   |------------|:---------:|:---------|
   | Video | PM | `cd /Volume/DRIVEID/` `find ./ -name "*.mkv" -exec mediaconch -p path/to/video_PM_policy.xml "{}" \; > /path/to/ICC/DRIVEID_Medicaconch_PMs.csv` |
   | Video | SC | `cd /Volume/DRIVEID/` `find ./ -name "*.mp4" -exec mediaconch -p path/to/video_SC_policy.xml "{}" \; > path/to/ICC/DRIVEID_Medicaconch_SCs.csv` |
   | Audio | PM | `cd /Volume/DRIVEID/` `find ./ -name "*_pm.wav" -exec mediaconch -p path/to/audio_PM_policy.xml "{}" \; > path/to/ICC/DRIVEID_Medicaconch_PMs.csv` |
   | Audio | EM |  `cd /Volume/DRIVEID/` `find ./ -name "*_em.wav" -exec mediaconch -p path/to/audio_EM_policy.xml "{}" \; > path/to/ICC/DRIVEID_Medicaconch_EMs.csv` |

- **Option B:** Use MediaConch GUI to check a selection of Preservation Master files, or a single file, against the NYPL PAMI Preservation Master policy.Under “Check Files”:
    - Select the NYPL Policy from the drop down list for the appropriate media type you are inspecting (analog / digital, audio / video)
    - Select Display MediaConch HTML
    - Choose Files: Select multiple PMs all at once &gt; done
    - Click “Check Files” on the ‘Checker’ interface
    - Adjust the number of items viewed in the list to 100 (upper left hand corner of results)
#### MediaConch Failures Procedure

  - CLI: _TBD_
    - Review the JSON metadata for the files to see if there are attributes of the file or source object that would require you to use a different policy for those specific Preservation Master files.
    - If there definitely is something wrong with the file, if it is critical and appears systematic, notify vendor immediately to prevent creation of more bad files. If it seems like a one-off, make note of it in the log and save for the full QC report on the entire shipment/invoice.

  - GUI:
    - Under “Results”, VIEW the report by clicking the ```[[SYMBOL GOES HERE]]``` symbol in the column under “Policy”. You can display the report in different formats using the “Display” drop down menu provided in the viewing window. MediaConch Text / HTML are easiest on the eyes.

**MEDIACONCH SCREENSHOT GOES HERE**

*Media Conch GUI, with PAMI Policy & “Download policy report” bubble showing.*

  - *Note on MediaConch limitations & Interlacing* MediaInfo does not always adequately report all characteristics of a file (or may report them incorrectly). If a file fails, review the report to see why it failed. Investigate and determine whether there is actually something wrong with the file, or just a flaw / glitch with the software / policy.
  - For more accurate confirmation of interlacing / Scan Type, use Ffmpeg - run the following command, which checks the field dominance of the first 1000 frames of video: ```ffmpeg -filter:v idet -frames:v 1000 -an -f rawvideo -y /dev/null -ipath/to/file.mov```

### Generating a QC list

  - ```Cd /path/to/Audio``` or Video directory
  - ```ls Audio/Video &gt; path/to/log/folder/batchID_assetlist.csv```
  - [Import csv into google sheets qc log created from template:]
    - The QC template has built-in formulas in the “list” tab.
        - Navigate to the “asset list” .csv file for the drive you are QCing.
        - Navigate to the “list” tab in your QC log
        - **Select the proper cell for either Audio or Video media that you are importing data for (i.e. if you’re importing an AUDIO asset list, select the audio cell as instructed in the log).** _The two cells have different formulas applied for the different quotas we are meeting for audio vs. video data (5% audio vs. 10% video)_
        - Once you’ve selected the cell, import _assetlist.csv_ into A1 of the “list” tab of the existing Google Sheets QC log (File>Import>Upload a file)  
            - Select **“Replace contents starting with selected cell”** and **“comma separated”** when the dialog window appears (because you are importing a .csv)
        - The line items will then be imported into the sheet, and the column next to it will generate a filtered list. This is your spot checking list.  
        - Copy/Paste Special>”Paste values only” the list of filtered Primary IDs into the “QClog” tab, in the Primary ID column. Do this for one media type at a time. (i.e. if there are both audio and video assets on a single drive, first copy the audio items list, then copy the video items list below it.
    - Proceed with spot checking.

### Content Inspection

#### General Overview

- Software requirements:
    - Text editor (Atom, Text Edit, Notepad all equally fine)
    - VLC


- Content inspection can be completed either on ICC or on the drive.  
   - **On ICC:** _make sure your machine is not going to create DS_Store files or Thumbs.db files inside bags._  
      - Locate the directory that contains batch to QC in the 3_Ready_To_QC folder, if assigned by MPA.
      - Follow the below instructions (skip “Mount Read Only” section)

    - **On Hard Drive:** _Mount Drive Read Only_ before opening any directories, and follow the below instructions

#### Formatting Hard Drives exFAT
See: https://joshuatj.com/2015/05/13/how-to-format-your-hard-drive-hdd-for-mac-os-x-compatibility-with-the-correct-exfat-allocation-unit-size/
* allocation unit size: 128kb
#### Spot Checking Content & JSON

  - Open and inspect JSON file using a text-editor (Atom / Notepad / Text Edit etc.) to ensure that:
    - There is one JSON file for each digital asset created from a physical object
    - JSON files are named properly  
    - All elements are properly structured
    - All fields contain values (except “bibliographic date”, which is allowed to be left empty).
    - Technical characteristics/configurations noted in JSON make sense for what you are hearing / seeing. *Note:* if content quality is questionable, make sure to check whether item was cleaned/baked/in poor condition. This will give perspective on the quality of the file.

 - Check files for anomalies
    - Manually check 30sec sections at beginning, middle, end of each file.

        - Things to consider when working with audio files:  
            - No 5 second overlap between heads and tails of Parts or Regions  
            - Reversed content that was not transferred as a separate region
            - Tip: _For a quick check of the entire drive for objects with Regions, grep the directory for “p01” or “r01”_

        - Things to consider when working with video files:
             - Service Copy plays and does not contain transcoding errors / is not corrupt.

#### Logging QC Failures & Flags

Use the Definitions below to review and mark-off the items listed in the QC log.
  - **Be as concise as possible when noting questions and errors, so MPA does not have to double-check or clarify with you before compiling notes for Vendors.**
  - Feel free to add rows for additional assets if you encounter more errors when troubleshooting. Rows are ‘per bag’.  
  - When QC is complete, send an email to notify MPA / Asst Mgr. that there are some items to review. They will compile all notes for a shipment into a single email and communicate to the vendor. **Note:** Try to troubleshoot errors to make sure you’re not missing something about the nature of the tape that would impact the quality or structure of the file or metadata, e.g. if it was a very poor quality tape and they baked it twice and cleaned it and tried it on multiple machines.

##### Definitions

  - *Question:* A question which will help determine whether an item should be reworked or not. Example:
    - Freeze frame at the head of the Preservation Master, not noted in the JSON signalNotes. Is this freeze-frame recorded in on-tape?

  - *Flag:* A moderate or minor error that is concerning but that DOES NOT require rework, but does require. Examples:
    - An audio Edit Master was not levelled-out. The volume level is the same as the Preservation Master, which is lower than the ideal listening volume.
    - Audio channels in a video Service Copy were not mixed down the audio from the single channel audible in the Preservation Master, so Service Copy only has one channel of audible content.

  - *Fail:* A severe, systematic, or critical error that you think will most likely require retransfer, updating of metadata, and/or rebagging. Examples:  
    - The metadata for a video asset describes audible content, but the Preservation Master and Service Copy do not have audio.  
    - An audio asset appears to sound entirely backwards (reversed content on a single face -f01 -was not split out into a separate Face -f02-)

  - *Pass* No errors, or any errors listed in the notes are inconsequential, inherent to tape, or only included as supplemental information for future cataloger inquiries.
##### Urgent / Systematic errors

- If you notice that there is something consistently and terribly wrong with many files in a row, please notify MPA / Asst. Mgr immediately so we can notify vendor and avoid replicating the error in future deliverables ASAP. _(e.g. the ’barcode’ field in the JSON files is consistently “000000000”, or the ‘duration’ values are all wrong, or every value for ‘filename’ is the same across an entire batch.)_

#### Media Ingest Preparation

- Make sure all logs are stored on ICC
- Update STATS 3
- Move Trello card to proper list - Passed QC / Hold for Vendor Response (if flags / fails)
- Store drive on proper shelf in C10:
  - Shelf 1 = there is a “Passed QC” level in here
  - Shelf 9 = there is a “Hold for Vendor response” level in here.  
  - _Alternatively, give the drive back to the MPA / Asst. Mgr. or leave it on their desk and send an email._

[QC complete! - if there are failures, all failures in an entire shipment will be combined and sent as a single email; report them to the MPA]


## .DS_Store Files

#### Prevent creation of .DS_Store files on network shares

   **Run in Terminal:**
   * `defaults write com.apple.desktopservices DSDontWriteNetworkStores -boolean true`

   **Run to check if it worked:**
   * `defaults read com.apple.desktopservices DSDontWriteNetworkStores`

     Should return “true” or “1”

#### Remove .DS_Store files

   * `cd [path to volume you want to clean] [enter]`
   * `find . -name '.DS_Store' -type f -delete [enter]`

     *Volume must be made writeable (be sure to put back to Read Only!), and you must not have anything in it selected in Finder - best not to open it in finder at all.*

   * Disable .DS_Store files on MacOS El Capitan:

     http://pixelcog.com/blog/2016/disable-ds_store-in-el-capitan/

   * Prevent creation of .DS_Store files on network shares:

     `defaults write com.apple.desktopservices DSDontWriteNetworkStores -boolean true`

   * Check if it worked:

     `defaults read com.apple.desktopservices DSDontWriteNetworkStores`

     (Should return “true” or “1”)

## Transcoding and Packaging for In-House Video Files

   A transcoding and packaging bash script (NYPLpackage.sh) that does it all (transcodes MKVs, MP4s, generates QCTools Reports, Framemd5 checksums, and packages all in the appropriate directory structure) is around for general use, but occasionally you may need to transcode single files or small groups of files. The following commands will help:

**To make an MKV from an uncompressed source:**

   * NTSC

     ```
     ffmpeg -i input_file -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order bt -vf setfield=bff,setdar=4/3 -color_primaries smpte170m -color_range tv -color_trc bt709 -colorspace smpte170m -c:a flac output_file.mkv
     ```

   * PAL

     ```
     ffmpeg -i input_file -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order tb -vf setfield=tff,setdar=4/3 -color_primaries bt470bg -color_range tv -color_trc bt709 -colorspace bt470bg -c:a flac output_file.mkv
     ```

**Batch version:**

   * NTSC:

       ```
       for file in *.mov ; do ffmpeg -i "$file" -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order bt -vf setfield=bff,setdar=4/3 -color_primaries smpte170m -color_range tv -color_trc bt709 -colorspace smpte170m -c:a flac "${file%.*}.mkv" ; done
       ```

   * PAL

       ```
       for file in *.mov ; do ffmpeg -i "$file" -map 0 -dn -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slicecrc 1 -slices 24 -field_order tb -vf setfield=tff,setdar=4/3 -color_primaries bt470bg -color_range tv -color_trc bt709 -colorspace bt470bg -c:a flac "${file%.*}.mkv" ; done
       ```

**To make an MP4:**

  ```
  ffmpeg -i input_file -map 0:a -map 0:v -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000 -aspect 4:3 output_file.mp4
  ```

**Batch version:**

  ```
  for file in *.mkv ; do ffmpeg -i "$file" -map 0:a -map 0:v -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000 -aspect 4:3 "${file%.*}_sc.mp4" ; done
  ```

**Batch version w/ pan left to center:**

  ```
for file in *mkv ; do ffmpeg -i "$file" -c:v libx264 -movflags faststart -filter_complex '[0:v]yadif[outv];[0:a]pan=stereo|c0=c0|c1=c0[outa]' -map '[outv]' -map '[outa]' -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -c:a aac -strict -2 -b:a 320000 -ar 48000 -aspect 4:3 "${file%.*}_sc.mp4" ; done
  ```

**Batch version w/ pan right to center:**

  ```
for file in *mkv ; do ffmpeg -i "$file" -c:v libx264 -movflags faststart -filter_complex '[0:v]yadif[outv];[0:a]pan=stereo|c0=c1|c1=c1[outa]' -map '[outv]' -map '[outa]' -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -c:a aac -strict -2 -b:a 320000 -ar 48000 -aspect 4:3 "${file%.*}_sc.mp4" ; done
  ```


**To make a Prores 422 HQ from an uncompressed or lossless source:**

```
ffmpeg -i input_file -map 0:a -map 0:v -c:v prores -profile:v 3 -vf yadif -c:a copy output_file.mov
```

**Batch version:**

```
for file in *.mkv ; do ffmpeg -i "$file" -map 0:a -map 0:v -c:v prores -profile:v 3 -vf yadif -c:a pcm_s24le "${file%.*}_prores.mov" ; done
```

**Rsyncing JSON and JPEGS:**

  `rsync -rtv /DRIVEID/*/*/data/*/*.json /path/to/destination`

  `rsync -rtv /DRIVEID/*/*/data/*/*.jpg /path/to/destination`

Occasionally, this will result in an “argument list too long” error (mostly a problem with audio drives, which can contain thousands and thousands of files). In these cases, the following will work:

  `find DRIVEID/ -name '*.json' -exec rsync -rtv --progress {} /path/to/destination ';'`

  `find DRIVEID/ -name '*.jpg' -exec rsync -rtv --progress {} /path/to/destination ';'`

## MPV

   Install mpv: https://mpv.io/installation/

## wget

   For FTP and other types of file transfer

   * Brew install wget:

     `wget -r 'ftp://username:password@ip/directoryname'`
   * Directory is cloned onto your current working directory

## Formatting Harddrives

   * `Brew cask install fuse`

   * `Brew install ntfs3g`

## Commands

   The following commands come in handy when troubleshooting specific errors, json failures, or preparing a machine for doing QC work.

### Mounting Drives Read-Only
The most important step during QC.

  * Open Terminal
  * Open Disk Utility
  * Plug in/turn on hard drive
  * Unmount using Disk Utility (or using Terminal command ‘umount’)
  * Make note of diskID:
    * In Disk utility, click “info” or select the drive on the list and type ‘command+i’
      * or use Terminal command ‘list’
  * In Terminal, type the following, where “diskID” = the diskID you just found (i.e. disk1s2):
    * Diskutil mount readOnly diskID
  * Your disk should be mounted read-only now

### JSON Validation

  - Run the following command(s) in Terminal to check if JSON is valid against schema
    - ```cd path/to/ami-metadata```
    - ```ajv validate -s path/to/versions/#.#/schema/digitized.json -r "versions/#.#/schema/*.json" -d "dir_of_bags/*/data/*/*.json"```
    - Select entire output of validation and export as DRIVEID_jsonvalidationlog.txt into log folder
    - ```grep -o -c -i -h -r invalid  path/to/ICC/Logs/Project/DRIVEID_jsonvalidationlog.txt```

  - **JSON invalid?:**
    - Run validation on individual failed files to retrieve specific errors and create a list to send failure report to vendor.  
        - To check for further errors, you must copy the file, fix the first error on the copy version, and validate the copy to see if more errors pop up - the validator will fail a file at the first error it encounters and stop there.

### Creating New HDmanifests

   These commands will create manifests for all files, excluding all subdirectories and BagIt related files. You can add/remove file types within the `-iname` flags to include or exclude other types.

#### Create a new HDmanifest for an Audio directory

   * `cd /Volumes/DRIVEID`
   * `find Audio/ -type f \( -iname "*.wav" -or -iname "*.json" \) > path/to/dest.csv`

#### Create a new HDmanifest for an Video directory

   * `cd /Volumes/DRIVEID`
   * `find Video/ -type f \( -iname "*.mkv" -or -iname "*.mp4" -or -iname "*.json" \) > path/to/dest.csv`

### Parsing Files and Reports

#### Move JSON / JPGs

   * `rsync -rtv /DRIVEID/*/data/*/*.json /path/to/destination`

   * `rsync -rtv /DRIVEID/*/*/data/*/*.jpg /path/to/destination`

   Occasionally, this will result in an “argument list too long” error (mostly a problem with audio drives, which can contain thousands and thousands of files). In these cases, the following will work:

   * `find DRIVEID/ -iname '*.json' -exec rsync -rtv --progress {} /path/to/destination ';'`

   * `find DRIVEID/ -iname '*.jpg' -exec rsync -rtv --progress {} /path/to/destination ';'`

#### Grep JSON

The Grep tool can be used for many things, including:
   * Parsing the ‘Logs’ folder on ICC to find the drive that contains a certain Bag
   * Performing mass fixes on specific recurring errors
   * Identifying all files with a known error, to make a list of things to fix / rework

   `grep -i -H -R "someString" Volumes/HardDrive/*/*/data/*/*.json`

   OR

   `Cd dir/of/bags/`

   `find . -name "*.json" | xargs grep "audio cassette digital"`

  *This recursively searches for specific text in a json file and returns the line of text as well as the filename and path containing the text. Use * to mark any directories that will have variable names (such as objects / bags)*

#### Grep Validation Logs

  The following are examples for parsing the json validation log and bag validation log for `invalid` objects.

   * `grep -i -H -R "invalid" path/to/jsonvalidationlog.txt`

   * `grep -i -H -R "invalid" path/to/validationLogFile.log`

## Google Sheet formulas:

### Return content/value after 'nth' character in a cell
`=RIGHT(A1,LEN(A1)-5)`
(where A1 is the source cell. Adjust number of characters from "-5" to match the number of characters you want to omit from new cell)

### Flag items that aren’t in a specified range
Insert the following formula next to a cell you’d like to confirm is in a given column. If the cell is not in the given column, it will return the value of that cell (which would enable you to create a filtered list of all items that show up as missing from the column).
`=IF(COUNTIF($C:$C, $B4)=0, B4, "")`

### Color-code duplicates in a range of columns
* Select range of columns (this works best with a small rage, where there are very few columns to consider, like 2)
* `ctrl-click` and select `conditional formatting` for just that range.
* Use custom formula below & set desired color of cell / formatting (where A:B is the range - adjust for different ranges):

`=COUNTIF($A$1:$B$1031, INDIRECT(ADDRESS(ROW(), COLUMN(), 4))) > 1`

  * Good for performing check-in of physical assets (to confirm that the original list of items has been scanned
  * Finding duplicates between two lists, i.e. the DNC list from one batch to another to make sure projects aren’t getting mixed up
  * Checking between a list of items that have been QC’d vs total items

### Creating a filtered list divided by a number (for 10%, 20% etc.)

### Query for cell content

   * `=QUERY( C1:C, "Select C Where C contains 'f01r01_pm.wav' " )`
        * Syntax = ([range], “Select [column in range] Where [same column in range] contains ‘[string]’ ” )

## Working with tars
For many years, the standard PAMI workflow was to tar (create a _(t)ape (ar)chive_, or "tarball") any complexly structured AMI deliverables. Typically, this was used for born digital original documentation, and by creating a singular file (with a .tar extension) that could stand in for multiple files and directories, we were able to achieve certain measure of control, consistency, and ease of movement/storage. The tar manual (`man tar`) offers a full list of options/flags, but here are some helpful commands:

### Creating tars
To create a tarball without compression:
```
tar -cvf mytar.tar input_directory
```
To create a tarball with gzip compression:
```
tar -czvf mytar.tar input_directory
```
The `-c` flag specifies the creation of a tar, `-v` the verbose output printed to your terminal window, `-z` the gzip compression, and `-f` the specified file that will be written to or read from.

### Examining tars
To get a list of all files and directories within a tar (with permissions and file sizes):
```
tar -tvf mytar.tar
```
Without permissions and file sizes:
```
tar -tf mytar.tar
```
To list all files (but not directories):
```
tar -tvf --exclude=".*" mytar.tar
```
Batching (output to csv):
```
find ExcelBornDigital/ -name '*.tar' -exec tar -tzf {} --exclude=".*" ';' > /Users/pamiaudio/Desktop/ICA_borndigital.csv
```

### Extracting files from tars
To extract a file from a tar:

`cd` into the directory in which you'd like to copy the file, and  

```
tar -xvf mytar.tar myfile.ext
```

Some things to note:
* The tar will still be intact; the file will simply be copied to your chosen location
* You'll need the full file path (which you can get by using the -tf command)
* Tar is picky about spaces, so you may need to transform something like this:
```
Volumes/lpa/Working Storage/Transfer/2 - Ready for Finishing/zUnprocessedOrigidocsDAN/myd_mgzidvd57093_v01/Capture Scratch/Alvin Ailey 2012/CAM A4.mov
```
* To something like this:
```
Volumes/lpa/Working\ Storage/Transfer/2\ -\ Ready\ for\ Finishing/zUnprocessedOrigidocsDAN/myd_mgzidvd57093_v01/Capture\ Scratch/Alvin\ Ailey 2012/CAM\ A4.mov
```

## Performing a Clean Installation for Apple Computers

* Open terminal, run: sysadminctl interactive -secureTokenOn [admin user shortname] -password -
* Then run: diskutil apfs updatePreboot /
* Plug in bootable installer (USB)
* Boot in recovery mode (hold command + R when restarting)
* Open Startup Security Utility, change external boot settings
* Click on new OS (Big Sur)
* Open Disk Utility, wipe Macintosh HD
* Close Disk Utility, restart computer holding Option key at first ding
* Install new OS

