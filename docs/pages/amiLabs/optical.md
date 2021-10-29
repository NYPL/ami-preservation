---
title: Optical
layout: default
nav_order: 6
parent: AMI Labs
---


# Optical Media Migration
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## CDs

## DVDs

### Creating an ISO

Insert your DVD and unmount:
  * Open terminal, run `diskutil list`
  * Locate the disk identifier of your DVD (typically something like `disk1`)
  * Run `diskutil umount [DISK ID]`

Use ddrescue to create an ISO (`brew install ddrescue` if needed):
  *  `ddrescue -b 2048 -r4 -v /dev/[DISK ID] [output ISO path] [output log path]`

### Generating a single MP4 to represent all of the content on an ISO
  * Open [MakeMKV](https://www.makemkv.com/){:target="\_blank"}, and open your ISO
  *  Select your output directory, and click `Make MKV`
  * Move all resulting MKVs into a single directory
  * Run dvd_concat.py on your directory `./dvd_concat.py -s [YOUR DIRECTORY] -d [output path for DVD]`
  * Rename MP4 according to NYPL convention, and delete all MKVs
