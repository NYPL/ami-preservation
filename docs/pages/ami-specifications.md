---
title: Digital Asset Specifications
layout: default
nav_order: 5
---

# AMI Digital Asset Specifications
This document outlines the technical specifications and requirements for digitization of analog media collections and digital packaging of deliverable files.

## Table Of Contents
<!-- MarkdownTOC -->

- [Specifications for Digital Assets](#specifications-for-digital-assets)
  - [Film Media](#film-media)
    - [Film Groups 1 and 2: motion picture film, silent / sound](#film-groups-1-and-2-motion-picture-film-silent--sound)
    - [Film Group 3: audio film](#film-group-3-audio-film)
    - [Film Group 4: filmstrips](#film-group-4-filmstrips)
  - [Video media](#video-media)
    - [Video Group 1: analog and digital cassettes, analog open reel](#video-group-1)
    - [Video Group 2: DV](#video-group-2-dv)
    - [Video Group 2: DV](#video-group-2-hdv)
    - [Video Group 3: optical video](#video-group-2)
  - [Audio media](#audio-media)
    - [Audio Group 1: analog magnetic](#audio-group-1)
    - [Audio Group 2: digital magnetic](#audio-group-2)
    - [Audio Group 3: optical audio](#audio-group-3)
  - [Data Media](#data-media)

<!-- /MarkdownTOC -->


<a name="specifications-for-digital-assets"></a>
# Specifications for Digital Assets

Specifications may be modified over time to reflect changes in best practices or NYPL’s digital infrastructure, or to reflect previously unspecified media or conditions.

The following sections are broken into format groups to define the file deliverables for different media types and format variations.

<a name="film-media"></a>
## Film Media

#### _Deliverables_
For each original recording, the following shall be produced:
* One preservation master file*
* One mezzanine file*
* One service copy file*
* One metadata file per media file
  
**If the object has audio content (i.e. composite sound print), audio must be synchronized and embedded in all final deliverables.**

**_Capture tools_**

Film must be digitized and captured either (1) as DPX, then transcoded along with synchronous Broadcast Wave files to FFV1/FLAC/Matroska using [RAWcooked](https://mediaarea.net/RAWcooked), or (2) directly to FFV1/FLAC/Matroska using a Lasergraphics scanner, provided that all NYPL specifications are met.

<a name="film-groups-1-and-2-motion-picture-film-silent--sound"></a>
### Film Groups 1 and 2: Motion picture film, silent / sound

<a name="pm-fg1-2"></a>
#### **_Preservation master file specifications: Film groups 1 & 2: Motion picture film, silent / sound_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| ---- | ---- | ---- | ---- |
| Video bit depth | 16 bit | 10 bit | 10 bit |
| Resolution | 4K optical side overscan | 2K optical side overscan | 2K optical side overscan |
| Video codec | FFv1 version 3 | FFv1 version 3  | FFv1 version 3 |
| File wrapper | Matroska (.mkv) | Matroska (.mkv) | Matroska (.mkv) |
| Frame size | 4096x3112 | 2048x1556 | 2048x1556 |
| Frame rate | (Same as source. If not described, please determine on viewing and describe in metadata signal) | (Same as source. If not described, please determine on viewing and describe in metadata signal) | (Same as source. If not described, please determine on viewing and describe in metadata signal) |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Audio bit depth* | 24 bit | 24 bit | 24 bit |
| Audio sampling rate* | 96,000 Hz | 96,000 Hz | 96,000 Hz |
| Audio codec/data encoding* | FLAC | FLAC | FLAC |
| Audio channels* | Same as source object | Same as source object | Same as source object |
| Color space | Linear RGB | Linear RGB | Linear RGB |
| Color primaries | BT.709 | BT.709 | BT.709 |
| Transfer characteristics | Printing Density | Printing Density | Printing Density |
| Notes | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. | Files may be transcoded from DPX using RAWcooked or captured directly to FFV1/MKV via an approved scanner. |

\* Where audio is applicable.

<a name="mezz-fg1-2"></a>
#### **_Mezzanine file specifications: Film group 1 & 2 (Motion picture film, silent / sound)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Bit depth | 10 bit | 10 bit | 10 bit |
| Resolution** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Display aspect ratio** | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed |
| Video codec | ProResHQ | ProResHQ | ProResHQ |
| File wrapper | Quicktime | Quicktime | Quicktime |
| Frame size** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Frame rate | (Same as preservation master) | (Same as preservation master) | (Same as preservation master) |
| Scan type | Progressive | Progressive | Progressive |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Audio data encoding* | PCM | PCM | PCM |
| Audio bit rate* | 2304 kbps | 2304 kbps | 2304 kbps |
| Audio bit depth* | 24 bit | 24 bit | 24 bit |
| Audio sampling rate* | 48,000 Hz | 48,000 Hz | 48,000 Hz |
| Audio channels* | same as Preservation Master* | same as Preservation Master* | same as Preservation Master* |
| Color space | 4:2:2 | 4:2:2 | 4:2:2 |
| Image corrections | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic |

\* Where audio is applicable.

<a name="sc-fg1-2"></a>
#### **_Service copy file specifications: Film group 1 & 2 (Motion picture film, silent / sound)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Bit depth | 8 bit | 8 bit | 8 bit |
| Resolution** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Display aspect ratio** | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed | 16:9 pillarboxed / letter boxed as needed |
| Video codec | H264 | H264 | H264 |
| File wrapper | MPEG-4 (.mp4) | MPEG-4 (.mp4) | MPEG-4 (.mp4) |
| Color space | 4:2:0 | 4:2:0 | 4:2:0 |
| Frame size** | 1920 x 1080 | 1920 x 1080 | 1920 x 1080 |
| Frame rate | (Same as preservation master) | (Same as preservation master)  | (Same as preservation master) |
| Scan type | Progressive | Progressive | Progressive |
| Pixel aspect ratio | 1.000 | 1.000 | 1.000 |
| Video bit rate | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 8 Mbps to approximate equivalent visual quality |
| Audio codec* | AAC | AAC | AAC |
| Audio bit rate* | 320 kbps | 320 kbps | 320 kbps |
| Audio sampling rate* | 48,000 Hz | 48,000 Hz | 48,000 Hz |
| Audio channels* | same as Mezzanine* | same as Mezzanine* | same as Mezzanine* |
| Image corrections| Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic | Color corrected for dye fading, cropped to picture - no frame-lines or sound track visible, Non-anamorphic |

\* Where audio is applicable.

<a name="film-group-3-audio-film"></a>
### Film Group 3: Audio film

<a name="pm-fg3"></a>
#### **_Preservation master file specifications: Film group 3 (Audio film)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Audio data encoding | Free Lossless Audio Encoding (FLAC) | Free Lossless Audio Encoding (FLAC) | Free Lossless Audio Encoding (FLAC) |
| Wrapper | FLAC (.flac) | FLAC (.flac) | FLAC (.flac) |
| Bit depth | 24 bit | 24 bit | 24 bit |
| Sampling rate | 96,000 Hz | 96,000 Hz | 96,000 Hz |
| Number of audio channels | (same as source) | (same as source) | (same as source) |
| Other characteristics | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. | If there are tones / sync marks present, they must be captured or resolved and described in metadata signal notes. |

<a name="edit-masters-fg3"></a>
#### **_Edit master file specifications: Film group 3 (Audio film)_**

| Source format | 35mm | 16mm | 8mm / Super 8mm / Double 8mm |
| --- | ---| --- | --- |
| Audio data encoding | FLAC | FLAC | FLAC |
| Wrapper | FLAC | FLAC | FLAC |
| Bit depth | equal to preservation master | equal to preservation master | equal to preservation master |
| Sampling rate | equal to preservation master | equal to preservation master | equal to preservation master |
| Number of audio channels | equal to preservation master | equal to preservation master | equal to preservation master|
| Other characteristics | If there are tones / sync marks present, they must be captured and described in metadata signal notes | If there are tones / sync marks present, they must be captured and described in metadata signal notes | If there are tones / sync marks present, they must be captured and described in metadata signal notes |

<a name="film-group-4-filmstrips"></a>
### Film Group 4: Filmstrips
NYPL will review recommendations for digitization of filmstrips (and accompanying audio media, where applicable) before defining a specification.

<a name="video-media"></a>
## Video media

<a name="deliverables"></a>
### _Deliverables_
For each original recording, the following shall be produced:
  * One preservation master file
      * If captions are present in source, one closed captions sidecar file
  * One service copy file
  * One metadata file per media file
  * Image files as described

**_Capture tools_**
Preservation master video files must be generated by professional-grade capture devices and software, with either direct capture to FFV1/FLAC/MKV, or transcoding from V210/PCM/MOV. Specific FFmpeg transcoding recipes will be provided by NYPL to ensure consistency.

<a name="guidelines-preservation-master-files-all-groups"></a>
### Guidelines: Preservation master files, all groups
  * Characteristics intrinsic to the broadcast standard of the source material, including frame rate, pixel aspect ratio, interlacing, resolution, and recording standard (NTSC, PAL, SECAM, etc.) should be preserved.
  * Signal extraction must be optimal, and carried out using the equipment and accessories that are appropriate for the original format characteristics.
  * The most direct and clean signal path must be used at all times from source to destination. There may be no devices inserted in the signal path that are not being used. If there are multiple destination formats being used in the transfer the signal path must be routed in parallel. No daisy-chaining of devices may occur.
  * The highest quality signal format (composite, S-Video, Component, SDI, etc.) available for the source media type must be used throughout the entirety of the signal path from source through destination. Exceptions to this must be explained and requested prior to performing the transfer.
  * Luminance, black, and color levels should be adjusted to existing color bars if they are present on tape and look accurate. If color bars are not present or are clearly inaccurate, preview each tape in order to adjust levels according to the content of the tape using known references (such as blue sky, known blacks and whites, flesh tone, etc.). Luma should be adjusted to fall within broadcast range (100 IRE max) and must not exceed 110 IRE.
  * The transfer should capture all content recorded on the original object, including any bars and tone, slates, or other material coming before the start of the recorded program.
  * The recording should run until the end of the recorded content (picture and sound).  If this endpoint cannot be unambiguously determined, the recording should run until the end of the original object.
  * If present on the source tape, closed captions must be captured.

<a name="video-preservation-master-sidecar-files"></a>
### Video preservation master sidecar files
#### Closed captions
  * If captions are present in source object, an .scc sidecar file must be created and accompany the preservation master file (closed captioning must be embedded in service copies. See service copy specifications).
      * Format: Scenarist Closed Caption File (.scc)
      * Naming Convention: division_PrimaryID_v01_pm.scc
  * Closed captions specifications may change in the future to accommodate updates to standards or NYPL infrastructure needs.

<a name="qctools-reports"></a>
### QCTools Reports
  * Each video preservation master file may also receive a corresponding QCTools report, which will be included in the PreservationMasters Bagged directory as a sidecar file.
      * Format: QCTools Report (gzipped XML) (https://www.bavc.org/preserve-media/preservation-tools)
      * Naming Convention: division_PrimaryID_v01_pm.mkv.qctools.xml.gz

<a name="video-group-1"></a>
**_Preservation master file specifications:_**
**_video group 1: analog and digital cassettes, analog open reel_**

| Attribute | Specification |
| ---- | ------ |
| Video codec | FFv1 version 3 |
| Data compression | Lossless, Intra-frame (GOP-1) only |
| Chroma subsampling | 4:2:2 YUV |
| Bit depth | 10-bit |
| File wrapper | Matroska (.mkv) |
| Frame rate | SD: 29.97 (NTSC) or 25 (PAL); HD: same as source |
| Frame size | SD: 720x486 (NTSC) or 720x576 (PAL); HD: 1920x1080 |
| Broadcast standard | (Same as original media) |
| Pixel aspect ratio | SD: 0.909 (NTSC) or 1.091 (PAL) |
| Slices | 24 |
| Slicecrc | 1 |
| Audio format | FLAC |
| Audio bit depth | 24-bit |
| Audio sampling rate | 48 kHz |
| Audio channels | (Same as original media, see guidelines for silent channels) |

<a name="silent-audio-channels"></a>
### Silent audio channels
  * If a channel is present but silent, it should be captured and noted in the JSON file, indicating that the tape and the channels in the preservation master file are silent. For example:

  * When soundField is set as "ch.1:mono, ch.2: none" instead of just "mono", it implies that the second channel exists, and source.audioRecording.numberOfAudioChannels should be set to 2. The preservation master file delivered will contain two audio channels, one of which is silent.

  * In cases where two silent channels are detected as actual channels (i.e., recorded with no sound rather than not recorded at all), both channels should be captured and included in the preservation master. Additionally, a signalNote should be added to indicate that the tape is silent.

<a name="timecode"></a>
### Timecode
  * Two forms of legacy/source timecode should be retained: LTC Timecode, recorded on an audio channel, should be captured as an audio stream in the resulting preservation master file; VITC timecode, if present, should be captured through the use of appropriate playback devices and a carefully routed SDI signal chain.

<a name="video-group-2"></a>
  **_Preservation master file specifications: video group 2: DV (digital video) cassettes_**

NYPL prefers native capture of DV content over FireWire whenever possible. All natively captured DV files must be processed using [dvpackager](https://mipops.github.io/dvrescue/sections/packaging.html), part of the DVRescue project, and rewrapped as Matroska (.mkv).

By default, dvpackager will segment files when there are changes to key signal parameters (such as aspect ratio or broadcast standard). NYPL prefers a minimal number of segments, but splitting is acceptable when necessary due to such changes. Segments are initially labeled as part1, part2, etc., but must be renamed to follow NYPL's filenaming convention using region identifiers (e.g., _v01r01, _v01r02, etc.).

When native capture is not possible due to object condition or playback issues, DV or HDV tapes may be captured via SDI as V210/MOV and subsequently transcoded and rewrapped as .mkv.

| Attribute | Specification | Notes |
| ---- | ---- | ---- |
| Video codec | DV | Native DV stream extracted from source |
| File wrapper | Matroska (.mkv) | DV files must be processed using dvpackager and rewrapped as .mkv |
| Other characteristics | (Same as source) | Splitting allowed when aspect ratio or broadcast standard changes mid-recording. Filenames must follow NYPL’s regional naming convention. |
| Alternate method | FFv1 in Matroska (.mkv) | If native capture fails, SDI capture to V210/MOV may be transcoded and rewrapped. |

<a name="video-group-2-hdv"></a>
### **_Preservation master file specifications: video group 2: HDV (high definition video) cassettes_**

NYPL prefers native capture of HDV content via FireWire, preserving the original MPEG-2 transport stream. Files should be saved as `.m2t` and subsequently rewrapped as Matroska (`.mkv`) using a lossless method that retains all original stream characteristics.

Native capture ensures the preservation of embedded metadata, timecode, and recording characteristics. NYPL prefers that a **single `.m2t` stream** is retained wherever possible, though segmentation is acceptable if necessitated by signal changes (e.g., aspect ratio shifts, standard transitions). Segmented files must be renamed according to NYPL's regional filenaming convention (e.g., `_v01r01`, `_v01r02`, etc.).

When native capture is not possible due to object condition or playback issues, HDV tapes may be captured via SDI as V210/MOV and then transcoded to FFV1/FLAC in Matroska (`.mkv`).

| Attribute           | Specification                           | Notes                                                                 |
|---------------------|------------------------------------------|-----------------------------------------------------------------------|
| Video codec          | MPEG-2                                   | Native HDV stream extracted from source                               |
| File wrapper         | Matroska (.mkv)                          | Original `.m2t` must be rewrapped as `.mkv`, preserving stream characteristics |
| Audio codec          | MPEG-1 Layer II or AC-3 (as in source)   | Retain original audio streams; do not convert                         |
| Other characteristics| (Same as source)                         | Segment splitting allowed if required by stream changes; use NYPL filenaming convention for regions |
| Alternate method     | FFV1/FLAC in Matroska (.mkv)             | If native capture fails, SDI capture to V210/MOV may be transcoded and rewrapped |


<a name="video-group-3"></a>
### **_Preservation master file specifications: video group 3: optical video discs_**

| Attribute | Specification |
| ---- | ------ |
| File system | (Preserve as-is from source disc; may include UDF, ISO 9660, or a hybrid structure) |
| File wrapper | ISO (.iso) |
| Other characteristics | Full disc image must retain original structure, including VIDEO_TS and AUDIO_TS directories where present |

<a name="service-copies-all"></a>
**_Service copy file specifications: all video groups_**

| Attribute | Specification |
| ---- | ------ |
| Video codec | H.264/MPEG-4 AVC (ISO/IEC 14496-10 - MPEG4 Part 10, Advanced Video Coding) |
| Video bit rate | CRF 21 (variable bitrate) for in-house workflows; vendors may use constant bitrate (CBR) encoding at 3.5 Mbps to approximate equivalent visual quality |
| Chroma subsampling | 4:2:0 YUV |
| Bit depth | 8-bit |
| File wrapper | MP4 |
| Frame rate | (Same as preservation master) |
| Frame size | (Same as preservation master, see below for Anamorphic video) |
| Broadcast standard | (Same as original media) |
| Pixel aspect ratio | (Same as preservation master, see below for Anamorphic video) |
| Audio codec | AAC |
| Audio bit rate | 320 kbps |
| Audio sampling rate | 48 kHz |
| Audio channels | 2 (see examples) |
| Closed captions* | CEA-608  (*if applicable) |

#### _Service copies, video group 3: optical video disc_
  * An individual service copy must be created for all discrete content. Example:
    * If a disc contains two discrete videos, each with different display aspect ratios (i.e. 16:9 vs. 4:3), a separate service copy must be made for each video.

<a name="additional-video-specifications"></a>
### Additional video specifications
#### _Anamorphic video_
  * For service copies created from Anamorphic preservation masters, treat source as D1/DV NTSC or PAL Widescreen to produce a 16 x 9 service copy without padding. Pixel aspect ratio should be 1.21 (NTSC) / 1.46 (PAL).

#### _Complex audio configurations_
  * 4 audio channels on source:
      * If a source tape has 4 audio channels of identical content (i.e. 4 mics in a single room recording the same content), the 4 channels captured in the preservation master should be mixed down to 2 for the service copy.
      * If each audio channel contains different content, consult with NYPL for how to proceed.
          * 2-channel Spanish / English language audio: If one channel contains Spanish dialogue and the other channel contains English dialogue, the audio content of the preservation master and the service copy must be identical.
      * Audible content in only one channel:
          * If there is only audible content in a single channel of any number of channels in a source tape and preservation master, the channel containing audible content should be mapped for production of a 2-channel service copy to provide a better user experience.

#### _Timecode_
  * Audible LTC Timecode should be eliminated, and “normal” content should be duplicated onto the second channel.

#### _Trimming of Heads and Tails_
  * Color bars must not be trimmed.
  * Long tails of black / “snow” / unrecorded content may be trimmed after confirmation that there is no visible or audible recorded content.
  * Trimming must not result in an abrupt end of visible or audible content.

<a name="audio-media"></a>
## Audio media

<a name="deliverables"></a>
### _Deliverables_
For each collection object, the following shall be produced:
  * One or more preservation master file(s)
  * One edit master file per preservation master
  * One metadata file per media file
  * For optical audio only, one CUE file per preservation master file
  * Image files as described

<a name="capture-tools"></a>
### _Capture tools_
Preservation master and edit master files must be captured/encoded as Broadcast Wave Format (BWF).

Files that exceed the Broadcast Wave Format 4GB file size limitation should be captured as RF64. Post-capture, all Broadcast Wave and RF64 files should be transcoded to the FLAC codec and container, with embedded metadata and original modification times retained through the use of the FLAC Utility (https://xiph.org/flac/download.html) by following the command listed on the FFmprovisr website (https://amiaopensource.github.io/ffmprovisr/#flac-tool). Original capture as Wave64 (.w64) is not acceptable.

<a name="audio-pms"></a>
#### Preservation master
  * Technical guidelines: The production of preservation master files will comply with the technical recommendations, practices and strategies outlined by the International Association of Sound and Audiovisual Archives
  * Strategic guidelines - IASA-TC 03, version 3: The production of preservation master files will comply with the ethical recommendations, practices and strategies outlined by the International Association of Sound and Audiovisual Archives.
  * Optimal signal extraction from analog sources seeks to be complete, and includes the transfer of the “lead-in” and “play-out” portions of a recording.
  * Analog signals will be converted to a digital bitstream by means of an Analog-to-Digital converter which complies with the specifications in FADGI’s Audio Analog-to-Digital Converter Performance Specification and Test Method.
  * No signal processing will be applied to the Analog-to-Digital converter’s digital bitstream, including, but not limited to equalization, level adjustment, dither, noise reduction.

#### Signal Extraction
  * Signal extraction from analog original audio recordings will comply with the technical recommendations, practices and strategies outlined by the International Association of Sound and Audiovisual Archives.
  * Optimal signal extraction for the production of preservation master files should aim to capture the complete dynamic and frequency ranges of the original recording.
  * Signal extraction must be carried out using the equipment and accessories that are appropriate and intended for the original format characteristics.
      * Example: a full-track mono recording on an open reel audio tape must be transferred using a full-track audio head (rather than a stereo head).
      * If this is not possible, provide an explicit proposal for work, subject to NYPL approval.
  * An optimal signal extraction from the original recording will be a flat (unmodified) transfer, free of signal processing, equalization, level adjustment, noise reduction, etc. Exceptions would include:
      * de-emphasis of a recording’s stated pre-emphasis (playback equalization)
      * decoding of a recording’s stated noise-reduction encoding
      * Optimal signal extraction from original sources includes the extraction of the intended signal, along with any unintended signal (such as artifacts and anomalies in the signal associated with the inherent limitations of historic recording technologies).
      * Preservation master files may be one or two-channel (interleaved), and the configuration employed will be determined by the needs of the original recording.
      * Levels may be adjusted ONLY if there is severe distortion or digital clipping from the source, and this adjustment must be noted clearly in the metadata.
      * If a sync tone is present (i.e. Pilottone), tone must be captured or resolved.  
      * For all grooved media, preservation master files must include the “needle-drop” and “needle-lift”.

#### Special circumstances and object-file relationships
  * **Faces:** In general, one preservation master file will be generated for each physically or technically discrete recording area of the original object.
      * For example, each side of an audio cassette or disc will be recorded as a separate preservation master file, identified with a designated Face number.
  * Considerations and circumstances that impact the number of preservation masters generated for each physical object, and/or for each discrete recording area:
      * For an object which is found to have content recorded both forwards and backwards on the same Face, a second Face may be created for the reversed content to be recorded in the proper direction.
      * **Region:** For an object with regions recorded at different speeds or sampling rates, a separate preservation master must be created for each Region (filename_v01f01r01_pm).

        * File overlap:
            * Speed Changes: If multiple preservation masters are created for a single recording due to speed changes, the cut should be made at a logical break in the audible content (if at all possible), and there must be exactly 5 seconds of audible content overlapping between the tail of the first preservation master and the head of the following PM so that the regions may be recombined in the future if necessary.
            * Sampling Rate Changes: If a digital source object has been recorded at multiple sampling rates, a separate preservation master must be created for each region. _These regions do not need to overlap, but please include a note listing the timestamp on the source object where each region begins._

#### Multi-track audio Preservation Masters
For multi-track audio masters, multiple **streams** are captured of identical length and intended to be mixed down. As mentioned below, the Edit Masters for these streams must not be trimmed or altered in any way.

<a name="audio-group-1"></a>
**_Preservation master file specifications: audio group 1: analog magnetic_**

  | Attribute | Specification |
  | ---- | ----- |
  |Audio data encoding | Free Lossless Audio Codec (FLAC) |
  | File wrapper | FLAC (.flac) |
  |Bit depth | 24 |
  | Sampling rate | 96,000 Hz |
  | Number of audio channels | (same as source) |

<a name="audio-group-2"></a>
**_Preservation master file specifications: audio group 2: digital magnetic_**

  | Attribute | Specification |
  | ---- | ----- |
  | Audio codec | Free Lossless Audio Codec |
  | File wrapper | FLAC (.flac) |
  | Bit depth | (same as source) |
  | Sampling rate | (same as source) |
  | Number of audio channels | (same as source) |

<a name="audio-group-3"></a>
**_Preservation master file specifications: audio group 3: optical disc_**

  | Attribute | Specification |
  | ---- | ----- |
  |Audio codec | Free Lossless Audio Codec (FLAC) |
  | File wrapper | FLAC (.flac) |
  | Bit depth | (same as source) |
  | Sampling rate | (same as source) |
  | Number of audio channels | 2 (left + right discrete) |
  | Other characteristics | CDs should be captured as a single file |

#### CUE sheet files
In congress with capturing a Broadcast Wave file prior to transcoding to .flac, a CUE file must be generated. The CUE file must:
* Follow the same naming convention as the WAV file, but instead with a ".cue" extension. Example: "myh_123456_v01f01_pm.cue"
* Be nested within the Preservation Masters directory, accompanying the Preservation Master WAV file (the Edit master must not have a .cue file):

  * PrimaryID
    * data
      * PreservationMasters
        * division_PrimaryID_v01f01.flac
        * division_PrimaryID_v01f01.cue
        * division_PrimaryID_v01f02.flac
        * division_PrimaryID_v01f02.cue
      * EditMasters
        * division_PrimaryID_v01f01.flac
        * division_PrimaryID_v01f02.flac

<a name="audio-group-4"></a>
**_Preservation master file specifications: audio group 4: grooved disc_**

  | Attribute | Specification |
  | ---- | ----- |
  | Audio data encoding | Free Lossless Audio Codec (FLAC) |
  | File wrapper | FLAC (.flac) |
  | Bit depth | 24 |
  | Sampling rate | 96,000 Hz |
  | Number of audio channels | 2 (left + right discrete) |

#### Reproduction details  
  * Playback EQ curves for all discs should be utilized.
      * If a disc’s playback curve is not known or stated on the label, the phono EQ should be set to RIAA (for microgrooves 1948-present) or a “default” curve of 400Hz turnover and -12dB @ 10kHz rolloff (for transcription discs). **All EQ curves should be noted in the metadata digitization process notes.**
  * Equipment
      * NYPL requires either the Time-Step line of phono EQs, or the KAB Souvenir Equalizer. Owl EQs are not acceptable due to the age, added noise floor, and lack of versatility needed for our collections. **Other phono EQs may be submitted for approval.**
  * All discs should be transferred with the cartridge switched to "lateral" unless otherwise indicated on the label.
  * A full complement of stylus shapes and sizes should be on-hand at the vendor transfer station, and **he best sounding size/shape stylus used for transfer should be noted in the metadata digitization process notes.**
        * Modern LP styli must **not** be used to transfer shellac, shellac-vinyl compound, or early vinyl discs.
  * Tone arm requirements:
        * Arm must be long enough to comfortably reach the outer grooves.
        * Arm should be vertically adjustable to accommodate the various thicknesses of pressings.
        * During playback, the angle of the tonearm from front to back should be perfectly parallel in relationship to the disc while it is playing.
  * While playing a face, for any speed changes or instances where the stylus has to be repositioned to continue playing, a separate preservation master must be created for each Region.
      * If the stylus skips, attempt to correct and retransfer the area before and after, add this note into the metadata along with time stamp.
        * If unable to perform these functions, set aside and return to NYPL.

<a name="audio-group-5"></a>
**_Preservation master file specifications: audio group 5: grooved cylinder_**

  | Attribute | Specification |
  | ---- | ----- |
  | Audio data encoding | Free Lossless Audio Codec (FLAC) |
  | File wrapper | FLAC (.flac) |
  | Bit depth | 24 |
  | Sampling rate | 96,000 Hz |
  | Number of audio channels | 2 (left + right discrete) |

#### Reproduction Details
  * No playback EQ curves for cylinder preservation masters. Must be transferred “flat”, with cartridge switched to “vertical”.  
  * At the start of the preservation master file, a 1kHz tone at operating level (-16 dBFS) for 30 seconds should be added.
  * Equipment must be approved by NYPL in writing. NYPL prefers use of Archeophone, Endpoint, or Levin CPS1 cylinder reproducers. Period equipment is not acceptable for use due to age and inconsistency of these machines and the greater potential for damage to the Archival Objects.
  * An appropriate assortment of stylus sizes and shapes for cylinders should be on-hand at the vendor transfer station and **the best sounding size/shape stylus used for transfer should be noted in the phonoCartridge metadata fields.**
  * Player setup and playback practices should adhere to best practices.
  * Careful determination of the groove pitch (Threads Per Inch or TPI), speed (with correction if needed), and cylinder material (brown wax, Gold Moulded, etc.) need to be determined BEFORE transfer and noted in metadata digitization process notes.

<a name="edit-masters-all"></a>
**_Edit master file specifications: all magnetic and optical audio groups_**

  | Attribute | Specification |
  | ---- | ----- |
  | Audio data encoding | Free Lossless Audio Codec (FLAC) |
  | File wrapper | FLAC (.flac) |
  | Bit depth | equal to preservation master |
  | Sampling rate | equal to preservation master |
  | Number of audio channels | Mono, 1; Stereo, 2 |

#### Multi-track audio exceptions to below EM requirements
For multi-track audio masters, multiple streams are captured of identical length and intended to be mixed down. The Edit Masters for these streams must not be trimmed or altered in any way.

#### Head and Tail Edits (Trimming)
  * The “needle-drop” and “needle-lift” present in preservation master files must be edited out of the edit master files.
  * Unrecorded portions of the collection object captured in the preservation master shall be eliminated for all Edit Masters except those created from multi-track production masters (for which the unrecorded portions are intentionally silent due to the mastering process).
  * Test tones and any equipment noise at the start and/or end of audible content (such as equipment on/off “clicks” or a stylus in the groove) should be trimmed. Trimming should not result in an abrupt start and/or end of audible content.
  * Elimination of the 5-second overlap included on any Preservation Masters that have been split out into multiple files for separate regions / streams / etc.

#### Level adjustment  
  * When balance and/or overall level are insufficient a peak level adjustment of max. -2db may be implemented as necessary.
#### Channel Adjustment
  * Ensuring that "mono" is true mono

<a name="data-media"></a>
## Data Media
### _Deliverables_
For each collection object, the following shall be produced:
  * One or more preservation master file(s)
  * One metadata file per media file
  * Image files as described

**Filenaming and metadata protocol for discs described as Audio or Video, but are found to actually contain files:**
* Unless the disc has two physical faces (i.e. DVD Dual Layer), Faces are not applicable to data optical discs (and video optical discs). Omit any provided Face metadata; filenames should not contain any component beyond Volume. Example: abc_123456_v01_pm.ISO
* Format and media type information should be updated to the formats allowable in the [Data Optical Disc JSON schema](https://github.com/NYPL/ami-metadata/blob/main/versions/2.0/schema/digitized_dataopticaldisc.json) 

#### Capture tools
Preservation masters must be captured/encoded as ISO9660 Disc Images.

<a name="data-group-1"></a>
**_Preservation master file specifications: Data optical disc_**
Media in Data Group 1 are distinguished from media in Audio Group 3 and Video Group 3 as follows:
  * Data Group 1 uses an ISO 9660 file system to encode data
  * Data Group 1 discs do not contain a top-level directory title “AUDIO_TS” or “VIDEO_TS”

  | Attribute | Specification |
  | ---- | ----- |
  |File system | ISO 9660 / UDF |
  | File wrapper | ISO (.iso) |
  | Other characteristics | (Same as source) |
