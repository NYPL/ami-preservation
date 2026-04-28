#!/usr/bin/env python3

import argparse
import subprocess
import os
import shutil
import pathlib
import itertools
import csv
import re
import logging
from pymediainfo import MediaInfo
import importlib.util
import json
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Optional

# IMPORTANT: Ensure numpy is installed in your environment (pip install numpy)
import numpy as np

LOGGER = logging.getLogger(__name__)
video_extensions = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
audio_extensions = {'.wav', '.flac'}

# ---------------------------------------------------------------------------
# Colorbar Detection Configuration / tunables
# ---------------------------------------------------------------------------
MAX_HEAD_SCAN = 300.0                # max seconds to inspect at head
MAX_BAR_START_TIME = 15.0            # do not start a head-bar run after this point
COARSE_SCAN_FPS = 2.0
REFINE_SCAN_FPS = 20.0
REFINE_WINDOW_PRE = 1.5              # seconds before coarse boundary to inspect again
REFINE_WINDOW_POST = 1.5             # seconds after coarse boundary to inspect again
MIN_BAR_DURATION = 1.0               # seconds of confirmed bars before trimming
NON_BAR_STREAK = 1.0                 # seconds of sustained non-bars required to end a run
TRIM_PADDING = 0.0                   # optional safety padding after detected boundary

ENTER_CONFIDENCE = 0.68              
KEEP_CONFIDENCE = 0.56               
EXIT_CONFIDENCE = 0.35               
POSITIVE_FRAME_CONFIDENCE = 0.60     
POSITIVE_FRACTION_TO_ENTER = 0.75    
NEGATIVE_FRACTION_TO_EXIT = 0.75     

BLACK_LUMA_THRESHOLD = 12.0
WHITE_LUMA_THRESHOLD = 245.0
HARD_SEAM_MOTION = 20.0              

AUDIO_SAMPLE_RATE = 8000
TONE_WINDOW_SECONDS = 0.50           
TONE_TARGET_LOW = 950.0
TONE_TARGET_HIGH = 1050.0
TONE_NEAR_LOW_1 = 800.0
TONE_NEAR_HIGH_1 = 940.0
TONE_NEAR_LOW_2 = 1060.0
TONE_NEAR_HIGH_2 = 1200.0
TONE_BROAD_LOW = 300.0
TONE_BROAD_HIGH = 3000.0
TONE_MIN_RMS = 0.0025
TONE_BOOST_WEIGHT = 0.22             

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

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))

def ffprobe_json(args: list) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.strip()}")
    return json.loads(result.stdout)

def get_video_info(path: pathlib.Path) -> dict:
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

def iter_sampled_frames(
    path: pathlib.Path,
    width: int,
    height: int,
    sample_rate: float,
    start_time: float,
    duration: float,
) -> Iterable[np.ndarray]:
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
                LOGGER.warning("Incomplete frame read; stopping frame iteration.")
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
    path: pathlib.Path,
    start_time: float,
    duration: float,
    sample_rate: int = AUDIO_SAMPLE_RATE,
) -> np.ndarray:
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

def _saturation_from_rgb(frame: np.ndarray) -> np.ndarray:
    maxc = frame.max(axis=2).astype(np.float32)
    minc = frame.min(axis=2).astype(np.float32)
    return maxc - minc

def _luma_from_rgb(frame: np.ndarray) -> np.ndarray:
    frame_f = frame.astype(np.float32)
    return 0.2126 * frame_f[:, :, 0] + 0.7152 * frame_f[:, :, 1] + 0.0722 * frame_f[:, :, 2]

def compute_visual_features(frame: np.ndarray, prev_frame: Optional[np.ndarray]) -> tuple[float, float, float, float, float, bool, float]:
    h, w, _ = frame.shape
    y0 = max(0, int(h * 0.08))
    y1 = min(h, int(h * 0.78))
    roi = frame[y0:y1, :, :]
    roi = roi[::4, ::4, :]

    luma = _luma_from_rgb(roi)
    sat = _saturation_from_rgb(roi)

    luma_mean = float(luma.mean())
    sat_mean = float(sat.mean())
    sat_spread = float(np.percentile(sat, 95) - np.percentile(sat, 5))
    luma_p95 = float(np.percentile(luma, 95))

    is_black = luma_mean < BLACK_LUMA_THRESHOLD and luma_p95 < 25.0

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
        structural_score = clamp(0.45 * distinct_score + 0.25 * alternating_score + 0.30 * low_variance_score)
    else:
        structural_score = 0.0

    sat_mean_score = clamp((sat_mean - 18.0) / 60.0)
    sat_spread_score = clamp((sat_spread - 35.0) / 120.0)
    luma_mid_score = clamp(1.0 - abs(luma_mean - 128.0) / 150.0)
    color_score = clamp(0.35 * sat_mean_score + 0.35 * sat_spread_score + 0.30 * luma_mid_score)

    if prev_frame is None:
        motion = 0.0
    else:
        prev_small = prev_frame[y0:y1:4, ::4, :].astype(np.float32)
        curr_small = roi.astype(np.float32)
        motion = float(np.mean(np.abs(curr_small - prev_small)))

    return luma_mean, sat_mean, sat_spread, structural_score, color_score, is_black, motion

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

def analyze_window(
    path: pathlib.Path,
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
            LOGGER.warning(f"  Audio analysis unavailable for this pass: {exc}")
            audio = np.empty(0, dtype=np.float32)

    frames: list[FrameFeatures] = []
    prev_frame: Optional[np.ndarray] = None

    for idx, frame in enumerate(iter_sampled_frames(path, width, height, sample_rate, start_time, duration)):
        t = start_time + (idx / sample_rate)
        luma_mean, sat_mean, sat_spread, structural_score, color_score, is_black, motion = compute_visual_features(frame, prev_frame)

        if is_black or luma_mean > WHITE_LUMA_THRESHOLD:
            visual_conf = 0.0
        else:
            visual_conf = clamp(0.60 * structural_score + 0.25 * color_score + 0.15 * clamp(1.0 - motion / 30.0))

        tone_conf = compute_tone_confidence(audio, AUDIO_SAMPLE_RATE, center_time=t - start_time) if has_audio else 0.0
        combined_conf = clamp(visual_conf + (TONE_BOOST_WEIGHT * tone_conf))

        frames.append(
            FrameFeatures(
                time=t, luma_mean=luma_mean, sat_mean=sat_mean, sat_spread=sat_spread,
                structural_score=structural_score, color_score=color_score, motion=motion,
                is_black=is_black, visual_confidence=visual_conf, tone_confidence=tone_conf,
                combined_confidence=combined_conf,
            )
        )
        prev_frame = frame.copy()

    return frames

def _window_metrics(window: list[FrameFeatures]) -> tuple[float, float]:
    if not window: return 0.0, 0.0
    avg_conf = float(np.mean([f.combined_confidence for f in window]))
    positive_fraction = float(np.mean([1.0 if f.combined_confidence >= POSITIVE_FRAME_CONFIDENCE else 0.0 for f in window]))
    return avg_conf, positive_fraction

def _negative_fraction(window: list[FrameFeatures]) -> float:
    if not window: return 0.0
    return float(np.mean([1.0 if f.combined_confidence <= EXIT_CONFIDENCE else 0.0 for f in window]))

def find_bar_end(
    features: list[FrameFeatures],
    sample_rate: float,
    max_bar_start_time: float = MAX_BAR_START_TIME,
    assume_in_bars: bool = False,
) -> Optional[float]:
    if not features: return None
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
            if f.time > max_bar_start_time: break
            enter_window = recent_list[-enter_len:]
            avg_conf, positive_fraction = _window_metrics(enter_window)
            if len(enter_window) >= enter_len and avg_conf >= ENTER_CONFIDENCE and positive_fraction >= POSITIVE_FRACTION_TO_ENTER:
                in_bars = True
                first_positive = next((x.time for x in enter_window if x.combined_confidence >= POSITIVE_FRAME_CONFIDENCE), enter_window[0].time)
                bar_start = first_positive
                last_bar_time = max((x.time for x in enter_window if x.combined_confidence >= KEEP_CONFIDENCE), default=enter_window[-1].time)
                LOGGER.info(f"  Head bars detected starting at ~{bar_start:.2f}s")
                continue

        if in_bars:
            if f.combined_confidence >= KEEP_CONFIDENCE:
                last_bar_time = f.time

            if (last_bar_time is not None and f.motion >= HARD_SEAM_MOTION and
                f.combined_confidence <= EXIT_CONFIDENCE and bar_start is not None and
                (last_bar_time - bar_start) >= MIN_BAR_DURATION):
                return last_bar_time

            exit_window = recent_list[-exit_len:]
            avg_exit_conf = float(np.mean([x.combined_confidence for x in exit_window])) if exit_window else 0.0
            neg_fraction = _negative_fraction(exit_window)
            if (len(exit_window) >= exit_len and avg_exit_conf <= EXIT_CONFIDENCE and
                neg_fraction >= NEGATIVE_FRACTION_TO_EXIT and last_bar_time is not None and
                bar_start is not None and (last_bar_time - bar_start) >= MIN_BAR_DURATION):
                return last_bar_time

    if in_bars and bar_start is not None and last_bar_time is not None and (last_bar_time - bar_start) >= MIN_BAR_DURATION:
        return last_bar_time
    return None

def detect_head_colorbars(
    path: pathlib.Path,
    info: Optional[dict] = None,
    max_scan: float = MAX_HEAD_SCAN,
) -> Optional[float]:
    if info is None:
        info = get_video_info(path)

    coarse_duration = min(max_scan, info["duration"] or max_scan)
    coarse_features = analyze_window(path, info, start_time=0.0, duration=coarse_duration, sample_rate=COARSE_SCAN_FPS)
    coarse_end = find_bar_end(coarse_features, sample_rate=COARSE_SCAN_FPS, max_bar_start_time=MAX_BAR_START_TIME)
    if coarse_end is None:
        return None

    refine_start = max(0.0, coarse_end - REFINE_WINDOW_PRE)
    refine_stop = min(coarse_duration, coarse_end + REFINE_WINDOW_POST)
    refine_duration = max(0.0, refine_stop - refine_start)
    if refine_duration <= 0:
        return coarse_end

    refine_features = analyze_window(path, info, start_time=refine_start, duration=refine_duration, sample_rate=REFINE_SCAN_FPS)
    refined_end = find_bar_end(refine_features, sample_rate=REFINE_SCAN_FPS, max_bar_start_time=refine_stop, assume_in_bars=True)

    if refined_end is not None:
        return refined_end
    return coarse_end

# ---------------------------------------------------------------------------
# Core Processing Functions
# ---------------------------------------------------------------------------

def remove_hidden_files(directory):
    logged = False
    for item in directory.rglob('.*'):
        if item.is_file():
            if not logged:
                LOGGER.info("Removing hidden files...")
                logged = True
            item.unlink()
            LOGGER.info(f"Removed hidden file: {item}")

def rename_files(input_directory, extensions):
    files = set(itertools.chain.from_iterable(input_directory.glob(ext) for ext in extensions))
    if files:
        logged = False
        for file in files:
            new_file_name = file.name.replace("_ffv1", "")
            if new_file_name != file.name:
                if not logged:
                    LOGGER.info("Renaming files...")
                    logged = True
                new_file = file.with_name(new_file_name)
                shutil.move(file, new_file)
                LOGGER.info(f"Renamed file: {file.name} -> {new_file.name}")

def convert_mkv_dv_to_mp4(input_directory, audio_pan, force_16x9=False, trim_colorbars=False):
    mkv_files = sorted(input_directory.glob("*.mkv"))
    dv_files  = sorted(input_directory.glob("*.dv"))
    
    if mkv_files or dv_files:
        LOGGER.info("Converting MKV and DV to MP4...")
        for file in itertools.chain(mkv_files, dv_files):
            convert_to_mp4(file, input_directory, audio_pan, force_16x9, trim_colorbars)

def process_mov_files(input_directory, audio_pan, force_16x9=False, trim_colorbars=False):
    mov_files = list(input_directory.glob("*.mov"))
    if mov_files:
        LOGGER.info("Processing MOV files...")
        for mov_file in mov_files:
            convert_mov_file(mov_file, input_directory, audio_pan, force_16x9, trim_colorbars)

def rename_mkv_parts(input_directory):
    mkv_files = list(input_directory.glob("*_part*.mkv"))
    if not mkv_files: return
        
    LOGGER.info("Renaming MKV part files...")
    from collections import defaultdict
    groups = defaultdict(list)
    part_pattern = re.compile(r"^(.*?)_part\d+$")
    
    for mkv in mkv_files:
        match = part_pattern.match(mkv.stem)
        if match:
            base_stem = match.group(1)
            groups[base_stem].append(mkv)
            
    for base_stem, files in groups.items():
        clean_stem = base_stem
        if clean_stem.endswith("_pm"):
            clean_stem = clean_stem[:-3]
            
        if len(files) == 1:
            new_file = input_directory / f"{base_stem}.mkv"
            files[0].rename(new_file)
            LOGGER.info(f"Renamed single MKV part: {files[0].name} -> {new_file.name}")
        elif len(files) > 1:
            for i, mkv_file in enumerate(sorted(files), start=1):
                new_file = input_directory / f"{clean_stem}f01r{i:02}_pm.mkv"
                mkv_file.rename(new_file)
                LOGGER.info(f"Renamed MKV part: {mkv_file.name} -> {new_file.name}")

def process_dv_files(input_directory):
    dv_files = list(input_directory.glob("*.dv"))
    if not dv_files: return []
        
    LOGGER.info("Processing DV files...")
    processed_directory = input_directory / "ProcessedDV"
    processed_directory.mkdir(exist_ok=True)
    
    for dv_file in dv_files:
        corresponding_mkvs = list(input_directory.glob(f"{dv_file.stem}*.mkv"))
        
        if not corresponding_mkvs:
            LOGGER.info(f"No corresponding MKVs found for {dv_file.name}, running dvpackager...")
            if not shutil.which("dvpackager"):
                raise FileNotFoundError("dvpackager is not found, please install dvrescue with Homebrew.")
            command = ['dvpackager', '-e', 'mkv', str(dv_file)]
            subprocess.run(command, check=True, input='y', encoding='ascii')
        else:
            LOGGER.info(f"Found existing MKVs for {dv_file.name}, skipping dvpackager.")
            
        shutil.move(str(dv_file), processed_directory / dv_file.name)
    return dv_files

def process_hdv_files(input_directory):
    hdv_files = list(input_directory.glob("*.m2t"))
    if not hdv_files: return []

    LOGGER.info("Processing HDV (.m2t) files...")
    processed_directory = input_directory / "ProcessedHDV"
    processed_directory.mkdir(exist_ok=True)

    for hdv in hdv_files:
        mkv_out = input_directory / f"{hdv.stem}.mkv"
        cmd = ["ffmpeg", "-i", str(hdv), "-c", "copy", str(mkv_out)]
        LOGGER.info(f"Rewrapping HDV: {hdv.name} → {mkv_out.name}")
        subprocess.run(cmd, check=True)
        shutil.move(str(hdv), processed_directory / hdv.name)

    return hdv_files

def generate_framemd5_files(input_directory):
    mkv_files = sorted(input_directory.glob("*.mkv"))
    if mkv_files:
        LOGGER.info("Generating framemd5 files...")
        for file in mkv_files:
            output_file = input_directory / f"{file.stem}.framemd5"
            if not output_file.exists():
                command = ["ffmpeg", "-i", str(file), "-f", "framemd5", "-an", str(output_file)]
                subprocess.run(command)

def module_exists(module_name):
    return importlib.util.find_spec(module_name) is not None

def transcribe_directory(input_directory, model, output_format):
    media_extensions = {'.mkv'}
    input_dir_path = pathlib.Path(input_directory)
    mkv_files = list(input_dir_path.rglob('*.mkv'))
    if not mkv_files:
        return

    LOGGER.info("Transcribing directory...")
    if module_exists("whisper"):
        import whisper
    else:
        LOGGER.error("Error: The module 'whisper' is not installed. Please install it with 'pip3 install -U openai-whisper'")
        return

    model = whisper.load_model(model)
    for file in input_dir_path.rglob('*'):
        if file.suffix in media_extensions:
            LOGGER.info(f"Processing {file}")
            transcription_response = model.transcribe(str(file), verbose=True)
                
            output_filename = file.with_suffix("." + output_format)
            output_writer = whisper.utils.get_writer(output_format, str(file.parent))
            output_writer(transcription_response, file.stem)

def detect_ltc_in_channel(input_file, stream_index, channel, probe_duration=240, match_threshold=6, min_unique=4, min_monotonic_ratio=0.6, fps_candidates=(24, 25, 30), start_time=0.0):
    pan_filter = 'pan=mono|c0=c0' if channel == 'left' else 'pan=mono|c0=c1'
    ffmpeg_command = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error"]
    if start_time > 0.0:
        ffmpeg_command.extend(["-ss", f"{start_time:.6f}"])
    ffmpeg_command.extend([
        "-t", str(probe_duration),
        "-i", str(input_file), "-map", f"0:{stream_index}", "-af", pan_filter,
        "-ar", "48000", "-ac", "1", "-f", "wav", "pipe:1"
    ])
    ltcdump_command = ["ltcdump", "-"]

    ffmpeg_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ltcdump_proc = subprocess.Popen(ltcdump_command, stdin=ffmpeg_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ffmpeg_proc.stdout.close()
    ltcdump_out, ltcdump_err = ltcdump_proc.communicate()
    ffmpeg_proc.wait()

    LOGGER.info(f"ltcdump output: {ltcdump_out}")

    tc_pat = re.compile(r'(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[.:;](?P<f>\d{2})')
    raw = [(int(m.group('h')), int(m.group('m')), int(m.group('s')), int(m.group('f'))) for m in tc_pat.finditer(ltcdump_out)]

    if not raw:
        LOGGER.info("Found LTC matches: []")
        return False

    def to_frames(h, m, s, f, fps):
        return (((h * 60) + m) * 60 + s) * fps + f

    seen = set()
    ordered_unique = []
    for tc in raw:
        if tc not in seen:
            seen.add(tc)
            ordered_unique.append(tc)

    best_ratio = 0.0
    best_fps = None
    best_valid_seq = []

    for fps in fps_candidates:
        valid = [(h, m, s, f) for (h, m, s, f) in ordered_unique if m < 60 and s < 60 and f < fps]
        if len(valid) < match_threshold or len(set(valid)) < min_unique: continue

        frames = [to_frames(h, m, s, f, fps) for (h, m, s, f) in valid]
        if len(frames) < 2: continue

        deltas = [frames[i+1] - frames[i] for i in range(len(frames) - 1)]
        max_jump = 2 * fps

        good_fwd = sum(1 for d in deltas if 0 < d <= max_jump)
        good_rev = sum(1 for d in deltas if -max_jump <= d < 0)
        ratio = max(good_fwd, good_rev) / len(deltas)

        if ratio > best_ratio:
            best_ratio = ratio
            best_fps = fps
            best_valid_seq = valid

    LOGGER.info(f"Found LTC matches: {[f'{h:02d}:{m:02d}:{s:02d}.{f:02d}' for (h, m, s, f) in best_valid_seq]}")
    LOGGER.info(f"LTC score → fps={best_fps} monotonic_ratio={best_ratio:.2f} valid={len(best_valid_seq)} unique={len(set(best_valid_seq))}")

    if best_fps is not None and best_ratio >= min_monotonic_ratio and len(best_valid_seq) >= match_threshold:
        return True
    return False

def analyze_channel_activity(input_file, stream_index, channel, probe_duration=240, headroom_db=8.0, min_active_ratio=0.01, start_time=0.0):
    chan_idx = 0 if channel == 'left' else 1
    af_astats = f"pan=mono|c0=c{chan_idx},highpass=f=20,lowpass=f=18000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.0.RMS_level:mode=print"
    cmd1 = ["ffmpeg","-hide_banner","-nostats"]
    if start_time > 0.0:
        cmd1.extend(["-ss", f"{start_time:.6f}"])
    cmd1.extend(["-t", str(probe_duration),"-i", str(input_file),"-map", f"0:{stream_index}","-af", af_astats, "-f", "null", "-"])
    proc1 = subprocess.run(cmd1, capture_output=True, text=True)

    regex_pattern = r"lavfi\.astats\.0\.RMS_level\s*[:=]\s*(-?\d+(?:\.\d+)?|-inf)"
    levels = [float(x) for x in re.findall(regex_pattern, proc1.stdout)]
    if not levels:
        fallback_pattern = r"(?:lavfi\.astats\.\d+\.RMS_level|RMS[_\s]?level(?:\s*dB)?)\s*[:=]\s*(-?\d+(?:\.\d+)?|-inf)"
        levels = [float(x) for x in re.findall(fallback_pattern, proc1.stderr)]

    def percentile(vals, p):
        if not vals: return None
        vals = sorted(vals)
        if p <= 0: return vals[0]
        if p >= 100: return vals[-1]
        idx = int(round((p/100.0) * (len(vals)-1)))
        return vals[idx]

    p20 = percentile(levels, 20) if levels else -90.0
    p50 = percentile(levels, 50) if levels else -90.0
    p95 = percentile(levels, 95) if levels else -90.0

    threshold = (p20 + headroom_db) if levels else -60.0
    active = sum(lvl > threshold for lvl in levels) if levels else 0
    active_ratio = (active / len(levels)) if levels else 0.0

    af_vol = f"pan=mono|c0=c{chan_idx},volumedetect"
    cmd2 = ["ffmpeg","-hide_banner","-nostats"]
    if start_time > 0.0:
        cmd2.extend(["-ss", f"{start_time:.6f}"])
    cmd2.extend(["-t", str(probe_duration),"-i", str(input_file),"-map", f"0:{stream_index}","-af", af_vol, "-f", "null", "-"])
    proc2 = subprocess.run(cmd2, capture_output=True, text=True)
    mean_m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", proc2.stderr)
    max_m  = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB",  proc2.stderr)
    mean_vol = float(mean_m.group(1)) if mean_m else None
    max_vol  = float(max_m.group(1))  if max_m  else None

    return {
        "noise_floor": p20, "median": p50, "p95": p95, "threshold": threshold,
        "active_ratio": active_ratio, "is_silent": (active_ratio < min_active_ratio),
        "mean_vol": mean_vol, "max_vol": max_vol
    }

def detect_audio_pan(input_file, audio_pan, probe_duration=240, relative_db_gate=8.0, start_time=0.0):
    LOGGER.info(f"  → Analyzing audio for auto-panning (probing 240s starting at {start_time:.3f}s)...")
    ffprobe_command = ["ffprobe", "-i", str(input_file), "-show_entries", "stream=index:stream=codec_type", "-select_streams", "a", "-of", "compact=p=0:nk=1", "-v", "0"]
    ffprobe_result = subprocess.run(ffprobe_command, capture_output=True, text=True)
    audio_streams = [int(line.split('|')[0]) for line in ffprobe_result.stdout.splitlines() if "audio" in line]

    LOGGER.info(f"Detected {len(audio_streams)} audio streams: {audio_streams} in {input_file}")

    pan_filters = []
    pan_filter_idx = 0

    for stream_index in audio_streams:
        LOGGER.info(f"Analyzing audio stream: {stream_index}")
        L = analyze_channel_activity(input_file, stream_index, 'left',  probe_duration=probe_duration, start_time=start_time)
        R = analyze_channel_activity(input_file, stream_index, 'right', probe_duration=probe_duration, start_time=start_time)

        def fmt(stats):
            return (f"nf={stats['noise_floor']:.1f}dB p50={stats['median']:.1f}dB "
                    f"p95={stats['p95']:.1f}dB thr={stats['threshold']:.1f}dB "
                    f"act={stats['active_ratio']*100:.2f}% "
                    f"mean={stats['mean_vol'] if stats['mean_vol'] is not None else 'NA'} "
                    f"max={stats['max_vol'] if stats['max_vol'] is not None else 'NA'}")

        LOGGER.info(f"Stream {stream_index} – L: {fmt(L)} | R: {fmt(R)}")

        left_is_silent  = L['is_silent']
        right_is_silent = R['is_silent']

        left_has_ltc = right_has_ltc = False
        if audio_pan == "auto":
            left_has_ltc  = detect_ltc_in_channel(input_file, stream_index, 'left',  probe_duration=probe_duration, start_time=start_time)
            right_has_ltc = detect_ltc_in_channel(input_file, stream_index, 'right', probe_duration=probe_duration, start_time=start_time)

        if left_has_ltc and not right_has_ltc:
            if right_is_silent:
                LOGGER.info(f"Stream {stream_index}: Left LTC + right silent → dropping stream.")
                continue
            else:
                LOGGER.info(f"Stream {stream_index}: Left LTC → using RIGHT as mono source.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
        elif right_has_ltc and not left_has_ltc:
            if left_is_silent:
                LOGGER.info(f"Stream {stream_index}: Right LTC + left silent → dropping stream.")
                continue
            else:
                LOGGER.info(f"Stream {stream_index}: Right LTC → using LEFT as mono source.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
        else:
            if not left_is_silent and right_is_silent:
                LOGGER.info(f"Stream {stream_index}: Right silent (abs) → LEFT-to-center.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
            elif not right_is_silent and left_is_silent:
                LOGGER.info(f"Stream {stream_index}: Left silent (abs) → RIGHT-to-center.")
                pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
            else:
                def loudness_hint(stats):
                    candidates = [stats['p95']]
                    if stats['mean_vol'] is not None: candidates.append(stats['mean_vol'])
                    if stats['max_vol'] is not None: candidates.append(stats['max_vol'])
                    return max(candidates)

                l_hint = loudness_hint(L)
                r_hint = loudness_hint(R)
                diff = l_hint - r_hint

                if diff >= relative_db_gate:
                    LOGGER.info(f"Stream {stream_index}: Both quiet by abs gate, but LEFT louder by {diff:.1f} dB → LEFT-to-center.")
                    pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c0[outa{pan_filter_idx}]")
                elif diff <= -relative_db_gate:
                    LOGGER.info(f"Stream {stream_index}: Both quiet by abs gate, but RIGHT louder by {-diff:.1f} dB → RIGHT-to-center.")
                    pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c1|c1=c1[outa{pan_filter_idx}]")
                else:
                    LOGGER.info(f"Stream {stream_index}: Both active or both similarly quiet → keep stereo.")
                    pan_filters.append(f"[0:{stream_index}]pan=stereo|c0=c0|c1=c1[outa{pan_filter_idx}]")

        pan_filter_idx += 1
    return pan_filters

def convert_to_mp4(input_file, input_directory, audio_pan, force_16x9=False, trim_colorbars=False):
    def get_video_metadata(input_file):
        ffprobe_command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,sample_aspect_ratio", "-of", "csv=p=0"]
        result = subprocess.run(ffprobe_command + [str(input_file)], capture_output=True, text=True)
        stdout = result.stdout.strip()
        if result.returncode != 0 or not stdout:
            raise ValueError(f"Could not determine metadata for {input_file!r}: {result.stderr.strip() or 'no output'}")
        clean = stdout.rstrip(",")
        parts = clean.split(",")
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(f"Unexpected metadata format for {input_file!r}: '{stdout}'")
        
        width, height = int(parts[0]), int(parts[1])
        sar = parts[2] if len(parts) > 2 else "0:1"
        return width, height, sar

    output_file_name = f"{input_file.stem.replace('_pm', '')}_sc.mp4"
    output_file = input_directory / output_file_name

    try:
        width, height, sar = get_video_metadata(input_file)
    except ValueError as e:
        LOGGER.error(f"Skipping {input_file.name}: {e}")
        return None

    trim_args = []
    content_start = 0.0
    if trim_colorbars:
        LOGGER.info(f"Checking {input_file.name} for head colorbars/tone to trim from the Service Copy...")
        try:
            info = get_video_info(input_file)
            detected_start = detect_head_colorbars(input_file, info)
            if detected_start is not None and detected_start > 0.0:
                if TRIM_PADDING > 0.0:
                    detected_start += TRIM_PADDING
                content_start = detected_start
                LOGGER.info(f"  → Found head colorbars. Service copy will be trimmed by {content_start:.3f} seconds.")
                trim_args = ["-ss", f"{content_start:.6f}"]
            else:
                LOGGER.info("  → No colorbars detected.")
        except Exception as e:
            LOGGER.error(f"  → Warning: Colorbar detection failed for {input_file.name}: {e}")

    ffprobe_audio = ["ffprobe", "-i", str(input_file), "-show_entries", "stream=index:stream=codec_type", "-select_streams", "a", "-of", "compact=p=0:nk=1", "-v", "0"]
    audio_result = subprocess.run(ffprobe_audio, capture_output=True, text=True)
    audio_streams = [int(line.split('|')[0]) for line in audio_result.stdout.splitlines() if "audio" in line]

    pan_filters = []
    if audio_pan in {"left", "right", "center"}:
        for i, idx in enumerate(audio_streams):
            if audio_pan == "left": pan_filters.append(f"[0:{idx}]pan=stereo|c0=c0|c1=c0[outa{i}]")
            elif audio_pan == "right": pan_filters.append(f"[0:{idx}]pan=stereo|c0=c1|c1=c1[outa{i}]")
            else: pan_filters.append(f"[0:{idx}]pan=stereo|c0=c0+c1|c1=c0+c1[outa{i}]")
    elif audio_pan == "auto":
        pan_filters = detect_audio_pan(input_file, audio_pan, start_time=content_start)

    if (width, height) == (720, 486):
        if force_16x9 or sar == "40:33": video_filter = "idet,bwdif=1,crop=w=720:h=480:x=0:y=4,setdar=16/9"
        else: video_filter = "idet,bwdif=1,crop=w=720:h=480:x=0:y=4,setdar=4/3"
    elif (width, height) == (720, 576):
        if force_16x9 or sar == "16:11": video_filter = "idet,bwdif=1,setdar=16/9"
        else: video_filter = "idet,bwdif=1"
    elif (width, height) == (1440, 1080):
        video_filter = "idet,bwdif=1"
    else:
        LOGGER.info(f"Unknown resolution {width}×{height}, using default filter.")
        video_filter = "idet,bwdif=1"

    command = ["ffmpeg"] + trim_args + [
        "-i", str(input_file), "-map", "0:v", "-c:v", "libx264", "-movflags", "faststart",
        "-pix_fmt", "yuv420p", "-crf", "21", "-vf", video_filter,
    ]

    if audio_pan != "none":
        if pan_filters:
            filter_complex = ";".join(pan_filters)
            command += ["-filter_complex", filter_complex]
            for i in range(len(pan_filters)):
                command += ["-map", f"[outa{i}]"]
        elif audio_streams:
            LOGGER.info("  → All audio streams stripped (LTC/Silence). No audio mapped.")
    else:
        for idx in audio_streams:
            command += ["-map", f"0:{idx}"]

    if pan_filters or (audio_pan == "none" and audio_streams):
        command += ["-c:a", "aac", "-b:a", "320k", "-ar", "48000"]

    command.append(str(output_file))

    LOGGER.info(f"FFmpeg command: {' '.join(command)}")
    subprocess.check_call(command)
    LOGGER.info(f"MP4 created: {output_file}")

    return output_file

def convert_mov_file(input_file, input_directory, audio_pan, force_16x9=False, trim_colorbars=False):
    def get_video_resolution(path):
        ffprobe_command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)]
        result = subprocess.run(ffprobe_command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            clean_out = result.stdout.strip().split('\n')[0].rstrip(',')
            parts = clean_out.split(',')
            if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                return int(parts[0].strip()), int(parts[1].strip())
            else: raise ValueError(f"Could not parse video resolution for {path}")
        else: raise ValueError(f"Could not determine video resolution for {path}")

    width, height = get_video_resolution(input_file)

    if width == 720 and height == 486:
        field_order, set_field_filter, dar_filter, color_primaries, color_range, color_trc, colorspace = "bt", "bff", "4/3", "smpte170m", "tv", "bt709", "smpte170m"
    elif width == 720 and height == 576:
        field_order, set_field_filter, dar_filter, color_primaries, color_range, color_trc, colorspace = "tb", "tff", "4/3", "bt470bg", "tv", "bt709", "bt470bg"
    else:
        field_order = set_field_filter = dar_filter = color_primaries = color_range = color_trc = colorspace = None

    mkv_output = input_directory / f"{input_file.stem}.mkv"
    ffv1_cmd = [
        "ffmpeg", "-i", str(input_file), "-map", "0", "-dn", "-c:v", "ffv1", "-level", "3",
        "-g", "1", "-slicecrc", "1", "-slices", "24", "-c:a", "flac"
    ]

    if field_order: ffv1_cmd += ["-field_order", field_order]

    vf_filters = []
    if set_field_filter: vf_filters.append(f"setfield={set_field_filter}")
    if dar_filter: vf_filters.append(f"setdar={dar_filter}")
    if vf_filters: ffv1_cmd += ["-vf", ",".join(vf_filters)]

    if color_primaries: ffv1_cmd += ["-color_primaries", color_primaries]
    if color_range: ffv1_cmd += ["-color_range", color_range]
    if color_trc: ffv1_cmd += ["-color_trc", color_trc]
    if colorspace: ffv1_cmd += ["-colorspace", colorspace]

    ffv1_cmd.append(str(mkv_output))

    LOGGER.info(f"Running MKV (FFV1) command: {' '.join(ffv1_cmd)}")
    subprocess.run(ffv1_cmd, check=True)
    LOGGER.info(f"Created Preservation Master: {mkv_output}")

    convert_to_mp4(input_file, input_directory, audio_pan, force_16x9, trim_colorbars)

def move_files(input_directory):
    files_to_move = list(itertools.chain(input_directory.glob("*.mp4"), input_directory.glob("*.mov"), input_directory.glob("*.mkv"), input_directory.glob("*.framemd5"), input_directory.glob("*.vtt")))
    if files_to_move:
        logged = False
        for file in files_to_move:
            target_dir_name = {
                ".mov": "V210",
                ".mkv": "PreservationMasters",
                ".framemd5": "PreservationMasters",
                ".vtt": "PreservationMasters",
                ".mp4": "ServiceCopies"
            }.get(file.suffix)

            if target_dir_name:
                if not logged:
                    LOGGER.info("Moving files...")
                    logged = True
                target_dir = input_directory / target_dir_name
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(file), str(target_dir / file.name))

def process_log_and_xml_files(input_directory):
    log_files = list(input_directory.glob("*.log"))
    xml_gz_files = list(input_directory.glob("*.xml.gz"))
    xml_files = list(input_directory.glob("*.xml"))
    
    if log_files or xml_gz_files or xml_files:
        LOGGER.info("Processing log and xml files...")
        
    for file in log_files:
        file.unlink()
    for file in xml_gz_files:
        pm_dir = input_directory / "PreservationMasters"
        pm_dir.mkdir(exist_ok=True)
        shutil.move(str(file), str(pm_dir / file.name))
    for file in xml_files:
        file.unlink()

def delete_empty_directories(input_directory, directories):
    logged = False
    for directory in directories:
        dir_path = input_directory / directory
        try:
            if not any(dir_path.iterdir()):
                if not logged:
                    LOGGER.info("Deleting empty directories...")
                    logged = True
                dir_path.rmdir()
        except FileNotFoundError: pass

def process_directory(directory):
    valid_extensions = video_extensions.union(audio_extensions)
    paths = []
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix.lower() in valid_extensions:
            if "ProcessedDV" not in path.parts and "V210" not in path.parts:
                paths.append(path)
    return paths

def has_mezzanines(file_path):
    for parent in file_path.parents:
        mezzanines_dir = parent / "Mezzanines"
        if mezzanines_dir.is_dir(): return True
    return False

def extract_track_info(media_info, path, project_code_pattern, valid_extensions):
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    for track in media_info.tracks:
        if track.track_type == "General":
            file_data = [
                path, '.'.join([path.stem, path.suffix[1:]]), path.stem, path.suffix[1:], track.file_size,
                pattern.search(track.file_last_modification_date).group(0) if pattern.search(track.file_last_modification_date) else None,
                track.format, track.audio_format_list.split()[0] if track.audio_format_list else None,
                track.codecs_video, track.duration,
            ]

            if track.duration:
                human_duration = str(track.other_duration[3]) if track.other_duration else None
                file_data.append(human_duration)
            else: file_data.append(None)

            media_type = None
            has_mezzanines_folder = has_mezzanines(path)

            if path.suffix.lower() in video_extensions: media_type = 'film' if has_mezzanines_folder else 'video'
            elif path.suffix.lower() in audio_extensions: media_type = 'audio'

            file_data.append(media_type)
            file_no_ext = path.stem
            role = file_no_ext.split('_')[-1]
            division = file_no_ext.split('_')[0]
            driveID = path.parts[2]
            file_data.extend([role, division, driveID])
            primaryID = path.stem
            file_data.append(primaryID.split('_')[1] if len(primaryID.split('_')) > 1 else None)

            match = project_code_pattern.search(str(path))
            if match:
                projectcode = match.group(1)
                file_data.append(projectcode)
            else: file_data.append(None)

            return file_data
    return None

def main():
    parser = argparse.ArgumentParser(description="Process video files in a specified directory and optionally extract MediaInfo.")
    parser.add_argument("-d", "--directory", type=str, required=True, help="Input directory containing video files.")
    parser.add_argument("-t", "--transcribe", action="store_true", help="Transcribe the audio of the MKV files to VTT format using the Whisper tool.")
    parser.add_argument("-o", "--output", help="Path to save csv (optional). If provided, MediaInfo extraction will be performed.", required=False)
    parser.add_argument("-m", "--model", default='medium', choices=['tiny', 'base', 'small', 'medium', 'large'], help='The Whisper model to use')
    parser.add_argument("-f", "--format", default='vtt', choices=['vtt', 'srt', 'txt', 'json'], help='The subtitle output format to use')
    parser.add_argument("-p", "--audio-pan", choices=["left", "right", "none", "center", "auto"], default="none", help="Pan audio to center from left, right, or auto-detect mono audio.")
    parser.add_argument("--force-16x9", action="store_true", help="For SD sources (720x486/576), force MP4 display aspect ratio to 16:9 (anamorphic).")
    parser.add_argument("--trim-colorbars", action="store_true", help="Detect and trim head colorbars/tone during the generation of the MP4 Service Copy.")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    input_dir = pathlib.Path(args.directory)

    if not input_dir.is_dir():
        LOGGER.error(f"Error: {input_dir} is not a valid directory.")
        exit(1)

    remove_hidden_files(input_dir)
    process_dv_files(input_dir)
    rename_mkv_parts(input_dir)
    process_hdv_files(input_dir)
    convert_mkv_dv_to_mp4(input_dir, args.audio_pan, args.force_16x9, args.trim_colorbars)
    process_mov_files(input_dir, args.audio_pan, args.force_16x9, args.trim_colorbars)
    generate_framemd5_files(input_dir)
    rename_files(input_dir, video_extensions.union(audio_extensions))
    move_files(input_dir)
    process_log_and_xml_files(input_dir)

    if args.transcribe:
        transcribe_directory(input_dir, args.model, args.format)

    delete_empty_directories(input_dir, ["V210", "PreservationMasters", "ServiceCopies", "ProcessedDV", "ProcessedHDV"])

    if args.output:
        project_code_pattern = re.compile(r'(\d{4}_\d{2}_\d{2})')
        valid_extensions = video_extensions.union(audio_extensions)
        file_data = []

        for path in process_directory(input_dir):
            media_info = MediaInfo.parse(str(path))
            track_info = extract_track_info(media_info, path, project_code_pattern, valid_extensions)
            if track_info:
                LOGGER.info(file_data)
                file_data.append(track_info)

        with open(args.output, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow([
            'filePath', 'asset.referenceFilename', 'technical.filename', 'technical.extension',
            'technical.fileSize.measure', 'technical.dateCreated', 'technical.fileFormat',
            'technical.audioCodec', 'technical.videoCodec', 'technical.durationMilli.measure',
            'technical.durationHuman', 'mediaType', 'role', 'divisionCode', 'driveID',
            'primaryID', 'projectID'
        ])
            csvwriter.writerows(file_data)

if __name__ == "__main__":
    main()