---
title: Generating Service Copies
layout: default
nav_order: 1
parent: DVD Processing
grand_parent: Optical Media

---

# Generating Service Copies
{: .no_toc }

Our approach to generating MP4 service copies from ISO disc images of DVDs has evolved over the years. Unlike other media formats, creating an MP4 service copy from a DVD requires decisions that may not fully capture the experience of viewing the DVD on a native DVD player or even in software like VLC, which more faithfully reproduces menu navigation and interactive features. However, these choices are necessary to ensure accessible, streamable service copies of these media objects.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

# Current Approach

We utilize our [ISO Transcoder MakeMKV Script](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/iso_transcoder_makemkv.py), which leverages MakeMKV to create intermediate MKV files for each video title set found within the ISO disc image of a DVD. This step provides a high-fidelity representation of each video title set, preserving essential structural information from the DVD.

The script’s default behavior is to produce one MP4 per video title set. However, DVDs vary widely in how they are authored. To address these variations, the script includes a `-f --force` flag, which concatenates the separate MKVs into a single MP4 file before transcoding. This option is intended only for cases where the title sets on an ISO appear to have been unintentionally fragmented.

## MediaInfo Extraction and Classification

In addition to transcoding, the ISO Transcoder MakeMKV Script now includes a **MediaInfo extraction and classification step**, which analyzes the resulting MP4s and classifies them based on the [Typical DVD MP4 Specifications](https://nypl.github.io/ami-preservation/pages/preservationLab/opticalMedia/dvdProcessing/service-copies.html#typical-dvd-mp4-specifications). 

The classification output provides a summary of how the MP4s conform to the expected categories and flags any files that do not match these specifications (outliers). Below is an example of the classification output:

```
Classification Summary:
- PAL DVD Half-D1 Resolution Widescreen: 1 MP4(s)
- PAL DVD Half-D1 Resolution: 4 MP4(s)
- NTSC DVD SD (D1 Resolution): 3 MP4(s)
- PAL DVD Widescreen: 4 MP4(s)
- NTSC DVD SD (4SIF Resolution): 1 MP4(s)
- PAL DVD SD (D1 Resolution): 1 MP4(s)

Outliers:
- /path/to/outlier1.mp4
- /path/to/outlier2.mp4
- /path/to/outlier3.mp4
```

Outliers should be carefully reviewed. These files may indicate discrepancies in the demuxing process or other structural issues with the original ISO. To investigate, mount the ISO and open the `VIDEO_TS` directory to check the technical specifications of the corresponding VOB files. If the specs of the VOBs do not match the outlier MP4s, consider reprocessing the ISO using the alternate approach detailed below.

---

## Alternative Approach for Challenging Cases

While the MakeMKV-based script is our preferred method due to its superior error handling, encryption handling, and retention of subtitles and chapters, there are scenarios where it may not be suitable:
1. **ISOs that fail processing with MakeMKV**: If MakeMKV cannot process an ISO, the alternate approach should be used.
2. **Outliers identified in the classification step**: In rare cases, MakeMKV’s demuxing may introduce discrepancies, resulting in MP4s that do not match the specifications of the original VOBs. For such cases, the alternate script provides a reliable fallback.

For these scenarios, we use the [ISO Transcoder Cat/MKVMerge Script](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/iso_transcoder_cat_mkvmerge.py). This script offers two processing options:
1. **`cat` Approach**: Concatenates the VOBs directly and quickly from the ISO before transcoding to MP4 with FFmpeg.
2. **`mkvmerge` Approach**: If `cat` fails, automatically uses MKVMerge to combine the VOBs into a single MKV file, which is then transcoded to MP4 with FFmpeg.

These methods are particularly useful for ISOs where MakeMKV encounters issues, such as structural anomalies, unsupported formats, or discrepancies in the resulting MP4s.

---

### Workflow Note for Outliers

When outliers are identified during the classification step:
1. **Mount the ISO and inspect the `VIDEO_TS` directory**:
   - Use MediaInfo or similar tools to extract the technical metadata of the VOB files.
   - Compare the specs of the VOBs to the flagged MP4 outliers.

2. **Reprocess with the alternate approach**:
   - If the specs of the VOBs differ from the outlier MP4s, reprocess the ISO using the Cat/MKVMerge Script.
   - This alternative method often resolves issues by bypassing MakeMKV and working directly with the VOBs.

By incorporating this additional layer of verification and reprocessing, we ensure that service copies accurately reflect the original content and conform to expected specifications.


## DVD Structure

Understanding the structure of DVDs is essential to accurately recreating service copies. DVDs are typically organized into:

- **Title Sets**: Each title set can contain multiple **VOB** (Video Object) files, along with **IFO** (Info) files that describe the structure, and **BUP** (Backup) files as backups for IFO data.
- **Cells**: Cells are the smallest unit within VOBs and may represent chapters or smaller segments within a title.

MakeMKV interprets this structure effectively, especially with DVDs created by amateur authors, where structure and file integrity can be inconsistent. The alternative `cat/mkvmerge` approach bypasses some of these inconsistencies, making it a reliable fallback.

## Advantages of MakeMKV and Matroska as an Intermediary

Using MakeMKV, and the Matroska (MKV) format as an intermediary, allows us to retain essential information from the original DVD, including chapters and subtitle tracks. MakeMKV performs faster and more effectively than other tools when processing problematic or slightly corrupted ISOs. This method ensures that as much structural and playback information as possible is preserved before the final MP4 transcode.

## Transcoding Approach with FFmpeg

Our current FFmpeg transcoding approach focuses on changing only the video and audio codecs when converting MKVs to MP4s, aligning with our analog video service copy specifications of H.264 for video codec and AAC for audio codec. We retain all other properties, such as aspect ratios (Display Aspect Ratio, Pixel Aspect Ratio, Sample Aspect Ratio), frame rates, and complex audio channel configurations, as they were in the MKV files.

This streamlined approach allows us to process a wide variety of DVDs without compromising playback quality. While we acknowledge typical specifications for standard DVD types (listed below), we may manipulate outliers on a case-by-case basis to ensure alignment with expected standards.

## Typical DVD MP4 Specifications

Our experience has led us to identify broad categories of typical DVD specifications, though these specifications may vary. Below are the most common configurations we encounter:

### NTSC DVD SD (D1 Resolution)
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

### NTSC DVD SD (4SIF Resolution)
- **Video Width**: 704
- **Video Height**: 480
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 0.909
- **Frame Rate**: 29.970

### NTSC DVD (SIF Resolution)
- **Video Width**: 352
- **Video Height**: 240
- **Display Aspect Ratio**: 1.339
- **Pixel Aspect Ratio**: 0.913
- **Frame Rate**: 29.970

### PAL DVD SD (D1 Resolution)
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

### PAL DVD (CIF Resolution)
- **Video Width**: 352
- **Video Height**: 288
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 1.092
- **Frame Rate**: 25.000

### PAL DVD (Half D1 Resolution)
- **Video Width**: 352
- **Video Height**: 576
- **Display Aspect Ratio**: 1.333
- **Pixel Aspect Ratio**: 2.182
- **Frame Rate**: 25.000

### PAL DVD (Half D1 Resolution Widescreen)
- **Video Width**: 352
- **Video Height**: 576
- **Display Aspect Ratio**: 1.778
- **Pixel Aspect Ratio**: 2.909
- **Frame Rate**: 25.000

---

This foundational approach gives us the flexibility to adapt to the variety of DVD authoring styles, while standardizing our output to maintain playback quality and accessibility. As we continue to refine this workflow, we will adjust these categories and processes as necessary.
