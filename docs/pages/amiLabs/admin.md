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
AMI Labs digitization projects originate from a few different sources and, depending on nature of the request, project management workflows will vary in slight but significant ways. The pathways by which media is sent to the Labs include:
* Larger batches (typically of new acquisitions) sent by Preservation Collections Processing (PCP) via the Registrar's office, through two shipping methods: (1) Secure Shipping or (2) Special Collections Movement. The [Guide to Archives Unit and Registrar Shipping Procedures](https://drive.google.com/file/d/1_-oILUt8mOq7pqni0WZGMHmVC4hnujEz/view?usp=sharing){:target="\_blank"} describes the differences between these methods; for most part, shipments between the Library Services Center (LSC) and the Library for the Performing Arts (LPA) are arranged through the more flexible Secure Shipping. Deliveries to the AMI Labs are set up by Archives Unit (AU) or Special Formats Processing (SFP) staff; returns, on the other hand, are initiated by AMI Labs staff, by (1) emailing AU/SFP, and (2) filling out the appropriate fields of the [Shipping Register.](https://docs.google.com/spreadsheets/d/12hF2RcBXEW-P_x3eshyUFbQ6Q_XlFK3IE7rrjCZGwPQ/edit?ts=5dbc4fae#gid=698603054){:target="\_blank"} Regardless of the shipping method, these larger deliveries will have been inventoried and batched in the Collection Management System (CMS) prior to arrival at the Labs.
* Smaller batches (on-demand requests driven by curators or public orders) delivered to the AMI Labs most often without having been previously inventoried by AU/SFP. For these items, AMI Labs staff are expected to perform a CMS inventory process for each individual item before "batching" all items as a group.

### CMS Inventory Process
The Collection Management System (CMS) of Preservation and Collections Processing is a complex, multi-part database that serves many functions within NYPL's Research Libraries. AMI-related tasks (inventorying, batching, etc.) are, in this sense, one piece of a much larger puzzle, and the following instructions should be understood as simplified by design. Note: CMS is a Filemaker Pro database maintained by Library IT, and the necessary software and either on-site or VPN access are required to work within.
* Before inventorying any items in CMS, an important first step is to identify the appropriate CMS collection. This can be a challenging determination; if in doubt, contact Melanie Yolles (Assistant Director, Special Collections Processing, <melanieyolles@nypl.org>) for guidance. The most commonly used CMS Collections for AMI on-demand requests include: (1) Cataloged Dance Original Media, (2) Theatre on Film and Tape Archive (TOFT) AMI, (3) LT Open Reel RHA Collection, and (4) LTC RHA audio cassettes.
* In the main menu of CMS, under the Collection Info header, click ```search/edit``` to search for the CMS collection (either by name or CMS Collection ID).
*  After locating a collection, select ```items``` and look in the upper right corner for ```items.all```. Click on ```items.all``` and change to ```media originals```; this will pull up a table view of all previously inventoried AMI within a collection.
* To add a new item to CMS, scroll to the bottom of this table view and click the ```+``` sign in the bottom left corner; this will auto-populate starter information that includes the next unique CMS ID assigned to your particular username.
* Add the following information to the record: **id.classmark, barcode, format.type, format.name, title, date (if known, according to ISO 8601), manufacturer, and notes.content**
* As items are added to CMS, ensure that CMS ID and barcode stickers are affixed to the item's original housing, ideally in a consistent manner that doesn't obscure any original documentation.
* After adding all new items to CMS, click ```CMS.collections.management``` in the upper left corner to return to the main menu.

### Creating CMS AMI Batches
* To create a new AMI Batch, click ```digitization batches``` under the AMI header in the CMS main menu; once there, click ```new batch```
* Change ```project.code``` to "PAMI" and add brief descriptive information to the ```project.name``` and ```batch.description``` fields. Enter "NYPL" in the field labeled ```digitizer```.
* To assign items to the newly formed batch, select ```manage items```.
* Unless items are contained within a CMS "box," they will need to be assigned to the batch one-by-one, a time-consuming process. To assign an item, click the ```search``` button and type the CMS ID into the ```id``` field. Click out of the ID cell and push ```Enter/Return``` on your keyboard to initiate a search.
* After a successful search, click on the unnamed drop-down menu under the ```search``` button to see a list of all AMI batches. Select the appropriate batch and click ```assign```. Continue as needed until all items are assigned to the batch.
* Return to the batch overview screen (```manage batches``` in upper right corner) and copy the date (M/DD/YYYY) from ```items.assigned``` to ```finalized```. This will allow you to create a spreadsheet export for the batch and update the move log.
* To create a spreadsheet for the batch, click ```spreadsheet``` in the batch overview window, next to ```manage items```. Note: the ```details``` button, also found in the same general area, will provide additional information regarding the batch (boxes/formats contained within, etc.).
* Update the ```move log```: select ```Received at``` and ```PAMI```; the date and your username will auto-populate.

### Creating AMI Database Work Orders


### CMS Export (Metadata Inventory) Cleanup

### Importing CMS Export into AMI Database


## Project Tracking

### Trello Cards and QC Spreadsheets

## Project Close-Out





  * sub-bullets with ```command line text```
