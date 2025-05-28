---
title: Digital Asset Specifications
layout: default
nav_order: 5
---

# AMI Digital Asset Specifications
This document outlines the technical specifications and requirements for the preservation-focused digitization of audio and moving image collections, along with guidelines for the packaging of digital deliverable files.

Last updated: 2025-05-19. For previous versions, see [changelog.md](https://github.com/NYPL/ami-preservation/commits/main/docs/pages/ami-specifications.md)

## Table Of Contents
<!-- MarkdownTOC -->

* [Specifications for Digital Assets](#specifications-for-digital-assets)
  * [Film Media](#film-media)
    * [Film Groups 1 and 2: Motion Picture Film, Silent / Sound](#film-groups-1-and-2-motion-picture-film-silent--sound)
    * [Film Group 3: Audio Film](#film-group-3-audio-film)
    * [Film Group 4: Filmstrips](#film-group-4-filmstrips)
  * [Video Media](#video-media)
    * [Video Group 1: Analog and Digital Cassettes, Analog Open Reel](#video-group-1)
    * [Video Group 2: DV](#video-group-2)
    * [Video Group 3: HDV](#video-group-3)
    * [Video Group 4: DVD-Video](#video-group-4)
    * [Video Group 5: VCD (Video CDs)](#video-group-5)
    * [Service Copy Specifications for Video](#service-copies)
    * [Additional Video Specifications](#additional-video-specifications)
  * [Audio Media](#audio-media)
    * [Audio Group 1: Analog Magnetic](#audio-group-1)
    * [Audio Group 2: Digital Magnetic](#audio-group-2)
    * [Audio Group 3: CD-DA (Compact Disc Digital Audio)](#audio-group-3)
    * [Audio Group 4: MiniDisc](#audio-group-4)
    * [Audio Group 5: Grooved Disc](#audio-group-5)
    * [Audio Group 6: Grooved Cylinder](#audio-group-6)
    * [Edit Master File Specifications](#edit-masters-all)
  * [Data Media](#data-media)
    * [Data Group 1: Optical Disc](#data-group-1)
  * [Image Deliverables](#image-deliverables)
  * [JSON Metadata Deliverables](#json-metadata-deliverables)

<!-- /MarkdownTOC -->

<a name="specifications-for-digital-assets"></a>

# Specifications for Digital Assets

Specifications may be modified over time to reflect changes in best practices or NYPL’s digital infrastructure, or to address previously unspecified media or conditions.

The following sections are broken into format groups to define the file deliverables for different media types and format variations.

**Note:** While this document outlines general specifications, the most precise and up-to-date technical criteria—particularly for file-level validation—can be found in our [MediaConch policy files](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/MediaconchPolicies).

**Digital Asset Packaging:**
All digital deliverables must be organized according to NYPL’s [digital asset packaging guidelines](https://nypl.github.io/ami-preservation/pages/preservationServices/vendorDigitization/vendor-ami-handling.html#digital-asset-packaging), which follow the [BagIt specification (v1.0)](https://tools.ietf.org/html/rfc8493). Each bag must:

* Represent only one inventoried collection object;
* Follow NYPL’s prescribed directory structure (`PreservationMasters`, `EditMasters`, `ServiceCopies`, `Images`, etc.);
* Include metadata JSON for each media file (image files excluded);
* Contain an `md5` manifest for all files in the `data` directory.

Bag directories must be named using the Primary ID of the collection object and must not be compressed.

**Filename Conventions:**
File naming rules are referenced throughout this document, but a full breakdown of filename components and role suffixes can be found in the [NYPL file naming convention guide](https://nypl.github.io/ami-preservation/pages/preservationServices/vendorDigitization/vendor-ami-handling.html#file-naming-convention).

Each filename is built from a standardized "root" that includes:

* a three-letter division prefix,
* the object's Primary ID,
* one or more structural components (e.g., `v01`, `f01`, `r01`, `s01`, `p01`, `t01`),
* and a two-letter suffix denoting the file’s role (`pm`, `em`, `sc`, `mz`).

**Examples:**

* `myd_123456_v01_pm.mkv` → Video Preservation Master
* `myh_987654_v01f01r01_pm.flac` → Audio Preservation Master (Face 1, Region 1)

For details on volume, face, region, stream, and part identifiers—as well as role suffixes—refer to the [file naming convention chart](https://nypl.github.io/ami-preservation/pages/preservationServices/vendorDigitization/vendor-ami-handling.html#file-naming-convention).

<a name="film-media"></a>

## Film Media

### _Deliverables_
For each original recording, the following should be produced:
* One preservation master file*
* One mezzanine file*
* One service copy file*
* One JSON metadata file per media file (see [JSON Metadata Deliverables](#json-deliverables))
* Optional image files as described in [Image Deliverables](#image-deliverables)

**If the object has audio content (i.e. composite sound print), audio must be synchronized and embedded in all final deliverables.**

**_Capture tools_**

Film must be digitized and captured either (1) as DPX, then transcoded along with synchronous Broadcast Wave files to FFV1/FLAC/Matroska using [RAWcooked](https://mediaarea.net/RAWcooked), or (2) directly to FFV1/FLAC/Matroska using a Lasergraphics scanner, provided that all NYPL specifications are met.

##### RAWcooked Parameters
When using RAWcooked to transcode from DPX to FFV1/Matroska, the following parameters must be used:
* `--output-name`: Set to match the NYPL filenaming convention
* `--framerate`: Set to match the source material's native frame rate
* `--check`: Enabled to verify successful encoding
* `--hash`: hash algorithm must be used/reversibility data created
* `--info`: Full encoding details must be preserved

<a name="film-groups-1-and-2-motion-picture-film-silent--sound"></a>

### Film Groups 1 and 2: Motion Picture Film, Silent / Sound

<a name="pm-fg1-2"></a>

#### **_Preservation Master File Specifications: Film Groups 1 & 2: Motion Picture Film, Silent / Sound_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| ---- | ---- | ---- | ---- |
| Video bit depth | 16 bit | 10 bit | 10 bit |
| Resolution | 4K optical side overscan | 2K optical side overscan | 2K optical side overscan |
| Video codec | FFv1 version 3 | FFv1 version 3  | FFv1 version 3 |
| File wrapper | Matroska (.mkv) | Matroska (.mkv) | Matroska (.mkv) |
| Frame size | 4096x3112 | 2048x1556 | 2048x1556 |
| Frame rate | (Same as source. If not described, please determine on viewing and describe in metadata) | (Same as source. If not described, please determine on viewing and describe in metadata) | (Same as source. If not described, please determine on viewing and describe in metadata) |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Audio bit depth* | 24 bit | 24 bit | 24 bit |
| Audio sampling rate* | 96000 Hz | 96000 Hz | 96000 Hz |
| Audio codec* | FLAC | FLAC | FLAC |
| Audio channels* | Same as source  | Same as source | Same as source |
| Color space | Linear RGB (4:4:4) | Linear RGB (4:4:4) | Linear RGB (4:4:4) |
| Color primaries | BT.709 | BT.709 | BT.709 |
| Transfer characteristics | Printing Density | Printing Density | Printing Density |
| Notes | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. |

\* Where audio is applicable.

<a name="mezz-fg1-2"></a>

#### **_Mezzanine File Specifications: Film Group 1 & 2 (Motion Picture Film, Silent / Sound)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Bit depth | 10 bit | 10 bit | 10 bit |
| Resolution** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Display aspect ratio** | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed |
| Video codec | ProResHQ | ProResHQ | ProResHQ |
| File wrapper | QuickTime (.mov) | QuickTime (.mov) | QuickTime (.mov) |
| Frame size | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Color space | YUV | YUV | YUV |
| Chroma subsampling | 4:2:2 | 4:2:2 | 4:2:2 |
| Frame rate | (Same as preservation master) | (Same as preservation master) | (Same as preservation master) |
| Scan type | Progressive | Progressive | Progressive |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Audio codec* | PCM | PCM | PCM |
| Audio bit rate* | 2304 kbps | 2304 kbps | 2304 kbps |
| Audio bit depth* | 24 bit | 24 bit | 24 bit |
| Audio sampling rate* | 48000 Hz | 48000 Hz | 48000 Hz |
| Audio channels* | same as Preservation Master* | same as Preservation Master* | same as Preservation Master* |
| Image corrections | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic |

\* Where audio is applicable.

<a name="sc-fg1-2"></a>

#### **_Service Copy File Specifications: Film Group 1 & 2 (Motion Picture Film, Silent / Sound)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Bit depth | 8 bit | 8 bit | 8 bit |
| Resolution** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Display aspect ratio** | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed |
| Video codec | H.264 | H.264 | H.264 |
| File wrapper | MPEG-4 (.mp4) | MPEG-4 (.mp4) | MPEG-4 (.mp4) |
| Color space | YUV | YUV | YUV |
| Chroma subsampling | 4:2:0 | 4:2:0 | 4:2:0 |
| Frame size | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Frame rate | (Same as preservation master) | (Same as preservation master)  | (Same as preservation master) |
| Scan type | Progressive | Progressive | Progressive |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Video bit rate | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality |
| Audio codec* | AAC | AAC | AAC |
| Audio bit rate* | 320 kbps (CBR) | 320 kbps (CBR) | 320 kbps (CBR) |
| Audio sampling rate* | 48000 Hz | 48000 Hz | 48000 Hz |
| Audio channels* | same as Mezzanine* | same as Mezzanine* | same as Mezzanine* |
| Image corrections| Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, non-anamorphic |

\* Where audio is applicable.

<a name="film-group-3-audio-film"></a>

### Film Group 3: Audio Film

<a name="pm-fg3"></a>

#### **_Preservation Master File Specifications: Film Group 3 (Audio Film)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Audio codec | FLAC | FLAC | FLAC |
| Wrapper | FLAC (.flac) | FLAC (.flac) | FLAC (.flac) |
| Bit depth | 24 bit | 24 bit | 24 bit |
| Sampling rate | 96000 Hz | 96000 Hz | 96000 Hz |
| Number of audio channels | (same as source) | (same as source) | (same as source) |
| Other characteristics | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. |

<a name="edit-masters-fg3"></a>

#### **_Edit Master File Specifications: Film Group 3 (Audio Film)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Audio codec | FLAC | FLAC | FLAC |
| Wrapper | FLAC | FLAC | FLAC |
| Bit depth | equal to preservation master | equal to preservation master | equal to preservation master |
| Sampling rate | equal to preservation master | equal to preservation master | equal to preservation master |
| Number of audio channels | equal to preservation master | equal to preservation master | equal to preservation master|
| Other characteristics | If there are tones / sync marks present, they must be captured and described in metadata signal notes | If there are tones / sync marks present, they must be captured and described in metadata signal notes | If there are tones / sync marks present, they must be captured and described in metadata signal notes |

**Note:** Unlike Film Groups 1 & 2, Film Group 3 (Audio film) uses Edit Masters rather than Mezzanine files. Service copies are not currently required for this group. The Edit Master serves as the primary access file.

<a name="film-group-4-filmstrips"></a>

### Film Group 4: Filmstrips
NYPL will review recommendations for digitization of filmstrips (and accompanying audio media, where applicable) before defining a specification.

<a name="video-media"></a>

## Video Media

<a name="deliverables"></a>

### _Deliverables_
For each original recording, the following should be produced:
  * One preservation master file
      * If EIA-608 (line 21) captions are present in source, one closed captions sidecar file
  * One service copy file
  * One JSON metadata file per media file (see [JSON Metadata Deliverables](#json-deliverables))
  * Optional image files as described in [Image Deliverables](#image-deliverables)

**_Capture tools_**
Preservation master video files must be generated by professional-grade capture devices and software, with either direct capture to FFV1/FLAC/MKV, or transcoding from V210/PCM/MOV. Specific FFmpeg transcoding recipes will be provided by NYPL to ensure consistency.

<a name="guidelines-preservation-master-files-all-groups"></a>

### Guidelines: Preservation Master Files, All Groups
  * Characteristics intrinsic to the broadcast standard of the source material—including frame rate, pixel aspect ratio, field dominance, resolution, and recording standard (NTSC, PAL, SECAM, etc.)—should be preserved.
  * Signal extraction must be optimal, and carried out using the equipment and accessories that are appropriate for the original format characteristics.
  * The most direct and clean signal path must be used at all times from source to destination. There may be no devices inserted in the signal path that are not being used. If there are multiple destination formats being used in the transfer the signal path must be routed in parallel. No daisy-chaining of devices may occur.
  * The highest quality signal format (Composite, S-Video, Component, SDI, etc.) available for the source media type must be used throughout the entirety of the signal path from source through destination. Exceptions to this must be explained and requested prior to performing the transfer.
  * Luminance, black, and color levels should be adjusted to existing color bars if they are present on tape and look accurate. If color bars are not present or are clearly inaccurate, preview each tape in order to adjust levels according to the content of the tape using known references (such as blue sky, known blacks and whites, flesh tone, etc.). Luma should be adjusted to fall within broadcast range (100 IRE max) and must not exceed 110 IRE.
  * The transfer should capture all content recorded on the original object, including any bars and tone, slates, or other material coming before the start of the recorded program.
  * The recording should run until the end of the recorded content (picture and sound).  If this endpoint cannot be unambiguously determined, the recording should run until the end of the original object.
  * If present on the source tape, EIA-608 (line 21) closed captions must be captured.
  * Audio tracks in preservation master files should be delivered as stereo pairs (e.g., two-channel interleaved tracks), regardless of the original channel configuration. This approach prevents playback and transcoding issues while maintaining the ability to manipulate individual channels. Mono sources should be mapped to stereo as needed.
  * For tapes that include both linear audio and Hi-Fi audio tracks, stereo track 1 (CH1/2) should capture the linear audio and stereo track 2 (CH3/4) should capture the Hi-Fi audio. Video tracking should be carefully adjusted to optimize Hi-Fi audio quality, provided that image quality is not compromised.

  
<a name="silent-audio-channels"></a>

### Silent Audio Channels

* If a channel is present but silent on the source tape, it should be captured and documented in the JSON file. For example:

    * When soundField is set as "ch.1: mono, ch.2: none" instead of just "ch.1: mono", it indicates that the source tape has two recorded channels, with channel 2 being silent. The source.audioRecording.numberOfAudioTracks should be set to 2.
    * The preservation master will contain one stereo track (following our standard practice), but the metadata will document that the source had two channels, one silent.

* When two silent channels are detected as actual recorded channels (recorded with no audio signal rather than unrecorded), both should be captured. The preservation master will still contain one stereo track, and a signalNote should indicate that the source tape channels are silent.

<a name="timecode"></a>

### Timecode
  * Two forms of legacy/source timecode should be retained: LTC Timecode, recorded on an audio channel, should be captured as an audio stream in the resulting preservation master file; VITC timecode, if present, should be captured through the use of appropriate playback devices and a carefully routed SDI signal chain.

### _Video Preservation Master Sidecar Files_

**EIA-608 (line 21) Closed Captions (.scc)**
* If EIA-608 (line 21) captions are present in the source object, a sidecar Scenarist Closed Caption File (.scc) must be created.
* The file should follow the naming convention: `division_PrimaryID_v01_pm.scc`
* Place the file alongside the video preservation master in the `PreservationMasters` directory.

**QCTools Report**
* Each video preservation master file may also receive a corresponding QCTools report as a gzipped XML file.
* The file should follow the naming convention: `division_PrimaryID_v01_pm.mkv.qctools.xml.gz`
* Place the file alongside the preservation master file in the `PreservationMasters` directory.

**Example directory structure:**

```
PrimaryID
├── data
│ ├── PreservationMasters
│ │ ├── division_PrimaryID_v01_pm.mkv
│ │ ├── division_PrimaryID_v01_pm.scc
│ │ └── division_PrimaryID_v01_pm.mkv.qctools.xml.gz
│ └── ServiceCopies
│ └── division_PrimaryID_v01_sc.mp4
```

<a name="video-group-1"></a>

### Video Group 1: Analog and Digital Cassettes, Analog Open Reel

#### **_Preservation Master File Specifications_**

| Attribute | Specification |
| ---- | ------ |
| Video codec | FFv1 version 3 |
| Data compression | Lossless, Intra-frame (GOP-1) only |
| Color space | YUV |
| Chroma subsampling | 4:2:2 |
| Bit depth | 10-bit |
| File wrapper | Matroska (.mkv) |
| Frame rate | SD: 29.97 (NTSC) or 25 (PAL); HD: same as source |
| Frame size | SD: 720x486 (NTSC) or 720x576 (PAL); HD: 1920x1080 |
| Broadcast standard | (Same as original media) |
| Pixel aspect ratio | SD: 0.909 (NTSC) or 1.091 (PAL); HD: 1.000 |
| Slices | 24 |
| Slicecrc | 1 |
| Audio format | FLAC |
| Audio bit depth | 24 bit |
| Audio sampling rate | 48 kHz |
| Audio channels | (Same as original media, see guidelines for silent channels) |

<a name="video-group-2"></a>

### Video Group 2: DV

NYPL prefers native capture of DV content over FireWire whenever possible. All natively captured DV files must be processed using [dvpackager](https://mipops.github.io/dvrescue/sections/packaging.html), part of the DVRescue project, and rewrapped as Matroska (.mkv).

By default, dvpackager will segment files when there are changes to key signal parameters (such as aspect ratio or broadcast standard). NYPL prefers a minimal number of segments, but splitting is acceptable when necessary due to such changes. Segments are initially labeled as part1, part2, etc., but must be renamed to follow NYPL's filenaming convention using region identifiers (e.g., _v01f01r01, _v01f01r02, etc.).

When native capture is not possible due to object condition or playback issues, DV or HDV tapes may be captured via SDI as V210/MOV and subsequently transcoded and rewrapped as .mkv.

#### **_Preservation Master File Specifications: DV Cassettes_**

| Attribute | Specification | Notes |
| ---- | ---- | ---- |
| Video codec | DV | Native DV stream extracted from source |
| File wrapper | Matroska (.mkv) | DV files must be processed using dvpackager and rewrapped as .mkv |
| Other characteristics | (Same as source) | Splitting allowed when aspect ratio or broadcast standard changes mid-recording. Filenames must follow NYPL's regional naming convention. |
| Alternate method | FFv1 in Matroska (.mkv) | If native capture fails, SDI capture to V210/MOV may be transcoded and rewrapped. |

#### SDI Capture Fallback Specifications (when native DV capture is not possible)

| Attribute | Specification |
| ---- | ------ |
| Initial capture codec | V210 (10-bit uncompressed) |
| Initial capture wrapper | QuickTime (.mov) |
| Transcode codec | FFv1 version 3 |
| Final wrapper | Matroska (.mkv) |
| Audio | FLAC (24 bit, 48kHz) |

<a name="video-group-3"></a>

### Video Group 3: HDV

NYPL prefers native capture of HDV content via FireWire, preserving the original MPEG-2 transport stream. Files should be saved as `.m2t` and subsequently rewrapped as Matroska (`.mkv`) using a lossless method that retains all original stream characteristics.

Native capture ensures the preservation of embedded metadata, timecode, and recording characteristics. NYPL prefers that a **single `.m2t` stream** is retained wherever possible, though segmentation is acceptable if necessitated by signal changes (e.g., aspect ratio shifts, standard transitions). Segmented files must be renamed according to NYPL's filenaming convention for regions (e.g., `_v01f01r01`, `_v01f01r02`, etc.).

When native capture is not possible due to object condition or playback issues, HDV tapes may be captured via SDI as V210/MOV and then transcoded to FFV1/FLAC in Matroska (`.mkv`).

#### **_Preservation Master File Specifications: HDV Cassettes_**

| Attribute           | Specification                           | Notes                                                                 |
|---------------------|------------------------------------------|-----------------------------------------------------------------------|
| Video codec          | MPEG-2                                   | Native HDV stream extracted from source                               |
| File wrapper         | Matroska (.mkv)                          | Original `.m2t` must be rewrapped as `.mkv`, preserving stream characteristics |
| Audio codec          | MPEG-1 Layer II or AC-3 (as in source)   | Retain original audio streams; do not convert                         |
| Other characteristics| (Same as source)                         | Segment splitting allowed if required by stream changes; use NYPL filenaming convention for regions |
| Alternate method     | FFV1/FLAC in Matroska (.mkv)             | If native capture fails, SDI capture to V210/MOV may be transcoded and rewrapped using the same parameters as the DV fallback method |

<a name="video-group-4"></a>

### Video Group 4: DVD-Video

#### **_Preservation Master File Specifications: DVD-Video_**

| Attribute | Specification |
| ---- | ------ |
| File system | Preserve as-is from source disc; may include UDF, ISO 9660, or a hybrid structure |
| File wrapper | ISO (.iso) |
| Other characteristics | Full disc image must retain original structure, including VIDEO_TS and AUDIO_TS directories where present |

<a name="video-group-5"></a>

### Video Group 5: Video CDs (VCD)

#### **_Preservation Master File Specifications: Video CDs (VCD)_**

| Attribute       | Specification                                                                                                 |
|-----------------|---------------------------------------------------------------------------------------------------------------|
| File wrapper    | BIN/CUE pair                                                                                                  |
| `.bin` file     | Full raw-sector copy of the disc (2352-byte sectors, [Mode 2 Form 2](https://www.isobuster.com/help/what_is_mode_2_form_2_on_cd))                                            |
| `.cue` file     | Track layout, indexing, mode and sector metadata for the `.bin`                                               |
| File system     | File system: Create full raw sector image that preserves the complete disc structure, including the CD-ROM XA file system and all AUDIO/VIDEO DAT files                                             |
| Other           | Use the same naming convention as other PM files |

<a name="service-copies"></a>

### Service Copy Specifications for Video
<a name="service-copies-1/2"></a>

#### **_Service Copy File Specifications: Video Groups 1 and 2_**

| Attribute | Specification |
| ---- | ------ |
| Video codec | H.264/MPEG-4 AVC |
| Video bit rate | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 3.5 Mbps to approximate equivalent visual quality |
| Color space | 4:2:0 YUV |
| Bit depth | 8 bit |
| File wrapper | MPEG-4 (.mp4) |
| Frame rate | 59.94 (NTSC) or 50 (PAL) |
| Frame size | 720x480 (NTSC) or 720x576 (PAL) |
| Broadcast standard | (Same as original media) |
| Pixel aspect ratio | 0.889 (NTSC 4:3) or 1.091 (PAL 4:3); 1.185 (NTSC DV Widescreen); 1.422 (PAL DV Widescreen) |
| Audio codec | AAC |
| Audio bit rate | 320 kbps (CBR) |
| Audio sampling rate | 48 kHz |
| Audio channels | Same as Preservation Master (see examples) |

<a name="service-copies-dvd"></a>

#### **_Service Copy File Specifications: Video Group 4 (DVD-Video)_**

Due to the variety of encoding structures present on source DVDs, NYPL allows a broader range of specifications for service copies derived from DVD (video group 4). Files must comply with the following general characteristics, with resolution, frame rate, display aspect ratio, and pixel aspect ratio varying according to the source.

| Attribute           | Specification |
|---------------------|----------------|
| Video codec         | H.264 / MPEG-4 AVC |
| Video bit rate | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 3.5 Mbps to approximate equivalent visual quality |
| Color space | YUV |
| Chroma subsampling | 4:2:0 |
| Bit depth     | 8bit |
| File wrapper        | MPEG-4 (.mp4) |
| Frame rate          | NTSC: 29.970 / 59.940 / 23.976 / 47.952; PAL: 25.000 / 50.000 |
| Frame size          | Based on source DVD: 720x480, 704x480, 352x480, 352x240 (NTSC); 720x576, 352x576, 352x288 (PAL) |
| Broadcast standard | (Same as original media) |
| Display aspect ratio| 4:3 or 16:9 (1.333, 1.777, 1.778) |
| Pixel aspect ratio  | Based on source; ranges from 0.889 to 2.909 |
| Audio codec         | AAC |
| Audio channels      | 2 |
| Audio sampling rate | 48000 Hz |
| Audio bit rate      | 320 kbps (CBR) |

**Note:** While these specs permit a variety of technical values to accommodate the source material, all DVD-derived service copies must validate against the [NYPL MediaConch DVD SC policy](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts/MediaconchPolicies).

**Note for VCDs:**
Apply the same service-copy settings as for DVDs (see [Service copy specifications: video group 4](#service-copies-dvd)), transcoding the MPEG-1 DAT streams into H.264/MP4 per spec.

<a name="additional-video-specifications"></a>

### Additional Video Specifications

#### _Anamorphic Video_
  *  Service copies created from anamorphic preservation masters must be reformatted to true 16:9 (widescreen). Do not letterbox or pillarbox.

#### _Complex Audio Configurations_
  * In general, when multiple distinct language tracks are present as separate tracks, these should be retained in the service copy to preserve access to all content.
  * If distinct languages appear on individual channels of a single track and the result is difficult to understand (e.g., overlapping language audio), consult with NYPL. In most cases, the service copy should retain the English channel and omit the others to ensure accessibility.
  * If there is only audible content in a single channel of any number of channels in a source tape and preservation master, the channel containing audible content should be duplicated to produce a 2-channel service copy for improved user experience.
  * If a channel contains audible LTC (Longitudinal Timecode), it must be removed from the service copy. The remaining “normal” audio content should be duplicated across both channels.

#### _Trimming of Heads and Tails_
  * Color bars must not be trimmed.
  * Long tails of black / "snow" / unrecorded content may be trimmed after confirmation that there is no visible or audible recorded content.
  * Trimming must not result in an abrupt end of visible or audible content.

<a name="audio-media"></a>

## Audio Media

### *Deliverables*

<a name="audio-deliverables"></a>
For each collection object, the following should be produced:

* One or more preservation master file(s)
* One edit master file per preservation master
* One JSON metadata file per media file (see [JSON Metadata Deliverables](#json-deliverables))
* For optical audio only, one CUE file per preservation master file
* Optional image files as described in [Image Deliverables](#image-deliverables)

### *Capture tools*

<a name="audio-capture-tools"></a>
Preservation master and edit master files must be captured/encoded as Broadcast Wave Format (BWF). Files that exceed the Broadcast Wave Format 4GB file size limitation should be captured as RF64. Post-capture, all Broadcast Wave and RF64 files must be transcoded to the FLAC codec and container using the FLAC Utility, retaining embedded metadata and original modification times. Original capture as Wave64 (.w64) is not acceptable.

### Guidelines: Preservation Master Files, Audio

<a name="audio-guidelines"></a>

* Preservation master files must comply with technical recommendations outlined by the International Association of Sound and Audiovisual Archives (IASA-TC 03, version 3).
* Signal extraction must be complete, including lead-in and play-out.
* Analog-to-Digital conversion must use converters meeting FADGI’s Audio ADC Performance Specifications.
* No signal processing may be applied during ADC transfer (e.g., no EQ, gain adjustment, dither, or noise reduction).

#### Signal Extraction

<a name="audio-signal-extraction"></a>

* Extraction must use equipment and accessories appropriate for the original format.
* Flat (unmodified) transfers are required, with limited exceptions:

  * de-emphasis of stated pre-emphasis (EQ)
  * decoding of stated noise-reduction encoding
* Both intended and unintended signal content must be captured.
* One- or two-channel interleaved preservation masters may be created depending on the original recording.
* Levels may be adjusted **only** if distortion or clipping occurs; this must be documented in metadata.
* Sync tones (e.g. Pilottone) must be captured or resolved.
* All grooved media must include needle-drop and needle-lift.

#### Special circumstances and object-file relationships

<a name="audio-special-cases"></a>

* **Faces:** Each side of a cassette or disc is a discrete Face with a separate preservation master.
* **Regions:** New Region required for changes in speed or sampling rate.

  * **Speed changes:** 5-second overlap required between PM files.
  * **Sampling rate changes:** Overlap not required; include timestamp note in metadata.

#### Multi-track Preservation Masters

<a name="audio-multitrack"></a>

When dealing with multi-track recordings (e.g., 8-, 16-, 24-track open-reel tapes, multi-channel DAT or N-track digital formats), follow these guidelines:

* **Parallel, synchronized streams**
  Each track must be recorded as its own file, with precisely the same duration and time-alignment. This preserves phase relationships for later mixdown or analysis.

* **Filenaming for stream identifiers**
  Append a stream index identifier (`s01`, `s02`, …) between the face/region code and role suffix.
  * Format: `division_PrimaryID_vXXfYYsZZ_pm.flac`
  * `sZZ` = stream number, zero-padded to two digits.

* **No trimming or processing**
  Preservation masters must be “flat” transfers: no edits, fades, trims, or level adjustments. All overlap and dead-air at splice points remains intact.

* **Edit masters**
  No trimming or alteration is allowed for Edit Masters derived from these streams.

**Example: 24-track, two-inch open-reel tape (Face 1, Region 1):**

```
myd_123456_v01f01s01_pm.flac
myd_123456_v01f01s02_pm.flac
myd_123456_v01f01s03_pm.flac
…
myd_123456_v01f01s24_pm.flac
```

<a name="audio-pm-specs"></a>

<a name="audio-group-1"></a>

### **Audio Group 1: Analog Magnetic**

#### *Preservation Master File Specifications*

| Attribute          | Specification    |
| ------------------ | ---------------- |
| Audio codec        | FLAC             |
| File wrapper       | FLAC (.flac)     |
| Bit depth          | 24               |
| Sampling rate      | 96000 Hz        |
| Number of channels | (same as source) |

<a name="audio-group-2"></a>

### **Audio Group 2: Digital Magnetic**

Whenever possible, digital magnetic audio formats should be transferred using original playback equipment that supports native digital extraction. This approach—similar to our preferred method for DV video—ensures bit-perfect preservation of the original digital signal. If native digital migration is not possible due to equipment availability or format degradation, analog playback and re-digitization may be used as a fallback, pending approval from NYPL. Vendors must confirm and document the transfer method used for each asset.

#### *Preservation Master File Specifications*

| Attribute          | Specification    |
| ------------------ | ---------------- |
| Audio codec        | FLAC             |
| File wrapper       | FLAC (.flac)     |
| Bit depth          | (same as source, commonly 16 bit) |
| Sampling rate      | (same as source, commonly 48000 Hz, 44100 Hz, 32000 Hz (DAT), 44056 Hz (PCM-1610/30, F1)) |
| Number of channels | (same as source) |

<a name="audio-group-3"></a>

### **Audio Group 3: CD-DA**

NYPL’s preference is for all audio content present on the disc—including multiple sessions, if applicable—to be extracted and preserved. Tracks should be concatenated into a single WAV file according to the original track order defined in the CUE sheet. This ensures accurate representation of the disc’s structure and content while simplifying preservation workflows.

#### *Preservation Master File Specifications*

| Attribute             | Specification                           |
| --------------------- | --------------------------------------- |
| Audio codec           | FLAC                                    |
| File wrapper          | FLAC (.flac)                            |
| Bit depth             | 16 bit                                  |
| Sampling rate         | 44100 Hz                                |
| Number of channels    | 2 (left + right discrete)               |
| Other characteristics | CD tracks should be concatenated into a single file according to Cue sheet|

#### CUE sheet files

<a name="audio-cue"></a>

* Generate a .cue file during BWF capture before FLAC transcode.
* Name to match the WAV file, e.g., `myh_123456_v01f01_pm.cue`
* Place alongside the WAV in the `PreservationMasters` directory only:

```
PrimaryID
├── data
│ ├── PreservationMasters
│ │ ├── division_PrimaryID_v01f01_pm.flac
│ │ └── division_PrimaryID_v01f01_pm.cue
│ └── EditMasters
│   └── division_PrimaryID_v01f01_em.flac
```

<a name="audio-group-4"></a>

### **Audio Group 4: MiniDisc**

For MiniDiscs, NYPL's preference is to capture each track as a discrete file, preserving the structure and segmentation of the original disc. This approach accommodates the non-contiguous nature of audio data on MD and reflects the limitations and capabilities of current extraction tools.

Preservation masters are captured in ATRAC format (ATRAC1, ATRAC3, ATRAC3plus, or PCM for Hi-MD) and stored with the `.aea` file extension. Alongside each set of preservation masters, a CSV file is included that documents the track layout and metadata as exported by the transfer software.

#### *Preservation Master File Specifications*

| Attribute             | Specification                                                      |
| ---------------------|--------------------------------------------------------------------|
| Audio codec           | ATRAC1 / ATRAC3 / ATRAC3plus / PCM (as present on source)         |
| File wrapper          | AEA (.aea)                                                         |
| Bit depth             | As present on source (typically 16-bit for PCM)                    |
| Sampling rate         | As present on source (commonly 44100 Hz)                           |
| Number of channels    | 2 (left + right discrete)                                          |
| Other characteristics | One `.aea` file per track; no concatenation.                      |
| Additional file       | One CSV track metadata file (UTF-8, comma-separated)               |
| Placement             | CSV must be placed alongside `.aea` files in the `PreservationMasters` directory |

#### CSV Track Metadata File

The accompanying CSV must retain its original structure, as exported by the MiniDisc extraction software (e.g.,[Web MiniDisc Pro](https://web.minidisc.wiki/). It includes fields such as:

```
INDEX,GROUP RANGE,GROUP NAME,NAME,FULL WIDTH NAME,ALBUM,ARTIST,DURATION,ENCODING,BITRATE
```

The CSV filename should match the root of the preservation master files and be placed in the `PreservationMasters` directory alongside the `.aea` files—for example:

```
PrimaryID
├── data
│ ├── PreservationMasters
│ │ ├── division_PrimaryID_v01f01r01_pm.aea
│ │ ├── division_PrimaryID_v01f01r02_pm.aea
│ │ └── division_PrimaryID_v01f01_pm.csv
│ └── EditMasters
│   ├── division_PrimaryID_v01f01r01_em.flac
│   └── division_PrimaryID_v01f01r02_em.flac
```

<a name="audio-group-5"></a>

### **Audio Group 5: Grooved Disc**

#### *Preservation Master File Specifications*

| Attribute          | Specification             |
| ------------------ | ------------------------- |
| Audio codec        | FLAC                      |
| File wrapper       | FLAC (.flac)              |
| Bit depth          | 24                        |
| Sampling rate      | 96000 Hz                 |
| Number of channels | 2 (left + right discrete) |

#### Reproduction Details

<a name="audio-reproduction-details-disc"></a>

* Playback EQ must be applied and documented in metadata.

  * Default for transcription discs: 400Hz turnover, -12dB @ 10kHz
* Equipment requirements:

  * Time-Step or KAB Souvenir phono EQs (Owl EQs not acceptable)
  * Cartridge set to "lateral" unless otherwise specified
  * Full stylus kit on-hand; best stylus choice noted in metadata
  * Arm must be long enough and vertically adjustable
  * Arm must remain parallel during playback
* For multiple Regions due to speed/stylus change, create separate PMs.

  * Reattempt retracking if skips occur; document outcomes

<a name="audio-group-6"></a>

### **Audio Group 6: Grooved Cylinder**

#### *Preservation Master File Specifications*

| Attribute          | Specification             |
| ------------------ | ------------------------- |
| Audio codec        | FLAC                      |
| File wrapper       | FLAC (.flac)              |
| Bit depth          | 24                        |
| Sampling rate      | 96000 Hz                  |
| Number of channels | Mono (1)                 |

#### Reproduction Details

<a name="audio-reproduction-details-cylinder"></a>

* Transfer must be flat (no EQ), cartridge set to "vertical"
* Appropriate stylus kit required; best choice noted in metadata
* Groove pitch (TPI), speed, and cylinder material must be assessed and noted prior to capture

<a name="edit-masters-all"></a>

### *Edit Master File Specifications: All Audio Groups*

| Attribute          | Specification                |
| ------------------ | ---------------------------- |
| Audio codec        | FLAC                         |
| File wrapper       | FLAC (.flac)                 |
| Bit depth          | Equal to preservation master |
| Sampling rate      | Equal to preservation master |
| Number of channels | Mono (1) or Stereo (2) \*    |

\* For mono recordings, channel count should reflect true mono configuration.

#### Guidelines for Edit Masters

* Needle-drop/lift, unrecorded portions, and equipment noise must be trimmed
* Do not trim multi-track masters; silence is intentional
* Eliminate 5-second overlaps where used in Preservation Masters
* Level adjustments up to -2dB allowed when needed
* Mono recordings must be rendered as true mono

## Data Media

### *Deliverables*

<a name="data-deliverables"></a>
For each collection object, the following should be produced:

* One or more preservation master file(s)
* One JSON metadata file per media file (see [JSON Metadata Deliverables](#json-deliverables))
* Optional image files as described in [Image Deliverables](#image-deliverables)

**Filenaming and metadata protocol for misidentified discs:**

* If a disc described as Audio or Video is actually a data disc, omit any Face metadata.
* Use Volume-level naming only, e.g., `abc_123456_v01_pm.iso`
* Update format/media type per [Data Optical Disc JSON schema](https://github.com/NYPL/ami-metadata/blob/main/versions/2.0/schema/digitized_dataopticaldisc.json)

### *Capture tools*

<a name="data-capture-tools"></a>

* Use sector-by-sector imaging tools
* Output as ISO file
* Retain all file system structures as-is (UDF, ISO 9660, or hybrid)

<a name="data-group-1"></a>

#### **Preservation Master File Specifications: Data Optical Disc**

| Attribute             | Specification                                    |
| --------------------- | ------------------------------------------------ |
| File system           | Preserve as-is; UDF, ISO 9660, or hybrid allowed |
| File wrapper          | ISO (.iso)                                       |
| Other characteristics | Same as source                                   |

<a name="image-deliverables"></a>

## Image Deliverables

### Images

Photographic documentation is encouraged for all magnetic and optical media and their enclosures, especially when significant bibliographic annotations, labeling, or physical features are present. Where appropriate, photographic documentation of film media may also be included at NYPL’s discretion.

### Image file naming convention and controlled vocabulary

Image files should follow the same pattern as the media files, and be placed in the `Images` directory, at the same hierarchical level as the `PreservationMasters` and `EditMasters` directories. The following controlled vocabulary must be appended as the final suffix in each image file name:

* assetfront
* assetback
* assetside
* assetrightside (if applicable)
* assetleftside (if applicable)
* assettop (if applicable)
* assetbottom (if applicable)
* boxfront
* boxback
* boxside
* boxrightside (if applicable)
* boxleftside (if applicable)
* boxtop (if applicable)
* boxbottom (if applicable)
* ephemera

**Example structure:**

```
PrimaryID
├── data
│   ├── PreservationMasters
│   ├── EditMasters
│   └── Images
│       ├── div_PrimaryID_v01f01.jpg
│       ├── div_PrimaryID_v01f02.jpg
│       ├── div_PrimaryID_v01_assetfront.jpg
│       ├── div_PrimaryID_v01_assetback.jpg
│       └── div_PrimaryID_v01_assetside.jpg
```

#### Image Specifications for Photographs of Media Objects

| Attribute               | Specification                                                                                                                                                                                       |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source format           | All magnetic and optical media                                                                                                                                                                      |
| Bit depth               | 8 bits per RGB channel                                                                                                                                                                              |
| Colorspace (ICC)        | sRGB IEC61966-2.1                                                                                                                                                                                   |
| File format & extension | JPEG (.jpg)                                                                                                                                                                                         |
| Resolution              | Minimum 400 true DPI, without interpolation                                                                                                                                                         |
| Surfaces                | All enclosures: front, back, top, bottom, left side, right side                                                                                                                                     |
| Notes                   | Images with text/content should be oriented correctly. If a surface lacks content, it may be skipped. If the media object has extensive labeling, media and enclosure may be photographed together. |

<a name="json-deliverables"></a>

## JSON Metadata Deliverables

NYPL metadata deliverables must adhere to the customized fields and controlled vocabulary defined in NYPL’s [ami-metadata](https://github.com/NYPL/ami-metadata) JSON Schema repository.

* **Per-file packaging**
  Each audio, video, or film media file must have exactly one JSON sidecar. Images do **not** require JSON metadata.

* **Schema validation**
  JSON must validate against the appropriate schema. Any validation errors (including BOM/encoding issues) will prompt a full redelivery of the Bagged asset.

* **Naming**
  Use the same filename “root” as the media file, with a `.json` extension only.
  * ✅ `division_PrimaryID_v01_pm.json`
  * ❌ `division_PrimaryID_v01_pm.mov.json`

* **Encoding**
  JSON files must be encoded as UTF-8 **without** a Byte Order Mark (BOM). Including a BOM often breaks downstream validation; please ensure your editor or export tool does not insert one.

* **Where to find samples & instructions**
  See the `samples/` [folder](https://github.com/NYPL/ami-metadata/tree/main/versions/2.0/sample) in the schema repo for sample JSON, plus README-based validation steps.
