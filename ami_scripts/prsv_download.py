#!/usr/bin/env python3
"""
preservica_cli.py

Fetch and download Preservica assets by AMI ID.

Features:
 - Credentials via CLI / env vars / config file
 - PreservicaClient class with token auth, retry/backoff
 - Logging, HTTP error handling, custom exceptions
 - Download progress percentage
 - Specify output directory via -o/--output
 - Accept AMI IDs via -i/--ids or -c/--csv
"""

import os
import sys
import argparse
import configparser
import logging
import re
import json
import csv
from typing import List, Tuple, Optional
from urllib.parse import unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import lxml.etree


# --- Custom Exceptions -------------------------------------------------------

class PreservicaError(Exception):
    """Base exception for all Preservica CLI errors."""


class AuthError(PreservicaError):
    """Raised when authentication fails."""


class ContentError(PreservicaError):
    """Raised when expected content is missing."""


# --- Preservica Client ------------------------------------------------------

class PreservicaClient:
    def __init__(
        self,
        username: str,
        password: str,
        tenant: str,
        base_url: str = "https://nypl.preservica.com",
    ):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.tenant = tenant

        # configure session with retries/backoff
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # authenticate once
        self._authenticate()

    def _authenticate(self):
        url = f"{self.base_url}/api/accesstoken/login"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            'username': self.username,
            'password': self.password,
            'tenant': self.tenant,
        }
        resp = self.session.post(url, headers=headers, data=payload)
        if not resp.ok:
            logging.error("Auth failed (%s): %s", resp.status_code, resp.text)
            raise AuthError("Failed to obtain access token")
        data = resp.json()
        if not data.get("success"):
            raise AuthError("Invalid credentials")
        token = data["token"]
        self.session.headers.update({
            "Preservica-Access-Token": token,
            "charset": "UTF-8"
        })
        logging.info("Authenticated successfully")

    def get(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, **kwargs)
        if resp.status_code == 401:
            logging.info("Token expired, re-authenticating")
            self._authenticate()
            resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def post(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, **kwargs)
        if resp.status_code == 401:
            logging.info("Token expired, re-authenticating")
            self._authenticate()
            resp = self.session.post(url, **kwargs)
        resp.raise_for_status()
        return resp

    def search_ami(self, ami_ids: List[str]) -> List[Tuple[Optional[str], Optional[str]]]:
        """
        Given a list of six-digit AMI IDs, return list of (title, IO UUID).
        """
        results = []
        for ami_id in ami_ids:
            if not re.fullmatch(r"\d{6}", ami_id):
                logging.warning("Skipping invalid AMI ID: %s", ami_id)
                results.append((None, None))
                continue

            data = {
                'q': json.dumps({
                    'fields': [
                        {'name': 'specObject.amiId', 'values': [ami_id]},
                        {'name': 'xip.identifier', 'values': ['ioCategory AMIMedia']}
                    ]
                }),
                'start': 0,
                'max': '1',
                'metadata': ['xip.title', 'id']
            }
            resp = self.post("/api/content/search?", data=data)
            json_body = resp.json()
            try:
                md = json_body['value']['metadata'][0]
                title = next(item['value'] for item in md if item['name']=="xip.title")
                io_uuid = next(item['value'] for item in md if item['name']=="id")
                results.append((title, io_uuid))
                logging.info("Found AMI %s → IO UUID %s", title, io_uuid)
            except (KeyError, IndexError, StopIteration):
                logging.warning("No result for AMI ID %s", ami_id)
                results.append((None, None))

        return results

    def get_content_object_uuids(self, io_uuid: str, specifier: str) -> List[str]:
        """
        Given an information object UUID and representation specifier,
        return list of ContentObject UUIDs.
        """
        headers = {"Accept": "application/xml"}  # Prefer Accept over Content-Type for GETs

        def fetch(spec: str):
            path = f"/api/entity/information-objects/{io_uuid}/representations/{spec}"
            try:
                return self.get(path, headers=headers)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    return None
                raise  # re-raise non-404s

        # try requested spec, then preservation_1 if needed
        resp = fetch(specifier)
        if resp is None and specifier == "preservation_2":
            logging.info("Representation preservation_2 not found; trying preservation_1")
            resp = fetch("preservation_1")

        if resp is None:
            raise ContentError(f"No representation for {io_uuid}")

        tree = lxml.etree.fromstring(resp.content)

        # Version-agnostic XPath (works for v8.1, future versions, etc.)
        texts = tree.xpath(
            "/*[local-name()='Representation']"
            "/*[local-name()='ContentObjects']"
            "/*[local-name()='ContentObject']/text()"
        )
        if not texts:
            texts = tree.xpath(
                "//*[local-name()='ContentObjects']/*[local-name()='ContentObject']/text()"
            )

        # Normalize to bare UUIDs (handles raw UUIDs or full URLs)
        uuid_re = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
        seen, uuids = set(), []
        for s in texts:
            m = uuid_re.search((s or "").strip())
            if m:
                u = m.group(0).lower()
                if u not in seen:
                    seen.add(u)
                    uuids.append(u)

        if not uuids:
            raise ContentError(f"No ContentObject UUIDs for IO {io_uuid}")
        logging.info("Found %d content object(s) for IO %s", len(uuids), io_uuid)
        return uuids

    def download_bitstream(self, co_uuid: str, output_dir: str):
            """
            Download the latest-active bitstream.
            If Content-Length is missing, fetch size from metadata XML (deep search).
            """
            os.makedirs(output_dir, exist_ok=True)

            base_path = f"/api/entity/content-objects/{co_uuid}/generations/latest-active/bitstreams/1"
            content_path = f"{base_path}/content"

            # Start the download stream
            resp = self.get(content_path, stream=True)

            # 1. Try to get size from headers
            total_bytes = resp.headers.get('Content-Length')
            total = int(total_bytes) if total_bytes and total_bytes.isdigit() else None

            # 2. Fallback: Fetch metadata
            if total is None:
                logging.info("Content-Length header missing; fetching metadata to find size...")
                try:
                    meta_resp = self.get(base_path, headers={"Accept": "application/xml"})
                    tree = lxml.etree.fromstring(meta_resp.content)
                    
                    # Search ANYWHERE in the XML for FileSize or Size
                    size_nodes = tree.xpath("//*[local-name()='FileSize']/text() | //*[local-name()='Size']/text()")
                    
                    if size_nodes:
                        total = int(size_nodes[0].strip())
                        logging.info("Found size in metadata: %s bytes", total)
                    else:
                        # DEBUG: Print the first 500 chars of XML if we can't find the tag
                        logging.warning("Could not find <FileSize> tag. XML Start: %s", meta_resp.text[:500])
                except Exception as e:
                    logging.warning("Failed to retrieve file size from metadata: %s", e)

            # Determine filename
            disp = resp.headers.get('Content-Disposition', '')
            filename = "output.bin"
            if "filename=" in disp:
                filename = unquote(disp.split("filename=")[1].strip('"\''))
            
            filepath = os.path.join(output_dir, filename)

            if total:
                logging.info("Saving bitstream to %s (%s bytes)", filepath, total)
            else:
                logging.info("Saving bitstream to %s (unknown bytes)", filepath)

            # Download loop
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total:
                        percent = downloaded / total * 100
                        sys.stdout.write(f"\r{percent:6.2f}% of {total} downloaded for {filename}")
                    else:
                        sys.stdout.write(f"\r{downloaded} bytes downloaded for {filename}")
                    sys.stdout.flush()

            print() 
            logging.info("Downloaded %s", filepath)


# --- Helpers & CLI -----------------------------------------------------------

def load_credentials(config_path: Optional[str]):
    """
    Load credentials from:
      a) env vars PRESERVICA_USERNAME etc.
      b) INI file at config_path (default ~/.preservica_credentials.ini)
    """
    username = os.getenv("PRESERVICA_USERNAME")
    password = os.getenv("PRESERVICA_PASSWORD")
    tenant   = os.getenv("PRESERVICA_TENANT")

    if username and password and tenant:
        return username, password, tenant

    config_path = config_path or os.path.expanduser("~/.preservica_credentials.ini")
    cfg = configparser.ConfigParser()
    if not cfg.read(config_path):
        logging.error("Cannot read config file %s", config_path)
        sys.exit(1)
    try:
        creds = cfg["default"]
        return creds["username"], creds["password"], creds["tenant"]
    except KeyError as e:
        logging.error("Missing %s in config", e)
        sys.exit(1)


def read_ids_from_csv(csv_path: str) -> List[str]:
    """
    Read the first column of a CSV file, skip any header row
    (non-six-digit values), and return list of six-digit strings.
    """
    ids: List[str] = []
    pattern = re.compile(r"^\d{6}$")
    with open(csv_path, newline='') as fp:
        reader = csv.reader(fp)
        for row in reader:
            if not row:
                continue
            val = row[0].strip()
            if pattern.fullmatch(val):
                ids.append(val)
            else:
                logging.debug("Skipping non-ID row: %r", row)
    if not ids:
        logging.error("No valid 6-digit AMI IDs found in %s", csv_path)
        sys.exit(1)
    return ids


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch and download Preservica assets by AMI ID"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-i", "--ids",
        nargs="+",
        help="One or more six-digit AMI IDs"
    )
    group.add_argument(
        "-c", "--csv",
        help="Path to CSV file containing AMI IDs (one per row, with or without header)"
    )
    parser.add_argument(
        "--config-file",
        help="Path to credentials.ini (default ~/.preservica_credentials.ini)",
        default=None
    )
    parser.add_argument(
        "-r", "--representation",
        choices=["access", "production", "preservation"],
        default="production",
        help="access → access_1, production → preservation_2, preservation → preservation_1"
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Directory to save downloaded files"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )

    # Determine list of IDs
    if args.csv:
        ami_ids = read_ids_from_csv(args.csv)
    else:
        ami_ids = args.ids  # type: ignore

    user, pw, tenant = load_credentials(args.config_file)
    client = PreservicaClient(user, pw, tenant)

    rep_map = {
        "access": "access_1",
        "production": "preservation_2",
        "preservation": "preservation_1"
    }

    results = client.search_ami(ami_ids)
    for title, io_uuid in results:
        if not (title and io_uuid):
            logging.warning("Skipping AMI with no data")
            continue
        logging.info("AMI: %s → IO UUID: %s", title, io_uuid)
        spec = rep_map[args.representation]
        try:
            co_uuids = client.get_content_object_uuids(io_uuid, spec)
            for co in co_uuids:
                client.download_bitstream(co, args.output)
        except PreservicaError as e:
            logging.error("Error processing %s: %s", io_uuid, e)


if __name__ == "__main__":
    main()