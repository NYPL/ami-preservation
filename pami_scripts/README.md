# PAMI Productions Scripts

## pull_mediainfo.py

The following instructions will allow you to extract the appropriate metadata using the `pull_mediainfo.py` script and to import the metadata into the FilemakerPro 15 database. This script requires `python3` and `pymediainfo,` which allow for  interaction with the MediaInfo Library. 

* Open Terminal on your Mac 

* Drag and drop the `pull_mediainfo.py` script into the window. Then enter the following script:
  ```
  -d /path/to/directory/ -o /path/to/file/filenameISworkorderID.csv
  ```

    * `-h` will show the instrucitons for the script
    * `-d` runs the script on a whole directory of files
    * `-f` runs the script on a single file
    * `-o` indicates the file path where you want to output the .csv and the name of the .csv
    
    _Note: If you do not specify the full output file path, the .csv will either be saved to the home folder by default or to whichever directory you are currently in._

* The .csv will include the JSON names in the top line and the values from mediainfo below. This allows the fields to be matched properly when importing the file into Filemaker.

For instructions to Import MediaInfo Metadata into Filemaker, go to the [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).
