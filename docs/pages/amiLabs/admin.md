---
title: Admin
layout: default
nav_order: 1
parent: AMI Labs
---


# AMI Labs Project Administration
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Project Initiation
### Arranging Deliveries to/from the AMI Labs
AMI Labs digitization projects originate from a few different sources and, depending on nature of the request, project management workflows may vary in slight but significant ways. The pathways by which media shipments arrive at the Labs include:
* Larger batches (typically of new acquisitions) sent by Preservation Collections Processing (PCP) via the Registrar's office, through two shipping methods: (1) Secure Shipping or (2) Special Collections Movement. The [Guide to Archives Unit and Registrar Shipping Procedures](https://drive.google.com/file/d/1_-oILUt8mOq7pqni0WZGMHmVC4hnujEz/view?usp=sharing){:target="\_blank"} describes the differences between these methods; for most part, shipments between the Library Services Center (LSC) and the Library for the Performing Arts (LPA) are arranged through the more flexible Secure Shipping. Deliveries to the AMI Labs are set up by Archives Unit (AU) or Special Formats Processing (SFP) staff; returns, on the other hand, are initiated by AMI Labs staff, by (1) emailing AU/SFP, and (2) filling out the appropriate fields of the [Shipping Register.](https://docs.google.com/spreadsheets/d/12hF2RcBXEW-P_x3eshyUFbQ6Q_XlFK3IE7rrjCZGwPQ/edit?ts=5dbc4fae#gid=698603054){:target="\_blank"} Regardless of the shipping method, these larger deliveries will have been inventoried and batched in the Collection Management System (CMS) prior to arrival at the Labs.
* Smaller batches (on-demand requests driven by curators or public orders) delivered to the AMI Labs most often without having been previously inventoried by AU/SFP. For these items, AMI Labs staff are expected to perform a CMS inventory process for each individual item before "batching" all items as a group.

### Inventorying Items in CMS
The Collection Management System (CMS) of the Preservation and Collections Processing Department is a complex, multi-part database that serves many functions within NYPL's Research Libraries. AMI-related tasks (inventorying, batching, etc.) are, in this sense, one piece of a much larger puzzle, and the following instructions should be understood as simplified by design. Note: CMS is a Filemaker Pro database maintained by Library IT, and the necessary software and either on-site or VPN access are required to work within.
* Before inventorying any items in CMS, first identify the appropriate CMS collection for said items. This can be a challenging determination; if in doubt, contact Melanie Yolles (Assistant Director, Special Collections Processing, <melanieyolles@nypl.org>) for guidance. The most commonly used CMS Collections for AMI on-demand requests include: (1) Cataloged Dance Original Media, (2) Theatre on Film and Tape Archive (TOFT) AMI, (3) LT Open Reel RHA Collection, and (4) LTC RHA audio cassettes.
* In the main menu of CMS, under the Collection Info header, click ```search/edit``` to search for the CMS collection (either by name or CMS Collection ID).
*  After locating a collection, select ```items``` and look in the upper right corner for ```items.all```. Click ```items.all``` and change to ```media originals```; this will pull up a table view of all previously inventoried AMI items within a collection.
* To add a new item to CMS, scroll to the bottom of this table view and click the ```+``` sign in the bottom left corner; this will auto-populate starter information that includes the next unique CMS ID assigned to your particular username.
* Add the following information to the record: **id.classmark, barcode, format.type, format.name, title, date (if known, according to ISO 8601), manufacturer, and notes.content**
* As items are added to CMS, ensure that CMS ID and barcode stickers are affixed to the item's original housing, ideally in a consistent manner that doesn't obscure any original documentation.
* After adding all new items to CMS, click ```CMS.collections.management``` in the upper left corner to return to the main menu.

### Creating AMI Batches in CMS
* To create a new AMI Batch, click ```digitization batches``` under the AMI header in the CMS main menu; once there, click ```new batch```
* Change ```project.code``` to "PAMI" and add brief descriptive information to the ```project.name``` and ```batch.description``` fields. Enter "NYPL" in the field labeled ```digitizer```.
* To assign items to the newly formed batch, select ```manage items```.
* Unless items are contained within a CMS "box," they will need to be assigned to the batch one-by-one, a time-consuming process. To assign an item, click the ```search``` button and type the CMS ID into the ```id``` field. Click out of the ID cell and push ```Enter/Return``` on your keyboard to initiate a search.
* After a successful search, click on the unnamed drop-down menu under the ```search``` button to see a list of all AMI batches. Select the appropriate batch and click ```assign```. Continue as needed until all items are assigned to the batch.
* Return to the batch overview screen (```manage batches``` in upper right corner) and copy the date (M/DD/YYYY) from ```items.assigned``` to ```finalized```. This will allow you to create a spreadsheet export for the batch and update the move log.
* To create a spreadsheet for the batch, click ```spreadsheet``` in the batch overview window, next to ```manage items```. Note: the ```details``` button, also found in the same general area, will provide additional information regarding the batch (boxes/formats contained within, etc.).
* Update the ```move log```: select ```Received at``` and ```PAMI```; the date and your username will auto-populate.

### Creating AMI Database Work Orders
As AMI Labs digitization projects can vary in size, the concept of the "work order" is used to maintain consistency, allow for controlled tracking through the digitization/ingest pipeline, and provide a structured method for reporting/statistical analysis. Within the Labs, work orders are created in the AMI Database, and used in the following ways:
  * For larger, routine digitization projects sent via PCP, work orders will be created at the box level (though still applied at the item level), with "keywords" that correspond to PCP labeling practices (typically a three-letter code that refers to the Research Division, followed by an arbitrary three-digit code).
  * For on-demand projects (exhibitions/programs, public orders, VIP), a work order will be created and applied to single items or small groups of items, with a "keyword" that is descriptive in nature.

Work Orders should conform to the following structure:
```
pamiID_projectCode_cmsBatch_keyword
```
Sample routine digitization work order:
```
2019_001_pami_087_dan409
```
Sample on-demand work order:
```
2019_010_pami_098_youngamerica
```

Beginning in FY20, the AMI Labs made an adjustment to its work order procedures, creating four overarching "pamiIDs" (2020_xxx) for each broad category of digitization, IDs that would carry through and be reapplied throughout the fiscal year:

```
2020_001_pami_xxx_routinedigitization
2020_002_pami_xxx_exhibitionorprogram
2020_003_pami_xxx_publicorder
2020_004_pami_xxx_vip
```

After creating a work order ID, update the following project tracking fields also located in the Work Orders table:
* Contact (the NYPL staff member who initiated the digitization project)
* Digitizer (NYPL by default)
* Type (routine in-house digitization, exhibitions or public programming, public order, VIP)
* Status (in process, on hold, quality control, ready for file transfer)

### CMS Export (Metadata Inventory) Cleanup
Before importing CMS spreadsheets into the AMI Database, a number of adjustments will need to be made to ensure compatibility/compliance with the [ami-metadata](https://github.com/NYPL/ami-metadata){:target="\_blank"} JSON schema. This cleanup process includes:
* Copy the header row from a JSON-compliant template file and replace the CMS default, confirming accuracy of column information and making adjustments as needed
* Change ```asset.fileRole``` (previously ```Filename (Reference)```) to ```pm``` for all rows
* Update ```source.object.format``` to reflect correct JSON terminology, for example: ```video cassette``` will need to be changed to ```video cassette analog``` or ```video cassette digital```, etc.
* Remove the default ```source.subobject.faceNumber``` from all non-audio items
* Remove the contents of ```source.physicalDescription.stockLength.measure``` from all rows
* Add current version of ```asset.schemaVersion``` to all rows (per May 2020 = 2.0.0)
* Add newly created Work Order IDs to ```workOrderID``` column; for larger batches, ensure box-level work order keywords match the CMS default ```projectManagement.archivalBoxNumber``` for each item

### Importing CMS Export into AMI Database
Refined CMS export spreadsheets will need to be imported into two different tables of the AMI Database: ```Objects``` and ```MASTER:: production data entry```. The following steps will need to be followed for both imports:
* Select the appropriate table from the ```Layout``` drop-down menu
* Go to ```File // Import Records // Import File...``` and select the spreadsheet export
* In the ```Import Field Mapping``` menu, ensure that source fields match target fields, in part by changing ```Arrange by``` to ```matching names```. Confirm the status of all field mapping arrows, in particular for Work Order IDs.
* Check the ```Don't import first record (contains field names)``` box to prevent header row import
* Click ```Import```, and select ```Perform auto-enter options while importing``` in the subsequent ```Import Options``` pop-up menu
* Click ```Import``` and pay attention to the number of ```Total records add / updated```
* Repeat the process for the second table, and confirm the total number of records added is consistent across tables

## Project Tracking

### Trello Cards

### Assigning Projects

### QC Spreadsheets

## Project Close-Out





  * sub-bullets with ```command line text```
