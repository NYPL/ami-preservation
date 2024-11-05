---
title: Generating Service Copies
layout: default
nav_order: 1
parent: DVD Processing
grand_parent: Optical Media

---

# Generating Service Copies
{: .no_toc }

Our approach to generating MP4 service copies from ISO disc images of DVDs has evolved over the years. Unlike other media formats, creating an MP4 service copy from a DVD requires decisions that may not fully capture the experience of viewing the DVD on a native DVD player or even in software like VLC, which more faithfully reproduces menu navigation and interactive features. However, these choices are necessary to ensure accessible, high-quality service copies of these media objects.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Current Approach

We utilize our [ISO Transcoder Script](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/iso_transcoder.py), which leverages MakeMKV to create intermediate MKV files for each video title set found within the ISO disc image of a DVD. This step provides a high-fidelity representation of each video title set, preserving essential structural information from the DVD.

Our script’s default behavior is to produce one MP4 per video title set, but DVDs vary widely in how they are authored. To address these variations, our script includes a `-f --force` flag, which concatenates the separate MKVs into a single MP4 file before transcoding. This option is intended only for cases where the title sets on an ISO appear to have been unintentionally fragmented.

## DVD Structure

Understanding the structure of DVDs is essential to accurately recreating service copies. DVDs are typically organized into:

- **Title Sets**: Each title set can contain multiple **VOB** (Video Object) files, along with **IFO** (Info) files that describe the structure, and **BUP** (Backup) files as backups for IFO data.
- **Cells**: Cells are the smallest unit within VOBs and may represent chapters or smaller segments within a title.

MakeMKV interprets this structure effectively, especially with DVDs created by amateur authors, where structure and file integrity can be inconsistent. MakeMKV helps overcome these inconsistencies by handling variations within DVD structures accurately and producing reliable intermediate MKV files.

## Advantages of MakeMKV and Matroska as an Intermediary

Using MakeMKV, and leveraging the Matroska (MKV) format as an intermediary, allows us to retain essential information from the original DVD, including chapters and subtitle tracks. MakeMKV performs faster and more effectively than other tools when processing problematic or slightly corrupted ISOs. This method ensures that as much structural and playback information as possible is preserved before the final MP4 transcode.

## Transcoding Approach with FFmpeg

Our current FFmpeg transcoding approach focuses on changing only the video and audio codecs when converting MKVs to MP4s, aligning with our service copy specifications of H.264 for video and AAC for audio. We retain all other properties, such as aspect ratios (Display Aspect Ratio, Pixel Aspect Ratio, Sample Aspect Ratio), frame rates, and complex audio channel configurations, as they were in the MKV files.

This streamlined approach allows us to process a wide variety of DVDs without compromising playback quality. While we acknowledge typical specifications for standard DVD types (listed below), we may manipulate outliers on a case-by-case basis to ensure alignment with expected standards.

## Typical DVD MP4 Specifications

Our experience has led us to identify broad categories of typical DVD specifications, though these specifications may vary. Below are the most common configurations we encounter:

### NTSC DVD SD
- **Video Width**: 720
- **Video Height**: 480
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 0.889
- **Frame Rate**: 29.970 (occasionally 24.000 or 23.976)

### NTSC DVD Widescreen
- **Video Width**: 720
- **Video Height**: 480
- **Display Aspect Ratio**: 1.777
- **Pixel Aspect Ratio**: 1.185
- **Frame Rate**: 29.970

### NTSC DVD SD (Alternate)
- **Video Width**: 704
- **Video Height**: 480
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 0.909
- **Frame Rate**: 29.970

### PAL DVD SD
- **Video Width**: 720
- **Video Height**: 576
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 1.067
- **Frame Rate**: 25.000

### PAL DVD Widescreen
- **Video Width**: 720
- **Video Height**: 576
- **Display Aspect Ratio**: 1.778
- **Pixel Aspect Ratio**: 1.422
- **Frame Rate**: 25.000

---

This foundational approach gives us the flexibility to adapt to the variety of DVD authoring styles, while standardizing our output to maintain playback quality and accessibility. As we continue to refine this workflow, we will adjust these categories and processes as necessary.
