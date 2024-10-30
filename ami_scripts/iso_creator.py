#!/usr/bin/env python3

import os
import subprocess
import time

def open_disc_tray(attempts=3):
    """Attempts to open the disc tray on a Mac with multiple tries."""
    for attempt in range(attempts):
        result = subprocess.run(["drutil", "tray", "open"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Disc tray opened successfully on attempt {attempt + 1}.")
            return
        else:
            print(f"Attempt {attempt + 1} to open disc tray failed. Retrying...")
            time.sleep(2)
    print("Failed to open the disc tray after multiple attempts.")

def close_disc_tray():
    """Closes the disc tray on a Mac."""
    subprocess.run(["drutil", "tray", "close"])

def kill_dvd_player(attempts=3):
    """Kills the DVD Player process if it is running, with multiple attempts and delay between them."""
    for attempt in range(attempts):
        result = subprocess.run(["pkill", "-x", "DVD Player"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Attempt {attempt + 1}: DVD Player was running and has been terminated.")
        else:
            print(f"Attempt {attempt + 1}: DVD Player was not running.")
        time.sleep(5)  # Increased delay between kill attempts

def get_dvd_path():
    """Detects the DVD drive path on a Mac by identifying external, physical drives with data."""
    result = subprocess.run(["diskutil", "list"], capture_output=True, text=True)
    dvd_path = None
    for line in result.stdout.splitlines():
        if "external, physical" in line and not any(x in line for x in ["EFI", "APFS", "Container"]):
            parts = line.split()
            dvd_path = parts[0] if parts else None
            print(f"Detected DVD path: {dvd_path}")  # For debugging
            break
    return dvd_path

def unmount_dvd(dvd_path):
    """Unmounts the DVD to allow ddrescue access and exits on failure."""
    result = subprocess.run(["diskutil", "unmount", dvd_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Unmount failed for {dvd_path}. Exiting.")
        exit(1)
    else:
        print("Unmounted DVD successfully.")

def remount_dvd(dvd_path):
    """Remounts the DVD to allow safe ejection."""
    result = subprocess.run(["diskutil", "mount", dvd_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Successfully remounted {dvd_path}")
    else:
        print(f"Failed to remount {dvd_path}. You may need to eject manually.")

def eject_disc(dvd_path):
    """Attempts to eject the disc using diskutil."""
    result = subprocess.run(["diskutil", "eject", dvd_path], capture_output=True, text=True)
    if result.returncode == 0:
        print("Disc ejected successfully.")
    else:
        print("Failed to eject the disc.")

def run_ddrescue(dvd_path, output_file, log_file):
    """Runs ddrescue with four passes and specified block size to create an ISO image."""
    try:
        command = [
            "ddrescue", "-b", "2048", "-r4", "-v", dvd_path, output_file, log_file
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return result
    except Exception as e:
        print(f"Error running ddrescue: {e}")
        return None

def main():
    print("Welcome to the DVD Backup Script")
    
    # Open the disc tray at the start
    print("Opening the disc tray...")
    open_disc_tray()

    # Prompt user for destination directory
    dest_dir = input("Enter the directory where ISO files should be saved: ").strip()
    if not os.path.isdir(dest_dir):
        print("Invalid directory. Exiting.")
        return
    
    while True:
        input("Please insert a DVD into the drive and press Enter to continue...")
        close_disc_tray()
        time.sleep(15)  # Increased wait time for the disc to load

        # Kill DVD Player if running, with multiple attempts and conditional retries
        kill_dvd_player(attempts=3)

        # Detect DVD path
        dvd_path = get_dvd_path()
        if not dvd_path:
            print("Could not detect DVD drive. Please check your setup.")
            continue

        # Unmount DVD and exit on failure
        unmount_dvd(dvd_path)
        
        # Prompt for filename
        output_file_name = input("Enter a name for the ISO image file (without extension): ")
        output_file = os.path.join(dest_dir, f"{output_file_name}.iso")
        log_file = os.path.join(dest_dir, f"{output_file_name}.log")

        print(f"Starting ddrescue to create {output_file} from {dvd_path}...")
        
        # Run ddrescue
        ddrescue_result = run_ddrescue(dvd_path, output_file, log_file)
        
        # Check ddrescue output for "Finished" to confirm success
        if ddrescue_result and "Finished" in ddrescue_result.stdout:
            print(f"Backup of {output_file} completed successfully.")
            
            # Remount DVD for safe ejection
            remount_dvd(dvd_path)
            time.sleep(15)
            
            # Attempt to eject the disc just once
            eject_disc(dvd_path)
            
            cont = input("Would you like to insert another disc? (yes/no): ").strip().lower()
            if cont != "yes":
                print("Exiting the script.")
                break
        else:
            print("An error occurred during the backup process. Please check the log file.")

if __name__ == "__main__":
    main()
