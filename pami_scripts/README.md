# PAMI Production Scripts

## csv_concat.py

For when cat ain't quite right. Will concat a directory of csvs, killing the first row of all but the first csv (so organize yourself carefully). Usage is typical:

 * `-d` for the directory of csvs
 * `-o` for the path and name of the output csv 
 
## csv_count.py

For counting up the number of files AND the number of unique CMS IDs in a chosen directory. Good for confirming large-scale files pulls that include a large number of multi-part audio. Will print in the terminal window, in order, the total number of files, the total number of CMS IDs, and a list of the CMS IDs. Note: currently only counts MP4s. Usage looks like:

* `./cms_count.py /Volumes/NYPL_16107/FreezeTest`

## file_pull.sh

For automating CMS collection-level file pulls. Will rsync a user-provided list of Service Copy MP4s or Edit Master Wavs from a hard drive, then transcode the Wavs to MP4s. To get started, you'll need a text file (recommend "make plain text") with your list of CMS numbers. Usage is script, CMS list, source directory, and destination. It looks like:

* `./file_pull.sh /Users/pamiaudio/Desktop/cmslist.txt /Volumes/NYPL230332 /Volumes/NYPL_16107/FreezeTest`

## pull_mediainfo.py

For pulling specific MediaInfo attributes from a bunch of files, making a csv. Dependencies include: `pymediainfo.` 

* Open Terminal on your Mac 

* Drag and drop the `pull_mediainfo.py` script into the window. Then enter the following:
  ```
  -d /path/to/directory/ -o /path/to/output.csv
  ```

    * `-h` will show instructions for the script
    * `-d` will run the script on a whole directory of files
    * `-f` will run the script on a single file
    * `-o` indicates the file path and name of the output csv 
    
    _Note: If you do not specify the full output file path, the .csv will either be saved to your current working directory._

* The .csv will include a top row of JSON schema terms, which will allow for proper matching upon FileMaker import.

For instructions on importing into Filemaker, see [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).
