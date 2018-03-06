# PAMI Production Scripts

## Pull MediaInfo 

The following instructions will show you how to extract MediaInfo attributes using the `pull_mediainfo.py` script. Dependencies include: `python3` and `pymediainfo.` 

* Open Terminal on your Mac 

* Drag and drop the `pull_mediainfo.py` script into the window. Then enter the following script:
  ```
  -d /path/to/directory/ -o /path/to/file/filenameISworkorderID.csv
  ```

    * `-h` will show the instructions for the script
    * `-d` will run the script on a whole directory of files
    * `-f` will run the script on a single file
    * `-o` indicates the file path and name of the output csv 
    
    _Note: If you do not specify the full output file path, the .csv will either be saved to the home folder by default or to whichever directory you are currently in._

* The .csv will include the JSON names in the top line and the values from mediainfo below. This allows the fields to be matched properly when importing the file into Filemaker.

For instructions to Import MediaInfo Metadata into Filemaker, go to the [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).
