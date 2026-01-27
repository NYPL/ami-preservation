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
 - RESUMABLE DOWNLOADS: Automatically retries dropped connections via Range headers
"""

import os
import sys
import argparse
import configparser
import logging
import re
import json
import csv
import time
from typing import List, Tuple, Optional
from urllib.parse import unquote

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, ConnectionError
from urllib3.exceptions import ProtocolError
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
        if url.startswith(self.base_url + self.base_url):
             # prevention against double-url construction if path already includes base
             url = path 
        
        resp = self.session.get(url, **kwargs)
        if resp.status_code == 401:
            logging.info("Token expired, re-authenticating")
            self._authenticate()
            # Re-issue request with NEW token
            resp = self.session.get(url, **kwargs)
        
        # Handle 416 Range Not Satisfiable (e.g. file fully downloaded)
        if resp.status_code == 416:
             return resp
             
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
        Download the latest-active bitstream with support for resuming interrupted downloads.
        """
        os.makedirs(output_dir, exist_ok=True)

        base_path = f"/api/entity/content-objects/{co_uuid}/generations/latest-active/bitstreams/1"
        content_path = f"{base_path}/content"

        # 1. Determine the filename first (needs a lightweight initial request)
        # We fetch headers but don't download content yet
        head_resp = self.get(content_path, stream=True)
        head_resp.close() 

        disp = head_resp.headers.get('Content-Disposition', '')
        filename = "output.bin"
        if "filename=" in disp:
            filename = unquote(disp.split("filename=")[1].strip('"\''))
        
        filepath = os.path.join(output_dir, filename)

        # 2. Get Total Size (Your existing robust logic)
        # Try headers first, then metadata
        total_bytes_str = head_resp.headers.get('Content-Length')
        total_size = int(total_bytes_str) if total_bytes_str and total_bytes_str.isdigit() else None

        if total_size is None:
            logging.info("Content-Length header missing; fetching metadata to find size...")
            try:
                meta_resp = self.get(base_path, headers={"Accept": "application/xml"})
                tree = lxml.etree.fromstring(meta_resp.content)
                size_nodes = tree.xpath("//*[local-name()='FileSize']/text() | //*[local-name()='Size']/text()")
                if size_nodes:
                    total_size = int(size_nodes[0].strip())
                    logging.info("Found size in metadata: %s bytes", total_size)
            except Exception as e:
                logging.warning("Failed to retrieve file size from metadata: %s", e)

        if total_size:
            logging.info("Target: %s (%s bytes)", filepath, total_size)
        else:
            logging.info("Target: %s (unknown size)", filepath)

        # 3. The Resumable Download Loop
        retries = 0
        max_retries = 20  # increased retry count for very large files
        
        while True:
            # Check how much we have downloaded so far
            if os.path.exists(filepath):
                current_pos = os.path.getsize(filepath)
            else:
                current_pos = 0

            # If we are done, break
            if total_size and current_pos >= total_size:
                logging.info("\nDownload complete: %s", filepath)
                break

            # If we have some data, resume. If 0, start fresh.
            headers = {}
            mode = 'ab' if current_pos > 0 else 'wb'
            
            if current_pos > 0:
                headers['Range'] = f'bytes={current_pos}-'
                logging.info(f"Resuming download from byte {current_pos}...")

            start_pos_for_this_attempt = current_pos
            try:
                # Use self.get() so we get the auto-refresh behavior!
                # Note: self.get() constructs full URL, so pass path only if possible, 
                # but we have full content_path.
                # Let's trust self.get logic to handle partial path logic or use full url if we must.
                # self.get expects `path`.
                
                # Careful: self.get does: url = f"{self.base_url}{path}"
                # content_path already has /api/... so passing it is correct.
                
                resp = self.get(content_path, headers=headers, stream=True)
                
                # Check for 416 Range Not Satisfiable - usually means we are done
                if resp.status_code == 416:
                    logging.info("Server returned 416 (Range Not Satisfiable). Assuming download complete.")
                    break

                # If server ignores Range header (returns 200 instead of 206), we must overwrite
                if current_pos > 0 and resp.status_code == 200:
                    logging.warning("Server does not support resuming (got 200, not 206). Restarting download.")
                    current_pos = 0
                    mode = 'wb'
                    # Truncate file
                    with open(filepath, 'wb') as f:
                        pass

                with open(filepath, mode) as f:
                    for chunk in resp.iter_content(chunk_size=1048576): # 1MB chunks
                        if not chunk:
                            continue
                        f.write(chunk)
                        current_pos += len(chunk)

                        # SMART RETRY LOGIC:
                        # If we successfully read *any* data, reset our retry counter.
                        # This means we only fail if we get N *consecutive* failures without progress.
                        if current_pos > start_pos_for_this_attempt + 1048576:
                             # Reset retries if we managed to DL at least 1MB this session
                             retries = 0

                        # Progress bar
                        if total_size:
                            percent = current_pos / total_size * 100
                            sys.stdout.write(f"\r{percent:6.2f}% of {total_size} | {filename}")
                        else:
                            sys.stdout.write(f"\r{current_pos} bytes | {filename}")
                        sys.stdout.flush()
                
            except (ChunkedEncodingError, ConnectionError, ProtocolError, requests.exceptions.RequestException, PreservicaError) as e:
                # Retries increment
                retries += 1
                logging.warning(f"\nStream interrupted: {e}. Retrying ({retries}/{max_retries})...")
                
                if retries > max_retries:
                    logging.error("Max retries exceeded with no significant progress.")
                    raise e
                
                # Backoff
                time.sleep(5 * retries)  # linear backoff 5, 10, 15...

        print() 


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