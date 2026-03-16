#!/usr/bin/env python3

import argparse
import sys
import subprocess
import csv
import struct
from pathlib import Path, PurePosixPath
from collections import Counter
import pycdlib


# ---------------------------------------------------------------------------
# UDF field decoders
# ---------------------------------------------------------------------------

def _clean_udf_text(val: str) -> str:
    """Normalize decoded UDF text."""
    return val.replace("\x00", "").strip(" \t\r\n")


def _looks_like_real_title(val: str) -> bool:
    """
    Reject known structural strings, placeholders, and obvious junk.
    """
    if not val:
        return False

    low = val.lower().strip()

    junk = {
        "osta compressed unicode",
        "udf lv info",
        "volume set identifier",
        "logical volume identifier",
        "volume identifier",
        "volume_identifier",
    }
    if low in junk:
        return False

    printable = sum(ch.isprintable() and ch != "\x00" for ch in val)
    if printable < 3:
        return False

    if sum(ch.isalnum() for ch in val) < 3:
        return False

    return True


def _decode_dstring(raw: bytes) -> str:
    """
    Decode a likely UDF dstring from a byte slice.

    Handles two common in-the-wild cases:
      1. [comp][len][content...]
      2. [comp][content ... null padding]
    """
    if len(raw) < 2 or raw[0] not in (8, 16):
        return ""

    comp = raw[0]

    length = raw[1]
    if length > 0 and 2 + length <= len(raw):
        content = raw[2:2 + length]
        try:
            if comp == 8:
                val = content.decode("latin-1", errors="ignore")
            else:
                content = content[: len(content) - (len(content) % 2)]
                val = content.decode("utf-16-be", errors="ignore")
            val = _clean_udf_text(val)
            if _looks_like_real_title(val):
                return val
        except Exception:
            pass

    payload = raw[1:]
    nul = payload.find(b"\x00")
    if nul != -1:
        payload = payload[:nul]

    try:
        if comp == 8:
            val = payload.decode("latin-1", errors="ignore")
        else:
            payload = payload[: len(payload) - (len(payload) % 2)]
            val = payload.decode("utf-16-be", errors="ignore")
        val = _clean_udf_text(val)
        if _looks_like_real_title(val):
            return val
    except Exception:
        pass

    return ""


def _scan_dstrings(raw: bytes) -> list[str]:
    """Scan a byte region for UDF-like strings."""
    results: list[str] = []
    seen: set[str] = set()

    i = 0
    while i < len(raw) - 2:
        if raw[i] in (0x08, 0x10):
            window = raw[i:i + 64]
            val = _decode_dstring(window)
            if val and val not in seen:
                seen.add(val)
                results.append(val)

                next_nul = window.find(b"\x00", 1)
                if next_nul != -1:
                    i += max(2, next_nul + 1)
                    continue
        i += 1

    return results


def _decode_regid(raw: bytes) -> str:
    """Decode a UDF EntityIdentifier (regid) from a byte window."""
    if not raw:
        return ""

    star = raw.find(b"*")
    if star != -1:
        name = raw[star:].split(b"\x00")[0].decode("latin-1", errors="ignore").lstrip("*").strip()
        if name:
            return name

    best = ""
    current: list[str] = []
    for b in raw:
        if 0x20 <= b <= 0x7E:
            current.append(chr(b))
        else:
            run = "".join(current).strip()
            if len(run) > len(best):
                best = run
            current = []
    run = "".join(current).strip()
    if len(run) > len(best):
        best = run

    return best if len(best) >= 5 else ""


def _pick_best_title(*candidates: str) -> str:
    """Choose the most plausible disc title from candidate strings."""
    cleaned: list[str] = []

    for c in candidates:
        c = (c or "").strip()
        if not c:
            continue
        if not _looks_like_real_title(c):
            continue
        cleaned.append(c)

    if not cleaned:
        return ""

    cleaned.sort(
        key=lambda s: (sum(ch.isalnum() for ch in s), len(s)),
        reverse=True,
    )
    return cleaned[0]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _append_note(record: dict, text: str) -> None:
    if record["Notes"]:
        record["Notes"] += f" | {text}"
    else:
        record["Notes"] = text


def _normalize_creator(raw: str) -> str:
    """Normalize creator/application strings for easier grouping."""
    if not raw:
        return ""

    low = raw.lower()

    if "imapi" in low and "roxio" in low:
        return "Microsoft/Roxio IMAPI"
    if "imapi" in low:
        return "Microsoft IMAPI"
    if "spruce" in low:
        return "Spruce"
    if "nero" in low:
        return "Nero"
    if "roxio" in low:
        return "Roxio"
    if "toast" in low:
        return "Roxio Toast"
    if "pioneer" in low:
        return "Pioneer"
    if "sony_dvdirect" in raw:
        return "SONY_DVDIRECT"
    if "sony_dvd_recorder" in raw:
        return "SONY_DVD_RECORDER"
    if raw.strip() == "LG":
        return "LG"
    if "sonic solutions" in low or "dvd producer" in low:
        return "Sonic Solutions / DVD Producer"
    if "sonic" in low:
        return "Sonic"
    if "cirrus sonata" in low or "sonata" in low:
        return "Cirrus Sonata"
    if "apple" in low:
        return "Apple"
    if "mkisofs" in low or "genisoimage" in low:
        return "mkisofs/genisoimage"

    return raw.strip()


def _format_top_entries(entries: list[str], max_items: int = 8) -> str:
    """Compact top-level entry summary for CSV."""
    if not entries:
        return ""

    trimmed = entries[:max_items]
    suffix = " ..." if len(entries) > max_items else ""
    return "; ".join(trimmed) + suffix


def _inspect_tail_padding(file_path: Path, expected_size: int) -> str:
    """
    Inspect any extra trailing bytes beyond expected size.
    Returns a simple classification.
    """
    try:
        actual_size = file_path.stat().st_size
        if expected_size is None or actual_size <= expected_size:
            return ""

        extra = actual_size - expected_size
        with open(file_path, "rb") as f:
            f.seek(expected_size)
            tail = f.read(min(extra, 1024 * 1024))

        if not tail:
            return "Empty"

        unique = set(tail)

        if unique == {0x00}:
            return "Zero-filled"
        if unique == {0xFF}:
            return "0xFF-filled"
        if len(unique) <= 4:
            return "Low-variance filler"
        return "Mixed"
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# Low-level signature / descriptor reconnaissance
# ---------------------------------------------------------------------------

def scan_descriptor_signatures(file_path: Path) -> dict:
    """
    Look for common ISO/UDF signatures and anchors.
    This is reconnaissance, not full validation.
    """
    out = {
        "iso_pvd_present": False,
        "udf_anchor_present": False,
        "udf_nsr_present": False,
        "udf_beg_present": False,
        "udf_tea_present": False,
        "backup_anchor_present": False,
        "signatures": [],
    }

    try:
        size = file_path.stat().st_size
        total_sectors = size // 2048

        with open(file_path, "rb") as f:
            f.seek(16 * 2048)
            pvd = f.read(2048)
            if len(pvd) >= 6 and pvd[1:6] == b"CD001":
                out["iso_pvd_present"] = True

            f.seek(16 * 2048)
            early = f.read(2048 * 32)
            if b"BEA01" in early:
                out["udf_beg_present"] = True
            if b"NSR02" in early or b"NSR03" in early:
                out["udf_nsr_present"] = True
            if b"TEA01" in early:
                out["udf_tea_present"] = True

            if total_sectors > 256:
                f.seek(256 * 2048)
                avdp = f.read(2048)
                if len(avdp) >= 2:
                    try:
                        tag_id = struct.unpack_from("<H", avdp, 0)[0]
                        if tag_id == 2:
                            out["udf_anchor_present"] = True
                    except Exception:
                        pass

            candidate_sectors = []
            if total_sectors > 257:
                candidate_sectors.extend([total_sectors - 256, total_sectors - 1])

            for sec in candidate_sectors:
                if sec < 0:
                    continue
                try:
                    f.seek(sec * 2048)
                    buf = f.read(2048)
                    if len(buf) >= 2 and struct.unpack_from("<H", buf, 0)[0] == 2:
                        out["backup_anchor_present"] = True
                        break
                except Exception:
                    continue

    except Exception:
        pass

    sigs = []
    if out["iso_pvd_present"]:
        sigs.append("ISO_PVD")
    if out["udf_beg_present"]:
        sigs.append("BEA01")
    if out["udf_nsr_present"]:
        sigs.append("NSR02/03")
    if out["udf_tea_present"]:
        sigs.append("TEA01")
    if out["udf_anchor_present"]:
        sigs.append("AVDP@256")
    if out["backup_anchor_present"]:
        sigs.append("BackupAVDP")

    out["signatures"] = sigs
    return out


# ---------------------------------------------------------------------------
# Per-format extractors
# ---------------------------------------------------------------------------

def sniff_pure_udf(file_path: Path) -> bool:
    """Check for pure-UDF images that have no ISO 9660 PVD."""
    try:
        with open(file_path, "rb") as f:
            f.seek(32768)
            data = f.read(2048 * 5)
            return any(sig in data for sig in (b"NSR02", b"NSR03", b"BEA01"))
    except Exception:
        return False


def get_pvd_fields(file_path: Path) -> dict:
    """Extract fields from the ISO 9660 Primary Volume Descriptor."""
    out = {
        "system_id": "",
        "volume_id": "",
        "volume_set_id": "",
        "publisher": "",
        "preparer": "",
        "app_id": "",
        "copyright_file": "",
        "abstract_file": "",
        "bibliographic_file": "",
    }

    try:
        with open(file_path, "rb") as f:
            f.seek(32768)
            pvd = f.read(2048)

        if pvd[1:6] != b"CD001":
            return out

        out["system_id"] = pvd[8:40].decode("ascii", "ignore").strip("\x00 ")
        out["volume_id"] = pvd[40:72].decode("ascii", "ignore").strip("\x00 ")
        out["volume_set_id"] = pvd[190:318].decode("ascii", "ignore").strip("\x00 ")
        out["publisher"] = pvd[318:446].decode("ascii", "ignore").strip("\x00 ")
        out["preparer"] = pvd[446:574].decode("ascii", "ignore").strip("\x00 ")
        out["app_id"] = pvd[574:702].decode("ascii", "ignore").strip("\x00 ")
        out["copyright_file"] = pvd[702:739].decode("ascii", "ignore").strip("\x00 ")
        out["abstract_file"] = pvd[739:776].decode("ascii", "ignore").strip("\x00 ")
        out["bibliographic_file"] = pvd[776:813].decode("ascii", "ignore").strip("\x00 ")
    except Exception:
        pass

    return out


def get_udf_fields(file_path: Path) -> dict:
    """Walk the UDF Main Volume Descriptor Sequence and extract key values."""
    out = {
        "creator": "",
        "disc_title": "",
        "lv_info_2": "",
        "lv_info_3": "",
        "iuvd_creator": "",
    }

    try:
        with open(file_path, "rb") as f:
            f.seek(256 * 2048)
            avdp = f.read(2048)
            if len(avdp) < 32 or struct.unpack_from("<H", avdp, 0)[0] != 2:
                return out

            mvds_len = struct.unpack_from("<I", avdp, 16)[0]
            mvds_loc = struct.unpack_from("<I", avdp, 20)[0]

            f.seek(mvds_loc * 2048)
            for _ in range(max(1, mvds_len // 2048)):
                sector = f.read(2048)
                if len(sector) < 512:
                    break

                tag_id = struct.unpack_from("<H", sector, 0)[0]

                if tag_id == 1:
                    creator = _decode_regid(sector[368:432])
                    if creator:
                        out["creator"] = creator

                elif tag_id == 4:
                    lv_strings = _scan_dstrings(sector[68:176])

                    if len(lv_strings) > 0:
                        out["disc_title"] = lv_strings[0]
                    if len(lv_strings) > 1:
                        out["lv_info_2"] = lv_strings[1]
                    if len(lv_strings) > 2:
                        out["lv_info_3"] = lv_strings[2]

                    iuvd_creator = _decode_regid(sector[208:240])
                    if iuvd_creator and "lv info" not in iuvd_creator.lower():
                        out["iuvd_creator"] = iuvd_creator

                elif tag_id == 8:
                    break

    except Exception:
        pass

    return out


def get_7z_data(file_path: Path) -> dict:
    """
    Call `7z l -slt` to read physical size, creator application, and paths.
    """
    data: dict = {
        "expected_size": None,
        "creator": None,
        "error": None,
        "paths": [],
    }

    try:
        result = subprocess.run(
            ["7z", "l", "-slt", str(file_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        for line in result.stdout.splitlines():
            if line.startswith("Physical Size ="):
                try:
                    data["expected_size"] = int(line.split("=", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("Creator Application ="):
                value = line.split("=", 1)[1].strip()
                if value:
                    data["creator"] = value
            elif line.startswith("Path ="):
                value = line.split("=", 1)[1].strip()
                if value and value != str(file_path):
                    data["paths"].append(value)

        if result.returncode != 0 and data["expected_size"] is None:
            data["error"] = f"7z exited {result.returncode}: {result.stderr.strip()[:200]}"
    except FileNotFoundError:
        data["error"] = "ERROR: 7z not found in PATH"
    except subprocess.TimeoutExpired:
        data["error"] = "ERROR: 7z timed out"
    except Exception as e:
        data["error"] = f"ERROR: {e}"

    return data


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------

def inventory_from_7z(paths: list[str]) -> dict:
    """
    Build a filesystem/content inventory from 7z-reported paths.
    Useful especially as fallback for UDF-only images.
    """
    out = {
        "top_level_entries": [],
        "file_count": 0,
        "dir_count": 0,
        "extensions": Counter(),
        "largest_file": "",
        "largest_file_size": "",
        "content_markers": set(),
        "readable": False,
    }

    if not paths:
        return out

    top = set()
    markers = set()

    for p in paths:
        pp = PurePosixPath(p.replace("\\", "/"))
        parts = [x for x in pp.parts if x not in ("/", "")]
        if not parts:
            continue

        top.add(parts[0])

        name = parts[-1]
        low = "/".join(parts).lower()

        if "." in name and not name.endswith("."):
            out["file_count"] += 1
            ext = Path(name).suffix.lower()
            if ext:
                out["extensions"][ext] += 1
        else:
            out["dir_count"] += 1

        if "video_ts" in low:
            markers.add("VIDEO_TS")
        if "audio_ts" in low:
            markers.add("AUDIO_TS")
        if "bdmv" in low:
            markers.add("BDMV")
        if "mpegav" in low:
            markers.add("MPEGAV")
        if "mpeg2" in low:
            markers.add("MPEG2")
        if "vcd" in low:
            markers.add("VCD")
        if "svcd" in low:
            markers.add("SVCD")
        if "dcim" in low:
            markers.add("DCIM")
        if low.endswith(".vob"):
            markers.add(".VOB")
        if low.endswith(".ifo"):
            markers.add(".IFO")
        if low.endswith(".bup"):
            markers.add(".BUP")
        if low.endswith(".jpg") or low.endswith(".jpeg"):
            markers.add(".JPG")
        if low.endswith(".wav"):
            markers.add(".WAV")
        if low.endswith(".mp3"):
            markers.add(".MP3")
        if low.endswith(".mov"):
            markers.add(".MOV")
        if low.endswith(".mpg") or low.endswith(".mpeg"):
            markers.add(".MPG")
        if low.endswith(".avi"):
            markers.add(".AVI")
        if low.endswith(".exe") or low.endswith(".msi"):
            markers.add(".EXE")
        if low.endswith(".pdf"):
            markers.add(".PDF")
        if low.endswith(".xml"):
            markers.add(".XML")
        if low.endswith(".ses"):
            markers.add(".SES")
        if low.endswith(".dvd"):
            markers.add(".DVD")

    out["top_level_entries"] = sorted(top)
    out["content_markers"] = markers
    out["readable"] = True
    return out


def _safe_decode_iso_name(name) -> str:
    """Best-effort decode for pycdlib filenames."""
    if name is None:
        return ""
    if isinstance(name, bytes):
        return name.decode("utf-8", errors="ignore").rstrip(";1").strip()
    return str(name).rstrip(";1").strip()


def inventory_from_pycdlib(file_path: Path) -> dict:
    """Walk ISO contents via pycdlib where possible."""
    out = {
        "top_level_entries": [],
        "file_count": 0,
        "dir_count": 0,
        "extensions": Counter(),
        "largest_file": "",
        "largest_file_size": 0,
        "content_markers": set(),
        "readable": False,
        "walk_error": "",
        "open_error": "",
    }

    iso = pycdlib.PyCdlib()

    try:
        iso.open(str(file_path))
        out["readable"] = True

        seen_top = set()
        markers = set()

        try:
            children = list(iso.list_children(iso_path="/"))
        except Exception as e:
            out["walk_error"] = str(e)
            children = []

        for child in children:
            try:
                name = ""
                is_dir = False
                size = None

                if hasattr(child, "file_identifier"):
                    name = _safe_decode_iso_name(child.file_identifier())
                elif hasattr(child, "rock_ridge_name"):
                    rr = child.rock_ridge_name()
                    if rr:
                        name = _safe_decode_iso_name(rr)
                elif hasattr(child, "joliet_path"):
                    name = _safe_decode_iso_name(child.joliet_path())

                if not name or name in (".", ".."):
                    continue

                seen_top.add(name)

                if hasattr(child, "is_dir"):
                    try:
                        is_dir = child.is_dir()
                    except Exception:
                        is_dir = False

                if is_dir:
                    out["dir_count"] += 1
                else:
                    out["file_count"] += 1
                    ext = Path(name).suffix.lower()
                    if ext:
                        out["extensions"][ext] += 1

                    if hasattr(child, "data_length"):
                        try:
                            size = int(child.data_length)
                        except Exception:
                            size = None

                    if size is not None and size > out["largest_file_size"]:
                        out["largest_file_size"] = size
                        out["largest_file"] = name

                low = name.lower()
                if low == "video_ts":
                    markers.add("VIDEO_TS")
                if low == "audio_ts":
                    markers.add("AUDIO_TS")
                if low == "bdmv":
                    markers.add("BDMV")
                if low == "mpegav":
                    markers.add("MPEGAV")
                if low == "mpeg2":
                    markers.add("MPEG2")
                if low == "vcd":
                    markers.add("VCD")
                if low == "svcd":
                    markers.add("SVCD")
                if low == "dcim":
                    markers.add("DCIM")
                if low.endswith(".vob"):
                    markers.add(".VOB")
                if low.endswith(".ifo"):
                    markers.add(".IFO")
                if low.endswith(".bup"):
                    markers.add(".BUP")
                if low.endswith(".jpg") or low.endswith(".jpeg"):
                    markers.add(".JPG")
                if low.endswith(".wav"):
                    markers.add(".WAV")
                if low.endswith(".mp3"):
                    markers.add(".MP3")
                if low.endswith(".mov"):
                    markers.add(".MOV")
                if low.endswith(".mpg") or low.endswith(".mpeg"):
                    markers.add(".MPG")
                if low.endswith(".avi"):
                    markers.add(".AVI")
                if low.endswith(".exe") or low.endswith(".msi"):
                    markers.add(".EXE")
                if low.endswith(".pdf"):
                    markers.add(".PDF")
                if low.endswith(".xml"):
                    markers.add(".XML")
                if low.endswith(".ses"):
                    markers.add(".SES")
                if low.endswith(".dvd"):
                    markers.add(".DVD")

            except Exception:
                continue

        out["top_level_entries"] = sorted(seen_top)
        out["content_markers"] = markers

    except Exception as e:
        out["open_error"] = str(e)
    finally:
        try:
            iso.close()
        except Exception:
            pass

    return out


def merge_inventories(primary: dict, fallback: dict) -> dict:
    """Merge pycdlib inventory with 7z fallback inventory."""
    return {
        "top_level_entries": sorted(set(primary["top_level_entries"]) | set(fallback["top_level_entries"])),
        "file_count": max(primary["file_count"], fallback["file_count"]),
        "dir_count": max(primary["dir_count"], fallback["dir_count"]),
        "extensions": primary["extensions"] + fallback["extensions"],
        "largest_file": primary["largest_file"] or fallback["largest_file"],
        "largest_file_size": primary["largest_file_size"] or fallback["largest_file_size"],
        "content_markers": set(primary["content_markers"]) | set(fallback["content_markers"]),
        "readable": primary["readable"] or fallback["readable"],
        "walk_error": primary.get("walk_error", ""),
        "open_error": primary.get("open_error", ""),
    }


# ---------------------------------------------------------------------------
# Disc-type and DVD validation
# ---------------------------------------------------------------------------

def infer_disc_type(filesystems: str, markers: set[str], creator_norm: str, extensions: Counter) -> str:
    """Heuristic disc classification."""
    fs_low = filesystems.lower()
    exts = {k.lower() for k in extensions.keys()}
    markers = {m.upper() for m in markers}

    if "VIDEO_TS" in markers or {".VOB", ".IFO", ".BUP"} & markers:
        return "DVD-Video"

    if "BDMV" in markers:
        return "Blu-ray-style data disc"

    if "MPEGAV" in markers or "VCD" in markers:
        return "Video CD (VCD)-style disc"

    if "MPEG2" in markers or "SVCD" in markers:
        return "Super Video CD (SVCD)-style disc"

    if "DCIM" in markers:
        return "Photo / camera media disc"

    if {".EXE", ".MSI"} & markers:
        return "Software / application disc"

    if {".PDF", ".XML"} & markers and {".JPG", ".MOV", ".MPG", ".AVI", ".WAV", ".MP3"} & markers:
        return "Mixed document/media data disc"

    if {".JPG"} & markers and len(exts) <= 4:
        return "Photo/data disc"

    if {".WAV", ".MP3"} & markers and not {"VIDEO_TS", "MPEGAV", "MPEG2"} & markers:
        return "Audio files on data disc"

    if "pure udf" in fs_low:
        if "imapi" in creator_norm.lower():
            return "Packet-written / drag-and-drop UDF data disc"
        return "Pure UDF data disc"

    if "udf" in fs_low and "iso9660" in fs_low:
        return "Hybrid ISO/UDF data disc"

    if "iso9660" in fs_low and "joliet" in fs_low:
        return "ISO9660/Joliet data disc"

    if "iso9660" in fs_low:
        return "ISO9660 data disc"

    return "Unknown"


def validate_dvd_video_structure(paths: list[str], top_entries: list[str], markers: set[str]) -> dict:
    """Check for basic DVD-Video structure coherence."""
    out = {
        "dvd_video_present": False,
        "dvd_core_files_present": False,
        "titleset_count": 0,
        "dvd_validation": "",
    }

    lower_paths = [p.replace("\\", "/").lower() for p in paths]
    lower_top = [x.lower() for x in top_entries]
    upper_markers = {m.upper() for m in markers}

    has_video_ts_dir = ("video_ts" in lower_top) or any(
        p == "video_ts" or p.startswith("video_ts/") for p in lower_paths
    )
    has_video_ts_ifo = any(p.endswith("video_ts/video_ts.ifo") for p in lower_paths)
    has_video_ts_bup = any(p.endswith("video_ts/video_ts.bup") for p in lower_paths)
    has_any_vob = any(p.endswith(".vob") and "video_ts/" in p for p in lower_paths) or (".VOB" in upper_markers)

    titlesets = set()
    for p in lower_paths:
        name = p.split("/")[-1]
        if name.startswith("vts_") and len(name) >= 6:
            titlesets.add(name[:6])

    out["dvd_video_present"] = has_video_ts_dir and (has_any_vob or ".IFO" in upper_markers or ".BUP" in upper_markers)
    out["dvd_core_files_present"] = has_video_ts_ifo and has_video_ts_bup
    out["titleset_count"] = len(titlesets)

    if out["dvd_video_present"] and out["dvd_core_files_present"]:
        out["dvd_validation"] = "Complete basic VIDEO_TS structure"
    elif out["dvd_video_present"]:
        out["dvd_validation"] = "VIDEO_TS structure present but incomplete"
    else:
        out["dvd_validation"] = ""

    return out


def assess_dvd_file_coherence(paths: list[str]) -> dict:
    """
    Check whether DVD-Video control/backup files are coherently paired.
    """
    out = {
        "video_ts_ifo_present": False,
        "video_ts_bup_present": False,
        "titleset_ifo_count": 0,
        "titleset_bup_count": 0,
        "missing_bup_for_titlesets": [],
        "missing_ifo_for_titlesets": [],
        "dvd_file_coherence": "",
    }

    lower_paths = [p.replace("\\", "/").lower() for p in paths]
    names = [p.split("/")[-1] for p in lower_paths]

    out["video_ts_ifo_present"] = "video_ts.ifo" in names
    out["video_ts_bup_present"] = "video_ts.bup" in names

    ifo_sets = set()
    bup_sets = set()

    for name in names:
        if name.startswith("vts_") and name.endswith("_0.ifo") and len(name) >= 10:
            ifo_sets.add(name[:6])
        elif name.startswith("vts_") and name.endswith("_0.bup") and len(name) >= 10:
            bup_sets.add(name[:6])

    out["titleset_ifo_count"] = len(ifo_sets)
    out["titleset_bup_count"] = len(bup_sets)
    out["missing_bup_for_titlesets"] = sorted(ifo_sets - bup_sets)
    out["missing_ifo_for_titlesets"] = sorted(bup_sets - ifo_sets)

    issues = []
    if out["video_ts_ifo_present"] and not out["video_ts_bup_present"]:
        issues.append("missing VIDEO_TS.BUP")
    if out["missing_bup_for_titlesets"]:
        issues.append("missing BUP for " + ", ".join(out["missing_bup_for_titlesets"]))
    if out["missing_ifo_for_titlesets"]:
        issues.append("missing IFO for " + ", ".join(out["missing_ifo_for_titlesets"]))

    out["dvd_file_coherence"] = "; ".join(issues) if issues else "Coherent basic IFO/BUP pairing"
    return out


def assess_makemkv_risk(record: dict) -> tuple[str, str, str]:
    """
    Heuristic MakeMKV triage.

    Returns:
      (makemkv_risk, preferred_access_path, basis)
    """
    fs_detail = (record.get("Filesystem Parse Detail") or "").lower()
    top_entries = (record.get("Top-Level Entries") or "").lower()
    primary_exts = (record.get("Primary Extensions") or "").lower()
    likely_type = record.get("Likely Disc Type", "")
    read_method = record.get("Read Method", "")
    dvd_validation = record.get("DVD-Video Validation", "")
    dvd_coherence = (record.get("DVD File Coherence") or "").lower()
    creator_norm = record.get("Software / Creator (Normalized)", "")
    filesystems = record.get("Filesystems", "")
    qc_status = record.get("QC Status", "")
    readable = record.get("Readable Filesystem", "")
    tail_type = record.get("Tail Padding Type", "")

    if likely_type != "DVD-Video":
        if readable == "No":
            return "Not applicable", "Manual assessment", "non-DVD disc; payload not readily accessible"
        if read_method == "pycdlib" and qc_status in ("PASS", "PASS (Padded)"):
            return "Not applicable", "Standard file extraction", "non-DVD image parsed normally"
        if read_method == "7z fallback":
            return "Not applicable", "Fallback file extraction", "non-DVD image relies on fallback reader"
        return "Not applicable", "Manual assessment", "non-DVD case"

    if readable == "No":
        return "High", "Manual assessment", "payload not readily accessible"

    if "duplicate" in fs_detail:
        return "High", "Direct VOB extraction recommended", "duplicate/conflicting filesystem entries"

    if "opendvd" in top_entries or ".ses" in primary_exts or ".dvd" in primary_exts:
        return "High", "Direct VOB extraction recommended", "authoring/project-style DVD image"

    if "pure udf" in filesystems.lower() and read_method != "7z fallback":
        return "High", "Manual assessment", "pure UDF DVD-like image without accessible payload listing"

    if "unknown/corrupt" in filesystems.lower():
        return "High", "Fallback extraction recommended", "filesystem appears structurally odd/corrupt"

    if "missing" in dvd_coherence:
        return "High", "Direct VOB extraction recommended", "IFO/BUP pairing is incomplete"

    recorder_creators = {
        "SONY_DVDIRECT",
        "SONY_DVD_RECORDER",
        "LG",
    }

    if "expected at least 2 udf anchors" in fs_detail:
        if (
            read_method == "7z fallback"
            and dvd_validation == "Complete basic VIDEO_TS structure"
            and dvd_coherence == "coherent basic ifo/bup pairing"
            and "video_ts" in top_entries
            and ".ses" not in primary_exts
            and ".dvd" not in primary_exts
            and creator_norm in recorder_creators
        ):
            return "Low", "Standard MakeMKV path likely", "recorder-authored DVD with clean VIDEO_TS payload despite UDF anchor warning"
        else:
            return "Medium", "Fallback extraction recommended", "UDF anchor warning with less-clean surrounding signals"

    if (
        read_method == "7z fallback"
        and dvd_validation == "Complete basic VIDEO_TS structure"
        and dvd_coherence == "coherent basic ifo/bup pairing"
        and "video_ts" in top_entries
        and ".ses" not in primary_exts
        and ".dvd" not in primary_exts
    ):
        return "Medium", "Fallback extraction recommended", "DVD payload is coherent but parser-dependent"

    if read_method == "pycdlib" and dvd_validation == "Complete basic VIDEO_TS structure":
        return "Low", "Standard MakeMKV path likely", "DVD parsed normally"

    return "Medium", "Fallback extraction recommended", "DVD payload present but structural behavior is nonstandard"


# ---------------------------------------------------------------------------
# Main analyser
# ---------------------------------------------------------------------------

def analyze_iso(file_path: Path) -> dict:
    print(f"\n{'-' * 52}\n💿  {file_path.name}\n{'-' * 52}")

    record = {
        "File Name": file_path.name,
        "Disc Title": "",
        "Likely Disc Type": "",
        "Actual Size (Bytes)": file_path.stat().st_size,
        "Expected Size (Bytes)": "Unknown",
        "Difference (Bytes)": "N/A",
        "Sector Aligned": "",
        "Tail Padding Type": "",
        "QC Status": "UNKNOWN",
        "Software / Creator": "Unknown",
        "Software / Creator (Normalized)": "",
        "Filesystems": "",
        "Filesystem Parse Status": "",
        "Filesystem Parse Detail": "",
        "Read Method": "",
        "Descriptor Signatures": "",
        "Readable Filesystem": "",
        "Top-Level Entries": "",
        "File Count": "",
        "Directory Count": "",
        "Primary Extensions": "",
        "Largest File": "",
        "Largest File Size": "",
        "System ID": "",
        "Volume Set ID": "",
        "Publisher": "",
        "DVD-Video Validation": "",
        "DVD Core Files Present": "",
        "Titleset Count": "",
        "DVD File Coherence": "",
        "Manual Review Suggested": "",
        "Authoring Pattern": "",
        "Review Reason": "",
        "MakeMKV Risk": "",
        "Preferred Access Path": "",
        "MakeMKV Heuristic Basis": "",
        "Notes": "",
    }

    # 1. Size & integrity QC
    seven_z = get_7z_data(file_path)
    expected = seven_z["expected_size"]
    actual = record["Actual Size (Bytes)"]

    record["Sector Aligned"] = "Yes" if actual % 2048 == 0 else "No"

    print(f"  Actual Size:        {actual:,} bytes")
    print(f"  Sector Aligned:     {record['Sector Aligned']}")

    if isinstance(expected, int):
        record["Expected Size (Bytes)"] = expected
        print(f"  Header/Expected:    {expected:,} bytes")
        diff = actual - expected
        record["Difference (Bytes)"] = diff

        if diff == 0:
            record["QC Status"] = "PASS"
            print("  QC Status:          ✅ PASS (sizes match exactly)")
        elif diff > 0:
            tail_type = _inspect_tail_padding(file_path, expected)
            record["Tail Padding Type"] = tail_type or ""

            if diff % 2048 == 0:
                record["QC Status"] = "PASS (Padded)"
                _append_note(record, f"+{diff} bytes (normal sector padding)")
                if tail_type:
                    _append_note(record, f"tail: {tail_type}")
                print(f"  QC Status:          ☑️  PASS (+{diff:,} bytes — normal sector padding)")
                if tail_type:
                    print(f"  Tail Padding:       {tail_type}")
            else:
                record["QC Status"] = "WARNING"
                _append_note(record, f"+{diff} bytes (non-sector-aligned extra data)")
                if tail_type:
                    _append_note(record, f"tail: {tail_type}")
                print(f"  QC Status:          ⚠️  WARNING (+{diff:,} bytes — non-sector-aligned, review rip)")
                if tail_type:
                    print(f"  Tail Padding:       {tail_type}")
        else:
            record["QC Status"] = "FAIL"
            _append_note(record, f"Truncated: {abs(diff):,} bytes missing")
            print(f"  QC Status:          ❌ FAIL ({diff:,} bytes — image appears truncated!)")
    else:
        record["QC Status"] = "ERROR"
        record["Notes"] = seven_z["error"] or "Header read error"
        print(f"  QC Status:          ⚠️  UNKNOWN ({record['Notes']})")

    # 2. Creator / authoring software
    software_list: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        key = name.strip()
        if key and key not in seen:
            seen.add(key)
            software_list.append(key)

    pvd = get_pvd_fields(file_path)
    udf = get_udf_fields(file_path)

    _add(pvd["preparer"])
    _add(pvd["app_id"])
    _add(udf["creator"])
    if udf["iuvd_creator"]:
        _add(udf["iuvd_creator"])
    if seven_z["creator"]:
        _add(seven_z["creator"])

    if software_list:
        record["Software / Creator"] = " / ".join(software_list)
        record["Software / Creator (Normalized)"] = _normalize_creator(software_list[0])

    print(f"  Creator Software:   {record['Software / Creator']}")

    # 3. Disc title / metadata
    disc_title = _pick_best_title(
        udf["disc_title"],
        udf["lv_info_2"],
        udf["lv_info_3"],
        pvd["volume_id"],
    )
    record["Disc Title"] = disc_title or "—"

    record["System ID"] = pvd["system_id"]
    record["Volume Set ID"] = pvd["volume_set_id"]
    record["Publisher"] = pvd["publisher"]

    for label, val in (
        ("LV2", udf["lv_info_2"]),
        ("LV3", udf["lv_info_3"]),
        ("PVD Publisher", pvd["publisher"]),
        ("Copyright File", pvd["copyright_file"]),
        ("Abstract File", pvd["abstract_file"]),
        ("Bibliographic File", pvd["bibliographic_file"]),
    ):
        if val:
            _append_note(record, f"{label}: {val}")

    print(f"  Disc Title:         {record['Disc Title']}")

    # 4. Low-level signature reconnaissance
    sigscan = scan_descriptor_signatures(file_path)
    record["Descriptor Signatures"] = "; ".join(sigscan["signatures"])
    if record["Descriptor Signatures"]:
        print(f"  Descriptor Sigs:    {record['Descriptor Signatures']}")

    # 5. Filesystem identification
    fs_list: list[str] = []
    parse_status = ""
    parse_detail = ""

    iso_obj = pycdlib.PyCdlib()
    pycdlib_open_ok = False

    try:
        iso_obj.open(str(file_path))
        pycdlib_open_ok = True
        parse_status = "Parsed by pycdlib"
        fs_list.append("ISO9660")
        if iso_obj.has_udf():
            fs_list.append("UDF")
        if iso_obj.has_joliet():
            fs_list.append("Joliet")
        if iso_obj.has_rock_ridge():
            fs_list.append("Rock Ridge")
    except Exception as e:
        err = str(e)
        parse_detail = err[:250]

        if "least one pvd" in err.lower():
            if sniff_pure_udf(file_path):
                fs_list.append("Pure UDF")
                parse_status = "pycdlib could not parse; pure-UDF signatures detected"
            else:
                fs_list.append("Unknown/Corrupt")
                parse_status = "pycdlib parse failed"
                _append_note(record, "corrupt or unrecognised headers")
        else:
            fs_list.append("Error")
            parse_status = "pycdlib parse failed"
            _append_note(record, f"FS detection error: {err[:180]}")
    finally:
        try:
            iso_obj.close()
        except Exception:
            pass

    record["Filesystems"] = " + ".join(fs_list)
    record["Filesystem Parse Status"] = parse_status
    record["Filesystem Parse Detail"] = parse_detail

    print(f"  Filesystems Found:  {record['Filesystems']}")
    if record["Filesystem Parse Status"]:
        print(f"  FS Parse Status:    {record['Filesystem Parse Status']}")
    if record["Filesystem Parse Detail"]:
        print(f"  FS Parse Detail:    {record['Filesystem Parse Detail']}")

    # 6. Inventory / readability
    inv_py = inventory_from_pycdlib(file_path)
    inv_7z = inventory_from_7z(seven_z["paths"])
    inv = merge_inventories(inv_py, inv_7z)

    record["Readable Filesystem"] = "Yes" if inv["readable"] else "No"

    if pycdlib_open_ok and inv_py["readable"]:
        record["Read Method"] = "pycdlib"
    elif inv_7z["readable"]:
        record["Read Method"] = "7z fallback"
    elif sigscan["udf_anchor_present"] or sigscan["udf_nsr_present"]:
        record["Read Method"] = "raw descriptor scan only"
    else:
        record["Read Method"] = "none"

    if not pycdlib_open_ok and inv_7z["readable"]:
        inferred_fs = []
        if sigscan["iso_pvd_present"]:
            inferred_fs.append("ISO9660?")
        if sigscan["udf_nsr_present"] or sigscan["udf_anchor_present"]:
            inferred_fs.append("UDF?")

        if inferred_fs:
            record["Filesystems"] = " + ".join(inferred_fs) + " (signature-based)"
        elif record["Filesystems"] == "Error":
            record["Filesystems"] = "Nonstandard / parser-resistant"

        if "VIDEO_TS" in inv["content_markers"] or {".VOB", ".IFO", ".BUP"} & inv["content_markers"]:
            record["Filesystem Parse Status"] = "Nonstandard DVD-Video structure; fallback inventory succeeded"
            _append_note(record, "pycdlib failed, but 7z successfully listed DVD-Video payload")

            if record["Software / Creator (Normalized)"] == "Cirrus Sonata":
                record["Authoring Pattern"] = "Sonata fallback-readable DVD"
                _append_note(record, "nonstandard Sonata-authored structure; payload appears intact")
        else:
            record["Filesystem Parse Status"] = "pycdlib failed; fallback inventory succeeded"

    record["Top-Level Entries"] = _format_top_entries(inv["top_level_entries"])
    record["File Count"] = inv["file_count"]
    record["Directory Count"] = inv["dir_count"]
    record["Largest File"] = inv["largest_file"]
    record["Largest File Size"] = inv["largest_file_size"] if inv["largest_file_size"] else ""

    if inv["extensions"]:
        most_common_exts = [f"{ext} ({count})" for ext, count in inv["extensions"].most_common(8)]
        record["Primary Extensions"] = "; ".join(most_common_exts)

    if inv.get("open_error"):
        _append_note(record, f"pycdlib open note: {inv['open_error'][:180]}")
    if inv.get("walk_error"):
        _append_note(record, f"tree walk note: {inv['walk_error'][:180]}")

    print(f"  Readable FS:        {record['Readable Filesystem']}")
    print(f"  Read Method:        {record['Read Method']}")
    if record["Top-Level Entries"]:
        print(f"  Top-Level Entries:  {record['Top-Level Entries']}")
    print(f"  File Count:         {record['File Count']}")
    print(f"  Directory Count:    {record['Directory Count']}")
    if record["Primary Extensions"]:
        print(f"  Primary Exts:       {record['Primary Extensions']}")
    if record["Largest File"]:
        print(f"  Largest File:       {record['Largest File']} ({record['Largest File Size']:,} bytes)")

    # 7. Disc-type inference
    record["Likely Disc Type"] = infer_disc_type(
        record["Filesystems"],
        inv["content_markers"],
        record["Software / Creator (Normalized)"],
        inv["extensions"],
    )
    print(f"  Likely Disc Type:   {record['Likely Disc Type']}")

    is_dvd_video = (
        record["Likely Disc Type"] == "DVD-Video"
        or "VIDEO_TS" in inv["content_markers"]
        or bool({".VOB", ".IFO", ".BUP"} & inv["content_markers"])
    )

    # 8. DVD-Video validation (only when relevant)
    if is_dvd_video:
        dvd = validate_dvd_video_structure(seven_z["paths"], inv["top_level_entries"], inv["content_markers"])
        record["DVD-Video Validation"] = dvd["dvd_validation"]
        record["DVD Core Files Present"] = "Yes" if dvd["dvd_core_files_present"] else "No"
        record["Titleset Count"] = dvd["titleset_count"]

        if record["DVD-Video Validation"]:
            print(f"  DVD Validation:     {record['DVD-Video Validation']}")
            print(f"  DVD Core Files:     {record['DVD Core Files Present']}")
            print(f"  Titleset Count:     {record['Titleset Count']}")

        dvd_files = assess_dvd_file_coherence(seven_z["paths"])
        record["DVD File Coherence"] = dvd_files["dvd_file_coherence"]
        if record["DVD File Coherence"]:
            print(f"  DVD File Coherence: {record['DVD File Coherence']}")
    else:
        record["DVD-Video Validation"] = "Not applicable"
        record["DVD Core Files Present"] = "N/A"
        record["Titleset Count"] = ""
        record["DVD File Coherence"] = "Not applicable"

    # 9. Manual review flag
    review = False

    if record["QC Status"] in ("FAIL", "ERROR"):
        review = True
    if record["Sector Aligned"] == "No":
        review = True
    if record["Readable Filesystem"] == "No":
        review = True
    if record["Filesystems"] == "Unknown/Corrupt":
        review = True
    if record["QC Status"] == "WARNING":
        review = True

    if (
        "Nonstandard" in record["Filesystem Parse Status"]
        or (record["Read Method"] == "7z fallback" and record["Likely Disc Type"] == "DVD-Video")
    ):
        review = True
        record["Review Reason"] = "Nonstandard structure; payload accessible via fallback tools"
        _append_note(record, "fallback extraction/access may be preferable to standard mount")

    if record["QC Status"] == "FAIL":
        record["Review Reason"] = "Possible truncation or missing data"
    elif record["QC Status"] == "WARNING" and not record["Review Reason"]:
        record["Review Reason"] = "Unexpected extra data or alignment issue"
    elif record["Readable Filesystem"] == "No" and not record["Review Reason"]:
        record["Review Reason"] = "Payload not readily accessible"
    elif record["Filesystems"] == "Unknown/Corrupt" and not record["Review Reason"]:
        record["Review Reason"] = "Filesystem signatures or structure appear corrupt"

    if record["Disc Title"] == "—" and "Pure UDF" in record["Filesystems"]:
        review = True
        if not record["Review Reason"]:
            record["Review Reason"] = "Pure UDF image with limited descriptive metadata"

    # 10. MakeMKV triage
    makemkv_risk, preferred_access_path, basis = assess_makemkv_risk(record)
    record["MakeMKV Risk"] = makemkv_risk
    record["Preferred Access Path"] = preferred_access_path
    record["MakeMKV Heuristic Basis"] = basis

    if (
        record["Likely Disc Type"] == "DVD-Video"
        and record["Read Method"] == "7z fallback"
        and (
            "duplicate" in (record["Filesystem Parse Detail"] or "").lower()
            or "opendvd" in (record["Top-Level Entries"] or "").lower()
            or ".ses" in (record["Primary Extensions"] or "").lower()
            or ".dvd" in (record["Primary Extensions"] or "").lower()
        )
    ):
        if not record["Authoring Pattern"]:
            record["Authoring Pattern"] = "Authoring/project-style DVD image"
        if not record["Review Reason"] or "fallback" in record["Review Reason"].lower():
            record["Review Reason"] = "Likely poor MakeMKV candidate; direct VOB extraction may be preferable"
        _append_note(record, "authoring/project-style disc structure may interfere with MakeMKV")

    record["Manual Review Suggested"] = "Yes" if review else "No"
    print(f"  Manual Review:      {record['Manual Review Suggested']}")
    if record["Authoring Pattern"]:
        print(f"  Authoring Pattern:  {record['Authoring Pattern']}")
    if record["Review Reason"]:
        print(f"  Review Reason:      {record['Review Reason']}")

    if is_dvd_video:
        print(f"  MakeMKV Risk:       {record['MakeMKV Risk']}")
        print(f"  Access Path:        {record['Preferred Access Path']}")
        print(f"  MakeMKV Basis:      {record['MakeMKV Heuristic Basis']}")
    else:
        print(f"  Access Path:        {record['Preferred Access Path']}")

    return record


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "QC and identification tool for ISO disc images — checks size integrity, "
            "extracts filesystem metadata, inventories contents, infers likely disc type, "
            "flags potential review issues, and triages likely MakeMKV failures."
        )
    )
    parser.add_argument(
        "-i", "--input", required=True, type=Path,
        help="Path to a single .iso file or a directory of .iso files."
    )
    parser.add_argument(
        "--csv", type=Path,
        help="Optional path to write a CSV report."
    )
    args = parser.parse_args()

    target: Path = args.input
    if not target.exists():
        print(f"Error: '{target}' does not exist.")
        sys.exit(1)

    if target.is_file():
        iso_files = [target]
    else:
        iso_files = sorted(
            f for f in target.rglob("*")
            if f.is_file() and f.suffix.lower() == ".iso"
        )
        if not iso_files:
            print(f"No .iso files found in '{target}' or its subdirectories.")
            sys.exit(0)

    print(f"Found {len(iso_files)} ISO(s). Beginning QC scan…")
    results = [analyze_iso(f) for f in iso_files]

    if args.csv:
        fieldnames = [
            "File Name",
            "Disc Title",
            "Likely Disc Type",
            "Actual Size (Bytes)",
            "Expected Size (Bytes)",
            "Difference (Bytes)",
            "Sector Aligned",
            "Tail Padding Type",
            "QC Status",
            "Software / Creator",
            "Software / Creator (Normalized)",
            "Filesystems",
            "Filesystem Parse Status",
            "Filesystem Parse Detail",
            "Read Method",
            "Descriptor Signatures",
            "Readable Filesystem",
            "Top-Level Entries",
            "File Count",
            "Directory Count",
            "Primary Extensions",
            "Largest File",
            "Largest File Size",
            "System ID",
            "Volume Set ID",
            "Publisher",
            "DVD-Video Validation",
            "DVD Core Files Present",
            "Titleset Count",
            "DVD File Coherence",
            "Manual Review Suggested",
            "Authoring Pattern",
            "Review Reason",
            "MakeMKV Risk",
            "Preferred Access Path",
            "MakeMKV Heuristic Basis",
            "Notes",
        ]

        print(f"\n{'-' * 52}\n💾  Saving report → {args.csv}\n{'-' * 52}")
        try:
            with open(args.csv, mode="w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            print("✅  CSV saved successfully.")
        except Exception as e:
            print(f"❌  Failed to write CSV: {e}")


if __name__ == "__main__":
    main()