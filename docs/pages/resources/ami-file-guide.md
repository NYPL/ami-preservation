---
title: AMI File Guide
layout: default
nav_order: 10
parent: Resources
---

# Quick Guide: Understanding AMI Digital Files
**For Curators, Exhibitors, and Stakeholders**

When requesting digital AMI assets, you will encounter several file types. The file you need depends entirely on what you plan to do with it.

### ⚡ The "Cheat Sheet"
| If you need to... | Media Type | Request this file | Extension | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Preview / Stream** | Video & Film | **Service Copy** | `.mp4` | *Standard* |
| **Edit / Exhibit** | **Film** | **Mezzanine** | `.mov` | *Standard* |
| **Edit / Exhibit** | **Video** | **Mezzanine** | `.mov` | *By Request* |
| **Archive / Restore** | Video & Film | **Preservation Master** | `.mkv` | *Standard* |
| **Listen** | Audio | **Service Copy** | `.mp4` | *By Request* |
| **Broadcast / Podcasting** | Audio | **Edit Master** | `.flac` | *Standard* |

---

## 1. Video Files (Tapes: VHS, U-matic, BetaSP, etc.)
For video tape formats, we typically generate two files by default: the Preservation Master and the Service Copy. If you need to edit or screen the footage in high quality, you must request a Mezzanine file.

### Preservation Master (PM) – *The "Raw" Archive File*
* **Format:** FFV1 in Matroska (`.mkv`)
* **What it is:** A lossless, mathematical copy of the tape signal. It includes all signal noise and typically requires special software (like VLC) to play.
* **Best for:** Long-term cold storage; deep digital restoration.

### Service Copy (SC) – *The "Access" File*
* **Format:** H.264 in MP4 (`.mp4`)
* **What it is:** A compressed, lightweight file similar to YouTube quality.
* **Best for:** Research, quick viewing on a laptop, sending via email/web.

### ⚠️ Mezzanine (MZ) – *The "Editing" File (On Request)*
* **Format:** ProRes HQ in QuickTime (`.mov`)
* **What it is:** A broadcast-standard file that is highly compatible with editing software (Premiere, Final Cut) and gallery hardware.
* **Note:** We do not make these by default for video. **You must specifically request this** if you are building an exhibition or editing a documentary.

---

## 2. Audio Files (Reels, Cassettes, Discs)
Audio workflows are unique because we create two high-quality versions: one that is purely raw, and one that is "mastered" for listening.

### Preservation Master (PM) – *The "Untouched" Capture*
* **Format:** FLAC (`.flac`)
* **The Content:** This is the raw transfer with **no digital adjustments**. It may include long periods of silence (lead-in/lead-out) and volume levels that fluctuate or are very quiet, exactly as they were on the physical carrier.
* **Best for:** Archiving and evidence.

### Edit Master (EM) – *The "Listenable" File*
* **Format:** FLAC (`.flac`)
* **The Content:** This file has been "cleaned up" by our engineers.
    * **Trimmed:** Heads/tails of silence are removed.
    * **Normalized:** The volume is adjusted to a standard loudness (-23 LUFS) so you don't have to ride the volume knob.
* **Best for:** High-quality listening, radio broadcast, podcasting, and publication.

### Service Copy (SC) – *The "Portable" File (On Request)*
* **Format:** AAC Audio (`.mp4` / `.m4a`)
* **The Content:** A compressed version derived from the Edit Master (so it retains the volume normalization and cleanup) but in a smaller file size.
* **Best for:** Streaming, sharing with researchers, and listening on mobile devices.

---

## 3. Film Scans (16mm, 35mm, 8mm)
Film scans differ significantly between the Preservation Master and the derivative copies regarding what you actually *see* in the frame.

### Preservation Master (PM) – *The "Edge-to-Edge" Scan*
* **Format:** FFV1 in Matroska (`.mkv`)
* **The Look:** This is an **overscan**. You will see the entire piece of film, including the sprocket holes, optical soundtrack, and frame edges.
* **Color:** No color correction is applied; it may look "flat" or faded.
* **Best for:** Archival preservation and **complex restoration**.
    * *Note:* Only request this for editing if you require the absolute best quality and are willing to perform manual cropping and color grading from scratch.

### Mezzanine (MZ) – *The "Production" File*
* **Format:** ProRes HQ (`.mov`)
* **The Look:**
    * **Cropped:** Zoomed in to show only the picture area (sprockets removed).
    * **Corrected:** Red fade is removed and color is balanced to look natural.
* **Best for:** Video editing, documentary production, and gallery exhibition. This provides high fidelity without the extra work of cropping and grading raw scans.

### Service Copy (SC) – *The "Streaming" File*
* **Format:** H.264 (`.mp4`)
* **The Look:** Visually identical to the Mezzanine (cropped and color corrected) but highly compressed.
* **Best for:** Streaming, quick download, and easy sharing.

---

## 4. File Size Estimates (Standard Definition Video)
Most of our video collection is Standard Definition (SD). Film scans (2K/4K) will be significantly larger.

| Content Duration | Service Copy (.mp4) | Mezzanine (.mov) | Preservation Master (.mkv) |
| :--- | :--- | :--- | :--- |
| **10 Minutes** | ~250 MB | ~5 GB | ~6 GB |
| **30 Minutes** | ~750 MB | ~15 GB | ~18 GB |
| **1 Hour** | ~1.5 GB | ~30 GB | ~35 GB |

---

## 5. Summary: Which file should I ask for?

**"I just want to listen to an interview for research."**
> **Request:** **Service Copy (Audio .mp4)**
> *Why:* It has all the benefits of the Edit Master (volume normalized, silence removed) but is small and plays on any device.

**"I am producing a podcast or radio show."**
> **Request:** **Edit Master (.flac)**
> *Why:* You get the cleaned-up, normalized audio, but in lossless quality that can withstand editing and mixing.

**"I'm editing a video documentary using our footage."**
> **Request:** **Mezzanine / ProRes .mov (Video)**
> *Why:* The Service Copy is too low quality for editing. The Preservation Master is too heavy. **Note:** You must ask us to generate this for you.

**"I'm showing a digitized 16mm film in a gallery."**
> **Request:** **Mezzanine / ProRes .mov (Film)**
> *Why:* It is cropped to the picture (no sprocket holes visible) and color-corrected, so it looks best on screen.

**"I want to see exactly what was on the original physical tape/film, warts and all."**
> **Request:** **Preservation Master**
> > *Why:* This is the only format that proves exactly what the physical object looked/sounded like before we did any work on it.