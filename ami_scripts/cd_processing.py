#!/usr/bin/env python3
"""
Process directories of CD WAV files using accompanying CUE files to concatenate tracks in the correct order using shntool.
If only one WAV is present, simply copy and rename instead of attempting to join.
Handles named tracks, diacritics, and falls back to alphabetical listing when necessary, ensuring unmatched tracks are filled.
* Default (join) mode  →  concatenate per‑track WAVs into a single master.
* Split mode (-s/--split) →  split a single master WAV/FLAC + CUE back into
    individual tracks (Track01.wav, Track02.wav, …).
"""
import argparse
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
import json


def strip_accents(txt: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn"
    ).casefold()

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

# ── EDIT-MASTER LOGIC ──────────────────────────────────────────────────────
TARGET_I   = -23.0          # EBU R128 target integrated loudness
TARGET_LRA = 7.0            # target loudness range
TARGET_TP  = -2.0           # target true-peak
TOLERANCE  = 1.0            # ±1 LU

def _probe_audio(wav: Path) -> tuple[int, int]:
    """
    Return (sample_rate, bit_depth).  Falls back to (44100, 16).
    """
    cmd = ["ffprobe", "-v", "error",
           "-select_streams", "a:0",
           "-show_entries", "stream=sample_rate,bits_per_raw_sample,bits_per_sample",
           "-of", "default=noprint_wrappers=1:nokey=1",
           str(wav)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()
    sr = next((int(v) for v in out if v.isdigit() and int(v) > 1000), 44100)
    bd = next((int(v) for v in out if v.isdigit() and int(v) in (16, 24, 32)), 16)
    return sr, bd

def measure_loudness(wav: Path) -> float | None:
    cmd = [
        "ffmpeg", "-nostats", "-i", str(wav),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    # find every “I: <number> LUFS”
    values = re.findall(r"\bI:\s*(-?\d+(?:\.\d*)?) LUFS", proc.stderr)
    if not values:
        return None
    try:
        # the last match is the summary “Integrated loudness”
        return float(values[-1])
    except ValueError:
        return None

def create_edit_master(pm_wav: Path, em_dir: Path) -> None:
    em_dir.mkdir(exist_ok=True)
    base = pm_wav.stem.replace("_pm", "_em") if "_pm" in pm_wav.stem else pm_wav.stem + "_em"
    # Determine correct extension: .wav or .flac for loudnorm output
    orig_ext = pm_wav.suffix.lower()
    out_ext = orig_ext if orig_ext in ('.wav', '.flac') else '.wav'
    em_wav = em_dir / f"{base}{out_ext}"

    # Preserve original sample rate & bit depth
    sample_rate, bit_depth = _probe_audio(pm_wav)
    codec = "pcm_s16le" if bit_depth <= 16 else "pcm_s24le"

    # ── FIRST PASS: MEASURE ────────────────────────────────────────────────
    print(f"   ↳ {pm_wav.name}: running first-pass loudnorm analysis…")
    analysis_filter = (
        f"loudnorm=dual_mono=true:"
        f"I={TARGET_I}:LRA={TARGET_LRA}:TP={TARGET_TP}:print_format=json"
    )
    proc = subprocess.run(
        ["ffmpeg", "-y", "-nostats", "-i", str(pm_wav),
         "-af", analysis_filter,
         "-f", "null", "-"],
        stderr=subprocess.PIPE, text=True
    )
    stderr = proc.stderr

    # If no JSON found, dump last lines and copy unchanged
    if "{" not in stderr:
        print(f"     ⚠  could not find JSON in ffmpeg output; copying as-is.")
        print("     └─ stderr preview:")
        print("\n".join(stderr.splitlines()[-10:]))
        shutil.copy2(pm_wav, em_wav)
        return

    # Extract JSON blob between first '{' and last '}'
    start = stderr.find("{")
    end   = stderr.rfind("}") + 1
    try:
        stats = json.loads(stderr[start:end])
    except Exception as e:
        print(f"     ⚠  JSON parse error ({e}); copying as-is.")
        print(stderr[start:end])
        shutil.copy2(pm_wav, em_wav)
        return

    # Cast all values to float for formatting & calculation
    input_i      = float(stats["input_i"])
    input_lra    = float(stats["input_lra"])
    input_tp     = float(stats["input_tp"])
    input_thresh = float(stats["input_thresh"])
    offset       = float(stats["target_offset"])

    print(f"     measured: I={input_i:.1f}, "
          f"LRA={input_lra:.1f}, TP={input_tp:.1f}, "
          f"offset={offset:.2f}")

    # If already within tolerance: copy WAV/FLAC, but re-encode AEA (or other) via FFmpeg
    if abs(input_i - TARGET_I) <= TOLERANCE:
        if orig_ext in ('.wav', '.flac'):
            print(f"     within ±{TOLERANCE} LU → copying without change.")
            shutil.copy2(pm_wav, em_wav)
        else:
            print(f"     within ±{TOLERANCE} LU → re-encoding {orig_ext[1:]} → PCM WAV for playback.")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(pm_wav),
                "-ar", str(sample_rate),
                "-c:a", codec,
                str(em_wav),
            ], check=True)
        return

    # ── SECOND PASS: NORMALIZE ─────────────────────────────────────────────
    print(f"     normalizing {input_i:.1f} → {TARGET_I} LUFS")
    normalize_filter = (
        f"loudnorm=I={TARGET_I}:LRA={TARGET_LRA}:TP={TARGET_TP}:"
        f"measured_I={input_i}:measured_LRA={input_lra}:"
        f"measured_TP={input_tp}:measured_thresh={input_thresh}:offset={offset}"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(pm_wav),
        "-af", normalize_filter,
        "-ar", str(sample_rate),
        "-c:a", codec,
        str(em_wav),
    ], check=True)

    print(f"     → wrote {em_wav.name}")

def safe_copy(src: Path, dst: Path, label: str = "file") -> None:
    """Copy src → dst but warn instead of crashing if something goes wrong."""
    try:
        shutil.copy2(src, dst)
    except Exception as e:                 # noqa: BLE001
        print(f"⚠  Could not copy {label} for {src.parent.name}: {e}")

def parse_cue_file(cue_path: Path) -> list[dict]:
    """
    Parse a CUE file and return track information including titles and performers.
    Handles complex CUE files with different indentation patterns.
    """
    tracks = []
    current_track = None
    in_track_section = False
    
    try:
        content = cue_path.read_text(encoding="utf-8", errors="ignore")
        
        # Print the first 500 chars of the CUE file for debugging
        print(f"CUE file sample:\n{content[:500]}...\n")
        
        # First extract all track sections with their indices
        track_sections = []
        track_pattern = re.compile(r'(\s*)TRACK\s+(\d+)\s+AUDIO\s*(.*?)(?=(?:\s*TRACK\s+\d+\s+AUDIO)|$)', 
                                   re.DOTALL)
        
        for match in track_pattern.finditer(content):
            track_num = int(match.group(2))
            section_text = match.group(0) + match.group(3)
            track_sections.append((track_num, section_text))
        
        print(f"Found {len(track_sections)} track sections in CUE file")
        
        # Process each track section
        for track_num, section in track_sections:
            track_info = {"number": track_num, "title": "", "performer": ""}
            
            # Extract title
            title_match = re.search(r'TITLE\s+"([^"]+)"', section)
            if title_match:
                track_info["title"] = title_match.group(1)
                print(f"Track {track_num} title: {track_info['title']}")
            
            # Extract performer
            performer_match = re.search(r'PERFORMER\s+"([^"]+)"', section)
            if performer_match:
                track_info["performer"] = performer_match.group(1)
                print(f"Track {track_num} performer: {track_info['performer']}")
                
            tracks.append(track_info)
        
        # Sort tracks by track number for safety
        tracks.sort(key=lambda x: x["number"])
            
    except Exception as e:
        print(f"Error parsing CUE file {cue_path}: {e}")
        import traceback
        traceback.print_exc()
    
    return tracks

# ── JOIN LOGIC ─────────────────────────────────────────────────────────────
def join_discs(root: Path, prefix: str, make_edit: bool) -> None:
    """
    Pass 1  →  create Preservation Masters for every disc.
    Pass 2  →  (optional) create loudness‑checked Edit Masters.
    """
    processed_dir = root / "Processed"
    pm_dir = root / "PreservationMasters"
    em_dir = root / "EditMasters"
    processed_dir.mkdir(exist_ok=True)
    pm_dir.mkdir(exist_ok=True)
    if make_edit:
        em_dir.mkdir(exist_ok=True)

    pm_files: list[Path] = []          # remember all PMs for the 2nd pass

    # ── PASS 1: JOIN PER DISC ────────────────────────────────────────────
    for disc_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if disc_dir.name in ("Processed", "PreservationMasters", "EditMasters"):
            continue
        if not (disc_dir.name.isdigit() and len(disc_dir.name) == 6):
            print(f"Skipping {disc_dir.name}: not a six‑digit ID.")
            continue
        print(f"\nNow processing 💿 {disc_dir.name}\n")
        # only real .cue files, not macOS AppleDouble sidecars:
        # ── find the directory that actually holds the .cue + .wav files ──
        work_dir = disc_dir
        cue_files = [p for p in work_dir.glob("*.cue") if not p.name.startswith("._")]

        # if there was no .cue at this level, look one level down
        if not cue_files:
            subdirs = [d for d in disc_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1:
                work_dir = subdirs[0]
                cue_files = [p for p in work_dir.glob("*.cue") if not p.name.startswith("._")]
                print(f"Using subdirectory `{work_dir.name}` for assets")
        
        if not cue_files:
            print(f"No .cue file in {disc_dir.name}, skipping.")
            continue

        cue_path = cue_files[0]

        track_info = parse_cue_file(cue_path)

        # now gather your WAVs from the same work_dir
        all_wavs = [p for p in work_dir.glob("*.wav")]
        if not all_wavs:
            print(f"No WAVs in {disc_dir.name} (or its only subdir), skipping.")
            continue

        def norm(p: Path | str) -> str:
            """
            Aggressive normaliser:
            • strip accents
            • case‑fold to lower
            • map all punctuation to spaces
            • retain only a‑z 0‑9 and single spaces
            """
            text = p.stem if isinstance(p, Path) else p
            text = strip_accents(text).casefold()

            # replace Unicode punctuation (including curly apostrophes, dashes, etc.)
            text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)

            # keep only a‑z 0‑9 and spaces, then collapse whitespace
            text = re.sub(r"[^a-z0-9\s]+", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            return text

        # Map wavs by normalized name for easier matching
        exact_map = {norm(w): w for w in all_wavs}
        
        used, ordered = set(), []

        # Use CUE track info to order WAVs
        if track_info:
            print(f"Found {len(track_info)} tracks in CUE file")
            
            for track in track_info:
                title = track.get("title", "")
                performer = track.get("performer", "")
                track_num = track.get("number", 0)
                print(f"\nProcessing track {track_num}: '{title}' by '{performer}'")
                
                search_terms = []
                
                # Add exact title+performer combinations first (highest priority)
                if performer and title:
                    search_terms.append(f"{performer} - {title}")
                
                # Add title and performer separately
                if title:
                    search_terms.append(title)
                if performer:
                    search_terms.append(performer)
                    
                # Add performer-title variations if both exist
                if performer and title:
                    search_terms.append(f"{performer} {title}")
                
                chosen = None
                matched_term = None
                
                print(f"Search terms: {search_terms}")
                
                # Try exact matches first (highest priority)
                for term in search_terms:
                    norm_term = norm(term)
                    if norm_term in exact_map and exact_map[norm_term] not in used:
                        chosen = exact_map[norm_term]
                        matched_term = term
                        print(f"Exact match found for term: '{term}'")
                        break
                
                # If no exact match, try partial matches with filename containing the term
                if not chosen:
                    for term in search_terms:
                        norm_term = norm(term)
                        # Try performers first if available
                        if term == performer:
                            cands = [w for w in all_wavs if norm_term in norm(w) and w not in used]
                            if cands:
                                chosen = sorted(cands, key=lambda p: len(p.name))[0]
                                matched_term = f"performer partial: '{term}'"
                                print(f"Partial match found with performer: '{term}'")
                                break
                    
                    # If still no match, try with any search term
                    if not chosen:
                        print("Trying broader partial matches...")
                        for term in search_terms:
                            norm_term = norm(term)
                            cands = [w for w in all_wavs if norm_term in norm(w) and w not in used]
                            if cands:
                                chosen = sorted(cands, key=lambda p: len(p.name))[0]
                                matched_term = f"partial: '{term}'"
                                print(f"Partial match found for term: '{term}'")
                                break
                
                # Last resort: try with individual words from the title or performer
                if not chosen and (title or performer):
                    words = []
                    if title:
                        words.extend([w for w in re.split(r'\W+', title) if len(w) > 3])
                    if performer:
                        words.extend([w for w in re.split(r'\W+', performer) if len(w) > 3])
                    
                    print(f"Trying individual keywords: {words}")
                    for word in words:
                        norm_word = norm(word)
                        cands = [w for w in all_wavs if norm_word in norm(w) and w not in used]
                        if cands:
                            chosen = sorted(cands, key=lambda p: len(p.name))[0]
                            matched_term = f"keyword: '{word}'"
                            print(f"Keyword match found for: '{word}'")
                            break
                
                if chosen:
                    ordered.append(chosen)
                    used.add(chosen)
                    print(f"Matched track {track_num}: '{title}' → {chosen.name} via {matched_term}")
                else:
                    ordered.append(None)
                    print(f"Warning: Track {track_num} '{title}' unmatched in {disc_dir.name}")
                    
                # Print remaining unused files for debugging
                if not chosen:
                    print(f"Remaining unused files: {[w.name for w in all_wavs if w not in used]}")

            # Fill in any unmatched tracks with remaining files
            remaining = [w for w in sorted(all_wavs) if w not in used]
            for i, v in enumerate(ordered):
                if v is None and remaining:
                    next_file = remaining.pop(0)
                    ordered[i] = next_file
                    print(f"Filling unmatched track {i+1} with: {next_file.name}")
            
            # Add any remaining WAVs at the end
            for remaining_wav in remaining:
                ordered.append(remaining_wav)
                print(f"Adding remaining unused WAV at end: {remaining_wav.name}")
        else:
            print("No valid track info in CUE file, falling back to alphabetical order")
            ordered = sorted(all_wavs)

        # Filter out any None values that might remain
        ordered = [o for o in ordered if o is not None]
        
        # Print the final ordering for confirmation
        print("\nFinal track order:")
        for i, wav in enumerate(ordered):
            print(f"{i+1}: {wav.name}")

        out_base = f"{prefix}_{disc_dir.name}_v01f01_pm"
        out_wav = pm_dir / f"{out_base}.wav"
        out_cue = pm_dir / f"{out_base}.cue"

        if len(ordered) > 1:
            run(["shntool", "join", "-o", "wav", "-r", "none",
                 "-d", str(pm_dir), *map(str, ordered)])
            joined = pm_dir / "joined.wav"
            if joined.exists():
                joined.rename(out_wav)
        else:
            shutil.copy2(ordered[0], out_wav)

        safe_copy(cue_path, out_cue, "CUE")
        if not out_cue.exists():
            print(f"⚠  Copy verification failed for {out_cue.name}")
        shutil.move(str(disc_dir), processed_dir)
        pm_files.append(out_wav)
        print(f"Finished {disc_dir.name}: {out_wav.name}")

    print("All Preservation Masters created.")

    # ── PASS 2: EDIT MASTERS ────────────────────────────────────────────
    if make_edit and pm_files:
        print("\nNow creating Edit Masters…")
        for pm in pm_files:
            create_edit_master(pm, em_dir)
        print("Edit Master generation complete.")

    mode = "join+edit" if make_edit else "join"
    print(f"All done ({mode} mode).")

    # after Edit Master pass (or right before the final mode print)
    missing = [pm for pm in pm_files if not (pm.with_suffix(".cue")).exists()]
    if missing:
        print("\n⚠  The following PMs are missing their CUE sheets:")
        for pm in missing:
            print(f"   • {pm.name}")
    else:
        print("\n✅ All Preservation Masters have matching CUE sheets. You’re all good!")

# ── SPLIT LOGIC (unchanged) ────────────────────────────────────────────────
def split_masters(pm_dir: Path) -> None:
    """
    Walk a PreservationMasters directory, split each master WAV/FLAC by its CUE.
    Masters that contain only a single track (one TRACK entry in the CUE) are
    handled by copying the whole file to Track01.ext.
    """
    parent   = pm_dir.parent
    out_root = parent / "Processed_Split"
    out_root.mkdir(exist_ok=True)

    masters = sorted(p for p in pm_dir.iterdir()
                     if p.suffix.lower() in (".wav", ".flac"))

    for master in masters:
        m = re.search(r"(\d{6})", master.stem)
        if not m:
            print(f"Skipping {master.name}: no 6‑digit ID in filename.")
            continue
        disc_id   = m.group(1)
        cue_path  = master.with_suffix(".cue")
        if not cue_path.exists():
            print(f"Missing CUE for {master.name}, skipping.")
            continue

        track_count = sum(1 for line in cue_path.read_text(
                          encoding="utf‑8", errors="ignore").splitlines()
                          if re.match(r"^\s*TRACK", line))

        dest = out_root / disc_id
        dest.mkdir(exist_ok=True)

        if track_count <= 1:
            new_name = f"Track01{master.suffix.lower()}"
            shutil.copy2(master, dest / new_name)
            shutil.copy2(cue_path, dest)
            print(f"Copied single‑track {master.name} → {dest/new_name}")
            continue

        fmt_out = "flac" if master.suffix.lower() == ".flac" else "wav"
        try:
            run(["shnsplit", "-f", str(cue_path), "-o", fmt_out,
                 "-t", "Track%n", "-d", str(dest), str(master)])
            shutil.copy2(cue_path, dest)
            print(f"Split {master.name} → {dest}")
        except subprocess.CalledProcessError as e:
            print(f"shnsplit failed on {master.name}: {e}")

    print("All done (split mode).")

# ── MINI DISC LOGIC ─────────────────────────────────────────────────────────

def process_minidiscs(root: Path, prefix: str, make_edit: bool) -> list[Path]:
    pm_dir = root / "PreservationMasters"
    em_dir = root / "EditMasters"
    processed_dir = root / "Processed"
    for d in (pm_dir, processed_dir):
        d.mkdir(exist_ok=True)
    if make_edit:
        em_dir.mkdir(exist_ok=True)

    pm_files: list[Path] = []

    for disc_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (disc_dir.name.isdigit() and len(disc_dir.name) == 6):
            continue

        # gather AEA and CSV
        aea_files = [p for p in disc_dir.glob("*.aea") if not p.name.startswith("._")]
        csv_files = [p for p in disc_dir.glob("*.csv") if not p.name.startswith("._")]
        if not aea_files:
            continue

        print(f"\nDetected MiniDisc package in {disc_dir.name}")

        # rename CSV like we do for CUE
        if csv_files:
            csv_src = csv_files[0]
            out_csv = pm_dir / f"{prefix}_{disc_dir.name}_v01f01.csv"
            safe_copy(csv_src, out_csv, "CSV")
            print(f"   ↳ Renamed CSV: {out_csv.name}")

        # copy & rename AEA files to PM with rNN suffix
        for idx, aea in enumerate(sorted(aea_files), start=1):
            # always f01 then rNN
            base = f"{prefix}_{disc_dir.name}_v01f01r{idx:02d}_pm"
            pm_file = pm_dir / f"{base}.aea"
            shutil.copy2(aea, pm_file)
            print(f"   ↳ Created PM: {pm_file.name}")
            pm_files.append(pm_file)

        # move processed input dir
        shutil.move(str(disc_dir), processed_dir)
        print(f"   → Moved {disc_dir.name} to Processed/")

    # if requested, run two-pass loudnorm Edit Masters using existing create_edit_master
    if make_edit and pm_files:
        print("\nNow creating MiniDisc Edit Masters with loudnorm…")
        for pm in pm_files:
            create_edit_master(pm, em_dir)
        print("MiniDisc Edit Master generation complete.")

    return pm_files

# ── CLI / main ─────────────────────────────────────────────────────────────
def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True,
                    help="Root folder of disc subdirs (join) OR PreservationMasters dir (split)")
    ap.add_argument("-p", "--prefix", default="xxx",
                    help="Three‑letter prefix for joined masters (join mode only)")
    ap.add_argument("-s", "--split", action="store_true",
                    help="Activate split mode (default is join)")
    ap.add_argument("-e", "--editmasters", action="store_true",
                    help="After joining, create loudness‑checked EditMasters")
    args = ap.parse_args()

    path = Path(args.input).expanduser().resolve()
    # Process MiniDiscs first (will skip if none)
    process_minidiscs(path, args.prefix, args.editmasters)

    if args.split:
        split_masters(path)
    else:
        join_discs(path, args.prefix, args.editmasters)


if __name__ == "__main__":
    cli()