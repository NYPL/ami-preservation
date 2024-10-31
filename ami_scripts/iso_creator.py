#!/usr/bin/env python3

import os
import subprocess
import time
import sys
import re


# Check for colorama installation
try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Automatically reset colors after each print
except ImportError:
    print("colorama is not installed. Please install it by running: python3 -m pip install colorama")
    sys.exit(1)

def open_disc_tray(attempts=3):
    """Attempts to open the disc tray on a Mac with multiple tries."""
    for attempt in range(attempts):
        result = subprocess.run(["drutil", "tray", "open"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{Fore.GREEN}Disc tray opened successfully on attempt {attempt + 1}.")
            return
        else:
            print(f"{Fore.YELLOW}Attempt {attempt + 1} to open disc tray failed. Retrying...")
            time.sleep(2)
    print(f"{Fore.RED}Failed to open the disc tray after multiple attempts.")

def close_disc_tray():
    """Closes the disc tray on a Mac."""
    subprocess.run(["drutil", "tray", "close"])

def kill_dvd_player(attempts=3):
    """Kills the DVD Player process if it is running, with multiple attempts and delay between them."""
    for attempt in range(attempts):
        result = subprocess.run(["pkill", "-x", "DVD Player"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{Fore.GREEN}Attempt {attempt + 1}: DVD Player was running and has been terminated.")
            return  # Exit if successfully killed
        else:
            print(f"{Fore.YELLOW}Attempt {attempt + 1}: DVD Player was not running.")
        time.sleep(5)  # Increased delay between kill attempts

def get_dvd_path():
    """Detects the DVD drive path on a Mac by identifying external, physical drives with data."""
    result = subprocess.run(["diskutil", "list"], capture_output=True, text=True)
    dvd_path = None
    for line in result.stdout.splitlines():
        if "external, physical" in line and not any(x in line for x in ["EFI", "APFS", "Container"]):
            parts = line.split()
            dvd_path = parts[0] if parts else None
            print(f"{Fore.GREEN}Detected DVD path: {dvd_path}")  # For debugging
            break
    return dvd_path

def unmount_dvd(dvd_path):
    """Unmounts the DVD to allow ddrescue access and exits on failure."""
    result = subprocess.run(["diskutil", "unmount", dvd_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{Fore.RED}Unmount failed for {dvd_path}. Exiting.")
        sys.exit(1)
    else:
        print(f"{Fore.GREEN}Unmounted DVD successfully.")

def remount_dvd(dvd_path):
    """Remounts the DVD to allow safe ejection."""
    result = subprocess.run(["diskutil", "mount", dvd_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{Fore.GREEN}Successfully remounted {dvd_path}")
    else:
        print(f"{Fore.RED}Failed to remount {dvd_path}. You may need to eject manually.")

def eject_disc(dvd_path):
    """Attempts to eject the disc using diskutil."""
    result = subprocess.run(["diskutil", "eject", dvd_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{Fore.GREEN}Disc ejected successfully.")
    else:
        print(f"{Fore.RED}Failed to eject the disc.")

def run_ddrescue(dvd_path, output_file, log_file):
    """Runs ddrescue with four passes and specified block size to create an ISO image."""
    try:
        command = [
            "ddrescue", "-b", "2048", "-r4", "-v", dvd_path, output_file, log_file
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Regular expression to match the "rescued" line
        rescued_pattern = re.compile(r"rescued:\s+([0-9.]+ \wB)")
        success_flag = False  # Flag to track if "Finished" is found

        for line in process.stdout:
            # Search for "rescued" in the line and display only that part
            rescued_match = rescued_pattern.search(line)
            if rescued_match:
                # Print the rescued amount in place
                print(f"\rData Rescued: {rescued_match.group(1)}", end="")

            # Check for "Finished" to set the success flag
            if "Finished" in line:
                success_flag = True

        process.wait()  # Wait for ddrescue to finish
        print()  # Move to the next line after ddrescue completes
        return success_flag  # Return whether "Finished" was found
    except Exception as e:
        print(f"{Fore.RED}Error running ddrescue: {e}")
        return False

def main():
    print(f"{Fore.CYAN}Welcome to the DVD Backup Script")

    # Statistics tracking
    total_attempts = 0
    successful_attempts = 0
    failed_attempts = 0
    failed_files = []

    # Open the disc tray at the start
    print(f"{Fore.CYAN}Opening the disc tray...")
    open_disc_tray()

    # Prompt user for destination directory
    dest_dir = input(f"{Fore.YELLOW}Enter the directory where ISO files should be saved: ").strip()
    if not os.path.isdir(dest_dir):
        print(f"{Fore.RED}Invalid directory. Exiting.")
        return
    
    while True:
        input(f"{Fore.YELLOW}Please insert a DVD into the drive and press Enter to continue...")
        close_disc_tray()
        time.sleep(15)  # Increased wait time for the disc to load

        # Kill DVD Player if running, with multiple attempts and conditional retries
        kill_dvd_player(attempts=3)

        # Detect DVD path
        dvd_path = get_dvd_path()
        if not dvd_path:
            print(f"{Fore.RED}Could not detect DVD drive. Please check your setup.")
            continue

        # Unmount DVD and exit on failure
        unmount_dvd(dvd_path)
        
        # Increment attempt counter
        total_attempts += 1
        
        # Prompt for filename
        output_file_name = input(f"{Fore.YELLOW}Enter a name for the ISO image file (without extension): ")
        output_file = os.path.join(dest_dir, f"{output_file_name}.iso")
        log_file = os.path.join(dest_dir, f"{output_file_name}.log")

        print(f"{Fore.CYAN}Starting ddrescue to create {output_file} from {dvd_path}...")
        
        # Run ddrescue and check the success flag directly
        ddrescue_success = run_ddrescue(dvd_path, output_file, log_file)
        
        if ddrescue_success:
            print(f"{Fore.GREEN}Backup of {output_file} completed successfully.")
            successful_attempts += 1
            
            # Remount DVD for safe ejection
            remount_dvd(dvd_path)
            time.sleep(15)
            
            # Attempt to eject the disc just once
            eject_disc(dvd_path)
            
        else:
            print(f"{Fore.RED}An error occurred during the backup process. Please check the log file.")
            failed_attempts += 1
            failed_files.append(output_file_name)  # Track failed file name
            
            # Remount and eject the problematic disc
            remount_dvd(dvd_path)
            eject_disc(dvd_path)
        
        # Ask user whether they'd like to insert another disc
        cont = input(f"{Fore.YELLOW}Would you like to insert another disc? (yes/no): ").strip().lower()
        if cont != "yes":
            print(f"{Fore.CYAN}Exiting the script.")
            break

    # Print summary of attempts
    print(f"\n{Fore.CYAN}Summary of DVD Backup Attempts:")
    print(f"{Fore.CYAN}Total DVDs attempted: {total_attempts}")
    print(f"{Fore.GREEN}Successful backups: {successful_attempts}")
    print(f"{Fore.RED}Failed backups: {failed_attempts}")
    if failed_files:
        print(f"{Fore.RED}Failed files:")
        for filename in failed_files:
            print(f"{Fore.RED} - {filename}")

if __name__ == "__main__":
    main()
