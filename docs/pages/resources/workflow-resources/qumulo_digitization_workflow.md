---
title: Qumolo workflow
layout: default
nav_order: 6
parent: Workflow Resources
grand_parent: Resources
---

# Qumulo-Based Digitization and Preservation Workflow

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
- **(b) Capture locally**, then use `rsync` to copy completed projects to the centralized `_READYFORQC/` directory:
  ```
  /Volumes/amip//_READYFORQC/
  ```

Use appropriate `rsync` flags (e.g., `-rtv --progress`) to preserve timestamps, resume transfers, and verify completion.

---

### 1.2 Directory Structure

Engineers maintain personal directories for in-progress work. Once a project is finished, it must be moved to the centralized QC queue.

- **Personal Directory** `/Volumes/amip/<username>/WORKING` – Used for active capture/working files.
- **QC Queue** `/Volumes/amip/_READYFORQC_` – The destination for all completed projects ready for QC handoff.

Project subdirectories should be named using the Media Digitization Request (MDR) ID, optionally followed by barcode:
```
MDR0001424_33433087970004
MDR0001438
```

Avoid altering files or structure after placing a project in the `_READYFORQC/` folder.

---

## 2. QC and Review Handoff

### 2.1 Review Trigger

The presence of a project folder in `_READYFORQC/` signals that digitization is complete and the project is ready for QC.

### 2.2 QC Process

Designated QC staff will follow the procedures documented in the [AMI Quality Control Workflow](https://nypl.github.io/ami-preservation/pages/preservationServices/qualityControl/qc-workflow.html).

QC review includes technical and structural verification and may result in notes or rework requests.

### 2.3 EAVie Copy

As part of the QC process, staff will:

- **Copy service copy files** (e.g., MP4 access derivatives) to the AWS-hosted repository used by the Early Access Viewer (EAVie), enabling internal staff access prior to full preservation ingest.

### 2.4 Post-QC Handoff

Upon successful completion of QC and the EAVie transfer:

- QC Staff will move the project folder from `_READYFORQC/` to the **`_QCPass/`** directory.
- This action signals to the Digital Preservation team that the content is approved for final ingest.

---

## 3. Preservica Ingest

The **Digital Repository Coordinator** will monitor the `_QCPass/` directory at regular intervals to perform preservation actions.

Current responsibilities include:

1.  **Copying all packages** from `_QCPass/` to **Amazon Deep Glacier** for short-term redundancy.
2.  **Ingesting all packages** into **Preservica**, NYPL’s digital preservation platform.
3.  **Moving successfully ingested packages** from the `_QCPass/` folder into the `_INGESTED/` folder.
4.  **Deleting projects** from the `_INGESTED/` directory once Deep Glacier and Preservica ingest are confirmed.

> *Note: Process details and automation scripts for Deep Glacier and Preservica ingest will be documented separately by the Digital Preservation team.*

---

## Roles and Responsibilities

| **Team** | **Responsibilities** |
|---------------------------|--------------------------------------------------------------------------------------|
| Media Preservation Engineers | Capture or transfer digitization packages to `READY/`; maintain directory hygiene  |
| QC Staff                  | Perform QC; log results; copy access files to AWS; move approved projects to `_QCPass/` |
| Digital Preservation Team | Monitor `_QCPass/`; copy to Deep Glacier; ingest to Preservica; move to `_INGESTED/` and delete post-verification |
