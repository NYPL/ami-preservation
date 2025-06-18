#!/usr/bin/env python3

import os
import sys
import logging
import jaydebeapi
import argparse
from pathlib import Path
from collections import namedtuple

# ── Configuration ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(message)s')

VIDEO_EXTS = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
AUDIO_EXTS = {'.wav', '.flac'}
ALL_EXTS   = VIDEO_EXTS | AUDIO_EXTS

JDBC_JAR   = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

# ── Helpers ────────────────────────────────────────────────────────────────────
def connect_to_database(dev: bool):
    """Return a jaydebeapi connection or sys.exit on failure."""
    server = os.getenv('FM_DEV_SERVER' if dev else 'FM_SERVER')
    db     = os.getenv('AMI_DATABASE')
    user   = os.getenv('AMI_DATABASE_USERNAME')
    pw     = os.getenv('AMI_DATABASE_PASSWORD')

    if not all([server, db, user, pw]):
        logging.error("Missing one of FM_SERVER/FM_DEV_SERVER, AMI_DATABASE, AMI_DATABASE_USERNAME, or AMI_DATABASE_PASSWORD in env.")
        sys.exit(1)

    url = f'jdbc:filemaker://{server}/{db}'
    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            url,
            [user, pw],
            JDBC_JAR
        )
        logging.info(f"Connected to {'DEV' if dev else 'PROD'} FileMaker at {server}")
        return conn
    except Exception as e:
        logging.error(f"Unable to connect to FileMaker: {e}")
        sys.exit(1)

def record_exists(conn, filename: str) -> bool:
    """Return True if tbl_metadata has a row where asset.referenceFilename = filename."""
    sql = 'SELECT COUNT(*) FROM tbl_metadata WHERE "asset.referenceFilename" = ?'
    curs = conn.cursor()
    try:
        curs.execute(sql, [filename])
        count = curs.fetchone()[0]
        return bool(count)
    finally:
        curs.close()

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Check FileMaker for every media file in a directory"
    )
    p.add_argument('-d', '--directory', required=True,
                   help="Root path to crawl for media files")
    p.add_argument('--dev-server', action='store_true',
                   help="Use FM_DEV_SERVER instead of FM_SERVER")
    args = p.parse_args()

    # 1) build list of all media files
    root = Path(args.directory)
    if not root.is_dir():
        logging.error(f"{root!r} is not a directory.")
        sys.exit(1)

    all_files = [f for f in root.rglob('*')
                 if f.is_file() and f.suffix.lower() in ALL_EXTS]
    logging.info(f"Found {len(all_files)} media files in {root}")

    # 2) connect
    conn = connect_to_database(args.dev_server)

    # 3) check each one
    Summary = namedtuple('Summary', ['matched', 'missing'])
    summary = Summary(matched=[], missing=[])

    for f in sorted(all_files):
        name = f.name
        if record_exists(conn, name):
            summary.matched.append(name)
        else:
            summary.missing.append(name)

    conn.close()

    # 4) print report
    total   = len(all_files)
    matched = len(summary.matched)
    missing = len(summary.missing)

    logging.info("\nSummary Report")
    logging.info("--------------")
    logging.info(f"Total media files scanned : {total}")
    logging.info(f"Records found in FileMaker: {matched}")
    logging.info(f"Records NOT found        : {missing}")

    if missing:
        logging.info("\nMissing filenames:")
        for name in summary.missing:
            logging.info(f"  • {name}")

if __name__ == '__main__':
    main()
