#!/usr/bin/env python3
"""
Audio channel configuration classifier (Batch Capable + Sorted + Stats + Freq Report)
Updates:
 - ADJUSTED: STEREO_WIDTH_MIN_DB raised to -10.0 (Conservative Stereo)
 - NEW: Detects Phase Inverted Mono (where Side > Mid) and classifies as Mono
 - Default duration = 240s
 - Robust 'asplit' logic
"""

import argparse
import subprocess
import json
import sys
import re
import math
import os
from typing import Dict, Tuple, List
from collections import Counter

# -------------------------
# Configuration
# -------------------------

SILENCE_THRESH_DB = -60.0
LTC_DR_THRESH_DB = 5.0
LTC_MIN_VOL_DB = -40.0

# --- Stereo vs Dual Mono Thresholds ---
# width_db = Side_RMS - Mid_RMS
#
# Previous value was -20.0 (Too sensitive, caught tape noise as Stereo)
# New value is -10.0.
# If the "Difference" is 12dB quieter than the "Sum", we now call it Mono.
STEREO_WIDTH_MIN_DB = -10.0     

# If Side is louder than Mid (Width > 0), it's likely Phase Inversion.
# If volumes are similar, we force this to Mono (Phase Inverted).
PHASE_INVERSION_WIDTH_DB = 0.0

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

def probe_file(input_file: str) -> Tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index,channels",
        "-of", "json",
        input_file
    ]
    try:
        output = subprocess.check_output(cmd, text=True)
        data = json.loads(output)
        streams = data.get("streams", [])
        total_channels = sum(int(s.get("channels", 0) or 0) for s in streams)
        return len(streams), total_channels
    except Exception as e:
        return 0, 0

def build_filter_graph(num_streams: int, total_channels: int) -> Tuple[str, int, int]:
    if total_channels <= 0:
        return "", 0, 0

    if num_streams > 1:
        inputs = "".join([f"[0:a:{i}]" for i in range(num_streams)])
        graph = f"{inputs}amerge=inputs={num_streams}[a0];"
        source_label = "[a0]"
    else:
        graph = ""
        source_label = "[0:a]"

    n_raw = total_channels
    n_pairs = total_channels // 2
    
    consumers = 1 + (2 * n_pairs)
    split_labels = [f"[src_copy{i}]" for i in range(consumers)]
    graph += f"{source_label}asplit={consumers}" + "".join(split_labels) + ";"
    
    raw_source = split_labels[0]
    mid_sources = split_labels[1::2]
    side_sources = split_labels[2::2]

    midside_labels: List[str] = []

    for p in range(n_pairs):
        l = p * 2
        r = p * 2 + 1
        mid_label = f"[mid{p}]"
        side_label = f"[side{p}]"
        
        src_mid = mid_sources[p]
        src_side = side_sources[p]

        graph += f"{src_mid}pan=mono|c0=0.5*c{l}+0.5*c{r}{mid_label};"
        graph += f"{src_side}pan=mono|c0=0.5*c{l}-0.5*c{r}{side_label};"
        midside_labels.extend([mid_label, side_label])

    merge_inputs = [raw_source] + midside_labels
    merge_n = len(merge_inputs)
    out_total = n_raw + (2 * n_pairs)

    graph += (
        f"{''.join(merge_inputs)}"
        f"amerge=inputs={merge_n},"
        f"aformat=sample_fmts=fltp,"
        f"astats=metadata=1:reset=1"
    )

    return graph, n_raw, out_total

def _safe_float(s: str) -> float:
    try:
        v = float(s)
        if math.isnan(v) or math.isinf(v):
            return float("-inf")
        return v
    except Exception:
        return float("-inf")

def parse_astats(stderr: str) -> Dict[int, Dict[str, float]]:
    stats: Dict[int, Dict[str, float]] = {}
    current_channel = None
    ch_re = re.compile(r"Channel:\s*(\d+)", re.I)
    rms_re = re.compile(r"RMS level(?: dB)?:\s*([^\s]+)", re.I)
    peak_re = re.compile(r"Peak level(?: dB)?:\s*([^\s]+)", re.I)

    for line in stderr.splitlines():
        m = ch_re.search(line)
        if m:
            current_channel = int(m.group(1))
            stats.setdefault(current_channel, {})
            continue
        if not current_channel:
            continue
        m = rms_re.search(line)
        if m:
            stats[current_channel]["rms"] = _safe_float(m.group(1))
            continue
        m = peak_re.search(line)
        if m:
            stats[current_channel]["peak"] = _safe_float(m.group(1))
            continue
    return stats

def classify_raw_channel(rms_db: float, peak_db: float) -> str:
    if rms_db == float("-inf") or rms_db <= SILENCE_THRESH_DB:
        return "None"
    if peak_db == float("-inf"):
        return "Mono"
    dr = abs(peak_db - rms_db)
    if (dr < LTC_DR_THRESH_DB) and (rms_db > LTC_MIN_VOL_DB):
        return "Timecode"
    return "Mono"

def analyze_pairs_with_midside(labels: Dict[int, str], stats: Dict[int, Dict[str, float]], n_raw: int, debug: bool = False) -> Tuple[Dict[int, str], List[str]]:
    flags: List[str] = []
    n_pairs = n_raw // 2

    for p in range(n_pairs):
        ch_l = p * 2 + 1
        ch_r = p * 2 + 2

        if labels.get(ch_l) != "Mono" or labels.get(ch_r) != "Mono":
            continue

        mid_idx = n_raw + 1 + 2 * p
        side_idx = n_raw + 2 + 2 * p
        
        if mid_idx not in stats or side_idx not in stats:
             if debug: print(f"[DEBUG] Pair {ch_l}/{ch_r}: Stats missing. Keep Mono/Mono.")
             continue

        mid_rms = stats.get(mid_idx, {}).get("rms", float("-inf"))
        side_rms = stats.get(side_idx, {}).get("rms", float("-inf"))

        if mid_rms == float("-inf") and side_rms == float("-inf"):
            continue

        width_db = 0.0 if mid_rms == float("-inf") else (side_rms - mid_rms)

        # --- LOGIC UPDATE V6 ---
        
        # 1. Check for Phase Inversion (Side > Mid)
        if width_db > PHASE_INVERSION_WIDTH_DB:
            # If Side is louder than Mid, it's out of phase.
            # If the source volumes are similar, this is Dual Mono Phase Inverted.
            rms_l = stats.get(ch_l, {}).get("rms", -99)
            rms_r = stats.get(ch_r, {}).get("rms", -99)
            vol_diff = abs(rms_l - rms_r)
            
            if vol_diff < 3.0: # If L/R volume is close
                if debug: print(f"[DEBUG] Pair {ch_l}/{ch_r}: Phase Inverted Mono (Width={width_db:.1f}dB). Labeling Mono.")
                flags.append(f"Pair {ch_l}/{ch_r}: Phase Inversion Detected (Side > Mid). Treated as Mono.")
                # We LEAVE them as "Mono" (Default)
                continue
            else:
                flags.append(f"Pair {ch_l}/{ch_r}: High Stereo Width (Out of Phase?)")

        # 2. Check for Stereo Separation
        if width_db < STEREO_WIDTH_MIN_DB:
            # Side signal is too quiet relative to Mid. Treat as Dual Mono.
            if debug: print(f"[DEBUG] Pair {ch_l}/{ch_r}: Narrow width ({width_db:.1f} dB). Keep Mono/Mono.")
            continue

        # 3. If we pass both checks, it's Stereo
        labels[ch_l] = "Stereo Left"
        labels[ch_r] = "Stereo Right"
        
    return labels, flags

def analyze_file(input_file: str, duration: int, debug: bool = False) -> Dict:
    n_streams, n_channels = probe_file(input_file)
    if n_channels <= 0:
        return {"result": "No Audio Channels", "status": "Error", "flags": [], "stats": {}}

    graph, n_raw, n_total = build_filter_graph(n_streams, n_channels)
    
    cmd = [
        "ffmpeg", "-hide_banner", "-v", "info", "-i", input_file,
        "-t", str(duration), "-filter_complex", graph, "-f", "null", "-"
    ]
    
    if debug: print(f"[DEBUG] Processing {input_file}...")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, stderr = proc.communicate()
    stats = parse_astats(stderr)

    labels = {}
    for ch in range(1, n_raw + 1):
        rms = stats.get(ch, {}).get("rms", float("-inf"))
        peak = stats.get(ch, {}).get("peak", float("-inf"))
        labels[ch] = classify_raw_channel(rms, peak)

    labels, flags = analyze_pairs_with_midside(labels, stats, n_raw, debug=debug)
    
    parts = [f"Ch{i}: {labels.get(i, 'None')}" for i in range(1, n_raw + 1)]
    generated = "; ".join(parts)
    status = "Exact Match" if generated in KNOWN_CONFIGS else "New Configuration"

    return {"result": generated, "status": status, "flags": flags, "stats": stats}

# -------------------------
# Main
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch Audio Classifier")
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-d", "--duration", type=int, default=240, help="Scan duration (s)")
    parser.add_argument("--debug", action="store_true", help="Show debug info")
    parser.add_argument("--show-stats", action="store_true", help="Show RMS/Peak values in report")
    args = parser.parse_args()

    files_to_process = []
    if os.path.isfile(args.input):
        files_to_process.append(args.input)
    elif os.path.isdir(args.input):
        print(f"Scanning directory: {args.input}")
        for root, dirs, files in os.walk(args.input):
            for file in files:
                if file.startswith("._") or file.startswith("."):
                    continue
                if file.lower().endswith(('.mov', '.mkv', '.mp4', '.mxf', '.avi', '.wav')):
                    files_to_process.append(os.path.join(root, file))
    
    if not files_to_process:
        print("No media files found.")
        sys.exit(0)

    files_to_process.sort()
    print(f"Found {len(files_to_process)} files to process.\n")

    summary_stats = {"Exact Match": 0, "New Configuration": 0, "Error": 0}
    config_counts = Counter() 

    for i, fpath in enumerate(files_to_process, 1):
        filename = os.path.basename(fpath)
        print(f"[{i}/{len(files_to_process)}] Analyzing: {filename}")
        
        data = analyze_file(fpath, args.duration, args.debug)
        
        if data['status'] == "Exact Match":
            summary_stats["Exact Match"] += 1
        elif data['status'] == "Error":
            summary_stats["Error"] += 1
        else:
            summary_stats["New Configuration"] += 1
            
        config_counts[data['result']] += 1

        print(f"  Result: {data['result']}")
        if data['status'] != "Exact Match":
             print(f"  Status: {data['status']}") 
        if data['flags']:
            for flag in data['flags']:
                print(f"  NOTE: {flag}")

        if args.show_stats and data['stats']:
            print("  Stats (dBFS):")
            for ch in sorted(data['stats'].keys()):
                rms = data['stats'][ch].get("rms", float("-inf"))
                peak = data['stats'][ch].get("peak", float("-inf"))
                rms_str = f"{rms:.1f}" if rms > -200 else "-inf"
                peak_str = f"{peak:.1f}" if peak > -200 else "-inf"
                print(f"    Ch{ch}: RMS={rms_str} Peak={peak_str}")

        print("-" * 50)
        
    print("\nBatch Complete.")
    print(f"Total Files: {len(files_to_process)}")
    print(f"Exact Matches: {summary_stats['Exact Match']}")
    print(f"New Configs:   {summary_stats['New Configuration']}")
    print(f"Errors:        {summary_stats['Error']}")
    print("-" * 50)
    print("Configuration Frequency:")
    for config, count in config_counts.most_common():
        print(f"[{count}] {config}")
    print("-" * 50)

if __name__ == "__main__":
    main()