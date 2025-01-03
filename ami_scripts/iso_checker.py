#!/usr/bin/env python3

import os
import argparse
import sys
from isolyzer import isolyzer
import xml.etree.ElementTree as ET
from collections import Counter

# Check for colorama installation
try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Automatically reset colors after each print
except ImportError:
    print("colorama is not installed. Please install it by running: python3 -m pip install colorama")
    sys.exit(1)


def sanitize_xml(element):
    """
    Recursively ensures all element text and attributes are strings.
    Handles cases where text is None or attributes are integers.
    """
    # Sanitize text
    if element.text is not None and not isinstance(element.text, str):
        element.text = str(element.text)

    # Sanitize attributes
    for attr_name, attr_value in element.attrib.items():
        if not isinstance(attr_value, str):
            element.attrib[attr_name] = str(attr_value)

    # Recursively sanitize children
    for child in element:
        sanitize_xml(child)


def safe_tostring(element):
    """Safely serialize XML element after sanitization."""
    sanitize_xml(element)
    return ET.tostring(element, encoding="utf-8").decode("utf-8")


def extract_file_system_types(isolyzer_result):
    """
    Extracts file system types from the Isolyzer XML result.
    Returns a list of file system types (e.g., ['ISO 9660', 'UDF']).
    """
    file_systems = isolyzer_result.findall("fileSystems/fileSystem")
    return [fs.attrib.get("TYPE", "Unknown") for fs in file_systems]


def process_isos(directory):
    # Find all .iso files in the directory
    iso_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
        if file.lower().endswith(".iso")
    ]

    if not iso_files:
        print(f"{Fore.RED}No ISO files found in the specified directory.{Style.RESET_ALL}")
        return

    # Process each ISO file
    size_as_expected = 0
    size_not_expected = 0
    failing_files = []
    file_system_types = Counter()

    for iso_file in iso_files:
        print(f"\nProcessing: {iso_file}")
        try:
            # Analyze the ISO file with Isolyzer
            isolyzer_result = isolyzer.processImage(iso_file, 0)

            # Extract and display file system types
            fs_types = extract_file_system_types(isolyzer_result)
            file_system_types.update(fs_types)
            print(f"File System Types: {', '.join(fs_types)}")

            # DEBUG: Safely serialize and print the XML result
            isolyzer_xml = safe_tostring(isolyzer_result)

            # Extract success and size status
            success = isolyzer_result.find("statusInfo/success").text
            smaller_than_expected = isolyzer_result.find("tests/smallerThanExpected").text

            if success == "True" and smaller_than_expected == "False":
                size_as_expected += 1
            else:
                size_not_expected += 1
                failing_files.append(iso_file)

        except Exception as e:
            print(f"{Fore.RED}Error processing {iso_file}: {e}{Style.RESET_ALL}")
            size_not_expected += 1
            failing_files.append(iso_file)

    # Print summary with color
    print(f"\n{Style.BRIGHT}Processing Summary:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total ISO files: {len(iso_files)}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Size as expected: {size_as_expected}{Style.RESET_ALL}")
    print(f"{Fore.RED}Size not as expected: {size_not_expected}{Style.RESET_ALL}")

    if failing_files:
        print(f"\n{Fore.RED}Files with unexpected size or errors:{Style.RESET_ALL}")
        for file in failing_files:
            print(f"  - {file}")

    # Print file system type summary
    print(f"\n{Style.BRIGHT}File System Types Summary:{Style.RESET_ALL}")
    for fs_type, count in file_system_types.items():
        print(f"{Fore.YELLOW}{fs_type}: {count}{Style.RESET_ALL}")


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Process .iso files using Isolyzer.")
    parser.add_argument(
        "-d", "--directory", required=True, help="Directory containing .iso files"
    )
    args = parser.parse_args()

    # Process the ISO files in the specified directory
    process_isos(args.directory)


if __name__ == "__main__":
    main()
