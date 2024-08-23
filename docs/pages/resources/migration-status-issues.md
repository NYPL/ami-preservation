---
title: Migration Status and Issues (SPEC) 
layout: default
nav_order: 5
parent: Resources
---

# Updating Migration Status and Adding Issues in SPEC

When digitization fails or is deferred, two fields must be updated in SPEC: **Migration Status** and **Issues**. Use this guide to navigate to these fields and choose the appropriate field values.

* [SPEC Navigation](#navigation)
  * [Object Record](#nav_objectrecord)
  * [Migration Status](#nav_migrationstatus)
  * [Issues](#nav_issues)
* [Guidelines](#guidelines)
  * [Migration Status](#guide_migrationstatus)
  * [Issues](#guide_issues)
* [Use Cases](#table)

<h2 id="navigation">SPEC navigation</h2>

<h3 id="nav_objectrecord">Object record navigation:</h3>

1. From the SPEC landing page, under the "Objects" menu, click <ins>Search all objects</ins>
2. Enter the AMI ID of your item in the "Any ID" field and hit `search`
3. Optional: next to "List edit:" click <ins>AMI</ins> to narrow your search results down to AMI items only
4. Open the Object Record by clicking on the title text (in the <ins>Object name</ins> column) of your item

<h3 id="nav_migrationstatus">Migration Status navigation:</h3>

1. Follow [steps](#nav_objectrecord) above to open the Object Record
2. On the left hand side of the Object record, look for "MIGRATION/DIGITIZATION STATUS" heading; click on the text of the current status to open the Migration / Digitization status card
3. At the bottom of the Migration / Digitization status card, click the `+ ADD MIGRATION STATUS` button
   * *n.b.: DO NOT change the current migration status directly from the dropdown menu: this will overwrite the status. Instead, click the `+ ADD MIGRATION STATUS` button: the current migration status will be converted to a historical status, and your new entry will be added as the current status*
4. You will see a pop-up alerting you that the current migration status will be replaced with the one you are entering: click `OK`
5. Choose the appropriate value from the dropdown menu
   * Refer to [Guidelines](#guide_migrationstatus) and/or examples in [Use cases table](#table) below

<h3 id="nav_issues">Issues navigation:</h3>

1. Follow [steps](#nav_objectrecord) above to open the Object Record
2. In the main body of the Object Record, look for the "ISSUES" heading; click <ins>View All / Edit / Add</ins> to open Issues tab
3. At the bottom of the Issues tab, click the `+ ADD ISSUE` button
4. Choose the appropriate values for these fields:
    1. TYPE
    2. ISSUE (a.k.a. subtype)
    3. NOTES
   * Refer to [Guidelines](#guide_issues) and/or examples in [Use cases table](#table) below

<h2 id="guidelines">Guidelines</h2>

<h3 id="guide_migrationstatus">Migration Status guidelines:</h3>

Choose from one of the following statuses (avoid using statuses not listed here):

* **AMI re-batch: special treatment vendor (film)**
  * for film items that will not be digitized in-house due to format limitations or condition issues
* **AMI re-batch: vendor (a/v)**:
  * for audio and video items that will not be digitized in-house due to format limitations or condition issues
* **AMI re-batch: vendor (mold)**:
  * for items that will not be digitized in-house or in a standard vendor project due to mold
* **AMI rebatch: in-house (a/v)**:
  * for items DNCed by vendors that should be retried in-house
  * for items batched in-house that need to be rerouted to a different engineer (e.g. a film item batched in an audio project)
* **AMI rebatch: in-house (digital archives)**
  * for items that are found to be data carriers rather than A/V
* **Migration failed (will retry)**
  * for items that are missing at the time of digitization project ONLY (for all other migration failure contexts, use one of the "re-batch" options above)
* **Will not migrate**:
  * for items that will definitively not be captured (e.g. blank media, items for which every possible option has been tried and failed)

The following statuses will no longer be used:
* **Migration failed (will not retry)**:
  * use **Will not migrate** instead

<h3 id="guide_issues">Issue guidelines:</h3>

There are three Issue fields to complete (in order): 
1. TYPE (dropdown)
2. ISSUE a.k.a. subtype (dropdown, dependent on TYPE)
3. NOTES (free text, when applicable)

Avoid using issue types and subtypes not listed here:

* **Hazard**:
  * for items that present health or safety hazards. Subtype required (see below)
  * Hazard subtypes:
    * **Inactive Mold**
      * NOTES: not required
    * **Nitrate**
      * NOTES: not required
* **Media Capture**:
  * for all other cases. Subtype required (see below)
  * Media Capture subtypes:
    * **Blank media**
      * for unused stock, or for media with tones/bars/video black/film leader only
      * NOTES: optional
    * **Commercial media**
      * for either consumer home media or off-air recordings
      * NOTES: optional
    * **Condition issue**
      * *n.b.: make sure to use "Condition Issue" as a subtype of "Media Capture", rather than as a type itself*
      * for any type of physical problems impeding preparation or digitization
      * NOTES: specify the exact problem (e.g. "delaminated disc") in the Issue's NOTES field
    * **Did not receive**
      * for when an expected item was not delivered to lab/vendor
      * NOTES: if possible, indicate which box the item was missing from in the Issue's NOTES field, e.g. "Missing from box 1234"
    * **Unsupported data format**
      * for an item that is a data format *and* cannot be digitized in current batch due to equipment limitations
      * NOTES: if possible, specify the format in the Issue's NOTES field
    * **Unsupported media format**
      * for an item that is an Audio/Video/Film format *but* cannot be digitized in current batch due to equipment limitations
      * NOTES: if possible, specify the format in the Issue's NOTES field

Avoid using "Other" (either as an Issue TYPE or subtype) whenever possible. Consult with colleagues to determine if any more specific type/subtype exists (or should exist). If "Other" must be used, make good use of the Issue's NOTES field.

<h2 id="table">Use Cases</h2>

| <br>Scenario | Migration<br>Status | Issue<br>Type | Issue<br>Subtype | Issue<br>Note |
|---|---|---|---|---|
| A/V, Film: <br>Expected item was not delivered to lab/vendor | `Migration failed (will retry)` | `Media Capture` | `Did not receive` | e.g. "Missing from box 1234" |
| A/V, Film: <br>Unrecorded/unused stock | `Will not migrate` | `Media Capture` | `Blank media` | *No additional note required* |
| A/V, Film: <br>No meaningful content (tones/bars/video black/film leader only) | `Will not migrate` | `Media Capture` | `Blank media` | e.g. "bars only" |
| A/V: <br>Unplayable/inaudible due to recording error -- in-house determination | `Will not migrate` | `Media Capture` | `Condition issue` | e.g. "Recording error, tried in multiple machines" |
| A/V: <br>Unplayable/inaudible due to recording error -- vendor determination | `AMI rebatch: in-house (a/v)` | `Media Capture` | `Condition issue` | e.g. "Recording error, tried in multiple machines" |
| A/V: <br>Commercial media (consumer media or off-air recording) | `Will not migrate` | `Media Capture` | `Commercial media` | e.g. "commercial DVD" |
| A/V: <br>Unsupported format -- in-house equipment limitation | `AMI re-batch: vendor (a/v)` | `Media Capture` | `Unsupported media format` | e.g. "No PAL 8mm equipment available" |
| A/V: <br>Unsupported format -- vendor equipment limitation | `AMI rebatch: in-house (a/v)` | `Media Capture` | `Unsupported media format` | e.g. "No PAL 8mm equipment available" |
| Data: <br>Unsupported format (item may have been inventoried as A/V) | `AMI rebatch: in-house (digital archives)` | `Media Capture` | `Unsupported data format` | e.g. "Digital8 data tape" |
| Film: <br>Unsupported format | `AMI re-batch: special treatment vendor (film)` | `Media Capture` | `Unsupported media format` | e.g. "35mm full-coat mag" |
| Film: <br>Unprocessed (exposed) stock | `AMI re-batch: special treatment vendor (film)` | `Media Capture` | `Condition issue` | e.g. "sealed, appears to be exposed but not processed" |
| A/V: <br>Item needing special treatment | `AMI re-batch: vendor (a/v)` | `Media Capture` | `Condition issue` | e.g. "delaminated disc" |
| Film: <br>Item needing special treatment | `AMI re-batch: special treatment vendor (film)` | `Media Capture` | `Condition issue` | e.g. "severe acetate decay, may need replasticizaion", "trims/outs (needs extensive prep)" |
| A/V, Film: <br>Item damaged beyond repair | `Will not migrate` | `Media Capture` | `Condition issue` | e.g. "Multiple transfer attempts, baked and cleaned, still unplayable due to SSS" |
| A/V, Film: <br>Moldy item | `AMI re-batch: vendor (mold)` | `Hazard` | `Inactive mold` | *No additional note required* |
| Film: <br>Nitrate | `AMI re-batch: special treatment vendor (film)` | `Hazard` | `Nitrate` | *No additional note required* |
