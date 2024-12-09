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

### Example Command

```bash
ffmpeg -i "path/to/source_video.mp4" \
       -vcodec mpeg2video -pix_fmt yuv420p -flags +ildct+ilme -top 1 \
       -b:v 6000k -minrate 6000k -maxrate 8000k -bufsize 1835k \
       -vf "scale=720:480,setsar=32/27" -r 24000/1001 \
       -g 15 -bf 2 -dc 10 \
       -acodec ac3 -b:a 192k -ar 48000 -ac 2 \
       -output_ts_offset 0 \
       output_widescreen.mpg
```

### What This Does
- Encodes video as MPEG-2, interlaced, with a DVD-friendly bitrate.
- Rescales and sets the aspect ratio for 16:9 widescreen.
- Sets the frame rate at 23.976 fps. Later, the DVD player will apply pulldown for 29.97 fps NTSC output.
- Encodes audio as AC-3 stereo at 48kHz and 192 kbps.

### Note on Scaling
If your source video is already at a suitable resolution (e.g., already DVD resolution), you may omit the scaling and `setsar` filters.

### Simplified Command
```bash
ffmpeg -i "path/to/source_video.mp4" \
       -target ntsc-dvd -aspect 16:9 \
       -b:v 4500k -b:a 192k \
       dvd_compliant.mpg
```
This uses presets for DVD output. Adjust `-b:v` if the final file is too large.

## Step 2: Authoring the DVD Structure with dvdauthor
After transcoding, create the DVD file structure (VIDEO_TS and AUDIO_TS directories, IFO/BUP files).

```bash
dvdauthor -o /path/to/dvd_structure -t dvd_compliant.mpg
export VIDEO_FORMAT=NTSC
dvdauthor -o /path/to/dvd_structure -T
```

### What This Does
- Creates the initial DVD title set.
- Sets the `VIDEO_FORMAT` environment variable to NTSC before finalizing, ensuring a proper VIDEO_TS directory.
- Finalizes the structure, resulting in a properly authored DVD folder structure.

## Step 3: Creating the ISO Image with mkisofs
Once the DVD structure is ready, convert it into an ISO image.

```bash
mkisofs -dvd-video -V "MyDVDTitle" -o dvd.iso /path/to/dvd_structure
```

### Options
- `-dvd-video`: Ensures a DVD-Video compliant ISO.
- `-V "MyDVDTitle"`: Sets the volume label displayed by DVD players.
- `-o dvd.iso`: Specifies the output ISO file.

### Adding Chapters
Chapters must be set during the `dvdauthor` step, using `-c`:

```bash
dvdauthor -o /path/to/dvd_structure \
          -t -c 0,5:00,10:00,... dvd_compliant.mpg
dvdauthor -o /path/to/dvd_structure -T
```
Replace the times as needed. Then run `mkisofs` as above.

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
- **Aspect Ratio and Scaling**: Adjust scaling and aspect ratio parameters to match your source. The provided commands assume a widescreen (16:9) target and scaling from a higher resolution source to standard DVD resolution.
