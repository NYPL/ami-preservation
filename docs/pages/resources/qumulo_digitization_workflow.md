---
title: Qumolo workflow
layout: default
nav_order: 9
parent: Resources
---

# Qumulo-Based Digitization and Preservation Workflow

## Overview

This document outlines the workflow and responsibilities for capturing digitized audio and video files directly to Qumulo working storage (`lpa-qu-cls.nypl.org`), using the `amip` share. The process includes digitization, file handoff, quality control (QC), and transfer to long-term digital preservation systems.

---

## 1. Capture and File Organization

### 1.1 Capture Options

Media Preservation Engineers (MPEs) may:

- **(a) Capture directly** to their personal directory on the Qumulo `amip` share:
  ```
  /Volumes/amip/bturkus/
  /Volumes/amip/<username>/
  ```
- **(b) Capture locally**, then use `rsync` to copy completed projects to the `READY/` folder within their personal Qumulo directory:
  ```
  /Volumes/amip/<username>/READY/
  ```

Use appropriate `rsync` flags (e.g., `-rtv --progress`) to preserve timestamps, resume transfers, and verify completion.

---

### 1.2 Directory Structure

Each Media Preservation Engineer's personal directory should contain:

- `READY/` – For completed, QC-ready projects.
- `WORKING/` – *(Optional)* For in-progress files not yet ready for handoff.

Project subdirectories should be named using the Media Digitization Request (MDR) ID, optionally followed by barcode:
```
MDR0001424_33433087970004
MDR0001438
```

Avoid altering files or structure after placing a project in the `READY/` folder.

---

## 2. QC and Review Handoff

### 2.1 Review Trigger

The presence of a project folder in `READY/` signals that digitization is complete and the project is ready for QC.

### 2.2 QC Process

Designated QC staff will follow the procedures documented in the [AMI Quality Control Workflow](https://nypl.github.io/ami-preservation/pages/preservationServices/qualityControl/qc-workflow.html).

QC review includes technical and structural verification and may result in notes or rework requests.

### 2.3 EAVie Copy

As part of the QC process, staff will:

- **Copy service copy files** (e.g., MP4 access derivatives) to the AWS-hosted repository used by the Early Access Viewer (EAVie), enabling internal staff access prior to full preservation ingest.

---

## 3. Preservica Ingest

Once QC is complete, responsibility transfers to the **Digital Preservation team**, specifically the **Digital Repository Coordinator**, for ingest into NYPL’s preservation systems.

Current responsibilities include:

1. **Copying all packages** to **Amazon Deep Glacier** for short-term redundancy.
2. **Ingesting all packages** into **Preservica**, NYPL’s digital preservation platform.
3. **Moving successfully ingested packages** from the `READY/` or `QCPass/` folder into an `INGESTED/` folder within each staff member’s Qumulo directory.

> *Note: Process details and automation scripts for Deep Glacier and Preservica ingest will be documented separately by the Digital Preservation team.*

---

## Roles and Responsibilities

| **Team**                  | **Responsibilities**                                                                 |
|---------------------------|--------------------------------------------------------------------------------------|
| Media Preservation Engineers | Capture or transfer digitization packages to `READY/`; maintain directory hygiene  |
| QC Staff                  | Perform QC; log results; copy access files to AWS for EAVie                          |
| Digital Preservation Team | Copy to Deep Glacier; ingest to Preservica; relocate packages post-ingest           |
