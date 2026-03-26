---
title: Technical Metadata Notes
layout: default
nav_order: 1
parent: Metadata
---

# Notes on Imperfect Technical Metadata Fields

Some technical metadata fields are more stable and meaningful than others. Two fields that can be especially difficult to interpret consistently across formats and workflows are:

- `technical.dateCreated`
- `technical.duration`

These fields can still be useful within established workflows, but they should not always be understood as precise, absolute, or universally comparable values across all file types.

We use these fields as **best-effort technical metadata** generated through a constrained and consistent set of workflows. They are useful in context, but they are not universally authoritative. Some variation is expected and does not necessarily indicate a problem with the file.

## Our approach

In our workflows, these fields are generated through a constrained set of tools and processes that we use consistently in-house, and through established delivery workflows with outside vendors. Within those environments, the values are often useful enough for operational and descriptive purposes.

At the same time, we recognize that these fields are imperfect. They are subject to variation depending on:

- file format
- container structure
- embedded metadata availability
- file system behavior
- software interpretation
- authoring or encoding history
- transfer, copying, or remuxing events

For that reason, these fields should generally be treated as **best-effort technical metadata**, not as authoritative preservation facts in every case.

---

## `technical.dateCreated`

### Why this field is imperfect

The field we have called `technical.dateCreated` is, in some respects, a misnomer. Across the file formats we manage, there is no single, universal concept of “creation date” that is stored consistently and exposed consistently by tools such as MediaInfo.

Depending on the format, the value reported may reflect:

- a container-level timestamp
- an embedded recording or origination date
- an optional metadata tag
- a file system last-modified date
- or no meaningful internal date at all

As a result, the same field name may represent different underlying concepts in different files.

### Format-specific considerations

#### MKV

Matroska files do not provide a universally dependable embedded creation date that can always be treated as authoritative. Date-related values may reflect muxing behavior, software defaults, or metadata written during file creation, but not necessarily a stable preservation-relevant “creation” event.

#### FLAC

FLAC supports metadata tags, including date-like values, but these are optional descriptive tags rather than inherent or authoritative file creation timestamps. If such tags are absent, reported dates may come from the file system instead.

#### WAV

WAV files do not reliably contain a universal creation-date field. Broadcast WAV may include origination date and time fields, but these are not guaranteed in every file and may reflect a particular workflow moment rather than a general creation timestamp. Standard WAV files often rely on file system dates when no embedded date exists.

#### MOV and MP4

MOV and MP4 more commonly contain container-level date fields, but these may reflect the creation of the container, a transcode event, a remux, or another software-mediated action. Even when present, these values are not always semantically equivalent to “the date this preservation file was created” in a broader workflow sense. These formats are also highly susceptible to UTC vs. Local Time shifts; i.e. a file moved from a server in New York to one in London may "shift" its creation time by 5 hours depending on how the software reads the header.

#### ISO images and DV files

Some formats may contain dates that are historically older than the digital file itself. ISO images may preserve timestamps inherited from the file system of the authored disc. DV files may contain embedded recording dates originating from the source tape itself, potentially years or decades earlier than the date of digitization or file creation.

### Why dates may not match perfectly

Because of these differences, date values may vary across related files even when there is no meaningful problem. Differences can arise through:

- copying or transfer between storage environments
- remuxing or transcoding
- normalization or derivative creation
- bagging, unpacking, or restoration from storage
- differences between embedded metadata and file system metadata
- differences in how software tools interpret available fields

For that reason, minor mismatches in `technical.dateCreated` should not automatically be treated as evidence of an error.

### Our position

We use `technical.dateCreated` as a practical, best-effort field within established workflows. It can be useful for reference, but it should not be treated as a universally precise or authoritative value across all file types.

In most cases, the more important facts are that the files are present, intact, properly identified, and technically valid. Variation in this field does not usually affect preservation or access outcomes in a meaningful way.

---

## `technical.duration` for ISO images

### Why this field is imperfect

Duration is straightforward for many standalone audiovisual files, but ISO images can be much more complex. In particular, authored optical disc formats such as DVD-Video are not simple media files. They are structured collections of video objects, titles, chapters, menus, and navigation logic.

Because of that, “duration” is not always a single, obvious property of the disc.

For a DVD-style ISO, different interpretations of duration may include:

- the duration of the main feature
- the duration of the longest playable title
- the sum of all titles
- the sum of all distinct video objects
- the duration of a title selected by a parsing tool
- or no single meaningful total at all

These are not necessarily equivalent.

### MediaInfo and DVD-style ISOs

For DVD-Video structures, MediaInfo's reported General duration should not be understood as “the total runtime of everything on the disc.” Rather, it is better understood as **the retained primary-duration content MediaInfo associates with the parsed DVD structure**.

In practice, this means the reported duration may align with the main title while excluding shorter supplementary content such as:

- bonus features
- interviews
- short clips
- menu animations
- alternate title structures

So if a disc contains a feature plus several shorter extras, MediaInfo may report only the duration most closely associated with the primary retained content, rather than a disc-wide total of all playable material.

### Why “total duration” can be misleading

For authored optical media, a disc may contain:

- one main title and many extras
- duplicate or alternate title structures
- titles that share underlying content
- navigation logic that references the same material in multiple ways
- supplemental menus and motion backgrounds

As a result, attempting to compute one “perfect” total duration can lead to ambiguity or overcounting. A sum of all titles, for example, may count overlapping or duplicated content more than once.

### Our position

For ISO images, especially DVD-style ISOs, `technical.duration` should be interpreted cautiously. In many cases it is most useful as a best-effort technical indicator generated through a consistent workflow, rather than as an exact statement of total playable disc runtime.

Within our own workflows, this approach is workable because we use a constrained set of tools and processes consistently. Likewise, with outside vendors, we establish delivery expectations and technical workflows in advance, which makes the resulting values usable in context.

However, we recognize that the field remains imperfect and format-dependent. Variation in reported duration does not necessarily indicate a problem with the file or disc image.