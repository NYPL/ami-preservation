---
title: cd_processing.py Overview
layout: default
nav_order: 3
parent: CD Processing
grand_parent: Optical Media
---

# `cd_processing.py` Overview
{: .no_toc }

This page provides a conceptual overview of the `cd_processing.py` script, which is designed to process directories created via ISOBuster extraction of Audio CDs. The script prepares these directories for ingest into our preservation workflows by creating structured Preservation and Edit Masters.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

### Purpose

The script is intended to transform the output of ISOBuster—typically a set of per-track WAV files and a CUE sheet—into a preservation-ready single-file WAV, with optional loudness normalization for edit master creation. It simplifies the preparation of Preservation Masters (PMs) and Edit Masters (EMs) for ingestion into our digital repository.

---

### Requirements

Each disc directory to be processed must:
- Be named with a six-digit SPEC AMI ID (e.g., `123456`)
- Contain one or more `.wav` files (audio tracks)
- Include a corresponding `.cue` file describing the CD structure

---

### Workflow Summary

#### 1. **Track Ordering and Joining**
- The script parses the `.cue` file in each subdirectory to determine the correct track order.
- It matches `.wav` files to track titles or performers listed in the `.cue`, using filename normalization techniques (e.g., stripping punctuation and accents).
- If no clear match is found, the script falls back to alphabetically sorting the tracks.
- Tracks are then concatenated using `shntool` to produce a single WAV file (Preservation Master).

#### 2. **Naming Convention and Prefix**
- Each output WAV and CUE file is named using a three-letter prefix (e.g., `mym`, `myd`), followed by the six-digit ID and suffix `_v01f01_pm` or `_v01f01_em`.
- This prefix must be provided via the `-p` or `--prefix` argument.
- Prefixes should remain consistent across all discs in a given project.

#### 3. **Output Directory Structure**
After processing, the following directory structure is created inside the input root:

```
/Processed             ← Original ISOBuster folders moved here after processing
/PreservationMasters   ← Joined WAVs + renamed CUE sheets (PMs)
/EditMasters           ← Normalized WAVs (EMs), if enabled
```

#### 4. **Edit Master Creation**
- If the `--editmasters` (`-e`) flag is used, the script will analyze the loudness of each PM using the EBU R128 `ebur128` filter in FFmpeg.
- If the integrated loudness is outside ±1 LU of -23 LUFS, the script will normalize the file to exactly -23 LUFS.
- The normalization step preserves the original sample rate and bit depth.

---

### Additional Features and Notes

- If only one WAV file exists in a disc directory, it is simply copied and renamed.
- The script is robust to inconsistencies in `.cue` file formatting and attempts to extract usable track metadata regardless of indentation or ordering.
- Any missing or unmatched CUE files are reported at the end of processing.
- A companion `--split` mode exists, which reverses the process—splitting a joined PM WAV or FLAC file into individual tracks based on its CUE.

---

### Recommended Usage

```bash
python3 cd_processing.py -i /path/to/discs -p mym --editmasters
```

Where:
- `/path/to/discs` contains multiple six-digit directories from ISOBuster
- `mym` is your three-letter prefix for the current project
- `--editmasters` enables loudness normalization

---

### Summary

| Function                   | Behavior                                                                 |
|----------------------------|--------------------------------------------------------------------------|
| Join Mode (default)        | Concatenates WAVs per disc using CUE sheet ordering                      |
| Edit Master Creation       | Normalizes joined WAVs to -23 LUFS (if enabled)                          |
| Directory Output           | Organizes results into `PreservationMasters`, `EditMasters`, and `Processed` |
| Input Requirements         | CUE file, matching WAVs, and six-digit folder name per disc              |
| Split Mode (`--split`)     | Splits a master WAV/FLAC into individual tracks using its CUE sheet      |

---

This script plays a central role in standardizing audio CD preservation output, ensuring consistency and quality across projects. For command-line arguments and usage examples, refer to the [technical usage page](./cd_processing_usage.md).
