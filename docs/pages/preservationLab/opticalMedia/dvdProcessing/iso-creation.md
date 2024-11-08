---
title: ISO Creation
layout: default
nav_order: 1
parent: DVD Processing
grand_parent: Optical Media

---

# ISO Creation
{: .no_toc }

This page provides a comprehensive guide for creating ISO images from DVDs as part of a preservation workflow. It outlines the tools and methods used to ensure the best possible recovery of data from discs, ranging from routine processes for handling minor damage to advanced techniques for recovering data from heavily damaged or non-standard DVDs.

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

### 1. ISO Creation

DVD preservation presents unique challenges due to potential for physical degradation and various forms of copy protection. Our approach leverages a combination of tools, with each stage representing an escalation in complexity and recovery capability.

#### **Preliminary Step: Physical Inspection and Cleaning**

Before any digital processing, inspect the DVD for scratches, dirt, or other physical damage. If issues are present, use the RTI/ELM USA DVD Resurfacing Machine to clean and repair the disc. This fully automatic machine offers four cleaning settings, with level 4 being the most intensive and effective for problematic discs.

#### **Primary Approach: MakeMKV with Plextor Disc Drive**

We start with MakeMKV, which is particularly effective at handling commercial DVDs and discs with minor damage. We use either the GUI or the command-line version (`makemkvcon`), with a Plextor external disc drive, preferred for its reliability with optical media.

##### **MakeMKV Strengths**
- Excellent handling of copy-protected commercial DVDs
- Strong error correction for video content
- Often recovers playable results from damaged discs
- Reliable at reading through minor disc errors quickly

##### **MakeMKV Weaknesses**
- Lacks low-level disc recovery capabilities
- May skip unreadable sections without extensive retries
- Limited for non-video content
- No partial/incremental backup functionality, unlike `ddrescue`

#### **Secondary Approach: ISOBuster with Nimbie on Windows**

If MakeMKV cannot produce a usable ISO, our next attempt is with ISOBuster and a Nimbie autoloader on a Windows system. ISOBuster excels at reading non-standard formats and recovering files from corrupted file systems.

##### **ISOBuster Strengths**
- Handles non-standard formats effectively
- Extracts specific files even from damaged file systems
- Provides detailed error reporting
- Useful for selective file recovery rather than full disc images

##### **ISOBuster Weaknesses**
- Requires a paid license
- Less automated than other tools
- Limited handling of copy-protected discs

#### **Final Approach: ddrescue with Plextor, ASUS, or LG Drives**

If both MakeMKV and ISOBuster fail to create a usable ISO, we use `ddrescue`, either with the same Plextor drive or an alternative (ASUS or LG). `ddrescue` provides a lower-level read with detailed logging for interrupted copies, making it ideal for more challenging discs.

##### **ddrescue Strengths**
- Performs multiple passes with different strategies
- Creates detailed logs for resuming interrupted copies
- Can recover partial data from heavily damaged areas
- Operates at the disc's lowest level, capturing exact disc data (for forensic accuracy)

##### **ddrescue Weaknesses**
- Does not handle copy protection
- Extensive retries may slow the process, especially on irrecoverable sectors
- Playability is not guaranteed even if data recovery is more complete
- Can be significantly slower than MakeMKV

In summary, we prioritize MakeMKV for its speed, copy protection handling, and high success rate with partially damaged discs. ISOBuster serves as our fallback for non-standard formats or corrupted file systems, while `ddrescue` is reserved for the most challenging cases requiring low-level recovery.

---

### 2. ISO Creation Tools: Installation Notes and Workflow Quirks

This section outlines the installation requirements and any quirks for using MakeMKV, ISOBuster, and `ddrescue`.

---

#### **MakeMKV**

MakeMKV is available on macOS and is easily installed via Homebrew:

```bash
brew install makemkv
```

This installs both the GUI and CLI (`makemkvcon`). Settings modified in the GUI will sync to the CLI. MakeMKV is free but requires a license key that renews every ~3 months. You can find the latest key on the MakeMKV forum [here](https://forum.makemkv.com/forum/viewtopic.php?t=1053), or automate the key retrieval using an API tool like [this one](https://github.com/AyrA/MakeMKV).

**Configuration for ISO Creation and DVD Title Organization:**  
To organize DVD Title Sets by Source ID, adjust the output filename template in the MakeMKV GUI:
1. Go to `Preferences` → `General` and turn on Expert Mode.
2. Go to `Advanced`.
3. Set the filename template to:

   ```
   {NAME1}{_s:SN}{-:CMNT1}{-:DT}{title:+DFLT}{_t:N2}
   ```
By adding `{_s:SN}` to MakeMKV's default output filename template, the resulting MKVs will be organized by DVD Source ID, which we’ve found to best reflect the native playback order of the DVD.

---

#### **ISOBuster**

ISOBuster + Nimbie requires a Windows system with restricted admin privileges.

1. Connect the Nimbie to the Windows computer.
2. Right-click on the disc drive in `My Computer` and select "Inspect Drive with ISOBuster" (Admin credentials will be required).

**ISO Creation Steps in ISOBuster:**  
1. Open ISOBuster; the contents of the DVD drive will display in the main window.
2. Right-click the drive or volume you want to create the ISO from, then select "Create ISO Image File...".
3. In the dialog:
   - Set output location and filename for the ISO.
   - Choose options such as including hidden files or creating a full raw image.
4. Click "Start" to begin the ISO creation.

---

#### **ddrescue**

`ddrescue` is particularly sensitive to whether the disc is mounted. To use it, follow these steps:

1. Insert the DVD and unmount it:
   ```bash
   diskutil list
   ```
   - Identify the disk identifier (e.g., `disk2`).
   - Run:
     ```bash
     diskutil umount /dev/[DISK ID]
     ```

2. Run `ddrescue`:
   ```bash
   ddrescue -b 2048 -r4 -v /dev/[DISK ID] [output ISO path] [output log path]
   ```

   We also have a script available to automate this process for batch processing ([see our GitHub repo](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/iso_creator.py)). Insert a disc, and the script will proceed with multiple discs until stopped.

---

### Summary of Approaches

| Approach           | Tool       | Strengths                                          | Weaknesses                                         |
|--------------------|------------|----------------------------------------------------|----------------------------------------------------|
| Preliminary        | RTI/ELM USA DVD Resurfacing Machine | Effective cleaning and repair of physical disc issues | Requires physical equipment and maintenance        |
| Primary            | MakeMKV    | Fast, good with copy protection, playable results  | Limited on non-video content, skips unreadable sections |
| Secondary          | ISOBuster  | Non-standard format handling, file-specific recovery | Manual, limited copy protection handling           |
| Tertiary (final)   | ddrescue   | Low-level recovery, detailed logs, multiple passes | Slow, lacks copy protection handling               |

---