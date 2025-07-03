---
title: Metadata
layout: default
nav_order: 5
has_children: true
---

# AMI Metadata Overview
{: .no_toc }

Every digitization project at NYPL—whether performed in-house by the Audio and Moving Image Preservation Lab or by an external vendor—is supported by structured metadata. This overview outlines how descriptive, technical, and process metadata are created, managed, and delivered across the digitization workflow.

- [AMI Metadata Overview](#ami-metadata-overview)
  - [Pre-Digitization: SPEC Export](#pre-digitization-spec-export)
  - [Post-Digitization: Technical \& Process Metadata](#post-digitization-technical--process-metadata)
  - [JSON Metadata Generation](#json-metadata-generation)
  - [Workflow Automation with Python](#workflow-automation-with-python)

---

## Pre-Digitization: SPEC Export

For each digitization batch, a metadata spreadsheet—referred to as the SPEC export—is generated. This spreadsheet includes descriptive fields provided by the Collection Management System (SPEC) and is delivered to either:

- The AMI Preservation Lab for in-house digitization, or  
- A vendor for outsourced digitization.

In the AMI Preservation Lab, this metadata is imported into FileMaker prior to digitization and forms the base record for each object.

## Post-Digitization: Technical & Process Metadata

Following digitization, each object's FileMaker record is updated with:

- Technical metadata (e.g., bit depth, duration, codecs)  
- Digitization process details (e.g., transfer path, hardware used)  
- Signal condition notes

The completion of this step is critical to producing accurate and validated metadata exports.

## JSON Metadata Generation

Once technical and process metadata have been added to FileMaker:

- Each record is exported as a structured JSON file.  
- These JSON files accompany each digital Preservation Master, Edit Master, Mezzanine, or Service Copy file.  
- JSON metadata follows the specifications defined by [`ami-metadata`](https://github.com/NYPL/ami-metadata), NYPL’s open schema for audiovisual materials.

## Workflow Automation with Python

The Lab uses a Python-based toolchain to automate the following:

- Derivative generation (Edit, Mezzanine, Service Copy)  
- FileMaker record duplication for derivatives  
- Technical metadata extraction and insertion into FileMaker  
- JSON file creation and validation  
- Object packaging and BagIt creation

👉 For a complete walkthrough of this workflow, see:  
[**FileMaker Integration and JSON Metadata Workflow**](https://nypl.github.io/ami-preservation/pages/workflows/filemaker-json-workflow.html)
