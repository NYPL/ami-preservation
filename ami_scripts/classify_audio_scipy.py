#!/usr/bin/env python3
"""
Enhanced Per-Stream Audio Configuration Classifier
WITH: Phase coherence, spectral correlation, SNR analysis, and multi-metric dual-mono detection

Improvements over original:
- Phase coherence analysis via cross-spectral density
- Spectral correlation in frequency domain
- SNR measurement for residual quality
- Gain stability across windows
- Multi-criteria decision logic with detailed diagnostics
- Tunable threshold profiles

Requires: ffmpeg, ffprobe, ltcdump (ltc-tools), numpy, scipy
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
from dataclasses import dataclass

import numpy as np
from scipy import signal

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

# Dual-mono classification thresholds (ENHANCED)
# Choose a profile: 'strict', 'balanced', 'lenient'
THRESHOLD_PROFILES = {
    'strict': {
        'corr_min': 0.985,
        'resid_max': 0.03,
        'phase_min': 0.93,
        'spec_corr_min': 0.97,
        'snr_min_db': 30.0,
        'lag_max': 5,
        'gain_stability_min': 0.90
    },
    'balanced': {
        'corr_min': 0.975,
        'resid_max': 0.045,
        'phase_min': 0.90,
        'spec_corr_min': 0.95,
        'snr_min_db': 26.0,
        'lag_max': 8,
        'gain_stability_min': 0.85
    },
    'lenient': {
        'corr_min': 0.96,
        'resid_max': 0.06,
        'phase_min': 0.85,
        'spec_corr_min': 0.92,
        'snr_min_db': 23.0,
        'lag_max': 12,
        'gain_stability_min': 0.80
    }
}

# Default profile
DEFAULT_PROFILE = 'balanced'

# Stereo thresholds (looser)
STEREO_CORR_MAX = 0.85
STEREO_RESID_MIN = 0.20

# Known configs
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
# Data Classes
# -------------------------

@dataclass
class PairMetrics:
    """Comprehensive metrics for channel pair analysis"""
    corr: float
    gain: float
    resid_ratio: float
    lag: int
    phase_coherence: float
    spectral_corr: float
    gain_stability: float
    snr_db: float

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
    """Decode [start, start+seconds) of a single audio stream to float32 PCM interleaved."""
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
# Enhanced Pair Analysis
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

def estimate_lag_xcorr(a: np.ndarray, b: np.ndarray, max_lag: int = 2000) -> Tuple[int, float]:
    """
    Estimate lag (samples) where b best aligns to a.
    Returns (lag, peak_correlation).
    """
    if a.size < 2048 or b.size < 2048:
        return 0, 1.0

    step = max(1, a.size // 50000)
    aa = a[::step].astype(np.float64, copy=False)
    bb = b[::step].astype(np.float64, copy=False)

    aa = aa - np.mean(aa)
    bb = bb - np.mean(bb)

    # Normalize for correlation coefficient
    aa_std = np.std(aa)
    bb_std = np.std(bb)
    if aa_std > 1e-12 and bb_std > 1e-12:
        aa_norm = aa / aa_std
        bb_norm = bb / bb_std
    else:
        return 0, 1.0

    max_lag_ds = max(1, max_lag // step)
    if max_lag_ds >= aa.size - 1:
        max_lag_ds = max(1, aa.size // 4)

    corr = np.correlate(bb_norm, aa_norm, mode="full")
    mid = corr.size // 2

    lo = max(0, mid - max_lag_ds)
    hi = min(corr.size, mid + max_lag_ds + 1)
    window = corr[lo:hi]

    idx = int(np.argmax(np.abs(window)))  # Use abs for polarity-inverted
    lag_ds = (lo + idx) - mid
    peak_corr = float(window[idx] / len(aa_norm))

    return int(lag_ds * step), peak_corr

def align_by_lag(a: np.ndarray, b: np.ndarray, lag: int) -> Tuple[np.ndarray, np.ndarray]:
    """Align b to a by trimming based on lag"""
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

def compute_phase_coherence(a: np.ndarray, b: np.ndarray, fs: int = 48000) -> float:
    """
    Compute phase coherence between two signals using cross-spectral density.
    Returns value in [0, 1] where 1 = perfect coherence.
    """
    if a.size < 512 or b.size < 512:
        return 1.0

    # Limit to max 10 seconds for performance
    n = min(a.size, b.size, fs * 10)
    a = a[:n]
    b = b[:n]

    try:
        # Compute cross-spectral density and auto-spectra
        nperseg = min(2048, n // 4)
        if nperseg < 256:
            return 1.0

        f, Pxy = signal.csd(a, b, fs=fs, nperseg=nperseg)
        f, Pxx = signal.welch(a, fs=fs, nperseg=nperseg)
        f, Pyy = signal.welch(b, fs=fs, nperseg=nperseg)

        # Coherence = |Pxy|^2 / (Pxx * Pyy)
        coherence = np.abs(Pxy)**2 / (Pxx * Pyy + 1e-20)

        # Average coherence in speech/music range (100 Hz - 8 kHz)
        mask = (f >= 100) & (f <= 8000)
        if np.sum(mask) == 0:
            return 1.0

        mean_coherence = float(np.mean(coherence[mask]))
        return min(1.0, max(0.0, mean_coherence))
    except Exception:
        return 1.0

def compute_spectral_correlation(a: np.ndarray, b: np.ndarray, fs: int = 48000) -> float:
    """
    Compute correlation between magnitude spectra.
    Dual-mono should have nearly identical spectral content.
    """
    if a.size < 512 or b.size < 512:
        return 1.0

    n = min(a.size, b.size, fs * 10)
    a = a[:n]
    b = b[:n]

    try:
        nperseg = min(2048, n // 4)
        if nperseg < 256:
            return 1.0

        # Compute magnitude spectra
        f, Pxx = signal.welch(a, fs=fs, nperseg=nperseg)
        f, Pyy = signal.welch(b, fs=fs, nperseg=nperseg)

        # Focus on audible range
        mask = (f >= 20) & (f <= 20000)
        if np.sum(mask) < 10:
            return 1.0

        spec_a = np.log10(Pxx[mask] + 1e-20)
        spec_b = np.log10(Pyy[mask] + 1e-20)

        # Pearson correlation of log-magnitude spectra
        if np.std(spec_a) < 1e-10 or np.std(spec_b) < 1e-10:
            return 1.0

        corr = float(np.corrcoef(spec_a, spec_b)[0, 1])
        return max(-1.0, min(1.0, corr))
    except Exception:
        return 1.0

def compute_snr_db(signal_aligned: np.ndarray, residual: np.ndarray) -> float:
    """
    Compute SNR between aligned signal and residual.
    Higher SNR suggests better match (dual-mono).
    """
    sig_power = np.mean(signal_aligned.astype(np.float64) ** 2)
    res_power = np.mean(residual.astype(np.float64) ** 2)

    if res_power < 1e-20 or sig_power < 1e-20:
        return 100.0  # Perfect match

    snr = 10 * np.log10(sig_power / res_power)
    return float(snr)

def analyze_pair_enhanced(
    L1: np.ndarray,
    R1: np.ndarray,
    *,
    L2: Optional[np.ndarray] = None,
    R2: Optional[np.ndarray] = None,
    fs: int = ANALYSIS_SAMPLE_RATE,
    thresholds: Optional[Dict[str, float]] = None,
    debug: bool = False
) -> Tuple[str, str, Dict[str, float], List[str]]:
    """
    Enhanced dual-mono vs stereo classification with multiple metrics.

    Uses phase coherence, spectral correlation, SNR, and gain stability
    to make more robust decisions.
    """
    if thresholds is None:
        thresholds = THRESHOLD_PROFILES[DEFAULT_PROFILE]

    flags: List[str] = []

    # === Window 1 Analysis ===
    lag1, peak_corr1 = estimate_lag_xcorr(L1, R1, max_lag=2000)
    L1_aligned, R1_aligned = align_by_lag(L1, R1, lag1)

    if L1_aligned.size == 0:
        return "Stereo Left", "Stereo Right", {"error": "alignment_failed"}, ["Alignment failed - defaulting to stereo"]

    # Zero-mean for residual calculation
    L1_zm = L1_aligned.astype(np.float64) - np.mean(L1_aligned)
    R1_zm = R1_aligned.astype(np.float64) - np.mean(R1_aligned)

    # Time-domain metrics
    corr1 = _safe_corrcoef(L1_zm, R1_zm)
    gain1 = best_fit_gain(L1_zm, R1_zm)
    residual1 = R1_zm - (gain1 * L1_zm)
    resid_ratio1 = rms(residual1) / (rms(R1_zm) + 1e-12)
    snr1 = compute_snr_db(gain1 * L1_zm, residual1)

    # Frequency-domain metrics
    phase_coh1 = compute_phase_coherence(L1_aligned, R1_aligned, fs)
    spec_corr1 = compute_spectral_correlation(L1_aligned, R1_aligned, fs)

    metrics1 = PairMetrics(
        corr=corr1,
        gain=gain1,
        resid_ratio=resid_ratio1,
        lag=lag1,
        phase_coherence=phase_coh1,
        spectral_corr=spec_corr1,
        gain_stability=1.0,
        snr_db=snr1
    )

    if debug:
        print(f"    W1: corr={corr1:.4f} resid={resid_ratio1:.4f} lag={lag1} "
              f"phase={phase_coh1:.4f} spec={spec_corr1:.4f} snr={snr1:.1f}dB")

    # === Window 2 Analysis (if available) ===
    metrics2 = None
    if L2 is not None and R2 is not None and L2.size >= fs:
        lag2, peak_corr2 = estimate_lag_xcorr(L2, R2, max_lag=2000)
        L2_aligned, R2_aligned = align_by_lag(L2, R2, lag2)

        if L2_aligned.size > 0:
            L2_zm = L2_aligned.astype(np.float64) - np.mean(L2_aligned)
            R2_zm = R2_aligned.astype(np.float64) - np.mean(R2_aligned)

            corr2 = _safe_corrcoef(L2_zm, R2_zm)
            gain2 = best_fit_gain(L2_zm, R2_zm)
            residual2 = R2_zm - (gain2 * L2_zm)
            resid_ratio2 = rms(residual2) / (rms(R2_zm) + 1e-12)
            snr2 = compute_snr_db(gain2 * L2_zm, residual2)

            phase_coh2 = compute_phase_coherence(L2_aligned, R2_aligned, fs)
            spec_corr2 = compute_spectral_correlation(L2_aligned, R2_aligned, fs)

            # Gain stability check
            gain_stability = 1.0 - abs(gain2 - gain1) / (abs(gain1) + 0.1)
            gain_stability = max(0.0, min(1.0, gain_stability))

            metrics2 = PairMetrics(
                corr=corr2,
                gain=gain2,
                resid_ratio=resid_ratio2,
                lag=lag2,
                phase_coherence=phase_coh2,
                spectral_corr=spec_corr2,
                gain_stability=gain_stability,
                snr_db=snr2
            )

            if debug:
                print(f"    W2: corr={corr2:.4f} resid={resid_ratio2:.4f} lag={lag2} "
                      f"phase={phase_coh2:.4f} spec={spec_corr2:.4f} snr={snr2:.1f}dB "
                      f"gain_stab={gain_stability:.4f}")

    # === Classification Decision ===

    def passes_dual_mono_test(m: PairMetrics, window_name: str) -> Tuple[bool, List[str]]:
        """Check if metrics pass all dual-mono criteria"""
        reasons = []

        if abs(m.corr) < thresholds['corr_min']:
            reasons.append(f"{window_name}: corr {abs(m.corr):.4f} < {thresholds['corr_min']}")

        if m.resid_ratio > thresholds['resid_max']:
            reasons.append(f"{window_name}: resid {m.resid_ratio:.4f} > {thresholds['resid_max']}")

        if abs(m.lag) > thresholds['lag_max']:
            reasons.append(f"{window_name}: lag {abs(m.lag)} > {thresholds['lag_max']}")

        if m.phase_coherence < thresholds['phase_min']:
            reasons.append(f"{window_name}: phase {m.phase_coherence:.4f} < {thresholds['phase_min']}")

        if m.spectral_corr < thresholds['spec_corr_min']:
            reasons.append(f"{window_name}: spec_corr {m.spectral_corr:.4f} < {thresholds['spec_corr_min']}")

        if m.snr_db < thresholds['snr_min_db']:
            reasons.append(f"{window_name}: snr {m.snr_db:.1f}dB < {thresholds['snr_min_db']}dB")

        return len(reasons) == 0, reasons

    # Test window 1
    w1_pass, w1_reasons = passes_dual_mono_test(metrics1, "W1")

    # Test window 2 if available
    w2_pass = True
    w2_reasons = []
    if metrics2 is not None:
        w2_pass, w2_reasons = passes_dual_mono_test(metrics2, "W2")

        # Additional gain stability check
        if metrics2.gain_stability < thresholds['gain_stability_min']:
            w2_pass = False
            w2_reasons.append(f"W2: gain_instability {metrics2.gain_stability:.4f} < {thresholds['gain_stability_min']}")

    # Decision: Both windows must pass
    if w1_pass and w2_pass:
        # Check for polarity inversion
        if metrics1.corr < 0:
            flags.append(f"Polarity-inverted dual-mono (corr={metrics1.corr:.4f})")
        else:
            flags.append(f"Dual-mono confirmed (corr={metrics1.corr:.4f}, snr={metrics1.snr_db:.1f}dB)")

        metrics_out = {
            'corr': metrics1.corr,
            'gain': metrics1.gain,
            'resid_ratio': metrics1.resid_ratio,
            'lag': float(metrics1.lag),
            'phase_coherence': metrics1.phase_coherence,
            'spectral_corr': metrics1.spectral_corr,
            'snr_db': metrics1.snr_db
        }

        if metrics2:
            metrics_out.update({
                'corr2': metrics2.corr,
                'gain_stability': metrics2.gain_stability,
                'snr2_db': metrics2.snr_db
            })

        return "Mono", "Mono", metrics_out, flags

    # Failed dual-mono test - classify as stereo
    if not w1_pass:
        reason_str = "; ".join(w1_reasons[:3])  # Limit output
        flags.append(f"Stereo: {reason_str}")

    if metrics2 and not w2_pass:
        reason_str = "; ".join(w2_reasons[:3])
        flags.append(f"Stereo: {reason_str}")

    # Check if it's clearly decorrelated stereo
    if abs(metrics1.corr) < 0.80 or metrics1.resid_ratio > 0.25:
        flags.append(f"Clear stereo (low correlation/high residual)")

    metrics_out = {
        'corr': metrics1.corr,
        'gain': metrics1.gain,
        'resid_ratio': metrics1.resid_ratio,
        'lag': float(metrics1.lag),
        'phase_coherence': metrics1.phase_coherence,
        'spectral_corr': metrics1.spectral_corr,
        'snr_db': metrics1.snr_db
    }

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
    threshold_profile: str = DEFAULT_PROFILE,
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
        print(f"[DEBUG] Using threshold profile: {threshold_profile}")

    thresholds = THRESHOLD_PROFILES.get(threshold_profile, THRESHOLD_PROFILES[DEFAULT_PROFILE])

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

    # Pair analysis per stream within chosen window, with 2-window confirmation
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

            lab_l, lab_r, m, pair_flags = analyze_pair_enhanced(
                L1, R1, L2=L2, R2=R2, fs=sr, thresholds=thresholds, debug=debug
            )
            labels[g_l] = lab_l
            labels[g_r] = lab_r

            if debug:
                if "corr2" in m:
                    print(
                        f"  [PAIR DEBUG] Ch{g_l}/Ch{g_r}: "
                        f"w1 corr={m['corr']:.3f} resid={m['resid_ratio']:.3f} lag={int(m['lag'])} "
                        f"phase={m['phase_coherence']:.3f} spec={m['spectral_corr']:.3f} | "
                        f"w2 gain_stab={m['gain_stability']:.3f}"
                    )
                else:
                    print(
                        f"  [PAIR DEBUG] Ch{g_l}/Ch{g_r}: "
                        f"corr={m['corr']:.3f} resid={m['resid_ratio']:.3f} lag={int(m['lag'])} "
                        f"phase={m['phase_coherence']:.3f} spec={m['spectral_corr']:.3f}"
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
        description="Enhanced Audio Configuration Classifier with Phase Coherence & Spectral Analysis",
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
    parser.add_argument("--profile", choices=['strict', 'balanced', 'lenient'], default=DEFAULT_PROFILE,
                        help=f"Threshold profile for dual-mono classification (default: {DEFAULT_PROFILE})")
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
    print(f"Found {len(files_to_process)} file(s) to process.")
    print(f"Threshold profile: {args.profile}")
    print()

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
            threshold_profile=args.profile,
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
