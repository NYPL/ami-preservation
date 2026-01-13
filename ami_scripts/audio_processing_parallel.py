#!/usr/bin/env python3
"""
This script processes audio files for digital preservation with a simplified workflow.
It transcodes audio files and organizes them into PreservationMasters, EditMasters,
and ServiceCopies directories.

Includes verification of matching EM and PM FLAC files, copying of data disc .iso files,
generation of AAC MP4 (M4A) service copies, and a data disc migration test.

Changes included:
- Safe parallel service-copy generation (ThreadPoolExecutor) with a single tqdm bar.
- Per-file ffmpeg logs written to ServiceCopies/*.ffmpeg.log for troubleshooting.
- New CLI flag: --sc-workers (default 2; clamped to <= 4).
"""

import argparse
import subprocess
import shutil
import os
import sys
import logging
import importlib
import re
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from subprocess import CalledProcessError
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed


# Centralized glob patterns
PATTERNS = {
    'pm_aea': "**/*_pm.aea",
    'pm_wav': "**/*_pm.wav",
    'em_wav': "**/*_em.wav",
    'wav': "**/*.wav",
    'cue': "**/*.cue",
    'csv': "**/*.csv",
    'iso': "**/*.iso",
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Enum for different workflow types."""
    MINIDISC = "minidisc"
    STANDARD = "standard"  # applies to CDs and other analog formats


@dataclass
class ProcessingConfig:
    """Configuration class for processing parameters."""
    source_dir: Path
    dest_dir: Path
    model: str = 'medium'
    output_format: str = 'vtt'
    transcribe: bool = False
    sc_workers: int = 2  # NEW: parallel workers for ServiceCopies


    @property
    def new_dest_dir(self) -> Path:
        """Get the new destination directory path."""
        return self.dest_dir / self.source_dir.name


class SimplifiedAudioProcessor:
    """Simplified audio processor for transcoding and basic file organization."""

    # Class constants
    SUPPORTED_MODELS = ['tiny', 'base', 'small', 'medium', 'large']
    SUPPORTED_FORMATS = ['vtt', 'srt', 'txt', 'json']
    MEDIA_EXTENSIONS = {'.flac'}
    FLAC_COMMAND_BASE = ['flac', '--best', '--preserve-modtime', '--verify']
    FFMPEG_FALLBACK_PARAMS = [
        '-c:a', 'flac',
        '-compression_level', '12',
        '-af', 'aformat=sample_fmts=s32',
        '-sample_fmt', 's32',
        '-bits_per_raw_sample', '24'
    ]

    def __init__(self, config: ProcessingConfig):
        """Initialize the SimplifiedAudioProcessor with configuration."""
        self.config = config
        self.fallback_files: List[Path] = []

    def process(self) -> None:
        """Main processing method that orchestrates the entire workflow."""
        try:
            self._verify_directories()
            self._initial_summary()
            workflow_type = self._detect_workflow()

            if workflow_type == WorkflowType.MINIDISC:
                self._process_minidisc_workflow()
            else:
                self._process_standard_workflow()

            # Verify matching EM and PM FLAC files
            self._verify_matching_flacs()

            # Log final FLAC counts
            self._final_summary()

        except Exception as e:
            logger.exception(f"Processing failed: {e}")
            raise

    def _verify_directories(self) -> None:
        """Verify source directory exists and create base destination directory."""
        if not self.config.source_dir.exists():
            raise FileNotFoundError(f"{self.config.source_dir} doesn't exist")
        if not self.config.source_dir.is_dir():
            raise NotADirectoryError(f"{self.config.source_dir} is not a directory")

        self.config.new_dest_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created base destination: {self.config.new_dest_dir}")

    def _initial_summary(self) -> None:
        """Log counts of EM/PM WAV, PM AEA, and ISO files before processing."""
        counts = {
            'PM AEA': len(list(self.config.source_dir.rglob(PATTERNS['pm_aea']))),
            'PM WAV': len(list(self.config.source_dir.rglob(PATTERNS['pm_wav']))),
            'EM WAV': len(list(self.config.source_dir.rglob(PATTERNS['em_wav']))),
            'ISO': len(list(self.config.source_dir.rglob(PATTERNS['iso']))),
        }
        logger.info("Initial file summary: " + ", ".join(f"{k}: {v}" for k, v in counts.items()))

    def _detect_workflow(self) -> WorkflowType:
        """Detect which workflow to use based on file types present."""
        if list(self.config.source_dir.rglob(PATTERNS['pm_aea'])):
            logger.info("Minidisc package detected: using Minidisc workflow")
            return WorkflowType.MINIDISC
        return WorkflowType.STANDARD

    def _make_work_dirs(self) -> Tuple[Path, Path, Path]:
        """Create and return PreservationMasters, EditMasters, and ServiceCopies directories."""
        base = self.config.new_dest_dir
        pm_dir = base / "PreservationMasters"
        em_dir = base / "EditMasters"
        sc_dir = base / "ServiceCopies"

        pm_dir.mkdir(parents=True, exist_ok=True)
        em_dir.mkdir(parents=True, exist_ok=True)
        sc_dir.mkdir(parents=True, exist_ok=True)

        return pm_dir, em_dir, sc_dir

    def _process_minidisc_workflow(self) -> None:
        """Process files using the Minidisc Workflow."""
        logger.info("Starting Minidisc Workflow")
        pm_dir, em_dir, sc_dir = self._make_work_dirs()

        self._copy_preservation_masters_minidisc(pm_dir)
        self._process_edit_masters_minidisc(em_dir)

        # Generate Service Copies from the newly processed EM files (parallel)
        self._generate_service_copies(em_dir, sc_dir)

        if self.config.transcribe:
            self._transcribe_directory()

        logger.info("Minidisc workflow completed")

    def _process_standard_workflow(self) -> None:
        """Process files using the Standard Workflow."""
        logger.info("Starting Standard Workflow")
        pm_dir, em_dir, sc_dir = self._make_work_dirs()

        # Copy data-disc ISO files
        self._copy_iso_files(pm_dir)

        # Gather all WAVs once
        wav_files = self._get_clean_files(self.config.source_dir.rglob(PATTERNS['wav']))
        wav_files = sorted(wav_files, key=lambda p: p.name)  # sort by filename

        # Transcode with a tqdm bar that names each file
        pbar = tqdm(wav_files, unit="file", dynamic_ncols=True)
        for wav in pbar:
            pbar.set_description(f"Transcoding {wav.name}")
            output_file = self.config.new_dest_dir / f"{wav.stem}.flac"
            if not self._transcode_single_file(wav, output_file):
                self._handle_transcode_failure(wav, output_file)

        # After bar completes, report any fallbacks
        self._report_fallback_files()

        # Organize into PM/EM dirs
        self._organize_files(pm_dir, em_dir)

        # Generate Service Copies from the organized EM files (parallel)
        self._generate_service_copies(em_dir, sc_dir)

        if self.config.transcribe:
            self._transcribe_directory()

        logger.info("Standard workflow completed")

    def _encode_service_copy_one(self, flac: Path, dest_dir: Path) -> Tuple[Path, bool, str]:
        """
        Encode one FLAC -> M4A service copy.

        Returns: (output_file, success, error_message)

        Writes ffmpeg stderr to a per-file log to keep the console clean and allow
        troubleshooting if a job stalls or fails.
        """
        new_stem = flac.stem.replace('_em', '_sc')
        output_file = dest_dir / f"{new_stem}.m4a"
        log_file = dest_dir / f"{new_stem}.ffmpeg.log"

        command = [
            "ffmpeg",
            "-y",  # Overwrite output files without asking
            "-i", str(flac),
            "-threads", "0",
            "-c:a", "aac",
            "-b:a", "320k",
            "-movflags", "+faststart",
            "-ar", "48000",
            str(output_file)
        ]

        try:
            with open(log_file, "w", encoding="utf-8") as lf:
                proc = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=lf,
                    text=True
                )
                rc = proc.wait()

            if rc != 0:
                return output_file, False, f"ffmpeg exit code {rc} (see {log_file.name})"

            return output_file, True, ""
        except Exception as e:
            return output_file, False, str(e)

    def _generate_service_copies(self, source_dir: Path, dest_dir: Path) -> None:
        """Generate AAC M4A service copies from FLAC files in the source directory (parallel)."""
        logger.info("Generating Service Copies (parallel)...")
        dest_dir.mkdir(parents=True, exist_ok=True)

        flac_files = sorted(self._get_clean_files(source_dir.glob("*.flac")), key=lambda p: p.name)
        if not flac_files:
            logger.warning(f"No FLAC files found in {source_dir} to generate Service Copies from.")
            return

        max_cpu = os.cpu_count() or 2
        workers = max(1, min(self.config.sc_workers, max_cpu))
        # "Safe parallel": cap at 4 unless you really know your storage/CPU can take more
        workers = min(workers, 4)

        logger.info(f"Service copy workers: {workers}")

        failures: List[Tuple[Path, str]] = []

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(self._encode_service_copy_one, flac, dest_dir): flac
                for flac in flac_files
            }

            pbar = tqdm(total=len(futures), unit="file", dynamic_ncols=True, desc="ServiceCopies")
            for fut in as_completed(futures):
                flac = futures[fut]
                try:
                    output_file, ok, err = fut.result()
                    if not ok:
                        failures.append((flac, err))
                        logger.error(f"SC failed for {flac.name}: {err}")
                    else:
                        logger.debug(f"SC created: {output_file.name}")
                except Exception as e:
                    failures.append((flac, str(e)))
                    logger.error(f"SC failed for {flac.name}: {e}")
                finally:
                    pbar.update(1)
            pbar.close()

        if failures:
            logger.warning("Some service copy encodes failed:")
            for flac, err in failures:
                logger.warning(f"  {flac.name}: {err}")
        else:
            logger.info("Service copy generation completed without errors.")


    def _copy_iso_files(self, pm_dir: Path) -> None:
        """Copy .iso files from source to PreservationMasters."""
        for iso in self._get_clean_files(self.config.source_dir.rglob(PATTERNS['iso'])):
            shutil.copy2(iso, pm_dir)
            logger.info(f"Copied ISO file: {iso.name}")

    def _copy_preservation_masters_minidisc(self, pm_dir: Path) -> None:
        """Copy preservation master files for Minidisc workflow."""
        for aea_file in self._get_clean_files(self.config.source_dir.rglob(PATTERNS['pm_aea'])):
            shutil.copy2(aea_file, pm_dir)
            logger.info(f"Copied PM AEA: {aea_file.name}")
        for csv_file in self._get_clean_files(self.config.source_dir.rglob(PATTERNS['csv'])):
            shutil.copy2(csv_file, pm_dir)
            logger.info(f"Copied CSV: {csv_file.name}")

    def _process_edit_masters_minidisc(self, em_dir: Path) -> None:
        """Process edit master files for Minidisc workflow."""
        for wav in self._get_clean_files(self.config.source_dir.rglob(PATTERNS['em_wav'])):
            logger.info(f"Transcoding {wav.name} to FLAC")
            output_flac = em_dir / f"{wav.stem}.flac"
            if self._transcode_single_file(wav, output_flac):
                logger.info(f"Successfully transcoded: {output_flac.name}")
            else:
                logger.error(f"Failed to transcode: {wav.name}")

    def _verify_matching_flacs(self) -> None:
        """Ensure matching EM and PM FLAC files (names and counts)."""
        pm_dir = self.config.new_dest_dir / "PreservationMasters"
        em_dir = self.config.new_dest_dir / "EditMasters"
        pm_files = {f.stem.replace('_pm', '') for f in pm_dir.glob("*.flac")}
        em_files = {f.stem.replace('_em', '') for f in em_dir.glob("*.flac")}

        missing_pm = em_files - pm_files
        missing_em = pm_files - em_files

        if missing_pm or missing_em:
            logger.error("Mismatch between EM and PM FLAC files:")
            if missing_pm:
                logger.error(f" EM files without PM: {missing_pm}")
            if missing_em:
                logger.error(f" PM files without EM: {missing_em}")
            sys.exit(1)
        else:
            logger.info("All EM and PM FLAC files match.")

    def _final_summary(self) -> None:
        """Log counts of PM and EM FLAC files after processing."""
        pm_count = len(list((self.config.new_dest_dir / "PreservationMasters").glob("*.flac")))
        em_count = len(list((self.config.new_dest_dir / "EditMasters").glob("*.flac")))
        sc_count = len(list((self.config.new_dest_dir / "ServiceCopies").glob("*.m4a")))
        logger.info(f"Final file summary: PM FLAC: {pm_count}, EM FLAC: {em_count}, Service Copies: {sc_count}")

    def _transcode_single_file(self, input_file: Path, output_file: Path) -> bool:
        """Transcode a single file from input to output format (with subprocess.run)."""
        flac_command = self.FLAC_COMMAND_BASE + [str(input_file), '-o', str(output_file)]
        try:
            result = subprocess.run(flac_command, capture_output=True, text=True, check=True)
            logger.debug(result.stdout)
            return True
        except CalledProcessError as e:
            logger.error(f"FLAC transcoding failed for {input_file.name}: {e.stderr}")
            return False

    def _handle_transcode_failure(self, input_file: Path, output_file: Path) -> None:
        """Handle transcoding failure with FFmpeg fallback for 32-bit float files."""
        if self._is_32bit_float(input_file):
            logger.info(f"Detected 32-bit float WAV for {input_file}. Attempting FFmpeg fallback.")
            ffmpeg_command = ['ffmpeg', '-i', str(input_file)] + self.FFMPEG_FALLBACK_PARAMS + [str(output_file)]
            try:
                subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
                logger.info(f"Successfully transcoded {input_file.name} using FFmpeg fallback.")
                self.fallback_files.append(input_file)
            except CalledProcessError as e:
                logger.error(f"FFmpeg fallback failed for {input_file.name}: {e.stderr}")
        else:
            logger.error(f"Transcoding failed for {input_file.name} and it's not a 32-bit float WAV. Skipping fallback.")

    def _report_fallback_files(self) -> None:
        """Report files that required FFmpeg fallback."""
        if self.fallback_files:
            logger.warning("FFmpeg fallback occurred for the following files:")
            for f in self.fallback_files:
                logger.warning(f"  {f}")

    def _is_32bit_float(self, file: Path) -> bool:
        """
        Simplified 32-bit float detection using mediainfo. Fallback to false if unavailable.
        """
        try:
            bitdepth = subprocess.run([
                'mediainfo', '--Language=raw', '--Full',
                '--Inform=Audio;%BitDepth%', str(file)
            ], capture_output=True, text=True, check=True).stdout.strip()
            if bitdepth == "32":
                fmt = subprocess.run([
                    'mediainfo', '--Language=raw', '--Full',
                    '--Inform=Audio;%Format%', str(file)
                ], capture_output=True, text=True, check=True).stdout.lower()
                return 'float' in fmt
        except CalledProcessError:
            logger.debug(f"Mediainfo unavailable for {file.name}, assuming standard format")
        return False

    def _organize_files(self, pm_dir: Path, em_dir: Path) -> None:
        """Organize files into PreservationMasters and EditMasters directories."""
        # Move PM FLACs in sorted order
        pm_files = sorted(
            self._get_clean_files(self.config.new_dest_dir.glob("*pm.flac")),
            key=lambda p: p.name
        )
        for file in pm_files:
            shutil.move(str(file), pm_dir / file.name)
            logger.info(f"Moved PM file: {file.name}")

        # Move EM FLACs in sorted order
        em_files = sorted(
            self._get_clean_files(self.config.new_dest_dir.glob("*em.flac")),
            key=lambda p: p.name
        )
        for file in em_files:
            shutil.move(str(file), em_dir / file.name)
            logger.info(f"Moved EM file: {file.name}")

        # Copy CUE and CSV
        self._batch_copy('cue', pm_dir, "Copied CUE file")
        self._batch_copy('csv', pm_dir, "Copied CSV file")
        # Move transcription outputs
        self._move_transcription_files(em_dir)

    def _batch_copy(self, pattern_key: str, target: Path, log_msg: str) -> None:
        """Generic copy for cue, csv, etc., using centralized patterns."""
        for f in self._get_clean_files(self.config.source_dir.rglob(PATTERNS[pattern_key])):
            shutil.copy2(f, target)
            logger.info(f"{log_msg}: {f.name}")

    def _move_transcription_files(self, em_dir: Path) -> None:
        """Move transcription files to EditMasters directory."""
        for file in self._get_clean_files(self.config.new_dest_dir.rglob(f"*.{self.config.output_format}")):
            shutil.move(str(file), em_dir / file.name)
            logger.info(f"Moved transcription file: {file.name}")

    def _transcribe_directory(self) -> None:
        """Transcribe audio files using Whisper."""
        import whisper  # now safe because we early-exit in main
        model = whisper.load_model(self.config.model)

        em_dir = self.config.new_dest_dir / "EditMasters"
        targets = list(em_dir.glob("*.flac")) if em_dir.exists() else []
        if not targets:
            targets = [f for f in self.config.new_dest_dir.rglob("*.flac") if 'em' in f.stem]

        for file in targets:
            logger.info(f"Processing transcription for {file.name}")
            try:
                resp = model.transcribe(str(file), verbose=True)
                writer = whisper.utils.get_writer(self.config.output_format, str(file.parent))
                writer(resp, file.stem)
                logger.info(f"Transcription completed for {file.name}")
            except Exception as e:
                logger.error(f"Transcription failed for {file.name}: {e}")

    @staticmethod
    def _module_exists(module_name: str) -> bool:
        """Check if a Python module exists."""
        return importlib.util.find_spec(module_name) is not None

    @staticmethod
    def _get_clean_files(file_iterator) -> List[Path]:
        """Filter out hidden files (starting with '._')."""
        return [file for file in file_iterator if not file.name.startswith("._")]


def check_data_disc_migrations(destination_directory: Path) -> List[Path]:
    """Identify directories with .iso files but no EditMasters folder."""
    migrations = []
    for id_folder in destination_directory.glob("*"):
        if id_folder.is_dir():
            iso_files = list(id_folder.rglob(PATTERNS['iso']))
            em_dirs = list(id_folder.rglob("**/EditMasters"))
            if iso_files and not em_dirs:
                migrations.append(id_folder)
    return migrations


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description='Simplified audio file transcoding and organization tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-s', '--source',
        help='path to the source directory of audio files',
        type=validate_directory,
        metavar='SOURCE_DIR',
        required=True
    )
    parser.add_argument(
        '-d', '--destination',
        help='path to the output directory',
        type=validate_directory,
        metavar='DEST_DIR',
        required=True
    )
    parser.add_argument(
        '-m', '--model',
        default='medium',
        choices=SimplifiedAudioProcessor.SUPPORTED_MODELS,
        help='The Whisper model to use for transcription'
    )
    parser.add_argument(
        '-f', '--format',
        default='vtt',
        choices=SimplifiedAudioProcessor.SUPPORTED_FORMATS,
        help='The subtitle output format'
    )
    parser.add_argument(
        '-t', '--transcribe',
        action='store_true',
        help='Transcribe the audio files using Whisper'
    )
    parser.add_argument(
        '--sc-workers',
        type=int,
        default=2,
        help='Number of parallel ffmpeg jobs for ServiceCopies (keep modest: 2–4)'
    )
    return parser


def validate_directory(path: str) -> Path:
    """Validate that the provided path is a directory."""
    path_obj = Path(path)
    if not path_obj.is_dir():
        raise argparse.ArgumentTypeError(f"{path} is not a valid directory.")
    return path_obj


def main() -> None:
    """Main entry point for the script."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Early-exit on missing Whisper dependency
    if args.transcribe and importlib.util.find_spec('whisper') is None:
        parser.error("Whisper is not installed. Please install with 'pip3 install -U openai-whisper'.")

    config = ProcessingConfig(
        source_dir=args.source,
        dest_dir=args.destination,
        model=args.model,
        output_format=args.format,
        transcribe=args.transcribe,
        sc_workers=args.sc_workers,
    )

    try:
        processor = SimplifiedAudioProcessor(config)
        processor.process()

        # Data disc migration test
        migrations = check_data_disc_migrations(config.new_dest_dir)
        if migrations:
            print("The following directories appear to be data-disc migrations without Edit Master folders:")
            for m in migrations:
                print(f"  {m}")
            print()

        logger.info("Processing completed successfully!")
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
    except Exception as e:
        logger.exception(f"Processing failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()