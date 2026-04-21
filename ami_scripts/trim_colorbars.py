#!/usr/bin/env python3
"""
trim_colorbars.py

Detects color bars at the beginning of video files and trims them using FFmpeg.
Supports FFV1/MKV, ProRes/MOV, H.264/MP4 (and more).

Major improvements over the earlier version:
- Separates video and audio analysis so timestamps cannot drift between mixed metadata streams.
- Uses a structural bar detector (multi-strip spatial layout), not just global frame statistics.
- Uses a persistence-based state machine to avoid one-frame false starts / false ends.
- Uses a coarse-to-fine scan: cheap global search, then a high-FPS local refinement.
- Fixes --exact-trim so it actually performs an exact decode/re-encode path.
- Treats 1 kHz tone as a confidence boost, not as an override.

Dependencies:
- FFmpeg / FFprobe in PATH
- numpy

Usage:
    python trim_heads.py -i input.mp4
    python trim_heads.py -i /path/to/video/directory
    python trim_heads.py -i input.mp4 --output-dir /path/to/output
    python trim_heads.py -i input.mp4 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Configuration / tunables
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".mkv", ".mov", ".mp4", ".mxf", ".avi", ".m4v"}

# Scan window
MAX_HEAD_SCAN = 300.0                # max seconds to inspect at head
MAX_BAR_START_TIME = 15.0            # do not start a head-bar run after this point

# Coarse/fine sampling
COARSE_SCAN_FPS = 2.0
REFINE_SCAN_FPS = 20.0
REFINE_WINDOW_PRE = 1.5              # seconds before coarse boundary to inspect again
REFINE_WINDOW_POST = 1.5             # seconds after coarse boundary to inspect again

# Bar run constraints
MIN_BAR_DURATION = 1.0               # seconds of confirmed bars before trimming
NON_BAR_STREAK = 1.0                 # seconds of sustained non-bars required to end a run
TRIM_PADDING = 0.0                   # optional safety padding after detected boundary

# Confidence thresholds
ENTER_CONFIDENCE = 0.68              # average combined confidence to enter bars
KEEP_CONFIDENCE = 0.56               # per-frame threshold for "still in bars"
EXIT_CONFIDENCE = 0.35               # average confidence below this ends bars
POSITIVE_FRAME_CONFIDENCE = 0.60     # positive frame threshold for persistence logic
POSITIVE_FRACTION_TO_ENTER = 0.75    # fraction of positive frames needed to enter bars
NEGATIVE_FRACTION_TO_EXIT = 0.75     # fraction of low-confidence frames needed to exit bars

# Visual analysis thresholds
BLACK_LUMA_THRESHOLD = 12.0
WHITE_LUMA_THRESHOLD = 245.0
HARD_SEAM_MOTION = 20.0              # mean abs RGB diff [0..255] suggesting a cut / abrupt change

# Audio analysis
AUDIO_SAMPLE_RATE = 8000
TONE_WINDOW_SECONDS = 0.50           # FFT window per sampled frame
TONE_TARGET_LOW = 950.0
TONE_TARGET_HIGH = 1050.0
TONE_NEAR_LOW_1 = 800.0
TONE_NEAR_HIGH_1 = 940.0
TONE_NEAR_LOW_2 = 1060.0
TONE_NEAR_HIGH_2 = 1200.0
TONE_BROAD_LOW = 300.0
TONE_BROAD_HIGH = 3000.0
TONE_MIN_RMS = 0.0025
TONE_BOOST_WEIGHT = 0.22             # tone boosts confidence but never overrides visual failure

# When trimming predictive codecs in stream-copy mode, snap to first keyframe at/after boundary
KEYFRAME_SNAP_WINDOW = 10.0

PREDICTIVE_CODECS = {"h264", "hevc", "h265", "mpeg4", "mpeg2video", "mpeg1video", "vp8", "vp9", "av1"}
INTRA_CODECS = {"ffv1", "prores", "prores_ks", "v210", "rawvideo", "mjpeg", "dnxhd", "dnxhr"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class FrameFeatures:
    time: float
    luma_mean: float
    sat_mean: float
    sat_spread: float
    structural_score: float
    color_score: float
    motion: float
    is_black: bool
    visual_confidence: float
    tone_confidence: float
    combined_confidence: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# FFprobe helpers
# ---------------------------------------------------------------------------


def ffprobe_json(args: list[str]) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.strip()}")
    return json.loads(result.stdout)



def get_video_info(path: Path) -> dict:
    data = ffprobe_json(["-show_streams", "-select_streams", "v:0", str(path)])
    streams = data.get("streams", [])
    if not streams:
        raise ValueError(f"No video stream found in {path}")
    s = streams[0]

    fps_raw = s.get("avg_frame_rate") or s.get("r_frame_rate", "25/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 25.0

    duration = float(s.get("duration", 0) or 0)
    if not duration:
        fmt = ffprobe_json(["-show_format", str(path)])
        duration = float(fmt.get("format", {}).get("duration", 0) or 0)

    audio_data = ffprobe_json(["-show_streams", "-select_streams", "a", str(path)])
    has_audio = len(audio_data.get("streams", [])) > 0

    return {
        "codec": s.get("codec_name", "").lower(),
        "width": int(s.get("width", 0)),
        "height": int(s.get("height", 0)),
        "fps": fps,
        "duration": duration,
        "stream_index": s.get("index", 0),
        "pix_fmt": s.get("pix_fmt", ""),
        "has_audio": has_audio,
    }



def get_keyframe_timestamps(path: Path, target_time: float) -> list[float]:
    search_start = max(0.0, target_time - KEYFRAME_SNAP_WINDOW)
    search_end = target_time + KEYFRAME_SNAP_WINDOW
    data = ffprobe_json([
        "-select_streams", "v:0",
        "-show_frames",
        "-skip_frame", "nokey",
        "-read_intervals", f"{search_start}%{search_end}",
        "-show_entries", "frame=best_effort_timestamp_time",
        str(path),
    ])
    frames = data.get("frames", [])
    timestamps: list[float] = []
    for f in frames:
        t = f.get("best_effort_timestamp_time")
        if t and t != "N/A":
            try:
                timestamps.append(float(t))
            except ValueError:
                pass
    return sorted(timestamps)



def snap_to_keyframe(ts: float, keyframes: list[float], mode: str = "after") -> float:
    if not keyframes:
        return ts
    if mode == "after":
        candidates = [k for k in keyframes if k >= ts]
        return candidates[0] if candidates else keyframes[-1]
    candidates = [k for k in keyframes if k <= ts]
    return candidates[-1] if candidates else keyframes[0]


# ---------------------------------------------------------------------------
# Raw decode helpers
# ---------------------------------------------------------------------------


def iter_sampled_frames(
    path: Path,
    width: int,
    height: int,
    sample_rate: float,
    start_time: float,
    duration: float,
) -> Iterable[np.ndarray]:
    """Yield sampled RGB frames as HxWx3 uint8 arrays."""
    if duration <= 0:
        return

    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{start_time:.6f}",
        "-t", f"{duration:.6f}",
        "-i", str(path),
        "-an",
        "-vf", f"fps={sample_rate}",
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "-vsync", "0",
        "-",
    ]

    frame_size = width * height * 3
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None

    try:
        while True:
            chunk = process.stdout.read(frame_size)
            if not chunk:
                break
            if len(chunk) != frame_size:
                log.warning("Incomplete frame read; stopping frame iteration.")
                break
            frame = np.frombuffer(chunk, dtype=np.uint8).reshape((height, width, 3))
            yield frame
    finally:
        stderr_bytes = b""
        if process.stderr is not None:
            stderr_bytes = process.stderr.read()
        ret = process.wait()
        if ret != 0:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ffmpeg frame decode failed: {stderr_text or f'return code {ret}'}")



def decode_audio_mono(
    path: Path,
    start_time: float,
    duration: float,
    sample_rate: int = AUDIO_SAMPLE_RATE,
) -> np.ndarray:
    """Decode audio to mono float32 PCM."""
    if duration <= 0:
        return np.empty(0, dtype=np.float32)

    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{start_time:.6f}",
        "-t", f"{duration:.6f}",
        "-i", str(path),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    if not result.stdout:
        return np.empty(0, dtype=np.float32)
    return np.frombuffer(result.stdout, dtype=np.float32)


# ---------------------------------------------------------------------------
# Visual feature extraction
# ---------------------------------------------------------------------------


def _saturation_from_rgb(frame: np.ndarray) -> np.ndarray:
    maxc = frame.max(axis=2).astype(np.float32)
    minc = frame.min(axis=2).astype(np.float32)
    return maxc - minc



def _luma_from_rgb(frame: np.ndarray) -> np.ndarray:
    frame_f = frame.astype(np.float32)
    return 0.2126 * frame_f[:, :, 0] + 0.7152 * frame_f[:, :, 1] + 0.0722 * frame_f[:, :, 2]



def compute_visual_features(frame: np.ndarray, prev_frame: Optional[np.ndarray]) -> tuple[float, float, float, float, float, bool, float]:
    """
    Returns:
        luma_mean, sat_mean, sat_spread, structural_score, color_score, is_black, motion
    """
    h, w, _ = frame.shape

    # Analyze a broad central/top region where bar structure is strongest and captions are less common.
    y0 = max(0, int(h * 0.08))
    y1 = min(h, int(h * 0.78))
    roi = frame[y0:y1, :, :]

    # Light downsample for speed; keeps enough structure for bars.
    roi = roi[::4, ::4, :]

    luma = _luma_from_rgb(roi)
    sat = _saturation_from_rgb(roi)

    luma_mean = float(luma.mean())
    sat_mean = float(sat.mean())
    sat_spread = float(np.percentile(sat, 95) - np.percentile(sat, 5))
    luma_p95 = float(np.percentile(luma, 95))

    is_black = luma_mean < BLACK_LUMA_THRESHOLD and luma_p95 < 25.0

    # Spatial bar structure: divide into strips and look for stable-but-distinct vertical bands.
    strip_count = 7
    strip_means = []
    strip_stds = []
    strip_width = max(1, roi.shape[1] // strip_count)
    for i in range(strip_count):
        xs = i * strip_width
        xe = roi.shape[1] if i == strip_count - 1 else min(roi.shape[1], (i + 1) * strip_width)
        strip = roi[:, xs:xe, :].astype(np.float32)
        if strip.size == 0:
            continue
        strip_means.append(strip.reshape(-1, 3).mean(axis=0))
        strip_stds.append(strip.reshape(-1, 3).std(axis=0))

    if len(strip_means) >= 2:
        strip_means_arr = np.stack(strip_means, axis=0)
        strip_stds_arr = np.stack(strip_stds, axis=0)
        adjacent_dists = np.linalg.norm(np.diff(strip_means_arr, axis=0), axis=1)
        distinct_score = clamp(float(np.median(adjacent_dists) - 22.0) / 60.0)
        alternating_score = clamp(float((adjacent_dists > 28.0).mean()))
        low_variance_score = clamp(1.0 - float(np.median(strip_stds_arr)) / 45.0)
        structural_score = clamp(
            0.45 * distinct_score +
            0.25 * alternating_score +
            0.30 * low_variance_score
        )
    else:
        structural_score = 0.0

    # Global colorfulness sanity checks.
    sat_mean_score = clamp((sat_mean - 18.0) / 60.0)
    sat_spread_score = clamp((sat_spread - 35.0) / 120.0)
    luma_mid_score = clamp(1.0 - abs(luma_mean - 128.0) / 150.0)
    color_score = clamp(
        0.35 * sat_mean_score +
        0.35 * sat_spread_score +
        0.30 * luma_mid_score
    )

    if prev_frame is None:
        motion = 0.0
    else:
        prev_small = prev_frame[y0:y1:4, ::4, :].astype(np.float32)
        curr_small = roi.astype(np.float32)
        motion = float(np.mean(np.abs(curr_small - prev_small)))

    return luma_mean, sat_mean, sat_spread, structural_score, color_score, is_black, motion


# ---------------------------------------------------------------------------
# Audio tone analysis
# ---------------------------------------------------------------------------


def compute_tone_confidence(audio: np.ndarray, sr: int, center_time: float, window_seconds: float = TONE_WINDOW_SECONDS) -> float:
    if audio.size == 0:
        return 0.0

    half = window_seconds / 2.0
    start = max(0, int((center_time - half) * sr))
    end = min(audio.shape[0], int((center_time + half) * sr))
    if end - start < max(256, int(0.1 * sr)):
        return 0.0

    segment = audio[start:end].astype(np.float32)
    rms = float(np.sqrt(np.mean(segment ** 2)))
    if rms < TONE_MIN_RMS:
        return 0.0

    segment = segment * np.hanning(segment.shape[0])
    spec = np.fft.rfft(segment)
    mag = np.abs(spec)
    freqs = np.fft.rfftfreq(segment.shape[0], d=1.0 / sr)

    def band_energy(lo: float, hi: float) -> float:
        mask = (freqs >= lo) & (freqs <= hi)
        if not np.any(mask):
            return 0.0
        return float(np.sum(mag[mask] ** 2))

    target = band_energy(TONE_TARGET_LOW, TONE_TARGET_HIGH)
    near = band_energy(TONE_NEAR_LOW_1, TONE_NEAR_HIGH_1) + band_energy(TONE_NEAR_LOW_2, TONE_NEAR_HIGH_2)
    broad = band_energy(TONE_BROAD_LOW, TONE_BROAD_HIGH)

    if target <= 0.0 or broad <= 0.0:
        return 0.0

    prominence = target / max(near, 1e-12)
    ratio = target / max(broad, 1e-12)

    prominence_score = clamp((prominence - 1.8) / 6.0)
    ratio_score = clamp((ratio - 0.08) / 0.35)
    rms_score = clamp((rms - TONE_MIN_RMS) / 0.05)

    return clamp(0.45 * prominence_score + 0.35 * ratio_score + 0.20 * rms_score)


# ---------------------------------------------------------------------------
# Combined analysis
# ---------------------------------------------------------------------------


def analyze_window(
    path: Path,
    info: dict,
    start_time: float,
    duration: float,
    sample_rate: float,
) -> list[FrameFeatures]:
    width = info["width"]
    height = info["height"]
    has_audio = info.get("has_audio", False)

    audio = np.empty(0, dtype=np.float32)
    if has_audio:
        try:
            audio = decode_audio_mono(path, start_time=start_time, duration=duration, sample_rate=AUDIO_SAMPLE_RATE)
        except Exception as exc:
            log.warning(f"  Audio analysis unavailable for this pass: {exc}")
            audio = np.empty(0, dtype=np.float32)

    frames: list[FrameFeatures] = []
    prev_frame: Optional[np.ndarray] = None

    for idx, frame in enumerate(iter_sampled_frames(path, width, height, sample_rate, start_time, duration)):
        t = start_time + (idx / sample_rate)
        luma_mean, sat_mean, sat_spread, structural_score, color_score, is_black, motion = compute_visual_features(frame, prev_frame)

        if is_black or luma_mean > WHITE_LUMA_THRESHOLD:
            visual_conf = 0.0
        else:
            visual_conf = clamp(
                0.60 * structural_score +
                0.25 * color_score +
                0.15 * clamp(1.0 - motion / 30.0)
            )

        tone_conf = compute_tone_confidence(audio, AUDIO_SAMPLE_RATE, center_time=t - start_time) if has_audio else 0.0
        combined_conf = clamp(visual_conf + (TONE_BOOST_WEIGHT * tone_conf))

        frames.append(
            FrameFeatures(
                time=t,
                luma_mean=luma_mean,
                sat_mean=sat_mean,
                sat_spread=sat_spread,
                structural_score=structural_score,
                color_score=color_score,
                motion=motion,
                is_black=is_black,
                visual_confidence=visual_conf,
                tone_confidence=tone_conf,
                combined_confidence=combined_conf,
            )
        )
        prev_frame = frame.copy()

    return frames


# ---------------------------------------------------------------------------
# Bar boundary logic
# ---------------------------------------------------------------------------


def _window_metrics(window: list[FrameFeatures]) -> tuple[float, float]:
    if not window:
        return 0.0, 0.0
    avg_conf = float(np.mean([f.combined_confidence for f in window]))
    positive_fraction = float(np.mean([1.0 if f.combined_confidence >= POSITIVE_FRAME_CONFIDENCE else 0.0 for f in window]))
    return avg_conf, positive_fraction



def _negative_fraction(window: list[FrameFeatures]) -> float:
    if not window:
        return 0.0
    return float(np.mean([1.0 if f.combined_confidence <= EXIT_CONFIDENCE else 0.0 for f in window]))



def find_bar_end(
    features: list[FrameFeatures],
    sample_rate: float,
    max_bar_start_time: float = MAX_BAR_START_TIME,
    assume_in_bars: bool = False,
) -> Optional[float]:
    if not features:
        return None

    enter_len = max(2, int(round(sample_rate * max(0.75, MIN_BAR_DURATION))))
    exit_len = max(2, int(round(sample_rate * max(0.75, NON_BAR_STREAK))))

    recent: deque[FrameFeatures] = deque(maxlen=max(enter_len, exit_len))
    in_bars = assume_in_bars
    bar_start: Optional[float] = features[0].time if assume_in_bars else None
    last_bar_time: Optional[float] = None

    if assume_in_bars:
        for f in features[:enter_len]:
            recent.append(f)
            if f.combined_confidence >= KEEP_CONFIDENCE:
                last_bar_time = f.time

    for f in features:
        recent.append(f)
        recent_list = list(recent)

        if not in_bars:
            if f.time > max_bar_start_time:
                break
            enter_window = recent_list[-enter_len:]
            avg_conf, positive_fraction = _window_metrics(enter_window)
            if len(enter_window) >= enter_len and avg_conf >= ENTER_CONFIDENCE and positive_fraction >= POSITIVE_FRACTION_TO_ENTER:
                in_bars = True
                first_positive = next((x.time for x in enter_window if x.combined_confidence >= POSITIVE_FRAME_CONFIDENCE), enter_window[0].time)
                bar_start = first_positive
                last_bar_time = max((x.time for x in enter_window if x.combined_confidence >= KEEP_CONFIDENCE), default=enter_window[-1].time)
                log.info(f"  Head bars detected starting at ~{bar_start:.2f}s")
                continue

        if in_bars:
            if f.combined_confidence >= KEEP_CONFIDENCE:
                last_bar_time = f.time

            # Abrupt seam detection: allow an abrupt transition to end bars,
            # but only if confidence collapses and motion is truly elevated.
            if (
                last_bar_time is not None and
                f.motion >= HARD_SEAM_MOTION and
                f.combined_confidence <= EXIT_CONFIDENCE and
                bar_start is not None and
                (last_bar_time - bar_start) >= MIN_BAR_DURATION
            ):
                log.info(f"  Abrupt transition detected near {f.time:.2f}s; clamping bar end to {last_bar_time:.3f}s")
                return last_bar_time

            exit_window = recent_list[-exit_len:]
            avg_exit_conf = float(np.mean([x.combined_confidence for x in exit_window])) if exit_window else 0.0
            neg_fraction = _negative_fraction(exit_window)
            if (
                len(exit_window) >= exit_len and
                avg_exit_conf <= EXIT_CONFIDENCE and
                neg_fraction >= NEGATIVE_FRACTION_TO_EXIT and
                last_bar_time is not None and
                bar_start is not None and
                (last_bar_time - bar_start) >= MIN_BAR_DURATION
            ):
                log.info(f"  End of head bars confirmed at {last_bar_time:.3f}s")
                return last_bar_time

    if in_bars and bar_start is not None and last_bar_time is not None and (last_bar_time - bar_start) >= MIN_BAR_DURATION:
        log.info(f"  Bars extend to scan limit / EOF. Using {last_bar_time:.3f}s")
        return last_bar_time

    return None


# ---------------------------------------------------------------------------
# Detection orchestration
# ---------------------------------------------------------------------------


def detect_head_colorbars(
    path: Path,
    info: Optional[dict] = None,
    max_scan: float = MAX_HEAD_SCAN,
) -> Optional[float]:
    if info is None:
        info = get_video_info(path)

    if info["duration"] <= 0:
        log.warning("  Unable to determine duration; detection may be incomplete.")

    coarse_duration = min(max_scan, info["duration"] or max_scan)
    log.info(f"  Coarse scan for head bars at {COARSE_SCAN_FPS:.1f} fps (up to {coarse_duration:.1f}s)...")
    coarse_features = analyze_window(path, info, start_time=0.0, duration=coarse_duration, sample_rate=COARSE_SCAN_FPS)
    coarse_end = find_bar_end(coarse_features, sample_rate=COARSE_SCAN_FPS, max_bar_start_time=MAX_BAR_START_TIME)
    if coarse_end is None:
        log.info("  No valid head color bars detected.")
        return None

    refine_start = max(0.0, coarse_end - REFINE_WINDOW_PRE)
    refine_stop = min(coarse_duration, coarse_end + REFINE_WINDOW_POST)
    refine_duration = max(0.0, refine_stop - refine_start)
    if refine_duration <= 0:
        return coarse_end

    log.info(f"  Refining boundary at {REFINE_SCAN_FPS:.1f} fps from {refine_start:.2f}s to {refine_stop:.2f}s...")
    refine_features = analyze_window(path, info, start_time=refine_start, duration=refine_duration, sample_rate=REFINE_SCAN_FPS)
    refined_end = find_bar_end(refine_features, sample_rate=REFINE_SCAN_FPS, max_bar_start_time=refine_stop, assume_in_bars=True)

    if refined_end is not None:
        return refined_end
    return coarse_end


# ---------------------------------------------------------------------------
# Trimming
# ---------------------------------------------------------------------------


def build_reencode_video_args(codec: str, pix_fmt: str) -> list[str]:
    codec = (codec or "").lower()
    pix_fmt = (pix_fmt or "").lower()

    if codec in {"h264", "avc1", "hevc", "h265", "mpeg4", "mpeg2video", "mpeg1video", "vp8", "vp9", "av1"}:
        args = ["-c:v", "libx264", "-crf", "18", "-preset", "medium"]
        if pix_fmt:
            args += ["-pix_fmt", pix_fmt]
        return args

    if codec == "ffv1":
        args = ["-c:v", "ffv1", "-level", "3", "-g", "1"]
        if pix_fmt:
            args += ["-pix_fmt", pix_fmt]
        return args

    if codec in {"prores", "prores_ks"}:
        # Rough profile preservation. This is intentionally conservative.
        profile = "3"  # hq
        if "4444" in pix_fmt:
            profile = "4"
        elif "422p10" in pix_fmt:
            profile = "3"
        elif "422" in pix_fmt:
            profile = "2"
        args = ["-c:v", "prores_ks", "-profile:v", profile]
        if pix_fmt:
            args += ["-pix_fmt", pix_fmt]
        return args

    # Conservative fallback for exact trims when the source codec is unusual.
    args = ["-c:v", "ffv1", "-level", "3", "-g", "1"]
    if pix_fmt:
        args += ["-pix_fmt", pix_fmt]
    return args



def build_ffmpeg_trim_cmd(
    input_path: Path,
    output_path: Path,
    start: float,
    info: dict,
    use_stream_copy: bool,
) -> list[str]:
    codec = info["codec"]
    pix_fmt = info.get("pix_fmt", "")

    if use_stream_copy:
        # Fast/keyframe-aligned trim.
        cmd = [
            "ffmpeg", "-v", "warning", "-stats",
            "-ss", f"{start:.6f}",
            "-i", str(input_path),
            "-map", "0:v",
            "-map", "0:a?",
            "-map", "-0:d?",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-write_tmcd", "0",
            "-metadata", "timecode=",
            "-metadata:s:v", "timecode=",
            "-y", str(output_path),
        ]
        return cmd

    # Exact trim: seek after input and decode/re-encode video.
    cmd = [
        "ffmpeg", "-v", "warning", "-stats",
        "-i", str(input_path),
        "-ss", f"{start:.6f}",
        "-map", "0:v",
        "-map", "0:a?",
        "-map", "-0:d?",
    ]
    cmd += build_reencode_video_args(codec, pix_fmt)
    cmd += [
        "-c:a", "copy",
        "-avoid_negative_ts", "make_zero",
        "-write_tmcd", "0",
        "-metadata", "timecode=",
        "-metadata:s:v", "timecode=",
        "-y", str(output_path),
    ]
    return cmd



def trim_file(
    input_path: Path,
    output_path: Path,
    start: float,
    info: dict,
    exact_trim: bool = False,
    dry_run: bool = False,
) -> bool:
    codec = info["codec"]
    is_predictive = codec in PREDICTIVE_CODECS
    use_stream_copy = not exact_trim

    if use_stream_copy and is_predictive:
        log.info(f"  Codec '{codec}' is predictive — finding first keyframe at/after boundary...")
        keyframes = get_keyframe_timestamps(input_path, start)
        if keyframes:
            snapped_start = snap_to_keyframe(start, keyframes, mode="after")
            log.info(f"  Keyframe-snapped start: {start:.3f}s → {snapped_start:.3f}s")
            start = snapped_start
        else:
            log.warning("  No keyframes found in window; using requested start timestamp")

    cmd = build_ffmpeg_trim_cmd(
        input_path=input_path,
        output_path=output_path,
        start=start,
        info=info,
        use_stream_copy=use_stream_copy,
    )

    log.info(f"  Output: {output_path}")
    if dry_run:
        log.info(f"  [DRY RUN] Would run: {' '.join(cmd)}")
        return True

    log.info(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        log.error(f"  FFmpeg failed with code {result.returncode}")
        return False

    log.info(f"  ✓ Trimmed successfully → {output_path.name}")
    return True


# ---------------------------------------------------------------------------
# File discovery & output path
# ---------------------------------------------------------------------------


def find_video_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [path]
        log.warning(f"File {path} has unsupported extension, attempting anyway")
        return [path]

    if path.is_dir():
        files: list[Path] = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(path.glob(f"*{ext}"))
            files.extend(path.glob(f"*{ext.upper()}"))
        files = sorted(set(files))
        log.info(f"Found {len(files)} video file(s) in {path}")
        return files

    raise FileNotFoundError(f"Path not found: {path}")



def make_output_path(input_path: Path, output_dir: Optional[Path], suffix: str = "_trimmed") -> Path:
    stem = input_path.stem + suffix
    ext = input_path.suffix
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / (stem + ext)
    return input_path.parent / (stem + ext)


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def process_file(input_path: Path, output_dir: Optional[Path], exact_trim: bool, dry_run: bool) -> bool:
    log.info(f"\n{'=' * 60}")
    log.info(f"Processing: {input_path.name}")

    try:
        info = get_video_info(input_path)
    except Exception as exc:
        log.error(f"  Could not probe {input_path.name}: {exc}")
        return False

    log.info(
        f"  Codec: {info['codec']}  |  {info['width']}×{info['height']}  |  "
        f"{info['fps']:.3f}fps  |  {info['duration']:.2f}s  |  Audio: {info.get('has_audio', False)}"
    )

    try:
        content_start = detect_head_colorbars(input_path, info)
    except Exception as exc:
        log.error(f"  Detection failed for {input_path.name}: {exc}")
        return False

    if content_start is None or content_start <= 0.0:
        log.info(f"  → No trimming needed for {input_path.name}")
        return True

    if TRIM_PADDING > 0.0:
        log.info(f"  Applying {TRIM_PADDING:.2f}s padding for dirty transition.")
        content_start += TRIM_PADDING

    output_path = make_output_path(input_path, output_dir)
    return trim_file(
        input_path=input_path,
        output_path=output_path,
        start=content_start,
        info=info,
        exact_trim=exact_trim,
        dry_run=dry_run,
    )



def main() -> None:
    global MAX_HEAD_SCAN, MIN_BAR_DURATION, TRIM_PADDING

    parser = argparse.ArgumentParser(
        description="Detect and trim head color bars from video files using FFmpeg.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-i", "--input", type=Path, required=True, help="Input video file or directory of video files")
    parser.add_argument("--output-dir", "-o", type=Path, default=None, help="Directory to write trimmed files")
    parser.add_argument("--exact-trim", action="store_true", help="Decode/re-encode video for an exact cut instead of stream-copying")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Detect bars and report trims without writing files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--max-head-scan", type=float, default=MAX_HEAD_SCAN, help=f"Max seconds to search for the end of head bars (default: {MAX_HEAD_SCAN})")
    parser.add_argument("--min-bar-duration", type=float, default=MIN_BAR_DURATION, help=f"Minimum seconds of bars to trigger trimming (default: {MIN_BAR_DURATION})")
    parser.add_argument("--trim-padding", type=float, default=TRIM_PADDING, help=f"Extra seconds to trim after the detected end of bars (default: {TRIM_PADDING})")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    MAX_HEAD_SCAN = args.max_head_scan
    MIN_BAR_DURATION = args.min_bar_duration
    TRIM_PADDING = args.trim_padding

    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            log.error(f"'{tool}' not found. Please install FFmpeg.")
            sys.exit(1)

    try:
        video_files = find_video_files(args.input)
    except FileNotFoundError as exc:
        log.error(str(exc))
        sys.exit(1)

    if not video_files:
        log.warning("No supported video files found.")
        sys.exit(0)

    results: list[tuple[Path, bool]] = []
    for vf in video_files:
        ok = process_file(vf, args.output_dir, args.exact_trim, args.dry_run)
        results.append((vf, ok))

    log.info(f"\n{'=' * 60}")
    log.info(f"Summary: {sum(1 for _, ok in results if ok)}/{len(results)} file(s) processed successfully")
    failed = [vf for vf, ok in results if not ok]
    if failed:
        log.warning("Failed files:")
        for vf in failed:
            log.warning(f"  {vf}")
        sys.exit(1)


if __name__ == "__main__":
    main()
