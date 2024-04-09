---
title: Command Line Resources
layout: default
nav_order: 4
---
# Resources
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Packages and Software

Nearly all macOs software required for AMI Preservation can be installed with the **[digarch-software-script](https://github.com/NYPL/digarch_scripts/blob/main/digiarch-software-script)**


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

#### **[ami-tools](https://github.com/NYPL/ami-tools)**
   _Many different scripts, mostly for bagit-related repair & validation tasks_

   * `pip3 install --user 'ami-tools @ git+https://github.com/NYPL/ami-tools'` 


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
#### General Overview

- Software requirements:
    - Text editor
    - VLC


- Content inspection can be completed either on ICC or on the drive.  
   - **On ICC:** _make sure your machine is not going to create DS_Store files or Thumbs.db files inside bags._  
      - Locate the directory that contains batch to QC in the 3_Ready_To_QC folder, if assigned by MPA.
      - Follow the below instructions (skip “Mount Read Only” section)

    - **On Hard Drive:** _Mount Drive Read Only_ before opening any directories, and follow the below instructions

#### Formatting Hard Drives exFAT
See: https://joshuatj.com/2015/05/13/how-to-format-your-hard-drive-hdd-for-mac-os-x-compatibility-with-the-correct-exfat-allocation-unit-size/
* allocation unit size: 128kb


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

   * Prevent creation of .DS_Store files on network shares:

     `defaults write com.apple.desktopservices DSDontWriteNetworkStores -boolean true`

   * Check if it worked:

     `defaults read com.apple.desktopservices DSDontWriteNetworkStores`

     (Should return “true” or “1”)

## Transcoding and Packaging for In-House Video Files

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
  ffmpeg -i input_file -map 0:a -map 0:v -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000 output_file.mp4
  ```

**Batch version:**

  ```
  for file in *.mkv ; do ffmpeg -i "$file" -map 0:a -map 0:v -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000  "${file%.*}_sc.mp4" ; done
  ```

**Batch version w/ pan left to center:**

  ```
for file in *mkv ; do ffmpeg -i "$file" -c:v libx264 -movflags faststart -filter_complex '[0:v]yadif[outv];[0:a]pan=stereo|c0=c0|c1=c0[outa]' -map '[outv]' -map '[outa]' -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -c:a aac -strict -2 -b:a 320000 -ar 48000 "${file%.*}_sc.mp4" ; done
  ```

**Batch version w/ pan right to center:**

  ```
for file in *mkv ; do ffmpeg -i "$file" -c:v libx264 -movflags faststart -filter_complex '[0:v]yadif[outv];[0:a]pan=stereo|c0=c1|c1=c1[outa]' -map '[outv]' -map '[outa]' -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -c:a aac -strict -2 -b:a 320000 -ar 48000 "${file%.*}_sc.mp4" ; done
  ```


**To make a Prores 422 HQ from an uncompressed or lossless source:**

```
ffmpeg -i input_file -map 0:a -map 0:v -c:v prores -profile:v 3 -vf yadif -c:a copy output_file.mov
```

**Batch version:**

```
for file in *.mkv ; do ffmpeg -i "$file" -map 0:a -map 0:v -c:v prores -profile:v 3 -vf yadif -c:a pcm_s24le "${file%.*}_prores.mov" ; done
```

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


### Creating New HDmanifests

   These commands will create manifests for all files, excluding all subdirectories and BagIt related files. You can add/remove file types within the `-iname` flags to include or exclude other types.

#### Create a new HDmanifest for an Audio directory

   * `cd /Volumes/DRIVEID`
   * `find Audio/ -type f \( -iname "*.wav" -or -iname "*.json" \) > path/to/dest.csv`

#### Create a new HDmanifest for an Video directory

   * `cd /Volumes/DRIVEID`
   * `find Video/ -type f \( -iname "*.mkv" -or -iname "*.mp4" -or -iname "*.json" \) > path/to/dest.csv`

### Parsing Files and Reports

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
