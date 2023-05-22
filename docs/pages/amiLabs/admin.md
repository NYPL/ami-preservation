---
title: Admin
layout: default
nav_order: 3
parent: Media Preservation Labs
---


# AMI Labs Project Administration
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Project Initiation
### Arranging Deliveries to/from MPL
AMI Labs digitization projects originate from different sources and, depending on nature of the request, project management workflows may vary in slight but significant ways. The pathways by which media shipments arrive at the Labs include:
* Larger batches (typically of new acquisitions) sent by Preservation Collections Processing (PCP) via the Registrar's office, through two shipping methods: (1) Secure Shipping or (2) Special Collections Movement. The [Guide to Archives Unit and Registrar Shipping Procedures](https://drive.google.com/file/d/1_-oILUt8mOq7pqni0WZGMHmVC4hnujEz/view?usp=sharing){:target="\_blank"} describes the differences between these methods; for most part, shipments between the Library Services Center (LSC) and the Library for the Performing Arts (LPA) are arranged through the more flexible Secure Shipping. Deliveries to the AMI Labs are set up by Archives Unit (AU) or Special Formats Processing (SFP) staff; returns, on the other hand, are initiated by AMI Labs staff, by (1) emailing AU/SFP, and (2) filling out the appropriate fields of the [Shipping Register.](https://docs.google.com/spreadsheets/d/12hF2RcBXEW-P_x3eshyUFbQ6Q_XlFK3IE7rrjCZGwPQ/edit?ts=5dbc4fae#gid=698603054){:target="\_blank"} Regardless of the shipping method, these larger deliveries will have been inventoried and batched in the Collection Management System (CMS) prior to arrival at the Labs.
* Smaller batches (on-demand requests driven by curators or public orders) delivered to the AMI Labs most often without having been previously inventoried by AU/SFP. For these items, AMI Labs staff are expected to perform a CMS inventory process for each individual item before "batching" items as a group.

### Inventorying Items in CMS
The Collection Management System (CMS) of the Preservation and Collections Processing Department is a complex, multi-part database that serves many functions within NYPL's Research Libraries. AMI-related tasks (inventorying, batching, etc.) are, in this sense, one piece of a much larger puzzle, and the following instructions should be understood as simplified by design. Note: CMS is a Filemaker Pro database maintained by Library IT, and the necessary software and either on-site or VPN access are required to work within.
* Before inventorying any items in CMS, an important first step is to identify the appropriate CMS collection. This can be a challenging determination; if in doubt, contact Melanie Yolles (Assistant Director, Special Collections Processing, <melanieyolles@nypl.org>) for guidance. The most commonly used CMS Collections for AMI on-demand requests include: (1) Cataloged Dance Original Media, (2) Theatre on Film and Tape Archive (TOFT) AMI, (3) LT Open Reel RHA Collection, and (4) LTC RHA audio cassettes.
* In the main menu of CMS, under the Collection Info header, click ```search/edit``` to search for the CMS collection (either by name or CMS Collection ID).
*  After locating a collection, select ```items``` and look in the upper right corner for ```items.all```. Click ```items.all``` and change to ```media originals```; this will pull up a table view of all previously inventoried AMI items within a collection.
* To add a new item to CMS, scroll to the bottom of this table view and click the ```+``` sign in the bottom left corner; this will auto-populate starter information that includes the next unique CMS ID assigned to your particular username.
* Add the following information to the record: **id.classmark, barcode, format.type, format.name, title, date (if known, according to ISO 8601), manufacturer, and notes.content**
* As items are added to CMS, ensure that CMS ID and barcode stickers are affixed to the item's original housing, ideally in a consistent manner that doesn't obscure any original documentation.
* After adding all new items to CMS, click ```CMS.collections.management``` in the upper left corner to return to the main menu.

### Creating AMI Batches in CMS
* To create a new AMI Batch, click ```digitization batches``` under the AMI header within the CMS main menu; once there, click ```new batch```
* Change ```project.code``` to "PAMI" and add brief descriptive information to the ```project.name``` and ```batch.description``` fields. Enter "NYPL" in the field labeled ```digitizer```.
* To assign items to a newly formed batch, select ```manage items```.
* Unless items are contained within a CMS "box," they will need to be assigned to the batch one-by-one. To assign an item, click the ```search``` button and type the CMS ID into the ```id``` field. Click out of the ID cell and push ```Enter/Return``` on your keyboard to initiate a search.
* After a successful search, click on the drop-down menu under the ```search``` button to see a list of all AMI batches. Select the appropriate batch and click ```assign```. Continue as needed until all items are assigned to the batch.
* Return to the batch overview screen (```manage batches``` in upper right corner) and copy the date (M/DD/YYYY) from ```items.assigned``` to ```finalized```. This will allow you to create a spreadsheet export for the batch and update the move log.
* To create a spreadsheet for the batch, click ```spreadsheet``` in the batch overview window, next to ```manage items```. Note: the ```details``` button, also found in this same general area, will provide additional information regarding the batch (boxes/formats contained within, etc.).
* Update the ```move log```: select ```Received at``` and ```PAMI```; the date and your username will auto-populate.

### Creating AMI Database Work Orders
As AMI Labs digitization projects can vary in size, the concept of the "work order" is used to maintain consistency, allow for controlled tracking through the digitization/ingest pipeline, and provide a structured method for reporting/statistical analysis. Within the Labs, work orders are created in the AMI Database and used in the following ways:
  * For larger, routine digitization projects sent via PCP, work orders will be created at the box level and applied to all items contained within the box. In these cases, "keywords" will correspond to PCP box labeling practices (typically a three-letter code referring to the Research Division, followed by an arbitrary three-digit code).
  * For on-demand projects (exhibitions/programs, public orders, VIP), a work order will be created and applied to either single items or small groups of items, with a "keyword" that is descriptive in nature.

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

Beginning in FY20, the AMI Labs made an adjustment to its work order procedures, creating four overarching "pamiIDs" (2020_xxx) for each broad category of digitization. These IDs will carry through and be reapplied throughout the fiscal year (i.e. all public order work order IDs will begin with ```2020_003```):

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
Before importing CMS spreadsheets into the AMI Database, a number of adjustments will need to be made to ensure compatibility/compliance with the [ami-metadata](https://github.com/NYPL/ami-metadata){:target="\_blank"} JSON schema. This process includes:
* Copying the header row from a JSON-compliant template file and replacing the CMS export default, confirming accuracy of column information and making adjustments as needed
* Changing ```asset.fileRole``` (previously ```Filename (Reference)```) to ```pm``` for all rows
* Updating ```source.object.format``` to reflect correct JSON terminology, for example: ```video cassette``` will need to be changed to ```video cassette analog``` or ```video cassette digital```, etc.
* Removing the default ```source.subobject.faceNumber``` from all non-audio items
* Removing the contents of ```source.physicalDescription.stockLength.measure``` from all rows
* Adding the current version of ```asset.schemaVersion``` to all rows (per May 2020 = 2.0.0)
* Adding newly created Work Order IDs to the ```workOrderID``` column; for larger batches, ensure box-level work order keywords match the CMS default ```projectManagement.archivalBoxNumber``` for each item

### Importing CMS Export into AMI Database
Refined CMS export spreadsheets will need to be imported into two different tables of the AMI Database: ```Objects``` and ```MASTER:: production data entry```. The following steps will need to be followed for both import processes:
* Select the appropriate table from the ```Layout``` drop-down menu
* Go to ```File // Import Records // Import File...``` and select the spreadsheet
* In the ```Import Field Mapping``` menu, ensure that source fields match target fields, in part by changing ```Arrange by``` to ```matching names```. Confirm the status of all field mapping arrows, in particular for Work Order IDs.
* Check the ```Don't import first record (contains field names)``` box to prevent header row import
* Click ```Import```, and select ```Perform auto-enter options while importing``` in the subsequent ```Import Options``` pop-up menu
* Click ```Import``` and pay attention to the number of ```Total records add / updated```
* Repeat the process for the second table, and confirm the total number of records added is consistent across tables

## Project Tracking

### Step-by-Step Walkthrough of a Project

| **Activity** | **Staff Responsible** |
|   -----          |     -----      |
|   Delivery of media to the AMI Labs      |  PCP/Curators; Asst. Manager AMI Labs |
|   Box-level check-in (if arriving via PCP)     |  Asst. Manager AMI Labs |
|   Inventory of items in CMS (if on-demand)    |  Asst. Manager AMI Labs |
|   Creation of AMI Batch in CMS      |  PCP or Asst. Manager AMI Labs |
|   Creation of AMI Works Orders      |  Asst. Manager AMI Labs |
|   CMS Export Clean-up/Import into AMI Database      |  Asst. Manager AMI Labs |
|   Creation of Trello Cards and QC Spreadsheets      |  Asst. Manager AMI Labs |
|   Item-level check-in      |  AMI Labs Staff |
|   Pre-transfer conservation treatments      |  AMI Labs Staff |
|   Digitization/Creation of Preservation Master files      |  AMI Labs Staff |
|   Generation of Derivative files (Edit Masters, Service Copies)      |  AMI Labs Staff |
|   Finalization of all database records      |  AMI Labs Staff |
|   JSON creation and validation      |  AMI Labs Staff |
|   Packaging of files, confirmation of adherence to directory structure, removal of hidden files, bagging      |  AMI Labs Staff |
|   Trello Card status updates      |  AMI Labs Staff |
|   Quality Control      |  AMI Labs Staff (round robin style) |
|   File Transfer to Ingest Staging     |  AMI Labs Staff, Asst. Manager AMI Labs |
|   Repacking of physical items and placement of box on Outgoing Shipment Racks      |  AMI Labs Staff |
|   CMS/AMI Database Work Order Update      |  Asst. Manager AMI Labs |

### Trello Cards and Production/QC Workflow

AMI Labs projects are assigned to media preservation engineers and tracked through digitization/ingest pipeline with the [AMI Labs](https://trello.com/b/cbbd5QgE/nypl-ami-labs){:target="\_blank"} Trello Board.

* At the start of each project, all Work Order IDs will be given a Trello card (copied from standardized Audio/Video templates) and assigned to either the **Audio or Video Batch Queue** Lists.
* During this initiation phase, QC spreadsheets will also be created and attached to each Trello card (under ```Add to Card```, click ```Attachment```, navigate to ```Attach a Link```, and add the appropriate Google Sheets URL).
* As media preservation engineers are assigned/self-assign Work Orders, they will (1) be added as "Members" to the card, and (2) the card itself will be dragged from the **Audio and Video Batch Queue** Lists to the respective engineer list. From this point on, engineers will be responsible for updating the Trello card on a rolling basis and checking off the following tasks from the Production Checklist as they are completed:

  * Pre-transfer treatments
  * Transfer/Preservation Master production
  * Edit Master/Service Copy production
  * Spot check files
  * Finalize all database entries
  * Create JSON and validate
  * Confirm files adhere to directory structure

* After production activities have been completed, the engineer will then move the card to the **QC Queue** list. Quality control responsibilities for the Work Order will be assigned to a fellow engineer (who will also be added a "Member" to the card), and the card will be moved to the **QC: In Progress** list. The QC engineer will have primary responsibility for updating the Trello card as the following quality control checklist tasks are completed:

  * Review JSON for inconsistencies/errors
  * Manual QC (log all errors/observations in Google Sheet)
  * Communicate errors to digitization engineer)

* If the QC engineer flags any items for rework/review, the card will be moved from the **QC: In Progress** list to the **QC: Flags for Review** list. If no items are flagged, the card will be moved to the **Passed QC** List.

### QC Spreadsheets

For tracking and accountability purposes, QC Spreadsheets will be created for each Work Order ID during the project initiation phase of the AMI Labs digitization workflow. These spreadsheets are stored (alongside a QC Log Template) on the [AMI Preservation Team Drive](https://drive.google.com/drive/u/1/folders/1fF2i_9S1y_AQ3m6nWr4jSMYW4tKas1lV){:target="\_blank"} and gathered by fiscal year. QC Spreadsheet set-up includes the following:
* Make a copy of the QC Log Template
* Rename the file to WorkOrderID_qclog
* Copy all CMS IDs included within the Work Order into the ```list``` sheet of the QC Spreadsheet, making sure to paste audio and video CMS IDs into the appropriate ```Replace with AUDIO csv only``` and ```Replace with VIDEO csv only``` columns (these columns include formulas that will generate a random sampling of CMS IDs according to the AMI Labs convention of qc-ing a smaller percentage of audio files vs. video files)
* Copy the random sampling of CMS IDs and paste into the ```bibliographic.primaryID``` column of the ```QCLog``` sheet
* Fill out the ```workOrder``` and ```source.object.type``` columns
* Attach the Google Sheets URL to the Trello card

### Project Close-Out and "Did Not Captures"

As projects enter the close-out phase of the AMI Labs digitization workflow, wrap up activities will be divided between the media preservation/digitization engineer and the assistant manager of the AMI Labs. The engineer will be responsible for completing and checking off the following tasks in Trello:
* Remove hidden files and bag project
* Move files to pre-ingest staging (if audio, transfer to Isilon/ICC "4_RTG_Audio"; if video, hand-off HDD containing media files to Assistant Manager)
* Complete all Trello checklists and move card to either **RTG on HDD (json)** or **RTG on ICC (json)*** lists
* Pack up physical media and move box to Outgoing Shipment racks

After "receiving" the packaged media files, whether on HDD or Isilon, the Assistant Manager will perform a set of project management tasks to close out the Work Order:

* Update the Work Order table of the AMI Database, specifically the ```fileLocation```, ```status```, and ```dateCompleted``` fields
* If boxes of media are ready for return to LSC, update the Shipping Register and email AU/SFP Staff
* If items within Work Order were deemed "DNC" (Did Not Capture), create a Filemaker DNC spreadsheet to email AU/SFP staff as part of the return shipping process
  * The DNC spreadsheet should include the following fields:
      * bibliographic.barcode
      * bibliographic.title
      * bibliographic.divisionCode
      * source.object.type
      * source.object.format
      * captureIssueCategory
      * captureIssueNote
      * digitizer.operator.lastName																	
