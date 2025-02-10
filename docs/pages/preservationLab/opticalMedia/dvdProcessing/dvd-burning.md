---
title: Burning DVDs
layout: default
nav_order: 3
parent: DVD Processing
grand_parent: Optical Media
---

# Burning ISO Disc Images to Disc
{: .no_toc }

This guide walks you through converting a video file into a DVD-Video compatible ISO image and then burning it to a physical DVD. The steps include:

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Prerequisites

- **FFmpeg**:  
  Install via Homebrew:
  ```bash
  brew install ffmpeg
  ```
- **dvdauthor**:
  ```bash
  brew install dvdauthor
  ```
- **mkisofs (via cdrtools)**:
  ```bash
  brew install cdrtools
  ```
- A DVD Burner and Blank DVDs (single-layer 4.7GB discs).

## Step 1: Transcoding the Source Video with FFmpeg
DVD-Video requires MPEG-2 video, AC-3 audio, a resolution of 720x480 (NTSC), and specific formatting. If your source is not already DVD-compliant, you must transcode it.

### Simplified Command
```bash
ffmpeg -i "path/to/source_video.mp4" -target ntsc-dvd dvd_compliant.mpg
```

### What This Does
- Uses FFmpeg’s `-target ntsc-dvd` preset, ensuring the correct video format, frame rate, and bitrate.
- Encodes audio as **AC-3 stereo**.
- FFmpeg automatically applies **telecine (2:3 pulldown)** if the source is 23.976 fps, ensuring smooth playback at 29.97 fps on NTSC DVD players.

### Notes
- PAL users should replace `ntsc-dvd` with `pal-dvd`.

## Step 2: Authoring the DVD Structure with dvdauthor
After transcoding, create the DVD file structure (VIDEO_TS and AUDIO_TS directories, IFO/BUP files) and include chapters.

```bash
dvdauthor -o /Users/benjaminturkus/Desktop/dvd_structure -t -c 0,5:00,10:00,15:00,20:00,25:00,30:00,35:00,40:00,45:00,50:00,55:00,1:00:00,1:05:00,1:10:00,1:15:00,1:20:00,1:25:00,1:30:00,1:35:00,1:40:00,1:45:00,1:50:00,1:55:00,2:00:00,2:05:00,2:10:00,2:15:00,2:20:00,2:25:00,2:30:00,2:35:00,2:40:00,2:45:00 dvd_compliant.mpg
```

```bash
export VIDEO_FORMAT=NTSC
```

```bash
dvdauthor -o /Users/benjaminturkus/Desktop/dvd_structure -T
```

## Step 3: Creating the ISO Image with mkisofs
```bash
mkisofs -dvd-video -V "MyDVDTitle" -o dvd.iso /Users/benjaminturkus/Desktop/dvd_structure
```

## Step 4: Burning the ISO to a Physical DVD
### On macOS
1. Insert a blank DVD.
2. In Finder, right-click the `dvd.iso` file.
3. Select "Burn 'dvd.iso' to Disc...".
4. Follow prompts to burn.

## Step 5: Testing the DVD
Test the burned DVD on a standalone DVD player (e.g., a Pioneer DVD player) to ensure it plays correctly. Check menus, chapters, and video quality.

## Additional Notes
- **File Size Considerations**: If the final MPEG-2 file is larger than 4.7GB, reduce `-b:v` (video bitrate) in FFmpeg so the final ISO fits on a single-layer DVD.