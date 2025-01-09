#!/usr/bin/env python3

import argparse
import csv
import logging
import os
import requests
import time
from typing import List, Dict

# Set up logging. Adjust level to DEBUG if you need extra detail:
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def get_scsb_availability(barcodes: List[str]) -> Dict[str, str]:
    """
    Retrieves item availability for a list of barcodes from the SCSB API.
    Returns a dict {barcode: availability or error_message}.
    """
    # Log which barcodes we're about to call with
    logging.info(f"Calling SCSB API for barcodes: {barcodes}")

    api_key = os.getenv("SCSB_API_KEY")
    url = os.getenv("SCSB_API_URL")  # e.g., https://[some_endpoint]/sharedCollection/itemAvailabilityStatus

    if not api_key or not url:
        logging.error("SCSB_API_KEY or SCSB_API_URL environment variables not set.")
        # Return an error status for each barcode.
        return {bc: "Error: Missing API credentials/URL" for bc in barcodes}

    headers = {
        'Accept': 'application/json',
        'api_key': api_key,
        'Content-Type': 'application/json'
    }
    payload = {
        "barcodes": barcodes
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            try:
                # response.json() should be a list of dicts,
                # e.g. [{"itemBarcode": "33433068831985", "itemAvailabilityStatus": "Available", ...}]
                results = response.json() or []
            except Exception as parse_exc:
                logging.error(f"Failed to parse JSON response: {parse_exc}")
                return {bc: f"Error: JSON parse error - {parse_exc}" for bc in barcodes}

            availability_dict = {}

            print("")
            for item in results:
                bc = item.get("itemBarcode", "")
                status = item.get("itemAvailabilityStatus", "unknown")

                # Log each barcode’s status
                logging.info(f"For barcode {bc}, got status: {status}")
                availability_dict[bc] = status

            return availability_dict
        else:
            logging.error(f"SCSB API returned status code: {response.status_code}")
            # Return an error status for each barcode in this batch
            return {bc: f"Error: API returned {response.status_code}" for bc in barcodes}
    except Exception as e:
        logging.error(f"SCSB API request failed: {e}")
        return {bc: f"Error: {str(e)}" for bc in barcodes}


def main():
    parser = argparse.ArgumentParser(description="Check SCSB availability for barcodes in a CSV.")
    parser.add_argument("input_csv", help="Path to the input CSV file.")
    parser.add_argument("output_csv", help="Path to the output CSV file.")
    args = parser.parse_args()

    input_path = args.input_csv
    output_path = args.output_csv

    # Read input CSV
    rows = []
    barcodes = []

    logging.info(f"Reading input CSV: {input_path}")
    with open(input_path, "r", newline="", encoding="utf-8") as f_in:
        # If your CSV is tab-delimited, change delimiter to "\t"
        reader = csv.DictReader(f_in, delimiter=",")
        if reader.fieldnames:
            reader.fieldnames = [fn.strip() for fn in reader.fieldnames]

        for r in reader:
            bc_str = str(r.get("id_barcode", "")).strip()
            rows.append(r)
            barcodes.append(bc_str)

    # Prepare to store barcode -> availability result
    availability_map = {}

    logging.info(f"Total barcodes read: {len(barcodes)}")

    # Batch up barcodes in groups of up to 100
    batch_size = 100
    for i in range(0, len(barcodes), batch_size):
        batch = barcodes[i:i+batch_size]
        # Log the batch info
        logging.info(f"Processing batch {i//batch_size + 1}, barcodes {i} to {i+len(batch)-1}")
        batch_result = get_scsb_availability(batch)
        # Merge into the availability_map
        availability_map.update(batch_result)
        # Delay 1 second between calls to stay polite
        time.sleep(5)

    # Write out the output CSV
    fieldnames = ["SPEC_ID", "id_barcode", "building", "room", "row", "SCSB_availability"]
    logging.info(f"Writing output to {output_path}")
    with open(output_path, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames, delimiter=",")
        writer.writeheader()
        for row in rows:
            bc_str = str(row.get("id_barcode", "")).strip()
            availability = availability_map.get(bc_str, "not_found_in_map")

            output_row = {
                "SPEC_ID": row.get("SPEC_ID", "").strip(),
                "id_barcode": bc_str,
                "building": row.get("building", "").strip(),
                "room": row.get("room", "").strip(),
                "row": row.get("row", "").strip(),
                "SCSB_availability": availability
            }
            writer.writerow(output_row)

    print("")
    logging.info(f"Done. Output CSV written to: {output_path}")


if __name__ == "__main__":
    main()
