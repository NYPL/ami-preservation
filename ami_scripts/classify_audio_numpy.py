#!/usr/bin/env python3
"""
Per-Stream / Per-Channel Audio Configuration Classifier (NumPy + ltcdump) - Late Audio Aware
WITH: lag-aligned pair metrics + 2-window confirmation for dual-mono

What it does:
- Finds audio streams/channels with ffprobe
- Searches for a non-silent analysis window even if audio starts late (0s, +step, +2*step...)
- Labels each channel: None / Timecode / Mono / Stereo Left / Stereo Right
- Uses ltcdump for LTC detection
- Uses NumPy waveform similarity for dual-mono vs stereo:
    - estimate lag, align signals, then compute corr + best-fit residual
    - only calls Dual Mono if it passes in TWO windows (early + later) when possible

Requires: ffmpeg, ffprobe, ltcdump (ltc-tools), numpy
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

import numpy as np

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

# Waveform thresholds (tuneable)
# Tighten these if you want to reduce false dual-mono further:
# e.g. DUAL_MONO_CORR_MIN=0.985, DUAL_MONO_RESID_MAX=0.03
DUAL_MONO_CORR_MIN = 0.97
DUAL_MONO_RESID_MAX = 0.15
DUAL_MONO_LAG_MAX_SAMPLES = 8

STEREO_CORR_MAX = 0.85
STEREO_RESID_MIN = 0.20

# Analysis decoding (numpy)
ANALYSIS_SAMPLE_RATE = 48000
DEFAULT_ANALYSIS_SECONDS = 300     # bigger default window for “late start” cases
DEFAULT_PAIR_SECONDS = 60          # more stable similarity stats

# Late-audio search defaults
DEFAULT_WINDOW_STEP_SECONDS = 180  # jump 3 minutes between attempts
DEFAULT_MAX_WINDOWS = 4            # try 0, +3m, +6m, +9m by default

# Dual-mono confirmation settings (second window inside the chosen decode window)
CONFIRM_OFFSET_SECONDS = 120       # try a second window ~2 minutes into the decoded chunk
CONFIRM_MIN_SECONDS = 5            # require >= 5 seconds for confirmation window

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
# Utilities
# -------------------------

def _dbfs_from_linear(x: float) -> float:
    if x <= 0.0 or not math.isfinite(x):
        return float("-inf")
    return 20.0 * math.log10(x)

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
    debug: bool = False,
) -> Tuple[np.ndarray, int]:
    """
    Decode [start, start+seconds) of a single audio stream to float32 PCM interleaved.
    Returns (pcm_1d, sample_rate).
    """
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
        if debug and err:
            try:
                sys.stderr.write(err.decode("utf-8", errors="replace") + "\n")
            except Exception:
                pass
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
# Pair similarity (waveform-based) WITH lag alignment + 2-window confirmation
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
    """
    Estimate lag (samples) where b best aligns to a.
    Positive lag means b is delayed vs a.
    Uses downsampled cross-correlation for speed.
    """
    if a.size < 2048 or b.size < 2048:
        return 0

    step = max(1, a.size // 50000)  # target <= ~50k samples
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
    """
    Align b to a by trimming.
    lag > 0: b is delayed -> trim first lag samples of b
    lag < 0: b is early   -> trim first -lag samples of a
    """
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
    """
    Compute corr + best-fit residual on aligned, zero-mean signals.
    """
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
    if L2 is not None and R2 is not None and L2.size > 0 and R2.size > 0:
        lag2 = estimate_lag_samples(L2, R2, max_lag=2000)
        m2 = pair_metrics_aligned(L2, R2, lag2)
        dm2, dm_flags2 = dual_mono_pass(m2, lag2)
    else:
        lag2 = None
        m2 = None
        dm2 = None
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

        # Window 1 said dual-mono, window 2 contradicted -> do NOT label dual-mono
        flags.append(
            f"Window1 looked dual-mono but Window2 did not "
            f"(w1 corr={m1['corr']:.3f} resid={m1['resid_ratio']:.3f} lag={lag1}; "
            f"w2 corr={m2['corr']:.3f} resid={m2['resid_ratio']:.3f} lag={lag2})"
        )

    # Stereo decisions based on window1 (aligned) metrics
    if abs(m1["corr"]) <= STEREO_CORR_MAX or m1["resid_ratio"] >= STEREO_RESID_MIN:
        if abs(m1["corr"]) > 0.90:
            flags.append(f"Highly correlated stereo (corr={m1['corr']:.3f}, resid={m1['resid_ratio']:.3f}, lag={lag1})")
        metrics_out = {"corr": m1["corr"], "gain": m1["gain"], "resid_ratio": m1["resid_ratio"], "lag": float(lag1)}
        return "Stereo Left", "Stereo Right", metrics_out, flags

    # Borderline: default stereo (more conservative)
    flags.append(f"Borderline -> Stereo (corr={m1['corr']:.3f}, resid={m1['resid_ratio']:.3f}, lag={lag1})")
    metrics_out = {"corr": m1["corr"], "gain": m1["gain"], "resid_ratio": m1["resid_ratio"], "lag": float(lag1)}
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
    fps_candidates: Tuple[int, ...] = LTC_FPS_CANDIDATES,
    debug: bool = False,
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
        assert ffmpeg_proc.stdout is not None
        ffmpeg_proc.stdout.close()
        ltcdump_out, _ = ltcdump_proc.communicate()
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
        print(f"  [LTC DEBUG] stream={stream_index} ch={channel_1based} start={start}s tokens={len(raw)}")

    if not raw:
        return False, None, 0.0, []

    def to_frames(h, m, s, f, fps):
        return (((h * 60) + m) * 60 + s) * fps + f

    # dedupe while preserving order
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
# Analysis
# -------------------------

def analyze_file_per_stream(
    input_file: str,
    ltc_duration: int,
    analysis_seconds: int,
    pair_seconds: int,
    max_offset_seconds: int,
    window_step_seconds: int,
    max_windows: int,
    debug: bool = False,
    enable_ltc: bool = True,
) -> Dict:
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

    stream_waveforms: Dict[int, np.ndarray] = {}

    # Per stream: find a decode window with real audio
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 0:
            continue
        base = stream_to_global_base[stream_index]

        chosen_samples: Optional[np.ndarray] = None
        chosen_stats: Optional[Dict[int, Dict[str, float]]] = None
        chosen_start = 0

        for w in range(max_windows):
            start = w * window_step_seconds
            if start > max_offset_seconds:
                break
            try:
                pcm, _ = decode_stream_pcm_f32le(
                    input_file=input_file,
                    stream_index=stream_index,
                    start=start,
                    seconds=analysis_seconds,
                    sample_rate=ANALYSIS_SAMPLE_RATE,
                    debug=debug
                )
                samples = reshape_interleaved(pcm, n_ch)
                st = compute_channel_stats_dbfs(samples)
            except Exception as e:
                flags.append(f"Stream {stream_index}: decode failed at {start}s ({e})")
                continue

            if stream_has_any_signal(st):
                chosen_samples = samples
                chosen_stats = st
                chosen_start = start
                break

            if debug:
                flags.append(f"Stream {stream_index}: window at {start}s appears silent; trying later window")

        if chosen_samples is None or chosen_stats is None:
            for local_ch in range(1, n_ch + 1):
                gch = base + (local_ch - 1)
                labels[gch] = "None"
                global_stats[gch] = {"rms": float("-inf"), "peak": float("-inf")}
            continue

        stream_waveforms[stream_index] = chosen_samples

        # initial channel labels from RMS
        for local_ch in range(1, n_ch + 1):
            gch = base + (local_ch - 1)
            rms_db = chosen_stats.get(local_ch, {}).get("rms", float("-inf"))
            peak_db = chosen_stats.get(local_ch, {}).get("peak", float("-inf"))
            global_stats[gch] = {"rms": rms_db, "peak": peak_db}
            labels[gch] = classify_silence_or_mono(rms_db)

        # LTC detection near the chosen window
        if enable_ltc:
            probe = min(ltc_duration, LTC_PROBE_DURATION_DEFAULT)
            for local_ch in range(1, n_ch + 1):
                gch = base + (local_ch - 1)
                if labels.get(gch) == "None":
                    continue
                is_ltc, best_fps, best_ratio, _ = detect_ltc_in_channel(
                    input_file=input_file,
                    stream_index=stream_index,
                    channel_1based=local_ch,
                    probe_duration=probe,
                    start=chosen_start,
                    debug=debug
                )
                if is_ltc:
                    labels[gch] = "Timecode"
                    if debug:
                        flags.append(f"Ch{gch}: LTC detected (fps={best_fps}, score={best_ratio:.2f}) at start={chosen_start}s")

    # Pair analysis per stream within chosen window, with 2-window confirmation when possible
    for s in streams:
        stream_index = s["index"]
        n_ch = s["channels"]
        if n_ch <= 1:
            continue
        base = stream_to_global_base[stream_index]
        samples = stream_waveforms.get(stream_index)
        if samples is None or samples.size == 0:
            continue

        sr = ANALYSIS_SAMPLE_RATE
        pair_frames = int(pair_seconds * sr)
        max_frames_early = min(samples.shape[0], pair_frames)
        early_win = samples[:max_frames_early, :]

        # Build a later confirmation window from inside the SAME decoded chunk
        late_start = int(CONFIRM_OFFSET_SECONDS * sr)
        late_end = min(samples.shape[0], late_start + pair_frames)
        have_late = (late_end - late_start) >= int(CONFIRM_MIN_SECONDS * sr)
        late_win = samples[late_start:late_end, :] if have_late else None

        n_pairs = n_ch // 2
        for p in range(n_pairs):
            local_l = (p * 2) + 1
            local_r = (p * 2) + 2
            g_l = base + (local_l - 1)
            g_r = base + (local_r - 1)

            if labels.get(g_l) != "Mono" or labels.get(g_r) != "Mono":
                continue

            L1 = early_win[:, local_l - 1]
            R1 = early_win[:, local_r - 1]

            L2 = None
            R2 = None
            if late_win is not None:
                L2 = late_win[:, local_l - 1]
                R2 = late_win[:, local_r - 1]

            lab_l, lab_r, m, pair_flags = analyze_pair_waveform(L1, R1, L2=L2, R2=R2)
            labels[g_l] = lab_l
            labels[g_r] = lab_r

            if debug:
                if "corr2" in m:
                    print(
                        f"  [PAIR DEBUG] Ch{g_l}/Ch{g_r}: "
                        f"w1 corr={m['corr']:.3f} resid={m['resid_ratio']:.3f} lag={int(m['lag'])} | "
                        f"w2 corr={m['corr2']:.3f} resid={m['resid_ratio2']:.3f} lag={int(m['lag2'])}"
                    )
                else:
                    print(
                        f"  [PAIR DEBUG] Ch{g_l}/Ch{g_r}: "
                        f"corr={m['corr']:.3f} resid={m['resid_ratio']:.3f} lag={int(m['lag'])}"
                    )

            for pf in pair_flags:
                flags.append(f"Ch{g_l}/Ch{g_r}: {pf}")

    parts = [f"Ch{i}: {labels.get(i, 'None')}" for i in range(1, total_global_channels + 1)]
    result = "; ".join(parts)
    status = "Exact Match" if result in KNOWN_CONFIGS else "New Configuration"

    return {"result": result, "status": status, "flags": flags, "stats": global_stats, "streams": streams}

# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Per-Stream Audio Configuration Classifier (NumPy + ltcdump, late-audio aware, 2-window dual-mono confirm)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-d", "--duration", type=int, default=240,
                        help="Max offset for seeking analysis windows + LTC probe upper bound (default: 240)")
    parser.add_argument("--analysis-seconds", type=int, default=DEFAULT_ANALYSIS_SECONDS,
                        help=f"Seconds decoded per window per stream (default: {DEFAULT_ANALYSIS_SECONDS})")
    parser.add_argument("--pair-seconds", type=int, default=DEFAULT_PAIR_SECONDS,
                        help=f"Seconds used for waveform pair similarity (default: {DEFAULT_PAIR_SECONDS})")
    parser.add_argument("--window-step-seconds", type=int, default=DEFAULT_WINDOW_STEP_SECONDS,
                        help=f"Seconds to jump between windows when searching for late audio (default: {DEFAULT_WINDOW_STEP_SECONDS})")
    parser.add_argument("--max-windows", type=int, default=DEFAULT_MAX_WINDOWS,
                        help=f"Max windows to try per stream (default: {DEFAULT_MAX_WINDOWS})")
    parser.add_argument("--max-offset-seconds", type=int, default=None,
                        help="Max start offset to search for audio. Defaults to -d/--duration.")
    parser.add_argument("--debug", action="store_true", help="Show debug output")
    parser.add_argument("--show-stats", action="store_true", help="Show RMS/Peak values")
    parser.add_argument("--no-ltc", action="store_true", help="Disable LTC detection")
    args = parser.parse_args()

    enable_ltc = not args.no_ltc

    analysis_seconds = max(1, int(args.analysis_seconds))
    pair_seconds = max(1, int(args.pair_seconds))
    ltc_duration = max(1, int(args.duration))
    window_step_seconds = max(1, int(args.window_step_seconds))
    max_windows = max(1, int(args.max_windows))
    max_offset_seconds = int(args.max_offset_seconds) if args.max_offset_seconds is not None else ltc_duration
    max_offset_seconds = max(0, max_offset_seconds)

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

        data = analyze_file_per_stream(
            input_file=fpath,
            ltc_duration=ltc_duration,
            analysis_seconds=analysis_seconds,
            pair_seconds=pair_seconds,
            max_offset_seconds=max_offset_seconds,
            window_step_seconds=window_step_seconds,
            max_windows=max_windows,
            debug=args.debug,
            enable_ltc=enable_ltc
        )

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
                rms_db = data["stats"][ch].get("rms", float("-inf"))
                peak_db = data["stats"][ch].get("peak", float("-inf"))
                rms_str = f"{rms_db:.1f}" if rms_db > -200 else "-inf"
                peak_str = f"{peak_db:.1f}" if peak_db > -200 else "-inf"
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
