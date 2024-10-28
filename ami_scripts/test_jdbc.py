#!/usr/bin/env python3

import argparse
import jaydebeapi
import os

def get_args():
    parser = argparse.ArgumentParser(description='Test JDBC connection to FileMaker Server')
    parser.add_argument('--use-dev', action='store_true',
                        help='Use the development server instead of the production server.')
    return parser.parse_args()

def test_jdbc_connection(use_dev=False):
    # Load environment variables
    server_ip = os.getenv('FM_DEV_SERVER') if use_dev else os.getenv('FM_SERVER')
    database_name = os.getenv('AMI_DATABASE')
    username = os.getenv('AMI_DATABASE_USERNAME')
    password = os.getenv('AMI_DATABASE_PASSWORD')

    # Print environment variables for troubleshooting
    print(f"Connecting to {'development' if use_dev else 'production'} server:")
    print(f"Server IP: {server_ip}")
    print(f"Database Name: {database_name}")
    print(f"Username: {username}")
    print(f"Password: {'<hidden>' if password else 'None'}")
    print(f"JDBC Path: {os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')}")

    # Dynamically set the JDBC path
    jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

    conn = None

    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{server_ip}/{database_name}',
            [username, password],
            jdbc_path
        )
        print(f"Connection to {'development' if use_dev else 'production'} server successful!")

    except Exception as e:
        print(f"Failed to connect to {'development' if use_dev else 'production'} server: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    args = get_args()
    test_jdbc_connection(args.use_dev)
