#!/usr/bin/env python3
"""
Per-Stream / Per-Channel Audio Configuration Classifier (NumPy + ltcdump) - Late Audio Aware
WITH: lag-aligned pair metrics + 2-window confirmation for dual-mono
WITH: Total Audio Track Count (including silent channels)

What it does:
- Finds audio streams/channels with ffprobe
- Searches for a non-silent analysis window even if audio starts late (0s, +step, +2*step...)
- Labels each channel: None / Timecode / Mono / Stereo Left / Stereo Right
- Uses ltcdump for LTC detection
- Uses NumPy waveform similarity for dual-mono vs stereo:
    - estimate lag, align signals, then compute corr + best-fit residual
    - only calls Dual Mono if it passes in TWO windows (early + later) when possible
- Reports Total Audio Tracks (container channel count)

Requires: ffmpeg, ffprobe, ltcdump (ltc-tools), numpy

Usage:
  python3 classify_audio_refactored.py -i <input_file_or_dir>
"""

import argparse
import subprocess
import json
import sys
import re
import math
import os
import shutil
import logging
import jaydebeapi
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Any
from collections import Counter

import numpy as np

# -------------------------
# Configuration
# -------------------------

# Logging setup will be done in main()
logger = logging.getLogger(__name__)

# FileMaker Config (Environment Variables)
DB_SERVER_IP = os.getenv('FM_SERVER')
DB_DEV_IP = os.getenv('FM_DEV_SERVER')
DB_NAME = os.getenv('AMI_DATABASE')
DB_USER = os.getenv('AMI_DATABASE_USERNAME')
DB_PASS = os.getenv('AMI_DATABASE_PASSWORD')
JDBC_PATH = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

SILENCE_THRESH_DB = -60.0

# LTC detection
LTC_PROBE_DURATION_DEFAULT = 240
LTC_MATCH_THRESHOLD = 6
LTC_MIN_UNIQUE = 4
LTC_MIN_MONOTONIC_RATIO = 0.6
LTC_FPS_CANDIDATES = (24, 25, 30)

# Waveform thresholds
DUAL_MONO_CORR_MIN = 0.97
DUAL_MONO_RESID_MAX = 0.15
DUAL_MONO_LAG_MAX_SAMPLES = 8

STEREO_CORR_MAX = 0.85
STEREO_RESID_MIN = 0.20

# Analysis decoding (numpy)
ANALYSIS_SAMPLE_RATE = 48000
DEFAULT_ANALYSIS_SECONDS = 300
DEFAULT_PAIR_SECONDS = 60

# Late-audio search defaults
DEFAULT_WINDOW_STEP_SECONDS = 180
DEFAULT_MAX_WINDOWS = 4

# Dual-mono confirmation settings
CONFIRM_OFFSET_SECONDS = 120
CONFIRM_MIN_SECONDS = 5

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
# Utilities
# -------------------------

def check_dependencies():
    """Ensure required external tools are available."""
    required_tools = ["ffmpeg", "ffprobe", "ltcdump"]
    missing = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing:
        logger.error(f"Missing required tools: {', '.join(missing)}")
        sys.exit(1)

def _dbfs_from_linear(x: float) -> float:
    if x <= 0.0 or not math.isfinite(x):
        return float("-inf")
    return 20.0 * math.log10(x)

def ffprobe_audio_streams(input_file: str) -> List[Dict[str, Any]]:
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
    except Exception as e:
        logger.error(f"ffprobe failed for {input_file}: {e}")
        return []

def classify_silence_or_mono(rms_db: float) -> str:
    if rms_db == float("-inf") or rms_db <= SILENCE_THRESH_DB:
        return "None"
    return "Mono"

# -------------------------
# NumPy decode + stats
# -------------------------

def decode_stream_pcm_f32le(
    input_file: str,
    stream_index: int,
    start: int,
    seconds: int,
    sample_rate: int = ANALYSIS_SAMPLE_RATE,
) -> Tuple[np.ndarray, int]:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
        "-ss", str(start),
        "-t", str(seconds),
        "-i", input_file,
        "-map", f"0:{stream_index}",
        "-vn",
        "-ar", str(sample_rate),
        "-acodec", "pcm_f32le",
        "-f", "f32le",
        "pipe:1"
    ]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH")

    if p.returncode != 0:
        if err:
            logger.debug(f"ffmpeg decode error: {err.decode('utf-8', errors='replace')}")
        raise RuntimeError(f"ffmpeg decode failed for stream {stream_index} at start={start}s")
    
    pcm = np.frombuffer(out, dtype=np.float32)
    return pcm, sample_rate

def reshape_interleaved(pcm: np.ndarray, channels: int) -> np.ndarray:
    n = (pcm.size // channels) * channels
    if n == 0:
        return np.zeros((0, channels), dtype=np.float32)
    return pcm[:n].reshape((-1, channels))

def compute_channel_stats_dbfs(samples: np.ndarray) -> Dict[int, Dict[str, float]]:
    stats: Dict[int, Dict[str, float]] = {}
    if samples.size == 0:
        return stats
    x = samples.astype(np.float64, copy=False)
    # Avoid mean of empty slice warning by checking size above
    rms = np.sqrt(np.mean(x * x, axis=0))
    peak = np.max(np.abs(x), axis=0)
    for i in range(samples.shape[1]):
        stats[i + 1] = {"rms": _dbfs_from_linear(float(rms[i])), "peak": _dbfs_from_linear(float(peak[i]))}
    return stats

def stream_has_any_signal(stats: Dict[int, Dict[str, float]]) -> bool:
    for _ch, st in stats.items():
        if st.get("rms", float("-inf")) > SILENCE_THRESH_DB:
            return True
    return False

# -------------------------
# Pair similarity / Dual-Mono Logic
# -------------------------

def rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))

def _safe_corrcoef(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 8 or b.size < 8:
        return 1.0
    sa = float(np.std(a))
    sb = float(np.std(b))
    if sa <= 1e-12 or sb <= 1e-12:
        return 1.0
    c = float(np.corrcoef(a, b)[0, 1])
    if not math.isfinite(c):
        return 1.0
    return max(-1.0, min(1.0, c))

def best_fit_gain(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.dot(a, a))
    if denom <= 1e-20:
        return 1.0
    return float(np.dot(b, a)) / denom

def estimate_lag_samples(a: np.ndarray, b: np.ndarray, max_lag: int = 2000) -> int:
    if a.size < 2048 or b.size < 2048:
        return 0

    step = max(1, a.size // 50000)
    aa = a[::step].astype(np.float64, copy=False)
    bb = b[::step].astype(np.float64, copy=False)

    aa = aa - np.mean(aa)
    bb = bb - np.mean(bb)

    max_lag_ds = max(1, max_lag // step)
    if max_lag_ds >= aa.size - 1:
        max_lag_ds = max(1, aa.size // 4)

    corr = np.correlate(bb, aa, mode="full")
    mid = corr.size // 2

    lo = max(0, mid - max_lag_ds)
    hi = min(corr.size, mid + max_lag_ds + 1)
    window = corr[lo:hi]
    idx = int(np.argmax(window))
    lag_ds = (lo + idx) - mid

    return int(lag_ds * step)

def align_by_lag(a: np.ndarray, b: np.ndarray, lag: int) -> Tuple[np.ndarray, np.ndarray]:
    if lag == 0:
        n = min(a.size, b.size)
        return a[:n], b[:n]

    if lag > 0:
        if lag >= b.size:
            return a[:0], b[:0]
        b2 = b[lag:]
        n = min(a.size, b2.size)
        return a[:n], b2[:n]
    else:
        lag2 = -lag
        if lag2 >= a.size:
            return a[:0], b[:0]
        a2 = a[lag2:]
        n = min(a2.size, b.size)
        return a2[:n], b[:n]

def pair_metrics_aligned(L: np.ndarray, R: np.ndarray, lag: int) -> Dict[str, float]:
    a, b = align_by_lag(L, R, lag)
    if a.size == 0 or b.size == 0:
        return {"corr": 1.0, "gain": 1.0, "resid_ratio": 0.0}

    l = a.astype(np.float64, copy=False)
    r = b.astype(np.float64, copy=False)

    l = l - np.mean(l)
    r = r - np.mean(r)

    corr = _safe_corrcoef(l, r)
    gain = best_fit_gain(l, r)
    resid = r - (gain * l)

    r_rms = rms(r)
    resid_rms = rms(resid)
    resid_ratio = (resid_rms / r_rms) if r_rms > 1e-12 else 0.0

    return {"corr": float(corr), "gain": float(gain), "resid_ratio": float(resid_ratio)}

def dual_mono_pass(metrics: Dict[str, float], lag: int) -> Tuple[bool, List[str]]:
    flags: List[str] = []
    corr = metrics["corr"]
    resid_ratio = metrics["resid_ratio"]

    if abs(corr) >= DUAL_MONO_CORR_MIN and resid_ratio <= DUAL_MONO_RESID_MAX and abs(lag) <= DUAL_MONO_LAG_MAX_SAMPLES:
        if corr < 0:
            flags.append(f"Polarity-inverted dual mono (corr={corr:.3f}, resid={resid_ratio:.3f}, lag={lag})")
        return True, flags
    return False, flags

def analyze_pair_waveform(
    L1: np.ndarray,
    R1: np.ndarray,
    *,
    L2: Optional[np.ndarray] = None,
    R2: Optional[np.ndarray] = None,
) -> Tuple[str, str, Dict[str, float], List[str]]:
    """
    Dual mono vs stereo with:
      - lag estimate + alignment before computing metrics
      - 2-window confirmation: only call dual-mono if it passes in window1 and window2 (when provided)
    """
    flags: List[str] = []

    # Window 1
    lag1 = estimate_lag_samples(L1, R1, max_lag=2000)
    m1 = pair_metrics_aligned(L1, R1, lag1)
    dm1, dm_flags1 = dual_mono_pass(m1, lag1)

    # Window 2 (optional)
    lag2 = None
    m2 = None
    dm2 = None
    
    if L2 is not None and R2 is not None and L2.size > 0 and R2.size > 0:
        lag2 = estimate_lag_samples(L2, R2, max_lag=2000)
        m2 = pair_metrics_aligned(L2, R2, lag2)
        dm2, dm_flags2 = dual_mono_pass(m2, lag2)
    else:
        dm_flags2 = []

    # Dual-mono requires window1 AND (if present) window2
    if dm1:
        if dm2 is None:
            flags.extend(dm_flags1)
            metrics_out = {"corr": m1["corr"], "gain": m1["gain"], "resid_ratio": m1["resid_ratio"], "lag": float(lag1)}
            return "Mono", "Mono", metrics_out, flags

        if dm2:
            flags.extend(dm_flags1)
            flags.extend(dm_flags2)
            metrics_out = {
                "corr": m1["corr"], "gain": m1["gain"], "resid_ratio": m1["resid_ratio"], "lag": float(lag1),
                "corr2": m2["corr"], "gain2": m2["gain"], "resid_ratio2": m2["resid_ratio"], "lag2": float(lag2),
            }
            return "Mono", "Mono", metrics_out, flags

        # Contradiction
        flags.append(
            f"Window1 looked dual-mono but Window2 did not "
            f"(w1 corr={m1['corr']:.3f} resid={m1['resid_ratio']:.3f} lag={lag1}; "
            f"w2 corr={m2['corr']:.3f} resid={m2['resid_ratio']:.3f} lag={lag2})"
        )

    # Stereo decisions based on window1 (aligned) metrics
    metrics_out = {"corr": m1["corr"], "gain": m1["gain"], "resid_ratio": m1["resid_ratio"], "lag": float(lag1)}
    
    if abs(m1["corr"]) <= STEREO_CORR_MAX or m1["resid_ratio"] >= STEREO_RESID_MIN:
        if abs(m1["corr"]) > 0.90:
            flags.append(f"Highly correlated stereo (corr={m1['corr']:.3f}, resid={m1['resid_ratio']:.3f}, lag={lag1})")
        return "Stereo Left", "Stereo Right", metrics_out, flags

    # Borderline: default stereo (conservative)
    flags.append(f"Borderline -> Stereo (corr={m1['corr']:.3f}, resid={m1['resid_ratio']:.3f}, lag={lag1})")
    return "Stereo Left", "Stereo Right", metrics_out, flags

# -------------------------
# LTC detection (ltcdump)
# -------------------------

def detect_ltc_in_channel(
    input_file: str,
    stream_index: int,
    channel_1based: int,
    probe_duration: int,
    start: int = 0,
    match_threshold: int = LTC_MATCH_THRESHOLD,
    min_unique: int = LTC_MIN_UNIQUE,
    min_monotonic_ratio: float = LTC_MIN_MONOTONIC_RATIO,
    fps_candidates: Tuple[int, ...] = LTC_FPS_CANDIDATES
) -> Tuple[bool, Optional[int], float, List[Tuple[int, int, int, int]]]:
    ch0 = channel_1based - 1
    pan_filter = f"pan=mono|c0=c{ch0}"

    ffmpeg_command = [
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
        "-ss", str(start),
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
        if ffmpeg_proc.stdout:
            ffmpeg_proc.stdout.close()
        ltcdump_out, _ = ltcdump_proc.communicate()
        ffmpeg_proc.wait()
    except Exception as e:
        logger.debug(f"[LTC] Exception for {input_file} s{stream_index} ch{channel_1based}: {e}")
        return False, None, 0.0, []

    tc_pat = re.compile(r'(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.:;](?P<f>\d{2})')
    raw = [(int(m.group('h')), int(m.group('m')), int(m.group('s')), int(m.group('f')))
           for m in tc_pat.finditer(ltcdump_out)]

    if not raw:
        return False, None, 0.0, []

    def to_frames(h, m, s, f, fps):
        return (((h * 60) + m) * 60 + s) * fps + f

    # Deduplicate preserving order
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

# -------------------------
# Analysis Helpers
# -------------------------

def find_active_window(
    input_file: str,
    stream_index: int,
    channels: int,
    analysis_seconds: int,
    window_step_seconds: int,
    max_windows: int,
    max_offset_seconds: int
) -> Tuple[Optional[np.ndarray], Optional[Dict[str, Any]], int, List[str]]:
    """
    Search for a window of audio that is not silent.
    Returns (samples, stats, start_time, logs).
    """
    logs = []
    for w in range(max_windows):
        start = w * window_step_seconds
        if start > max_offset_seconds:
            break
        try:
            pcm, rate = decode_stream_pcm_f32le(
                input_file=input_file,
                stream_index=stream_index,
                start=start,
                seconds=analysis_seconds
            )
            samples = reshape_interleaved(pcm, channels)
            stats = compute_channel_stats_dbfs(samples)
            
            if stream_has_any_signal(stats):
                return samples, stats, start, logs
            
            logs.append(f"Stream {stream_index}: window at {start}s appears silent, skipping.")
        except Exception as e:
            logs.append(f"Stream {stream_index}: decode failed at {start}s ({e})")
            continue

    return None, None, 0, logs

def process_stream_ltc(
    input_file: str,
    stream_index: int,
    base_channel: int,
    local_channels: int,
    start_time: int,
    ltc_duration: int,
    labels: Dict[int, str]
) -> List[str]:
    """
    Check for LTC in channels that are not 'None'.
    Updates 'labels' in place.
    """
    logs = []
    probe = min(ltc_duration, LTC_PROBE_DURATION_DEFAULT)
    for local_ch in range(1, local_channels + 1):
        gch = base_channel + (local_ch - 1)
        if labels.get(gch) == "None":
            continue
        
        is_ltc, best_fps, best_ratio, _ = detect_ltc_in_channel(
            input_file=input_file,
            stream_index=stream_index,
            channel_1based=local_ch,
            probe_duration=probe,
            start=start_time
        )
        if is_ltc:
            labels[gch] = "Timecode"
            logs.append(f"Ch{gch}: LTC detected (fps={best_fps}, score={best_ratio:.2f})")
            
    return logs

def process_stream_pairs(
    stream_index: int,
    base_channel: int,
    channels: int,
    samples: np.ndarray,
    labels: Dict[int, str],
    pair_seconds: int
) -> List[str]:
    """
    Analyze stereo pairs for Mono vs Stereo.
    Updates 'labels' in place.
    """
    logs = []
    if channels <= 1 or samples is None or samples.size == 0:
        return logs

    sr = ANALYSIS_SAMPLE_RATE
    pair_frames = int(pair_seconds * sr)
    max_frames_early = min(samples.shape[0], pair_frames)
    early_win = samples[:max_frames_early, :]

    # Confirmation window
    late_start = int(CONFIRM_OFFSET_SECONDS * sr)
    late_end = min(samples.shape[0], late_start + pair_frames)
    have_late = (late_end - late_start) >= int(CONFIRM_MIN_SECONDS * sr)
    late_win = samples[late_start:late_end, :] if have_late else None

    n_pairs = channels // 2
    for p in range(n_pairs):
        local_l = (p * 2) + 1
        local_r = (p * 2) + 2
        g_l = base_channel + (local_l - 1)
        g_r = base_channel + (local_r - 1)

        # Only check if both are currently Mono
        if labels.get(g_l) != "Mono" or labels.get(g_r) != "Mono":
            continue

        L1 = early_win[:, local_l - 1]
        R1 = early_win[:, local_r - 1]
        L2 = late_win[:, local_l - 1] if late_win is not None else None
        R2 = late_win[:, local_r - 1] if late_win is not None else None

        lab_l, lab_r, m, pair_flags = analyze_pair_waveform(L1, R1, L2=L2, R2=R2)
        labels[g_l] = lab_l
        labels[g_r] = lab_r

        # Detailed pair logging
        corr_str = f"corr={m.get('corr',0.0):.3f}"
        if 'corr2' in m:
             corr_str += f", corr2={m.get('corr2',0.0):.3f}"
        logs.append(f"Ch{g_l}/Ch{g_r} Pair Analysis: {corr_str}")
        for pf in pair_flags:
            logs.append(f"Ch{g_l}/Ch{g_r}: {pf}")

    return logs

def analyze_file_per_stream(
    input_file: str,
    ltc_duration: int,
    analysis_seconds: int,
    pair_seconds: int,
    max_offset_seconds: int,
    window_step_seconds: int,
    max_windows: int,
    enable_ltc: bool = True,
) -> Dict[str, Any]:
    streams = ffprobe_audio_streams(input_file)
    if not streams:
        return {"result": "No Audio Channels", "status": "Error", "flags": [], "stats": {}, "streams": []}

    # Map stream_index -> global_channel_start
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

    labels: Dict[int, str] = {}
    global_stats: Dict[int, Dict[str, float]] = {}
    flags: List[str] = []
    
    stream_waveforms: Dict[int, np.ndarray] = {}

    # 1. Decode & Initial Labeling (None vs Mono)
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 0:
            continue
        base = stream_to_global_base[stream_index]

        # A. Find active window
        samples, stats, start_time, search_logs = find_active_window(
            input_file, stream_index, n_ch, analysis_seconds, 
            window_step_seconds, max_windows, max_offset_seconds
        )
        for log in search_logs:
            logger.debug(log)
        
        # B. Default to None if failed
        if samples is None:
            for local_ch in range(1, n_ch + 1):
                labels[base + local_ch - 1] = "None"
            continue
            
        stream_waveforms[stream_index] = samples
        
        # C. Initial RMS Check
        for local_ch in range(1, n_ch + 1):
            gch = base + (local_ch - 1)
            ch_stats = stats.get(local_ch, {})
            rms_val = ch_stats.get("rms", float("-inf"))
            global_stats[gch] = ch_stats
            labels[gch] = classify_silence_or_mono(rms_val)

        # D. LTC Detection
        if enable_ltc:
            ltc_logs = process_stream_ltc(
                input_file, stream_index, base, n_ch, 
                start_time, ltc_duration, labels
            )
            flags.extend(ltc_logs)

    # 2. Pair Analysis (Mono vs Stereo)
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 1:
            continue
        
        samples = stream_waveforms.get(stream_index)
        if samples is None:
            continue
            
        base = stream_to_global_base[stream_index]
        pair_logs = process_stream_pairs(
            stream_index, base, n_ch, samples, labels, pair_seconds
        )
        flags.extend(pair_logs)

    # 3. Final Result Generation
    parts = [f"Ch{i}: {labels.get(i, 'None')}" for i in range(1, total_global_channels + 1)]
    result = "; ".join(parts)
    status = "Exact Match" if result in KNOWN_CONFIGS else "New Configuration"

    return {
        "result": result,
        "status": status,
        "flags": flags,
        "stats": global_stats,
        "streams": streams,
        "track_count": total_global_channels
    }

# -------------------------
# Database Interaction
# -------------------------

def connect_to_database(use_dev=False):
    target_ip = DB_DEV_IP if use_dev else DB_SERVER_IP
    if not target_ip:
        logger.error("Database IP not set in environment variables.")
        return None
    
    url = f'jdbc:filemaker://{target_ip}/{DB_NAME}'
    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            url,
            [DB_USER, DB_PASS],
            JDBC_PATH
        )
        logger.info(f"Connected to FileMaker at {target_ip}")
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def update_record_safe(conn, filename, sound_field, track_count, dry_run=False):
    """
    Check if record exists, then update.
    Returns: 'Updated', 'Skipped', 'Missing', or 'Error'
    """
    if not conn:
        return 'Skipped'
        
    curs = conn.cursor()
    try:
        # Check existence
        curs.execute('SELECT COUNT(*) FROM tbl_metadata WHERE "asset.referenceFilename" = ?', [filename])
        count = curs.fetchone()[0]
        
        if count == 0:
            logger.warning(f"[DB] Record not found: {filename}")
            return 'Missing'
            
        if dry_run:
            logger.info(f"[DB] Dry Run: Would update {filename} -> {sound_field}, {track_count} tracks")
            return 'Skipped'
            
        # Update
        query = """
            UPDATE tbl_metadata 
            SET "source.audioRecording.audioSoundField" = ?,
                "source.audioRecording.numberOfAudioTracks" = ?
            WHERE "asset.referenceFilename" = ?
        """
        curs.execute(query, [sound_field, track_count, filename])
        logger.info(f"[DB] Updated {filename}")
        return 'Updated'
        
    except Exception as e:
        logger.error(f"[DB] Error updating {filename}: {e}")
        return 'Error'
    finally:
        curs.close()

# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audio Configuration Classifier (Refactored)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-d", "--duration", type=int, default=240, help="LTC probe duration & max offset")
    parser.add_argument("--analysis-seconds", type=int, default=DEFAULT_ANALYSIS_SECONDS)
    parser.add_argument("--pair-seconds", type=int, default=DEFAULT_PAIR_SECONDS)
    parser.add_argument("--window-step-seconds", type=int, default=DEFAULT_WINDOW_STEP_SECONDS)
    parser.add_argument("--max-windows", type=int, default=DEFAULT_MAX_WINDOWS)
    parser.add_argument("--max-offset-seconds", type=int, default=None)
    
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--show-stats", action="store_true", help="Show RMS/Peak values")
    parser.add_argument("--no-ltc", action="store_true", help="Disable LTC detection")
    
    # DB Flags
    parser.add_argument("--update", action="store_true", help="Perform actual DB updates")
    parser.add_argument("--dev-server", action="store_true", help="Use Dev Server")

    args = parser.parse_args()

    # Logging Setup
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(message)s' if not args.debug else '%(asctime)s [%(levelname)s] %(message)s',
    )

    check_dependencies()

    # DB Connection
    conn = connect_to_database(use_dev=args.dev_server)
    if not conn:
        logger.warning("Continuing in offline mode (Analysis Only).")

    # Arguments
    max_offset = args.max_offset_seconds if args.max_offset_seconds is not None else args.duration
    enable_ltc = not args.no_ltc

    # File Discovery
    files_to_process = []
    if os.path.isfile(args.input):
        files_to_process.append(args.input)
    elif os.path.isdir(args.input):
        logger.info(f"Scanning directory: {args.input}")
        for root, _, files in os.walk(args.input):
            for file in files:
                if not file.startswith(".") and file.lower().endswith(('.mov', '.mkv', '.mp4', '.mxf', '.avi', '.wav')):
                    files_to_process.append(os.path.join(root, file))

    if not files_to_process:
        logger.error("No media files found.")
        sys.exit(0)

    files_to_process.sort()
    logger.info(f"Found {len(files_to_process)} file(s) to process.\n")

    summary = Counter()
    db_stats = Counter()
    config_counts = Counter()

    for i, fpath in enumerate(files_to_process, 1):
        filename = os.path.basename(fpath)
        logger.info(f"[{i}/{len(files_to_process)}] {filename}")
        
        data = analyze_file_per_stream(
            input_file=fpath,
            ltc_duration=args.duration,
            analysis_seconds=args.analysis_seconds,
            pair_seconds=args.pair_seconds,
            max_offset_seconds=max_offset,
            window_step_seconds=args.window_step_seconds,
            max_windows=args.max_windows,
            enable_ltc=enable_ltc
        )
        
        summary[data["status"]] += 1
        config_counts[data["result"]] += 1
        
        logger.info(f"  Result: {data['result']}")
        logger.info(f"  Total Audio Tracks: {data.get('track_count', 0)}")
        if data["status"] != "Exact Match":
            logger.info(f"  Status: {data['status']}")
            
        for flag in data.get("flags", []):
            logger.info(f"  ⚠️  {flag}")
            
        if args.show_stats:
            logger.info("  Channel Stats (dBFS):")
            for ch in sorted(data["stats"].keys()):
                s = data["stats"][ch]
                logger.info(f"    Ch{ch}: RMS={s.get('rms', -inf):.1f}  Peak={s.get('peak', -inf):.1f}")

        # DB Update
        if conn or args.update:
             res = update_record_safe(
                 conn, 
                 filename, 
                 data['result'], 
                 int(data['track_count']), 
                 dry_run=not args.update
             )
             db_stats[res] += 1
        
        logger.info("-" * 70)

    if conn:
        conn.close()

    logger.info("\n" + "=" * 70)
    logger.info("BATCH ANALYSIS COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total Files: {len(files_to_process)}")
    logger.info(f"  Exact Matches:      {summary['Exact Match']}")
    logger.info(f"  New Configurations: {summary['New Configuration']}")
    logger.info(f"  Errors:             {summary['Error']}")
    
    if args.update or args.dev_server:
        logger.info("-" * 70)
        logger.info("Database Actions:")
        logger.info(f"  Updated: {db_stats['Updated']}")
        logger.info(f"  Skipped: {db_stats['Skipped']}")
        logger.info(f"  Missing: {db_stats['Missing']}")
        logger.info(f"  Errors:  {db_stats['Error']}")

    logger.info("-" * 70)
    logger.info("Configuration Frequency:")
    for config, count in config_counts.most_common():
        pct = (count / len(files_to_process)) * 100
        logger.info(f"  [{count:3d}] ({pct:5.1f}%)  {config}")

if __name__ == "__main__":
    main()
