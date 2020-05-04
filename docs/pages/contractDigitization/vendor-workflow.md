---
title: Vendor Workflow
layout: default
parent: Contract Digitization
nav_order: 2
---
# Project Implementation
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Creation of Vendor Project Worksheet:
* MPC creates a copy of the Vendor Project Worksheet Template:
  * [20##_###_keyword_###_metadataInventory_DATE - TEMPLATE](https://docs.google.com/spreadsheets/d/1IaWGYeKfHa6YcWiHXGkfQ1wMFL8oqu6SmpeKbPMjZV4/edit?usp=sharing)
* Import the contents of the CMS batch export into the 'metadataInventory' tab of the project worksheet, ensuring that the data is entered into the correct columns.

## CMS Export (Metadata Inventory) Cleanup:
CMS exports often contain characters and values which are incompatible with JSON metadata. After copying the CMS export into the template, **these values and characters must be manually removed / updated before the spreadsheet (the "...metadataInventory.xlsx" sheet) is sent to vendors for database import.**

### Search entire inventory sheet for the described content and make edits as instructed:
* Remove the default ```source.subobject.faceNumber``` from all non-audio items
* Remove the contents of ```source.physicalDescription.stockLength.measure``` from all rows
* **Metadata version**: add current version (per May 2017 = 2.0.0)
* Update ```source.object.format``` to reflect correct JSON terminology, for example: ```video cassette``` will need to be changed to ```video cassette analog``` or ```video cassette digital```, etc.
* Add current version of ```asset.schemaVersion``` to all rows (per May 2020 = 2.0.0)

### Find & Replace:
* Select "search using regular expressions"
  * Select "this sheet" (for the sheet you're working on),
  * Review the specific ranges mentioned below and find/replace as described:
* Find the following characters...
  * double quotations: ```“``` (replace with two single-quotes placed side by side, without spaces (Example: ```Audio Reel 10"``` becomes ```Audio Reel 10''```)
  * semicolon: ```;``` (replace with```-```)
  * backslash: ```\``` (replace with ```-```)
  * new line: ```\n``` (replace with ```-```)
  * vertical tab: ```\v``` (replace with ```-```)
  * tab: ```\t``` (replace with ```-```)
  * carriage return: ```\r``` (replace with ```-```)

* Double check to make sure you replaced all values as needed (sometimes the first one you find is skipped)

### Media Inventory & Physical Preparation
* Box Check-Out:
  * The template for the box check-out sheet is included in the Vendor Project Worksheet template. When you import the CMS batch export data, the 'box-barcode-list' tab in that sheet should be autopopulated using the values from the 'metadataInventory' tab. Do not alter the locked sheets.
  * the 'box-check-out' and 'box-check-in' tabs are pre-filled with formulas that should pull the box barcodes from the auto-populated list. The check-out/in sheets may need to have rows added to them in order to accommodate the actual number of boxes that exist in the project. To do this, 'add rows' and drag drag formulas in columns A & B down to the last row, so that all formulas are working properly for all rows. Test by entering in valid and invalid barcodes into the column.
  * Boxes are pulled by SFP team & PAMI staff by staging boxes on carts to prepare for movement.
  * Once a cart is full and ready to move, PAMI Media Preservation Coordinator or Assistant scans box barcodes into the prepared Box Check-Out sheet - before they are moved to LSC room 306. The check-out sheet confirms that the scanned barcode matches the list of barcodes that is expected from the finalized Metadata Inventory in the Vendor Project Worksheet. If any discrepancies occur, box barcodes must be checked against the metadataInventory spreadsheet tab.
* Boxes on carts are brought to LSC room 306 and palletized; wrapp 2 with plastic if possible to give shippers a head start;


### Box Check-Out/In Google Sheet Color-Coding Guide
* Column B ("Inventory Box Barcodes Confirmation") value defaults to the value "CHECK BARCODE". Therefor, if you scan a box and the barcode is not on the expected barcode list, Column B will remain colored red with the CHECK BARCODE value, instructing you to double-check the barcode.
* If Column B turns orange, it means that you have already scanned that box barcode, or there is a duplicated barcode, and you must double check this box.
* If Column B returns the same barcode number you just scanned, then all is well. Proceed with barcode-scanning.

## Shipping Coordination
See [Shipping](shipping).

## Quality Control
See [Quality Control workflow documentation](quality-control)

# Project Close-Out
## Project Summaries
* Compiling Manifests & Reports

### Capture Issue Review
* **Capture Issues:** Find & delete the following characters in the vendor's DNC reports & HDmanifests
  - vertical tab ```\v```
  - tab ```\t```
  - carriage return ```\r```
  - new line [similar to carriage return but they both appeared separately] ```\n```

* Separate the items by original project fund (pami work orders should at a minimum be separated by project fund). Example: Slifka, Mellon. No need to separate by unit or research center.
* Manager will forward the DNC list separately, and you can review to identify what should be sent to PAMI. Manager will pull objects and box-up according to project fund. On return, media goes back into they're original boxes.
* For PAMI metadata, pull  item records from the original metadata inventory from initial project and create internal db records (remembering to change the cms project code).
  CMS:
  * CMS project code: PAMI
  * CMS title / description: DNC - [fund name]....EXAMPLE: dnc - mellon
  CMS batch #:... next available sequential ## (can we put a placeholder in PAMI work orders until this is ready?)
