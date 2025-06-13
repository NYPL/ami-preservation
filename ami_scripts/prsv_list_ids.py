#!/usr/bin/env python3
"""
prsv_list_ids.py

Generate a CSV of every six-digit AMI ID stored in Preservica.
Re-uses PreservicaClient, load_credentials, and PreservicaError
from prsv_download.py.

Outputs to:
  <output_dir>/prsv_all_ami_ids_YYYY-MM-DD.csv
"""

import os
import sys
import argparse
import logging
import csv
import json
from datetime import date
from typing import List

# import your client & loader from the download script
from prsv_download import PreservicaClient, load_credentials, PreservicaError

# how many records to fetch per page (you can adjust this)
PAGE_SIZE = 1000


def fetch_all_ami_ids(client: PreservicaClient, page_size: int = PAGE_SIZE) -> List[str]:
    """
    Page through the search API, collecting every specObject.amiId
    where xip.identifier == 'ioCategory AMIMedia'.
    """
    all_ids: List[str] = []
    start = 0

    query_body = {
        "fields": [
            {"name": "xip.identifier", "values": ["ioCategory AMIMedia"]}
        ]
    }

    while True:
        payload = {
            "q": json.dumps(query_body),
            "start": start,
            "max": str(page_size),
            # request only the AMI ID metadata
            "metadata": ["specObject.amiId"]
        }

        resp = client.post("/api/content/search?", data=payload)
        value = resp.json().get("value", {})
        batch = value.get("metadata", [])

        if not batch:
            # no more results
            break

        for record in batch:
            # record is a list of dicts; find the AMI ID
            for md in record:
                if md.get("name") == "specObject.amiId":
                    all_ids.append(md.get("value"))
                    break

        start += len(batch)
        logging.info("Fetched %d IDs (total %d so far)", len(batch), len(all_ids))

    return all_ids


def parse_args():
    p = argparse.ArgumentParser(
        description="List all AMI IDs in Preservica and write to CSV"
    )
    p.add_argument(
        "--config-file",
        help="Path to credentials.ini (default ~/.preservica_credentials.ini)",
        default=None
    )
    p.add_argument(
        "-o", "--output",
        default=".",
        help="Directory in which to write the CSV"
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )

    # load creds & init client
    user, pw, tenant = load_credentials(args.config_file)
    client = PreservicaClient(user, pw, tenant)

    try:
        ami_ids = fetch_all_ami_ids(client)
    except PreservicaError as e:
        logging.error("Error fetching AMI IDs: %s", e)
        sys.exit(1)

    # sort the IDs before writing
    ami_ids.sort()
    logging.info("Total AMI IDs found: %d (writing in sorted order)", len(ami_ids))

    # ensure output directory exists
    os.makedirs(args.output, exist_ok=True)

    # auto-generate filename
    today_str = date.today().isoformat()  # YYYY-MM-DD
    filename = f"prsv_all_ami_ids_{today_str}.csv"
    output_path = os.path.join(args.output, filename)

    # write out CSV
    with open(output_path, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["amiId"])
        for ami in ami_ids:
            writer.writerow([ami])

    logging.info("Wrote all AMI IDs to %s", output_path)


if __name__ == "__main__":
    main()
