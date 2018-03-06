# PAMI Production Scripts

## pull_mediainfo.py

The following instructions will show you how to extract select MediaInfo attributesusing the `pull_mediainfo.py` script. Dependencies include: `python3` and `pymediainfo.` 

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

* The .csv will include a top row of JSON schema terms, which will allow for  proper matching upon FileMaker import.

For instructions on imporitng into Filemaker, see [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).
