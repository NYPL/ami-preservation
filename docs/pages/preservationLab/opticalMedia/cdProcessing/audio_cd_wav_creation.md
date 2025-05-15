---
title: WAV Creation
layout: default
nav_order: 1
parent: CD Processing
grand_parent: Optical Media
---

# WAV Creation
{: .no_toc }

This page provides a detailed guide for extracting audio from Audio CDs using ISOBuster and the Nimbie disc robot. The process ensures preservation-quality WAV creation, aligned with our AMI digitization workflows.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

### 1. WAV Extraction from Audio CDs

Our Audio CD migration process is based on a Windows PC equipped with the Acronova Nimbie disc robot and ISOBuster version 4.9. This combination is effective for high-volume extraction and reliable with challenging discs.

#### **System Setup and Access**

1. Use a Windows PC configured with ISOBuster and the Nimbie.
2. Log in with your standard Windows Library credentials.
3. To initialize ISOBuster with the Nimbie drive:
   - Open File Explorer and navigate to `This PC`.
   - Right-click on the Nimbie device (e.g., `BD-RE Drive (E:)`) and select **Investigate with IsoBuster**.
   - You’ll be prompted by a User Account Control window to enter admin credentials (posted on the workstation).

If successful, ISOBuster will launch and display the Nimbie drive, typically listed as `E: PIONEER BD-RW BDR 212-M`.

---

#### **Disc Loading and File System Recognition**

1. Open or close the tray using the top-left icon in ISOBuster.
2. Insert the Audio CD and wait for it to process the file system.
3. A true Audio CD (CD-DA) will display a hierarchy like:
   ```
   CD
   └── Session 1
       ├── Track 01
       ├── Track 02
       └── ...
   ```

---

#### **Extracting WAV Files**

1. Right-click on the top-level `CD`.
2. Select:  
   **Extract CD Content → Extract Audio to Wave File (.wav)**
3. A "Browse for Folder" dialog will appear — select or create your destination directory.
4. ISOBuster will output:
   - A folder named `CD`
   - Inside: `Session 1` directory
   - Inside that: Individual WAV tracks (Track 01.wav, Track 02.wav, etc.)

---

#### **Preparing the Output Directory**

1. Rename the outer `CD` folder to the **six-digit SPEC AMI ID** associated with the disc.
   - This is required for the `cd_processing.py` script to recognize and process the disc later.
2. You should now have:
   ```
   [SPEC_ID]/
   └── Session 1/
       ├── Track 01.wav
       ├── Track 02.wav
       └── ...
   ```

---

#### **Cue Sheet Creation**

1. Right-click on the top-level `CD` entry again.
2. Select:  
   **Create Cue Sheet File → Image contains M1 and/or M2 and/or Audio (2352)**
3. Save the `.cue` file **inside the Session 1 directory**, alongside the WAV tracks.
   - Accept the default filename (usually `CD.cue`, or a title-based name if present).

---

#### **Handling Errors and Problematic Discs**

If ISOBuster encounters problematic sectors, it may prompt you to choose:

1. Omit Sector  
2. Replace with all zeroes  
3. Replace with dummy data

Consult [ISOBuster’s official guidance](https://www.isobuster.com/help/errors_during_extraction) for context. Generally:
- Choose "Always Apply Selection" to avoid repeated prompts.
- We currently do not enforce a specific option but recommend documenting the choice.

---

### 2. Workflow Summary and Folder Structure

Repeat this process for each disc. Your final project directory should resemble:

```
project_directory/
├── 123456/
│   └── Session 1/
│       ├── Track 01.wav
│       ├── Track 02.wav
│       └── CD.cue
├── 123457/
│   └── Session 1/
│       ├── Track 01.wav
│       ├── Track 02.wav
│       └── CD.cue
...
```

Each subdirectory should be named using the corresponding six-digit SPEC AMI ID.

---

### Summary of Audio CD Extraction Process

| Step                   | Tool/Action                  | Notes                                                                 |
|------------------------|------------------------------|-----------------------------------------------------------------------|
| System Access          | Windows login + Admin access | Required to run ISOBuster via right-click                            |
| Disc Recognition       | ISOBuster                    | Shows CD → Session → Track hierarchy                                 |
| WAV Extraction         | ISOBuster                    | Outputs individual tracks as WAV files                               |
| Directory Renaming     | Manual                       | Must match six-digit SPEC AMI ID                                     |
| Cue Sheet Creation     | ISOBuster                    | Required for further processing with `cd_processing.py`              |
| Error Handling         | ISOBuster prompts            | Choose best option; apply setting to all                            |

---

This workflow supports a batch-oriented approach to Audio CD preservation, using reliable tools for maximum compatibility and data integrity. For combining individual tracks into single WAVs and further processing, refer to our [`cd_processing.py`](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/cd_processing.py) script.
