---
title: MiniDisc Processing
layout: default
nav_order: 3
parent: Optical Media
grand_parent: Preservation Lab
---

# MiniDisc Processing
{: .no_toc }

This page outlines NYPL’s recommended workflow for migrating MiniDiscs (MD and Hi-MD) using Web MiniDisc Pro and the Sony MZ-RH1 recorder. The process ensures bit-accurate extraction of original ATRAC/PCM audio data along with metadata, aligned with AMI digitization specifications.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

### 1. Overview of the MiniDisc Format

MiniDisc (MD) is a magneto-optical disc format introduced by Sony in 1992, supporting both compressed and, in later models, uncompressed audio. There are two general categories:

- **MD (Standard)**: Uses ATRAC1/ATRAC3 lossy compression
- **Hi-MD**: Supports ATRAC3plus and uncompressed Linear PCM (WAV)

Audio is written non-contiguously, often with multiple fragments per track, making file-based extraction (rather than real-time playback) crucial for preservation.

For more background, refer to the [MiniDisc Wiki](https://www.minidisc.wiki/start/) which offers extensive technical detail, format comparisons, and software recommendations.

---

### 2. Hardware and Software Requirements

#### **Recommended Setup**

- **Recorder**: Sony MZ-RH1 (required for Hi-MD and native ATRAC extraction)
- **Cable**: USB-A to USB-Micro cable (direct connection preferred)
- **Computer**: macOS (Intel preferred); tested on macOS Sonoma 14.7.6
- **Browser**: Chromium-based (e.g., Google Chrome or Microsoft Edge)
- **App**: [Web MiniDisc Pro](https://web.minidisc.wiki/)

> ⚠️ Note: Connection stability varies between devices and OS versions. Avoid USB hubs or converters when possible.

---

### 3. Connecting the MiniDisc Recorder

1. Power on the MZ-RH1 and insert the MiniDisc.
2. Connect the device directly to your Mac via USB.
3. Launch a Chromium browser and go to: [https://web.minidisc.wiki](https://web.minidisc.wiki)
4. Click the **Connect** button.
5. Select the MZ-RH1 from the device list.
6. If successful, you’ll see:
   - Model name of the recorder
   - List of tracks with duration, encoding mode, and bitrate

---

### 4. Downloading Tracks and Metadata

#### **Download Individual Tracks**

1. Highlight each track one at a time — the selection turns pink.
2. Click **Download** (not **Download and Convert**).
3. Files are downloaded as `.aea` (ATRAC audio) to your `Downloads` folder.

#### **Export Track Metadata**

Before ejecting the disc:

1. Click the three-dot menu (top-right corner of the Web MiniDisc interface).
2. Select **Export Songtitles to CSV**.
3. A CSV file will be downloaded with the following headers:

```
INDEX,GROUP RANGE,GROUP NAME,GROUP FULL WIDTH NAME,NAME,FULL WIDTH NAME,ALBUM,ARTIST,DURATION,ENCODING,BITRATE
```

---

### 5. Folder Organization and Processing

1. Create a folder named using the **six-digit SPEC AMI ID**.
2. Move the `.aea` files and the `.csv` metadata file into this folder.

Your directory should look like this:

```
PrimaryID
├── division_PrimaryID_v01f01t01.aea
├── division_PrimaryID_v01f01t02.aea
└── division_PrimaryID_v01f01_pm.csv
```

3. Run the [`cd_processing.py`](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/cd_processing.py) script.

This will:

- Rename `.aea` files per NYPL’s filenaming convention
- Create corresponding FLAC edit masters
- Package files into the correct bag structure

---

### 6. Summary of MiniDisc Extraction Process

| Step                   | Tool / Action              | Notes                                                      |
|------------------------|----------------------------|------------------------------------------------------------|
| Hardware               | Sony MZ-RH1                | Required for native data extraction                        |
| Software               | Web MiniDisc Pro (browser) | Free, open-source tool for MD access                       |
| Track Download         | `.aea` files               | Retains ATRAC/PCM streams exactly as recorded              |
| Metadata Export        | CSV file                   | Functions similarly to a cue sheet                         |
| Directory Naming       | Manual                     | Must match SPEC AMI ID                                     |
| Post-Processing        | `cd_processing.py`         | Renames, transcodes, and bags per AMI spec                 |

---

This workflow supports reliable, non-real-time extraction of MiniDisc audio with full track segmentation and metadata preservation. It is designed to support NYPL’s long-term preservation goals while remaining adaptable to future MD formats and transfer tools.
