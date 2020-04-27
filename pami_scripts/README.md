# PAMI Production Scripts

## audio_decoder.py

For transcoding a JSON directory of FLAC files back to Broadcast WAV (but why would you wanna do that?). Usage:

* `./audio_decoder.py -s /Users/benjaminturkus/Desktop/flac -d /Users/benjaminturkus/Desktop/wav`

## audio_transcoder_excel.py

For transcoding a legacy spreadsheet directory of WAV files to FLAC. Will copy over any spreadsheets included in a source Metadata directory and will bag upon completion. Usage:

* `./audio_transcoder_excel.py -s /Users/benjaminturkus/Desktop/wav -d /Users/benjaminturkus/Desktop/flac`

## audio_transcoder_json.py

Same as above, but designed for new JSON directory structure. Will transcode all WAV files to FLAC (using the Flac Utility), copy over any JSON files, and will update all JSON to reflect the new specs of losslessly compressed files. Usage:

* `./audio_transcoder_json.py -s /Users/benjaminturkus/Desktop/wav -d /Users/benjaminturkus/Desktop/flac`

## classmark2cms.py

For using a list (.txt) of old classmark idenitifiers to determine appropriate CMS IDs for file pulls (use in conjunction with cms2hdd.py and filepull.sh). Requires (1) a master consolidated CSV of all JSON files ever produced as part of the AMI Initiative, and (2) a plain-text list of classmarks. Usage:

* `./classmark2cms.py /Users/benjaminturkus/Desktop/halprince/jsons.csv /Users/benjaminturkus/Desktop/halprince/prince.txt`

## cms_count.py

For counting up the number of files AND the number of unique CMS IDs in a chosen directory. Good for confirming large-scale files pulls that include a large number of multi-part audio. Will print in the terminal window, in order, the total number of files, the total number of CMS IDs, and a list of the CMS IDs. Note: currently only counts MP4s. Usage:

* `./cms_count.py /Volumes/NYPL_16107/FreezeTest`

## cms2hdd.py

For identifying which hard drives need to be gathered as part of a CMS collection-level file pull. For this to work, you'll need: (1) a master PAMI survey MediaInfo CSV (like the one you'll get from csv_concat.py), and (2) a plain-text list of CMS IDs. Will spit out a list of HDDs for you to pull files from (using file_pull.sh!). Usage:

* `./cms2hdd.py /Users/pamiaudio/Desktop/mastermediainfo.csv /Users/pamiaudio/Desktop/cms_tester.txt`

## csv_concat.py

For when cat ain't quite right. Will concat a directory of csvs, killing the first row of all but the first csv (so organize yourself carefully). Usage:

 * `./csv_concat.py -d /Users/benjaminturkus/Desktop/FileSurvey_201901` 
 * `-d` for the directory of csvs
 * `-o` for the path and name of the output csv 
 
 Alt/UNIX Method:
 
 * `head -1 director/one_file.csv > output csv   ## writing the header to the final file` 
 * `tail -n +2  director/*.csv >> output.csv  ## writing the content of all csv starting with second line into final file` 

## dv_concatenator.py

For automating the FFmpeg concatenation process for a directory of DV files (with .dv extension). Will first generate a mylist.txt of all DV files within a directory, and will then use that list to concatenate, copying the DV streams and creating a single DV file (named appropriately). NOTE: your DV clips should probably be named in the correct sequential order. Usage:

 * `./dv_concatenator.py -d /LiveCapture_clips/303648 -o /Users/benjaminturkus/Desktop/FileSurvey_201901` 
 * `-d` for the directory of DV clips
 * `-o` for the path and name of the output DV

## file_pull.sh

For automating CMS collection-level file pulls. Will rsync a user-provided list of Service Copy MP4s or Edit Master Wavs from a hard drive, then transcode the Wavs to MP4s. To get started, you'll need a text file (recommend "make plain text") with your list of CMS numbers. Usage is script, CMS list, source directory, and destination. Usage:

* `./file_pull.sh /Users/pamiaudio/Desktop/cmslist.txt /Volumes/NYPL230332 /Volumes/NYPL_16107/FreezeTest`

Note: if you're pulling files off of a hard drive that has thousands of Wavs on it, it may take some time for the rsyncing to begin. Go do something else.

## json_tester.py

An imperfect (but still incredibly useful) quality control script that will run a battery of tests on a directory of media and JSON files. Tests include: (1) media and JSON equivalency (does every media file have a corresponding JSON file?), (2) Preservation Master/Edit Master/Service Copy equivalency (does every PM have either a corresponding EM or SC?), (3) accuracy of MediaInfo represented in JSON files (testes for filename, format, and creation date accuracy). Will report on media files missing JSON, files that missing corresponding derivatives (or masters), and PSS/FAIL for every JSON file found. Usage:

 * `./json_tester.py -s /Volumes/NYPL_16107` 
 
## make_bags.sh

A copy of ami-tools script for bagging a bunch of directories. Usage:

* `cd into directory of directories to be bagged`  
* `./make_bags.sh *`

## NYPLpackage_noqctools.sh

Shell script for transcoding and packaging video files. Will be reworked in the future, but currently ONLY works with NTSC v210/mov (PAL v210/mov requires separate transcoding to FFV1/MKV). But will generate MP4s for both NTSC and PAL FFV1/MKV, and will move all files into their appropriate directories (PreservationMasters, ServiceCopies. AuxiliaryFiles, V210). Usage:

* `cd in chosen directory with v210/mov or FFV1/MKV`
* `./NYPLpackage_noqctools.sh *`

## pandas_stats.py

A very specific (but adaptable) script for FY annual reporting. Requires a master Excel files (DB export) of all FY projects, with MediaInfo information. Will report on: total # of files, total # of CMS objects, total data, total data by media type, average size, average size of MKVs and WAVs, total number of hours of content, average duration of MKVs and WAVs, total duration by media type, objects by media type, format and role breakdown, Division breakdown, CMS collection breakdown, CMS project breakdown, PAMI Staff breakdown, and PAMI equipment breakdown). 

Dependencies: Python module hurry.filesize (pip3 install hurry.filesize). Script also requires that your sheet be named "Sheet1."

Usage:

* `./pandas_stats.py /Users/benjaminturkus/Desktop/pamiaudio_desktop/stats/FY18Stats_PAMI.xlsx`

## pull_mediainfo.py

For pulling specific MediaInfo attributes from a bunch of files, making a csv. Dependencies include: `pymediainfo.` Usage:

 * `./pull_mediainfo -d /Volumes/NYPL_16107 -o /Desktop/NYPL_16107_mediainfo.csv
 * `-f` for single file
 * `-d` for the directory of media files
 * `-o` for the path and name of the output csv 
  
* The .csv will include a top row of JSON schema terms, which will allow for proper matching upon FileMaker import.

For instructions on importing into Filemaker, see [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).

## sep_by_specs.py

Kinda lame, but useful if you need to spearate a bunch of media files by a particular MediaInfo attribute (say, for example, splitting apart NTSC and PAL video files). Currently set up for separating NTSC and PAL MP4s (using frame rate as guide), but adaptable. Usage:

* `./sep_by_sepcs.py -s /Volumes/NYPL_16107/wilson/wilson_video -d /Volumes/NYPL_16107/wilson/wilson_fixer`

## transcoder.py

Video transcoder for legacy spreadsheet packages. Will transcode both NTSC and PAL v210/movs (from one HDD to another, if needed), creating correct FFV1/MKV versions. Will also copy over any spreadsheets located in a Metadata directory, and bag upon completion. NOTE: not currently set up to deal with DV/movs, so use with care. Usage:

* `./transcoder.py -s /Volumes/NYPL_16107/wilson/wilson_video -d /Volumes/NYPL_16107/wilson/wilson_fixer`




