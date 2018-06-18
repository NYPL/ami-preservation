# PAMI Production Scripts

## csv_concat.py

For when cat ain't quite right. Will concat a directory of csvs, killing the first row of all but the first csv (so organize yourself carefully). Usage is typical:

 * `-d` for the directory of csvs
 * `-o` for the path and name of the output csv 
 
## pull_mediainfo.py

The following instructions will describe how to extract select MediaInfo attributes by using the `pull_mediainfo.py` script. Dependencies include: `python3` and `pymediainfo.` 

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

For instructions on importing into Filemaker, see [NYPL AMI Lab wiki](NYPL-AMI-Lab.md).
