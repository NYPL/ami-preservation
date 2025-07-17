#!/usr/bin/env python3
import argparse
import subprocess
import os
import re
from pathlib import Path

def run_mediaconch(file_path):
    """Run MediaConch on a file and return the output."""
    try:
        result = subprocess.run(
            ["mediaconch", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to run mediaconch on {file_path}:\n{e.stderr}")
        return None

def extract_conch_results(output):
    """Extract pass/fail status and error details from MediaConch output."""
    lines = output.splitlines()
    
    if not lines:
        return {"status": "unknown", "errors": []}
    
    # First line indicates pass/fail status
    first_line = lines[0].strip()
    if first_line.startswith("pass!"):
        return {"status": "pass", "errors": []}
    elif first_line.startswith("fail!"):
        status = "fail"
        errors = []
        
        # Parse error details from subsequent lines
        current_error = None
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("-- ") and not line.startswith("--    "):
                # New error type (e.g., "-- TRUNCATED-ELEMENT")
                current_error = line[3:]  # Remove "-- "
            elif line.startswith("--    [fail]"):
                # This indicates a failure detail is coming
                continue
            elif line.startswith("--     [") and current_error:
                # Error detail line
                error_detail = line[7:-1]  # Remove "--     [" and "]"
                errors.append(f"{current_error}: {error_detail}")
                current_error = None
        
        # If no specific errors were parsed, use a generic message
        if not errors and status == "fail":
            errors.append("MediaConch validation failed")
            
        return {"status": status, "errors": errors}
    else:
        return {"status": "unknown", "errors": ["Unexpected MediaConch output format"]}

def get_file_size(file_path):
    """Get file size in bytes."""
    try:
        return file_path.stat().st_size
    except OSError:
        return 0

def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def process_directories(input_paths):
    """Process directories and check MKV files with MediaConch."""
    passed_files = []
    failed_files = []
    
    for input_path in input_paths:
        for mkv_file in Path(input_path).rglob("*.mkv"):
            # Skip hidden files (starting with .)
            if mkv_file.name.startswith('.'):
                continue
                
            # Extract six-digit bag ID from filename (fallback to stem)
            m = re.search(r"(\d{6})", mkv_file.name)
            bag_id = m.group(1) if m else mkv_file.stem
            
            # Get file size
            file_size = get_file_size(mkv_file)
            
            print(f"\n[INFO] Checking file: {mkv_file}")
            print(f"       File size: {format_file_size(file_size)}")
            
            output = run_mediaconch(mkv_file)
            if not output:
                continue
            
            result = extract_conch_results(output)
            
            file_info = {
                "bag_id": bag_id,
                "file_path": mkv_file,
                "file_size": file_size,
                "formatted_size": format_file_size(file_size)
            }
            
            if result["status"] == "pass":
                print(f"  {bag_id}: Pass")
                passed_files.append(file_info)
            elif result["status"] == "fail":
                file_info["errors"] = result["errors"]
                error_summary = "; ".join(result["errors"][:2])  # Show first 2 errors
                if len(result["errors"]) > 2:
                    error_summary += f" (and {len(result['errors']) - 2} more)"
                print(f"  {bag_id}: Fail – {error_summary}")
                failed_files.append(file_info)
            else:
                file_info["errors"] = result["errors"]
                print(f"  {bag_id}: Unknown – {'; '.join(result['errors'])}")
                failed_files.append(file_info)
    
    return passed_files, failed_files

def main():
    parser = argparse.ArgumentParser(
        description="Check MKV files for MediaConch conformance issues."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        nargs="+",
        help="One or more paths to input directories"
    )
    args = parser.parse_args()
    
    passed, failed = process_directories(args.input)
    
    # Sort failed files by size (largest first)
    failed.sort(key=lambda x: x["file_size"], reverse=True)
    
    # Summary report
    print("\n=== Summary Report ===")
    print(f"Passed files: {len(passed)}")
    if passed:
        print("  Pass IDs:", ", ".join([f["bag_id"] for f in passed]))
    
    print(f"\nFailed files: {len(failed)}")
    if failed:
        print("  Details (sorted by file size, largest first):")
        for file_info in failed:
            print(f"    • {file_info['bag_id']} ({file_info['formatted_size']})")
            for error in file_info["errors"]:
                print(f"      - {error}")
    
    # Size statistics
    if failed:
        total_failed_size = sum(f["file_size"] for f in failed)
        print(f"\nTotal size of failed files: {format_file_size(total_failed_size)}")
        print(f"Largest failed file: {failed[0]['formatted_size']} ({failed[0]['bag_id']})")
        print(f"Smallest failed file: {failed[-1]['formatted_size']} ({failed[-1]['bag_id']})")

if __name__ == "__main__":
    main()