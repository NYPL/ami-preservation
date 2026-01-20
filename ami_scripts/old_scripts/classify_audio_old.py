#!/usr/bin/env python3
"""
Per-Stream / Per-Channel Audio Configuration Classifier (Updated)

1) Dual-mono now requires STRONG evidence:
   - Side much weaker than Mid (width very negative), AND/OR
   - Very high correlation estimate (close to 1.0), AND
   - Channels closely level-matched
2) “Borderline” cases now default to STEREO (with a warning flag), not MONO.
   Rationale: your reported failure mode is falsely calling stereo “dual mono.”
   Defaulting to stereo reduces that error.

Notes:
- This remains a heuristic classifier. The most robust discriminator is still
  a direct L/R similarity check (e.g., correlation on PCM samples), but this
  update tightens your existing mid/side approach without adding heavy DSP deps.
"""

import argparse
import subprocess
import json
import sys
import re
import math
import os
from typing import Dict, Tuple, List, Optional
from collections import Counter

# -------------------------
# Configuration
# -------------------------

SILENCE_THRESH_DB = -60.0

# LTC detection
LTC_PROBE_DURATION_DEFAULT = 240
LTC_MATCH_THRESHOLD = 6
LTC_MIN_UNIQUE = 4
LTC_MIN_MONOTONIC_RATIO = 0.6
LTC_FPS_CANDIDATES = (24, 25, 30)

# Mid/Side width thresholds (Side RMS - Mid RMS)
# Dual-mono (L≈R) should have Side MUCH weaker than Mid.
# True stereo can still be center-heavy, but Side usually isn't *that* far down.
DUAL_MONO_MAX_WIDTH_DB = -6.0     # <= -6 dB is strong evidence of dual-mono
STEREO_MIN_WIDTH_DB = -2.0        # >= -2 dB is strong evidence of stereo

# Correlation estimate thresholds (from mid/side energies)
# This estimate tends to be "moderately positive" for many real stereo mixes.
# So, use it only as strong evidence when it's VERY high.
CORRELATION_DUAL_MONO_MIN = 0.85  # must be very high to call dual-mono in borderline
CORRELATION_STEREO_MAX = 0.30     # low correlation suggests stereo (but not required)

# Volume difference heuristics
VOLUME_MATCH_DB = 1.5
VOLUME_DIFFERENT_DB = 3.0

# Known configs (your original list)
KNOWN_CONFIGS = [
    "Ch1: None; Ch2: None",
    "Ch1: Mono",
    "Ch1: None",
    "Ch1: Mono; Ch2: Mono",
    "Ch1: Mono; Ch2: Mono; Ch3: Mono",
    "Ch1: Mono; Ch2: Mono; Ch3: None",
    "Ch1: Mono; Ch2: Mono; Ch3: Timecode",
    "Ch1: Mono; Ch2: None; Ch3: Timecode",
    "Ch1: Mono; Ch2: Mono; Ch3: Mono; Ch4: Mono",
    "Ch1: Mono; Ch2: Mono; Ch3: Mono; Ch4: None",
    "Ch1: Mono; Ch2: Mono; Ch3: None; Ch4: None",
    "Ch1: Mono; Ch2: Mono; Ch3: None; Ch4: Mono",
    "Ch1: None; Ch2: None; Ch3: None; Ch4: Mono",
    "Ch1: Mono; Ch2: None; Ch3: Mono; Ch4: None",
    "Ch1: None; Ch2: None; Ch3: None; Ch4: None",
    "Ch1: Mono; Ch2: None; Ch3: None; Ch4: None",
    "Ch1: None; Ch2: None; Ch3: Mono; Ch4: Mono",
    "Ch1: Mono; Ch2: Mono; Ch3: Stereo Left; Ch4: Stereo Right",
    "Ch1: Mono; Ch2: None",
    "Ch1: Mono; Ch2: Timecode",
    "Ch1: None; Ch2: Mono",
    "Ch1: None; Ch2: Timecode",
    "Ch1: None; Ch2: Timecode; Ch3: Stereo Left; Ch4: Stereo Right",
    "Ch1: None; Ch2: None; Ch3: Timecode",
    "Ch1: Stereo Left; Ch2: Mono; Ch3: Stereo Right; Ch4: Mono",
    "Ch1: Stereo Left; Ch2: Stereo Left; Ch3: Stereo Right; Ch4: Stereo Right",
    "Ch1: Stereo Left; Ch2: Stereo Right",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: None",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Timecode",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Mono",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: None; Ch4: Mono",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Mono; Ch4: Mono",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Stereo Left; Ch4: Stereo Right",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: None; Ch4: None",
    "Ch1: Timecode; Ch2: Mono",
    "Ch1: Timecode; Ch2: Timecode",
    "Ch1: None; Ch2: Mono; Ch3: None; Ch4: None",
    "Ch1: None; Ch2: Mono; Ch3: None; Ch4: Mono",
    "Ch1: None; Ch2: Mono; Ch3: Timecode",
    "Ch1: None; Ch2: None; Ch3: None",
    "Ch1: Mono; Ch2: None; Ch3: Stereo Left; Ch4: Stereo Right",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Mono; Ch4: None",
    "Ch1: Timecode; Ch2: None",
    "Ch1: None; Ch2: None; Ch3: Stereo Left; Ch4: Stereo Right",
    "Ch1: Stereo Left; Ch2: Stereo Right; Ch3: Stereo Left; Ch4: Stereo Right; Ch5: Stereo Left; Ch6: Stereo Right; Ch7: Stereo Left; Ch8: Stereo Right",
]

# -------------------------
# Helpers
# -------------------------

def _safe_float(s: str) -> float:
    try:
        v = float(s)
        if math.isnan(v) or math.isinf(v):
            return float("-inf")
        return v
    except Exception:
        return float("-inf")


def ffprobe_audio_streams(input_file: str) -> List[Dict]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index,channels,channel_layout,codec_name",
        "-of", "json",
        input_file
    ]
    try:
        out = subprocess.check_output(cmd, text=True)
        data = json.loads(out)
        streams = data.get("streams", []) or []
        cleaned = []
        for s in streams:
            cleaned.append({
                "index": int(s.get("index")),
                "channels": int(s.get("channels") or 0),
                "channel_layout": s.get("channel_layout") or "",
                "codec_name": s.get("codec_name") or ""
            })
        return cleaned
    except Exception:
        return []


def parse_astats(stderr: str) -> Dict[int, Dict[str, float]]:
    stats: Dict[int, Dict[str, float]] = {}
    current_channel = None

    ch_re = re.compile(r"Channel:\s*(\d+)", re.I)
    rms_re = re.compile(r"RMS level(?: dB)?:\s*([^\s]+)", re.I)
    peak_re = re.compile(r"Peak level(?: dB)?:\s*([^\s]+)", re.I)
    rms_peak_re = re.compile(r"RMS peak(?: dB)?:\s*([^\s]+)", re.I)

    for line in stderr.splitlines():
        m = ch_re.search(line)
        if m:
            current_channel = int(m.group(1))
            stats.setdefault(current_channel, {})
            continue
        if current_channel is None:
            continue

        m = rms_re.search(line)
        if m:
            stats[current_channel]["rms"] = _safe_float(m.group(1))
            continue

        m = peak_re.search(line)
        if m:
            stats[current_channel]["peak"] = _safe_float(m.group(1))
            continue

        m = rms_peak_re.search(line)
        if m:
            stats[current_channel]["rms_peak"] = _safe_float(m.group(1))
            continue

    return stats


def classify_silence_or_mono(rms_db: float, peak_db: float) -> str:
    if rms_db == float("-inf") or rms_db <= SILENCE_THRESH_DB:
        return "None"
    return "Mono"


def calculate_correlation_estimate(mid_rms: float, side_rms: float) -> float:
    """
    corr ≈ (M² - S²) / (M² + S²), with M/S in linear power (derived from dB)
    - Dual mono (L=R): Side ~ -inf => corr ~ 1
    - Uncorrelated-ish stereo: Mid ≈ Side => corr ~ 0
    - Anti-corr (L=-R): Mid ~ -inf => corr ~ -1
    """
    if mid_rms == float("-inf") and side_rms == float("-inf"):
        return 1.0
    if mid_rms == float("-inf") and side_rms != float("-inf"):
        return -1.0
    if side_rms == float("-inf"):
        return 1.0

    mid_power = 10 ** (mid_rms / 10)
    side_power = 10 ** (side_rms / 10)
    denom = mid_power + side_power
    if denom <= 0:
        return 1.0
    corr = (mid_power - side_power) / denom
    return max(-1.0, min(1.0, corr))


def detect_ltc_in_channel(
    input_file: str,
    stream_index: int,
    channel_1based: int,
    probe_duration: int,
    match_threshold: int = LTC_MATCH_THRESHOLD,
    min_unique: int = LTC_MIN_UNIQUE,
    min_monotonic_ratio: float = LTC_MIN_MONOTONIC_RATIO,
    fps_candidates: Tuple[int, ...] = LTC_FPS_CANDIDATES,
    debug: bool = False,
) -> Tuple[bool, Optional[int], float, List[Tuple[int, int, int, int]]]:
    ch0 = channel_1based - 1
    pan_filter = f"pan=mono|c0=c{ch0}"

    ffmpeg_command = [
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
        "-t", str(probe_duration),
        "-i", str(input_file),
        "-map", f"0:{stream_index}",
        "-af", pan_filter,
        "-ar", "48000", "-ac", "1",
        "-f", "wav", "pipe:1"
    ]
    ltcdump_command = ["ltcdump", "-"]

    try:
        ffmpeg_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ltcdump_proc = subprocess.Popen(
            ltcdump_command,
            stdin=ffmpeg_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        assert ffmpeg_proc.stdout is not None
        ffmpeg_proc.stdout.close()
        ltcdump_out, _ltcdump_err = ltcdump_proc.communicate()
        ffmpeg_proc.wait()
    except FileNotFoundError as e:
        if debug:
            print(f"  [LTC DEBUG] tool missing: {e}")
        return False, None, 0.0, []
    except Exception as e:
        if debug:
            print(f"  [LTC DEBUG] exception: {e}")
        return False, None, 0.0, []

    tc_pat = re.compile(r'(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.:;](?P<f>\d{2})')
    raw = [(int(m.group('h')), int(m.group('m')), int(m.group('s')), int(m.group('f')))
           for m in tc_pat.finditer(ltcdump_out)]

    if debug:
        print(f"  [LTC DEBUG] stream={stream_index} ch={channel_1based} tokens={len(raw)}")

    if not raw:
        return False, None, 0.0, []

    def to_frames(h, m, s, f, fps):
        return (((h * 60) + m) * 60 + s) * fps + f

    seen = set()
    ordered_unique = []
    for tc in raw:
        if tc not in seen:
            seen.add(tc)
            ordered_unique.append(tc)

    best_ratio = 0.0
    best_fps: Optional[int] = None
    best_valid_seq: List[Tuple[int, int, int, int]] = []

    for fps in fps_candidates:
        valid = [(h, m, s, f) for (h, m, s, f) in ordered_unique
                 if m < 60 and s < 60 and f < fps]

        if len(valid) < match_threshold or len(set(valid)) < min_unique:
            continue

        frames = [to_frames(h, m, s, f, fps) for (h, m, s, f) in valid]
        if len(frames) < 2:
            continue

        deltas = [frames[i + 1] - frames[i] for i in range(len(frames) - 1)]
        max_jump = 2 * fps

        good_fwd = sum(1 for d in deltas if 0 < d <= max_jump)
        good_rev = sum(1 for d in deltas if -max_jump <= d < 0)
        ratio = max(good_fwd, good_rev) / len(deltas)

        if ratio > best_ratio:
            best_ratio = ratio
            best_fps = fps
            best_valid_seq = valid

    if best_fps is not None and best_ratio >= min_monotonic_ratio and len(best_valid_seq) >= match_threshold:
        return True, best_fps, best_ratio, best_valid_seq

    return False, best_fps, best_ratio, best_valid_seq


def get_raw_channel_stats_for_stream(input_file: str, stream_index: int, duration: int) -> Dict[int, Dict[str, float]]:
    filt = "aformat=sample_fmts=fltp,astats=metadata=1:reset=1:measure_perchannel=RMS_level+Peak_level+RMS_peak"
    cmd = [
        "ffmpeg", "-hide_banner", "-v", "info",
        "-i", input_file,
        "-t", str(duration),
        "-map", f"0:{stream_index}",
        "-af", filt,
        "-f", "null", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, stderr = proc.communicate()
    return parse_astats(stderr)


def get_pair_midside_rms(
    input_file: str,
    stream_index: int,
    duration: int,
    l0: int,
    r0: int
) -> Tuple[float, float]:
    filt = (
        f"[0:{stream_index}]asplit=2[a][b];"
        f"[a]pan=mono|c0=0.5*c{l0}+0.5*c{r0}[mid];"
        f"[b]pan=mono|c0=0.5*c{l0}-0.5*c{r0}[side];"
        f"[mid][side]amerge=inputs=2,"
        f"aformat=sample_fmts=fltp,"
        f"astats=metadata=1:reset=1:measure_perchannel=RMS_level"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-v", "info",
        "-i", input_file,
        "-t", str(duration),
        "-filter_complex", filt,
        "-f", "null", "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, stderr = proc.communicate()
    stats = parse_astats(stderr)
    mid_rms = stats.get(1, {}).get("rms", float("-inf"))
    side_rms = stats.get(2, {}).get("rms", float("-inf"))
    return mid_rms, side_rms


def analyze_pair(
    global_ch_l: int,
    global_ch_r: int,
    labels: Dict[int, str],
    raw_stats_global: Dict[int, Dict[str, float]],
    mid_rms: float,
    side_rms: float,
    debug: bool = False
) -> Tuple[str, str, List[str]]:
    flags: List[str] = []

    # Only analyze pairs where both are currently Mono (and not None/Timecode/etc.)
    if labels.get(global_ch_l) != "Mono" or labels.get(global_ch_r) != "Mono":
        return labels.get(global_ch_l, "Mono"), labels.get(global_ch_r, "Mono"), flags

    rms_l = raw_stats_global.get(global_ch_l, {}).get("rms", float("-inf"))
    rms_r = raw_stats_global.get(global_ch_r, {}).get("rms", float("-inf"))
    peak_l = raw_stats_global.get(global_ch_l, {}).get("peak", float("-inf"))
    peak_r = raw_stats_global.get(global_ch_r, {}).get("peak", float("-inf"))

    width_db = float("-inf")
    if mid_rms != float("-inf") and side_rms != float("-inf"):
        width_db = side_rms - mid_rms

    vol_diff_db = 0.0
    if rms_l != float("-inf") and rms_r != float("-inf"):
        vol_diff_db = abs(rms_l - rms_r)

    corr = calculate_correlation_estimate(mid_rms, side_rms)

    if debug:
        print(f"  [PAIR DEBUG] Ch{global_ch_l}/Ch{global_ch_r}:")
        print(f"    L: RMS={rms_l:.1f}, Peak={peak_l:.1f}")
        print(f"    R: RMS={rms_r:.1f}, Peak={peak_r:.1f}")
        mr = f"{mid_rms:.1f}" if mid_rms > -200 else "-inf"
        sr = f"{side_rms:.1f}" if side_rms > -200 else "-inf"
        wd = f"{width_db:.1f}" if width_db > -200 else "-inf"
        print(f"    Mid={mr}  Side={sr}  Width={wd}  VolDiff={vol_diff_db:.1f}  Corr={corr:.3f}")

    # Polarity-inverted dual mono (mid=-inf, side has energy)
    if mid_rms == float("-inf") and side_rms != float("-inf"):
        flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: Polarity-inverted dual mono (Mid=-inf)")
        return "Mono", "Mono", flags

    # --- Strong evidence rules ---

    # 1) Clear dual mono: Side far below Mid AND channels level-match reasonably
    if width_db != float("-inf"):
        if width_db <= DUAL_MONO_MAX_WIDTH_DB and vol_diff_db <= VOLUME_MATCH_DB:
            # Optional extra confidence: corr should also be high-ish
            if corr >= 0.70:
                return "Mono", "Mono", flags
            # Even if corr isn't super high, very weak side + level match is usually dual-mono
            flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: Weak side (width={width_db:.1f}dB) -> Dual mono")
            return "Mono", "Mono", flags

        # 2) Clear stereo: Side not much weaker than Mid
        if width_db >= STEREO_MIN_WIDTH_DB:
            # This includes center-heavy stereo (width around -1 to -2 dB)
            if corr < 0:
                flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: Anti-correlated/phasey stereo (corr={corr:.2f})")
            return "Stereo Left", "Stereo Right", flags

    # --- Borderline zone (between the above width thresholds, or missing width) ---
    # This is where your old logic over-called dual-mono.
    # We now require VERY strong correlation AND close level match to call dual-mono.
    if corr >= CORRELATION_DUAL_MONO_MIN and vol_diff_db <= VOLUME_MATCH_DB:
        flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: High corr ({corr:.2f}) + level match -> Dual mono")
        return "Mono", "Mono", flags

    # If correlation is low, treat as stereo.
    if corr <= CORRELATION_STEREO_MAX:
        flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: Low corr ({corr:.2f}) -> Stereo")
        return "Stereo Left", "Stereo Right", flags

    # Large level difference often means stereo or at least non-identical channels
    if vol_diff_db > VOLUME_DIFFERENT_DB:
        flags.append(f"Ch{global_ch_l}/Ch{global_ch_r}: Level mismatch ({vol_diff_db:.1f}dB) -> Stereo")
        return "Stereo Left", "Stereo Right", flags

    # Final fallback: default to stereo to avoid the common failure mode (stereo miscalled as mono)
    flags.append(
        f"Ch{global_ch_l}/Ch{global_ch_r}: Borderline (width={width_db if width_db!=-float('inf') else float('nan'):.1f}dB, corr={corr:.2f}), defaulting to Stereo"
    )
    return "Stereo Left", "Stereo Right", flags


def analyze_file_per_stream(input_file: str, duration: int, debug: bool = False, enable_ltc: bool = True) -> Dict:
    streams = ffprobe_audio_streams(input_file)
    if not streams:
        return {"result": "No Audio Channels", "status": "Error", "flags": [], "stats": {}, "streams": []}

    global_ch = 1
    stream_to_global_base: Dict[int, int] = {}
    total_global_channels = 0
    for s in streams:
        if s["channels"] > 0:
            stream_to_global_base[s["index"]] = global_ch
            global_ch += s["channels"]
            total_global_channels += s["channels"]

    if total_global_channels == 0:
        return {"result": "No Audio Channels", "status": "Error", "flags": [], "stats": {}, "streams": streams}

    if debug:
        print(f"[DEBUG] Processing {input_file}")
        print(f"[DEBUG] Audio streams: {len(streams)}, total channels: {total_global_channels}")

    labels: Dict[int, str] = {}
    global_stats: Dict[int, Dict[str, float]] = {}
    flags: List[str] = []

    # Pass 1: RAW channel stats + initial None/Mono labels
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 0:
            continue
        base = stream_to_global_base[stream_index]

        raw_stats = get_raw_channel_stats_for_stream(input_file, stream_index, duration)
        for local_ch in range(1, n_ch + 1):
            gch = base + (local_ch - 1)
            rms = raw_stats.get(local_ch, {}).get("rms", float("-inf"))
            peak = raw_stats.get(local_ch, {}).get("peak", float("-inf"))
            global_stats[gch] = {"rms": rms, "peak": peak}
            labels[gch] = classify_silence_or_mono(rms, peak)

        # LTC detection
        if enable_ltc:
            ltc_probe = min(duration, LTC_PROBE_DURATION_DEFAULT)
            for local_ch in range(1, n_ch + 1):
                gch = base + (local_ch - 1)
                if labels.get(gch) == "None":
                    continue
                is_ltc, best_fps, best_ratio, _seq = detect_ltc_in_channel(
                    input_file=input_file,
                    stream_index=stream_index,
                    channel_1based=local_ch,
                    probe_duration=ltc_probe,
                    debug=debug
                )
                if is_ltc:
                    labels[gch] = "Timecode"
                    if debug:
                        flags.append(f"Ch{gch}: LTC detected (fps={best_fps}, score={best_ratio:.2f})")

    # Pass 2: Per-stream pair analysis (only within each stream)
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 1:
            continue
        base = stream_to_global_base[stream_index]
        n_pairs = n_ch // 2

        for p in range(n_pairs):
            local_l = (p * 2) + 1
            local_r = (p * 2) + 2
            g_l = base + (local_l - 1)
            g_r = base + (local_r - 1)

            if labels.get(g_l) != "Mono" or labels.get(g_r) != "Mono":
                continue

            mid_rms, side_rms = get_pair_midside_rms(
                input_file=input_file,
                stream_index=stream_index,
                duration=duration,
                l0=local_l - 1,
                r0=local_r - 1
            )

            label_l, label_r, pair_flags = analyze_pair(
                global_ch_l=g_l,
                global_ch_r=g_r,
                labels=labels,
                raw_stats_global=global_stats,
                mid_rms=mid_rms,
                side_rms=side_rms,
                debug=debug
            )
            labels[g_l] = label_l
            labels[g_r] = label_r
            flags.extend(pair_flags)

    parts = [f"Ch{i}: {labels.get(i, 'None')}" for i in range(1, total_global_channels + 1)]
    result = "; ".join(parts)
    status = "Exact Match" if result in KNOWN_CONFIGS else "New Configuration"

    return {
        "result": result,
        "status": status,
        "flags": flags,
        "stats": global_stats,
        "streams": streams
    }


def main():
    parser = argparse.ArgumentParser(
        description="Per-Stream Audio Configuration Classifier (Updated dual-mono/stereo logic)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-d", "--duration", type=int, default=240, help="Scan duration (default: 240)")
    parser.add_argument("--debug", action="store_true", help="Show debug output")
    parser.add_argument("--show-stats", action="store_true", help="Show RMS/Peak values")
    parser.add_argument("--no-ltc", action="store_true", help="Disable LTC detection")
    args = parser.parse_args()

    enable_ltc = not args.no_ltc

    files_to_process: List[str] = []
    if os.path.isfile(args.input):
        files_to_process.append(args.input)
    elif os.path.isdir(args.input):
        print(f"Scanning directory: {args.input}")
        for root, _dirs, files in os.walk(args.input):
            for file in files:
                if file.startswith("."):
                    continue
                if file.lower().endswith(('.mov', '.mkv', '.mp4', '.mxf', '.avi', '.wav')):
                    files_to_process.append(os.path.join(root, file))

    if not files_to_process:
        print("No media files found.")
        sys.exit(0)

    files_to_process.sort()
    print(f"Found {len(files_to_process)} file(s) to process.\n")

    summary_stats = {"Exact Match": 0, "New Configuration": 0, "Error": 0}
    config_counts = Counter()

    for i, fpath in enumerate(files_to_process, 1):
        filename = os.path.basename(fpath)
        print(f"[{i}/{len(files_to_process)}] {filename}")

        data = analyze_file_per_stream(fpath, args.duration, debug=args.debug, enable_ltc=enable_ltc)

        if data["status"] == "Exact Match":
            summary_stats["Exact Match"] += 1
        elif data["status"] == "Error":
            summary_stats["Error"] += 1
        else:
            summary_stats["New Configuration"] += 1

        config_counts[data["result"]] += 1

        if args.debug and data.get("streams"):
            stream_desc = ", ".join(
                f"#{s['index']}({s['codec_name']},{s['channels']}ch)"
                for s in data["streams"] if s.get("channels", 0) > 0
            )
            print(f"  Streams: {stream_desc}")

        print(f"  Result: {data['result']}")
        if data["status"] != "Exact Match":
            print(f"  Status: {data['status']}")

        for flag in data.get("flags", []):
            print(f"  ⚠️  {flag}")

        if args.show_stats and data.get("stats"):
            print("  Channel Stats (dBFS):")
            for ch in sorted(data["stats"].keys()):
                rms = data["stats"][ch].get("rms", float("-inf"))
                peak = data["stats"][ch].get("peak", float("-inf"))
                rms_str = f"{rms:.1f}" if rms > -200 else "-inf"
                peak_str = f"{peak:.1f}" if peak > -200 else "-inf"
                print(f"    Ch{ch}: RMS={rms_str:>6s}  Peak={peak_str:>6s}")

        print("-" * 70)

    print("\n" + "=" * 70)
    print("BATCH ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Total Files Processed: {len(files_to_process)}")
    print(f"  ✓ Exact Matches:      {summary_stats['Exact Match']}")
    print(f"  ⚠ New Configurations: {summary_stats['New Configuration']}")
    print(f"  ✗ Errors:             {summary_stats['Error']}")
    print("-" * 70)
    print("Configuration Frequency (most common first):")
    print("-" * 70)
    for config, count in config_counts.most_common():
        pct = (count / len(files_to_process)) * 100
        print(f"  [{count:3d}] ({pct:5.1f}%)  {config}")
    print("=" * 70)


if __name__ == "__main__":
    main()
