#!/usr/bin/env python3
"""
Audio Quality Control Tool
Advanced signal analysis for preservation and edit master validation
"""

import argparse
import json
import subprocess
import csv
import sys
import shlex
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np
from dataclasses import dataclass, field


@dataclass
class QCResult:
    """Results from quality control analysis"""
    filepath: Path
    duration: float = 0.0
    channels: int = 0
    sample_rate: int = 0
    bit_depth: int = 0
    
    # Volume metrics
    peak_level_db: float = -np.inf
    rms_level_db: float = -np.inf
    lufs_integrated: float = -np.inf
    lufs_range: float = 0.0
    true_peak_db: float = -np.inf
    crest_factor: float = 0.0
    
    # Channel metrics
    channel_peaks: List[float] = field(default_factory=list)
    channel_rms: List[float] = field(default_factory=list)
    
    # Phase/correlation
    phase_correlation: float = 0.0
    phase_correlation_min: float = 1.0
    phase_correlation_max: float = 1.0
    stereo_width: float = 0.0
    
    # Spectral analysis
    dc_offset: List[float] = field(default_factory=list)
    spectral_centroid: float = 0.0
    bandwidth: float = 0.0
    
    # Quality warnings
    warnings: List[str] = field(default_factory=list)
    
    # Comparison (for PM/EM pairs)
    comparison_file: Optional[Path] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    duration_diff: Optional[float] = None
    
    status: str = "pass"


class AudioQC:
    """Audio Quality Control analyzer"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ffmpeg = config.get('ffmpeg_path', 'ffmpeg')
        self.ffprobe = config.get('ffprobe_path', 'ffprobe')
        
        # QC thresholds
        self.peak_threshold = config.get('peak_threshold_db', -0.1)
        self.true_peak_threshold = config.get('true_peak_threshold_db', -1.0)
        self.phase_correlation_min = config.get('phase_correlation_min', 0.7)
        self.dc_offset_threshold = config.get('dc_offset_threshold', 0.001)
        self.min_lufs = config.get('min_lufs', -40.0)
        self.max_lufs = config.get('max_lufs', -10.0)
        self.silence_threshold_db = config.get('silence_threshold_db', -60.0)
        self.silence_duration_threshold = config.get('silence_duration_threshold', 0.5)
        
    def analyze_file(self, filepath: Path) -> QCResult:
        """Perform complete QC analysis on audio file"""
        result = QCResult(filepath=filepath)
        
        try:
            # Get basic file info
            self._get_media_info(result)
            
            # Analyze audio levels and quality
            self._analyze_levels(result)
            
            # Analyze phase correlation
            self._analyze_phase(result)
            
            # Analyze spectral content
            self._analyze_spectrum(result)
            
            # Check for silence
            self._detect_silence(result)
            
            # Generate warnings based on thresholds
            self._generate_warnings(result)
            
        except Exception as e:
            result.status = "fail"
            result.warnings.append(f"Analysis failed: {str(e)}")
            
        return result
    
    def _get_media_info(self, result: QCResult):
        """Extract basic media information using ffprobe"""
        cmd = [
            self.ffprobe,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(result.filepath)
        ]
        
        output = subprocess.check_output(cmd, text=True)
        data = json.loads(output)
        
        # Find audio stream
        audio_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break
        
        if not audio_stream:
            raise ValueError("No audio stream found")
        
        result.channels = int(audio_stream.get('channels', 0))
        result.sample_rate = int(audio_stream.get('sample_rate', 0))
        
        # Better bit depth extraction: Check raw bits first (FLAC quirk)
        bits = audio_stream.get('bits_per_raw_sample') or audio_stream.get('bits_per_sample') or 0
        if int(bits) > 0:
            result.bit_depth = int(bits)
        else:
            # Fallback to sample_fmt
            sample_fmt = audio_stream.get('sample_fmt', '')
            if 's16' in sample_fmt:
                result.bit_depth = 16
            elif 's24' in sample_fmt:
                result.bit_depth = 24
            elif 's32' in sample_fmt or 'flt' in sample_fmt or 'dbl' in sample_fmt:
                result.bit_depth = 32
        
        result.duration = float(data.get('format', {}).get('duration', 0))
    
    def _analyze_levels(self, result: QCResult):
        """Analyze audio levels using astats and ebur128"""
        # Escape path for amovie filter just in case of spaces/apostrophes
        safe_path = str(result.filepath).replace("'", r"\'")
        
        # Linear filter chain: Much more stable for ffprobe reading
        filter_complex = (
            "astats=metadata=1:reset=1:measure_perchannel=Peak_level+RMS_level+DC_offset,"
            "ebur128=metadata=1:framelog=verbose"
        )
        
        cmd = [
            self.ffprobe,
            '-f', 'lavfi',
            '-i', f"amovie='{safe_path}',{filter_complex}",
            '-show_entries', 'frame_tags',
            '-print_format', 'json',
            '-v', 'quiet'
        ]
        
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
            data = json.loads(output)
            
            # Process frame data
            channel_peaks = [[] for _ in range(result.channels)]
            channel_rms = [[] for _ in range(result.channels)]
            dc_offsets = [[] for _ in range(result.channels)]
            overall_peaks = []
            overall_rms = []
            lufs_measurements = []
            
            for frame in data.get('frames', []):
                tags = frame.get('tags', {})
                
                # Collect per-channel stats
                for ch in range(result.channels):
                    ch_num = ch + 1
                    peak_key = f'lavfi.astats.{ch_num}.Peak_level'
                    rms_key = f'lavfi.astats.{ch_num}.RMS_level'
                    dc_key = f'lavfi.astats.{ch_num}.DC_offset'
                    
                    if peak_key in tags and tags[peak_key] != '-inf':
                        channel_peaks[ch].append(float(tags[peak_key]))
                    if rms_key in tags and tags[rms_key] != '-inf':
                        channel_rms[ch].append(float(tags[rms_key]))
                    if dc_key in tags:
                        dc_offsets[ch].append(abs(float(tags[dc_key])))
                
                # Overall peak
                if 'lavfi.astats.Overall.Peak_level' in tags:
                    val = tags['lavfi.astats.Overall.Peak_level']
                    if val != '-inf':
                        overall_peaks.append(float(val))
                
                # Overall RMS
                if 'lavfi.astats.Overall.RMS_level' in tags:
                    val = tags['lavfi.astats.Overall.RMS_level']
                    if val != '-inf':
                        overall_rms.append(float(val))
                
                # LUFS measurements
                if 'lavfi.r128.I' in tags:
                    lufs_measurements.append(float(tags['lavfi.r128.I']))
            
            # Calculate results
            if overall_peaks:
                result.peak_level_db = max(overall_peaks)
            if overall_rms:
                result.rms_level_db = np.mean(overall_rms)
            if lufs_measurements:
                result.lufs_integrated = lufs_measurements[-1]  # Final integrated value
            
            # Per-channel metrics
            result.channel_peaks = [max(ch) if ch else -np.inf for ch in channel_peaks]
            result.channel_rms = [np.mean(ch) if ch else -np.inf for ch in channel_rms]
            result.dc_offset = [np.mean(ch) if ch else 0.0 for ch in dc_offsets]
            
            # Calculate crest factor (peak to RMS ratio in dB)
            if result.peak_level_db > -np.inf and result.rms_level_db > -np.inf:
                result.crest_factor = result.peak_level_db - result.rms_level_db
                
        except Exception as e:
            result.warnings.append(f"Level analysis error: {str(e)}")
    
    def _analyze_phase(self, result: QCResult):
        """Analyze phase correlation for stereo content"""
        if result.channels != 2:
            return
            
        safe_path = str(result.filepath).replace("'", r"\'")
            
        cmd = [
            self.ffprobe,
            '-f', 'lavfi',
            '-i', f"amovie='{safe_path}',aphasemeter=video=0",
            '-show_entries', 'frame_tags=lavfi.aphasemeter.phase',
            '-print_format', 'json',
            '-v', 'quiet'
        ]
        
        try:
            output = subprocess.check_output(cmd, text=True)
            data = json.loads(output)
            
            correlations = []
            for frame in data.get('frames', []):
                tags = frame.get('tags', {})
                if 'lavfi.aphasemeter.phase' in tags:
                    correlations.append(float(tags['lavfi.aphasemeter.phase']))
            
            if correlations:
                result.phase_correlation = np.mean(correlations)
                result.phase_correlation_min = min(correlations)
                result.phase_correlation_max = max(correlations)
                
        except Exception as e:
            result.warnings.append(f"Phase analysis error: {str(e)}")
    
    def _analyze_spectrum(self, result: QCResult):
        """Analyze spectral content"""
        # This is a simplified version - could be enhanced with more detailed FFT analysis
        cmd = [
            self.ffmpeg,
            '-i', str(result.filepath),
            '-af', 'aspectralstats',
            '-f', 'null',
            '-'
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True
            )
            
            stderr_output = process.communicate()[1]
            
            # Parse spectral statistics from output
            for line in stderr_output.split('\n'):
                if 'Centroid mean' in line:
                    try:
                        result.spectral_centroid = float(line.split(':')[1].strip().split()[0])
                    except:
                        pass
                elif 'Spread mean' in line:
                    try:
                        result.bandwidth = float(line.split(':')[1].strip().split()[0])
                    except:
                        pass
                        
        except Exception as e:
            result.warnings.append(f"Spectral analysis error: {str(e)}")
    
    def _detect_silence(self, result: QCResult):
        """Detect silence at beginning and end of file"""
        cmd = [
            self.ffmpeg,
            '-i', str(result.filepath),
            '-af', f'silencedetect=n={self.silence_threshold_db}dB:d={self.silence_duration_threshold}',
            '-f', 'null',
            '-'
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True
            )
            
            stderr_output = process.communicate()[1]
            
            silence_starts = []
            silence_ends = []
            
            for line in stderr_output.split('\n'):
                if 'silence_start' in line:
                    try:
                        time = float(line.split('silence_start:')[1].strip())
                        silence_starts.append(time)
                    except:
                        pass
                elif 'silence_end' in line:
                    try:
                        time = float(line.split('silence_end:')[1].split('|')[0].strip())
                        silence_ends.append(time)
                    except:
                        pass
            
            # Check for silence at start
            if silence_ends and silence_ends[0] > self.silence_duration_threshold:
                result.warnings.append(f"Silence at start: {silence_ends[0]:.2f}s")
            
            # Check for silence at end
            if silence_starts and (result.duration - silence_starts[-1]) > self.silence_duration_threshold:
                duration = result.duration - silence_starts[-1]
                result.warnings.append(f"Silence at end: {duration:.2f}s")
                
        except Exception as e:
            pass  # Silence detection is optional
    
    def _generate_warnings(self, result: QCResult):
        """Generate warnings based on analysis"""
        # Peak level warnings
        if result.peak_level_db > self.peak_threshold:
            result.warnings.append(f"Peak level too high: {result.peak_level_db:.2f} dB")
        
        # LUFS warnings
        if result.lufs_integrated > -np.inf:
            if result.lufs_integrated > self.max_lufs:
                result.warnings.append(f"LUFS too loud: {result.lufs_integrated:.1f} LUFS")
            elif result.lufs_integrated < self.min_lufs:
                result.warnings.append(f"LUFS too quiet: {result.lufs_integrated:.1f} LUFS")
        
        # Phase correlation warnings (for stereo)
        if result.channels == 2:
            if result.phase_correlation < self.phase_correlation_min:
                result.warnings.append(f"Phase correlation low: {result.phase_correlation:.3f}")
        
        # DC offset warnings
        for i, offset in enumerate(result.dc_offset):
            if abs(offset) > self.dc_offset_threshold:
                result.warnings.append(f"DC offset on channel {i+1}: {offset:.4f}")
        
        # Per-channel warnings
        for i, peak in enumerate(result.channel_peaks):
            if peak > self.peak_threshold:
                result.warnings.append(f"Channel {i+1} peak too high: {peak:.2f} dB")
    
    def compare_pm_em(self, pm_result: QCResult, em_result: QCResult):
        """Compare Preservation Master and Edit Master files"""
        # Link the results
        pm_result.comparison_file = em_result.filepath
        em_result.comparison_file = pm_result.filepath
        
        # Duration comparison
        pm_result.duration_diff = pm_result.duration - em_result.duration
        em_result.duration_diff = em_result.duration - pm_result.duration
        
        if abs(pm_result.duration_diff) > 0.1:
            warning = f"Duration difference vs {em_result.filepath.name}: {pm_result.duration_diff:.2f}s"
            pm_result.warnings.append(warning)
        
        # Level comparison
        level_diff = pm_result.lufs_integrated - em_result.lufs_integrated
        if abs(level_diff) > 3.0:
            pm_result.warnings.append(f"LUFS difference vs EM: {level_diff:.1f} LUFS")
            em_result.warnings.append(f"LUFS difference vs PM: {-level_diff:.1f} LUFS")
        
        # Spectral comparison
        if pm_result.spectral_centroid > 0 and em_result.spectral_centroid > 0:
            centroid_diff_pct = abs(pm_result.spectral_centroid - em_result.spectral_centroid) / pm_result.spectral_centroid * 100
            if centroid_diff_pct > 10:
                pm_result.warnings.append(f"Spectral centroid differs by {centroid_diff_pct:.1f}%")


def find_file_pairs(files: List[Path]) -> Tuple[List[Path], List[Tuple[Path, Path]]]:
    """Find PM/EM file pairs and standalone files"""
    pm_files = {}
    em_files = {}
    standalone = []
    
    for filepath in files:
        name = filepath.stem
        
        if '_pm' in name.lower():
            base = name.lower().replace('_pm', '')
            pm_files[base] = filepath
        elif '_em' in name.lower():
            base = name.lower().replace('_em', '')
            em_files[base] = filepath
        else:
            standalone.append(filepath)
    
    # Find pairs
    pairs = []
    for base, pm_path in pm_files.items():
        if base in em_files:
            pairs.append((pm_path, em_files[base]))
        else:
            standalone.append(pm_path)
    
    # Add unpaired EM files to standalone
    for base, em_path in em_files.items():
        if base not in pm_files:
            standalone.append(em_path)
    
    return standalone, pairs


def create_visualization(filepath: Path, output_dir: Path, ffmpeg_path: str = 'ffmpeg'):
    """Create advanced QC visualization (Waveform + Spectrum + Vectorscope)"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{filepath.stem}.png"
    
    # Updated: Removed 'format=rgba' from overlay filter to allow auto-negotiation
    filter_complex = (
        "[0:a]asplit=3[a][b][c];"
        # Waveform
        "[a]showwavespic=s=1920x540:split_channels=1:colors=0x3232c8|0x6464dc,format=rgba[wave];"
        # Spectrum
        "[b]showspectrumpic=s=1920x540:legend=1:mode=separate,format=rgba,scale=1920:540[spec];"
        # Vectorscope
        "[c]avectorscope=s=400x400:rate=25:zoom=1:draw=line:rc=0:gc=200:bc=0,"
        "format=rgba,colorchannelmixer=aa=0.7[vec];"
        # Stack
        "[wave][spec]vstack=inputs=2[bg];"
        # Overlay - note NO format=rgba here!
        "[bg][vec]overlay=x=main_w-overlay_w-20:y=20"
    )
    
    cmd = [
        ffmpeg_path,
        '-i', str(filepath),
        '-filter_complex', filter_complex,
        '-frames:v', '1',
        '-y',
        str(output_file)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"\n[!][!] Visualization ERROR for {filepath.name} [!][!]")
        print(f"Command attempted: {' '.join(shlex.quote(s) for s in cmd)}")
        print(f"FFmpeg Stderr Output:\n{e.stderr.decode()}")
        print("-" * 50)
        return None
    except Exception as e:
        print(f"Warning: Could not create visualization for {filepath.name}: {e}")
        return None


def write_csv_report(results: List[QCResult], output_path: Path):
    """Write comprehensive CSV report"""
    headers = [
        'Filepath',
        'Status',
        'Warnings',
        'Duration (s)',
        'Channels',
        'Sample Rate',
        'Bit Depth',
        'Peak Level (dB)',
        'RMS Level (dB)',
        'LUFS Integrated',
        'Crest Factor (dB)',
        'Phase Correlation',
        'DC Offset Ch1',
        'DC Offset Ch2',
        'Spectral Centroid (Hz)',
        'Comparison File',
        'Duration Diff (s)'
    ]
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for r in results:
            dc1 = r.dc_offset[0] if len(r.dc_offset) > 0 else ''
            dc2 = r.dc_offset[1] if len(r.dc_offset) > 1 else ''
            
            row = [
                str(r.filepath),
                r.status,
                '; '.join(r.warnings) if r.warnings else '',
                f'{r.duration:.3f}',
                r.channels,
                r.sample_rate,
                r.bit_depth,
                f'{r.peak_level_db:.2f}' if r.peak_level_db > -np.inf else '',
                f'{r.rms_level_db:.2f}' if r.rms_level_db > -np.inf else '',
                f'{r.lufs_integrated:.1f}' if r.lufs_integrated > -np.inf else '',
                f'{r.crest_factor:.1f}' if r.crest_factor > 0 else '',
                f'{r.phase_correlation:.3f}' if r.phase_correlation != 0 else '',
                f'{dc1:.4f}' if dc1 != '' else '',
                f'{dc2:.4f}' if dc2 != '' else '',
                f'{r.spectral_centroid:.0f}' if r.spectral_centroid > 0 else '',
                str(r.comparison_file.name) if r.comparison_file else '',
                f'{r.duration_diff:.2f}' if r.duration_diff is not None else ''
            ]
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description='Audio Quality Control Tool - Advanced signal analysis for preservation files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('inputs', nargs='+', help='Input audio files or directories')
    parser.add_argument('-o', '--output', help='Output directory for CSV report', type=Path)
    parser.add_argument('-c', '--config', help='Configuration JSON file', type=Path)
    parser.add_argument('-v', '--visualize', action='store_true', help='Create waveform visualizations')
    parser.add_argument('--compare-pairs', action='store_true', help='Compare PM/EM file pairs')
    
    args = parser.parse_args()
    
    # Load configuration
    config = {
        'ffmpeg_path': 'ffmpeg',
        'ffprobe_path': 'ffprobe',
        'peak_threshold_db': -0.1,
        'true_peak_threshold_db': -1.0,
        'phase_correlation_min': 0.7,
        'dc_offset_threshold': 0.001,
        'min_lufs': -40.0,
        'max_lufs': -10.0,
        'silence_threshold_db': -60.0,
        'silence_duration_threshold': 0.5
    }
    
    if args.config and args.config.exists():
        with open(args.config) as f:
            config.update(json.load(f))
    
    # Find input files
    input_files = []
    for input_path in args.inputs:
        path = Path(input_path)
        if path.is_dir():
            # Find all audio files
            for ext in ['*.wav', '*.WAV', '*.flac', '*.FLAC', '*.aiff', '*.AIFF']:
                input_files.extend(path.rglob(ext))
        elif path.is_file():
            input_files.append(path)
    
    if not input_files:
        print("Error: No audio files found!")
        sys.exit(1)

    # Sort files naturally
    input_files.sort()
    
    print(f"Found {len(input_files)} files to analyze")
    
    # Set up output
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    if args.output:
        output_dir = args.output
    else:
        output_dir = Path.home() / 'Desktop'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_output = output_dir / f'audioqc_report_{timestamp}.csv'
    
    # Initialize QC analyzer
    qc = AudioQC(config)
    
    # Find PM/EM pairs if requested
    if args.compare_pairs:
        standalone, pairs = find_file_pairs(input_files)
        pairs.sort(key=lambda p: p[0])
        print(f"Found {len(pairs)} PM/EM pairs and {len(standalone)} standalone files")
    else:
        standalone = input_files
        pairs = []
    
    # Analyze files
    results = []
    
    # Analyze standalone files
    for i, filepath in enumerate(standalone, 1):
        print(f"[{i}/{len(standalone)}] Analyzing: {filepath.name}")
        result = qc.analyze_file(filepath)
        results.append(result)
        
        if args.visualize:
            viz_dir = output_dir / f'{timestamp}_visualizations'
            create_visualization(filepath, viz_dir, config['ffmpeg_path'])
    
    # Analyze pairs
    for i, (pm_path, em_path) in enumerate(pairs, 1):
        print(f"[Pair {i}/{len(pairs)}] Analyzing: {pm_path.name} <-> {em_path.name}")
        
        pm_result = qc.analyze_file(pm_path)
        em_result = qc.analyze_file(em_path)
        
        qc.compare_pm_em(pm_result, em_result)
        
        results.extend([pm_result, em_result])
        
        if args.visualize:
            viz_dir = output_dir / f'{timestamp}_visualizations'
            create_visualization(pm_path, viz_dir, config['ffmpeg_path'])
            create_visualization(em_path, viz_dir, config['ffmpeg_path'])
    
    # Write report
    write_csv_report(results, csv_output)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Analysis complete!")
    print(f"Total files analyzed: {len(results)}")
    print(f"Files with warnings: {sum(1 for r in results if r.warnings)}")
    print(f"Failed analyses: {sum(1 for r in results if r.status == 'fail')}")
    print(f"\nReport saved to: {csv_output}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()