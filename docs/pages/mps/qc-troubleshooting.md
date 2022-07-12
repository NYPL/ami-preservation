---
title: QC Troubleshooting Resource
layout: default
nav_order: 2
parent: Quality Control 
---

# Quality Control Workflow
{: .no_toc }

Internal resource for troubleshooting some of the most common issues encountered during our quality control process. The steps outlined below utilize a combination of open source and custom-built tools built in collaboration with and maintained by Media Preservation Services, Media Preservation Labs, and Digital Preservation. 

The workflows outlined on this page make use of the following NYPL GitHub repositories:

* [NYPL/ami-metadata](https://github.com/NYPL/ami-metadata)

* [NYPL/ami-preservation](https://github.com/NYPL/ami-preservation)

* [NYPL/ami-tools](https://github.com/NYPL/ami-tools)


**Note**: In most cases, you will be required to have full access to the drive/files you are working on to perform these repairs. 

While some errors may require a vendor or engineer to rework and re-deliver files, many of the most common errors encountered during QC can be fixed by using the steps outlined below. 

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}


## Repairable Errors

###  Invalid Oxum (Size Discrepancy)

[insert image]

The oxum of a bag may become invalid when the number of files listed in the manifest-md5.txt file do not correspond with the number of files present in the bag. Fixing an invalid oxum requires manually inspecting the manifest-md5.txt file against the number of items in the bag and using ```fix_baginfo.py``` and ```validate_ami_bags.py``` to fix and confirm validation of the bag.  

Repairing invalid oxum requires use of scripts within the [NYPL/ami-tools](https://github.com/NYPL/ami-tools) repo, managed by NYPL's Digital Preservation department.

* Check the number of files in the manifest-md5 against the number of files present in each of the directories within the bag using ```ls -a``` from within the various directories of the bag to show hidden files) 
* Conform the manifest-md5.txt to match the files present in bag, either by removing unwanted files from the bag or by adding existing files and their corresponding md5 checksums to the manifest-md5.txt if they have not been included. (See below for more information on hidden system files and how to address them.) 
* Delete tag manifest
* Repair bag using ```fix_baginfo.py```
* Validate bag
```
/path/to/ami-tools/bin/validate_ami_bags.py -b path/to/bag
```

###  Invalid JSON (Metadata Issues)

[insert image]

A JSON file may be invalid when the contents or structure do not adhere to NYPL’s [ami-metadata schema]([https://nypl.github.io/ami-preservation/pages/ami-specifications.html](https://github.com/NYPL/ami-metadata) or other [metadata requirements outlined in NYPL's specifications](https://nypl.github.io/ami-preservation/pages/ami-handling.html#metadata). Some of the most common causes for invalid JSON include: empty required fields, use of terms not included in controlled vocabularies, inclusion of unrecognized characters, unnecessary blank spaces, and invalid JSON file structure. Repairing invalid JSON files requires using a combination of manual inspection and ```ajv validate```, ```fix_baginfo.py```, and ```validate_ami_bags.py``` to validate the file against a schema, fix the bag that contains the file, and confirm validation of the repaired bag. 

Repairing JSON requires identifying and resolving specific errors one at a time, and validating single JSON files against individual schema files to receive more detailed error logging. 

* Create a working copy of the error-ridden JSON file you are analyzing on your personal workstation (never experiment with original files - only copies)
* Determine the appropriate schema type based on the media format listed in the JSON
  * Locate the sourceObjectFormat field in the JSON file
  * Locate the schema file in ami-metadata that corresponds to the file you want to validate
* Validate the single JSON files against the selected schema file using the code below (also described on the ami-metadata repo README)
```
cd /path/to/ami-metadata/versions/2.0/schema
```
``` 
ajv validate -s /path/to/version/2.0/schema/format schema -r path/to/versions/2.0/schema/fields.json -d /path/to/file you want to check
```

Ajv will report any fields that don’t correspond to values allowed by the format's schema.

* Compare errors reported to the schema rules to determine issue(s) 
* Manually repair errors on your personal copy of the file created in step 1, and save file
* Validate single file again against the proper shchema 
* If valid, replace original JSON file in bag with your new repaired copy
* Validate all JSON files in a group of bags using ajv to double-check validation
``` 
ajv validate --all-errors --multiple-of-precision=2 --verbose -s /path/to/ami-metadata/versions/2.0/schema/digitized.json -r "/path/to/ami-metadata/versions/2.0/schema/*.json" -d "/Volumes/DRIVE-ID/*/*/data/*/*.json"
```
* Once JSON file has been reapired and replaced, this new JSON file will have a different md5 checksum than the original; the md5 manifest must now be updated. Do this using using ```fix_baginfo.py``` as directed.

* Validate bag structure (Note: below command does not validate checksums - only structure and contents) 
 ```
 validate_ami_bags.py -b path/to/bag 
 ```

###  Hidden System Files

[insert image]

Another common issue that can occur during QC is the presence of hidden files. Invisible files are generated by an operating system — often during production or bagging — and because they are hidden, go unnoticed until the validation process. A bag containing hidden files will not validate due to a discrepancy between the number of files listed in the manifest-md5.txt file and the number of files present in the bag; this will often result in an invalid oxum as well. Hidden file filenames often begin with a period and are easy to identify once the contents of a bag are identified. Examples: .Trashes, .DS_store; or they may resemble existing filenames, such as .abc_123456_v01_pm.mov

Rather than mass eliminating hidden files within a batch, it is usually best to address problems with bags individually. The below describes how to identify and remove single hidden files.

```
cd path/to/bag/inner/directory/
```
* List contents of directory 

```
ls -a
```

* Send invisible files to your trash / recycle bin

```
trash .filename
```
* Run ```fix_baginfo.py``` to fix bag info if needed
* repeat process for each directory as needed
* Validate directory/bag to check if removal of system file resulted in a valid bag
```
validate_ami_bags.py –quiet -d path/to/directory
```

## Irrepairable Errors 

Media Preservation Services may not be able to repair some errors if the physical media requires re-digitization or the quantity of error(s) is substantial enough to justify re-work. In instances where it has been determined Media Preservation Services is unable to resolve an error, the vendor or the appropriate Media Preservation Labs Engineer is notified and re-work is requested. All errors and resolutions / decisions are noted in QC logs. 

## Supplemental Resources

The following resources may be used in tandem with the steps outlined above to fix some common errors. 

###  Moving and Removing Files and Directories 

Occasionally during QC, files and directories may need to be moved or removed for a variety of reasons, including: they fail quality control and need to be redelivered, or they pass and need to be moved to a new location. 

If vendor project files fail QC and an entire asset (or group of assets) need to be redelivered, the files are removed from the hard drive and quality control is completed on the remaining approved files. When the redelivered files are received, they must undergo the entire quality control process before they can be approved for ingest. 

When an in-house project passes QC, the project is moved from InHouse to the QC-pass directory on ICA. If an in-house project fails QC, the Media Preservation Labs Manager and Engineer is notified and the corrected files are redelivered to the InHouse directory on ICA. The reworked assets are subject to the entire quality control process before they can be approved for ingest.  

* Move a file or directory from one location to another
```
mv /path/to/source path/to/destination
```

* Remove a file or directory
  * use [Trash](https://hasseg.org/trash/). Trash will safely remove a file or directory and move it to your Trash / recycle bin


##  Locate a string within a file type 

During QC it may be necessary to locate recurring file types, filenames, operators, or errors within a directory. 

Information about using grep can be found on the NYPL Media Preservation Documentation [Command Line Resources](https://nypl.github.io/ami-preservation/pages/resources.html#parsing-files-and-reports) page. 

* Navigate to the directory 

```
cd /path/to/directory
```

* Locate string within a directory

```
find . -name "*.ext" | xargs grep "string"
```


## Tools
See our [Command Line Resources ](https://nypl.github.io/ami-preservation/pages/resources.html)for descriptions, usage, and installation instructions of various tools we use in this workflow.
