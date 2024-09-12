#!/usr/bin/env python3

import jaydebeapi
import os
import argparse
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap

def fetch_data_from_jdbc(use_dev=False, record_limit=None):
    # Load environment variables for the appropriate server
    server_ip = os.getenv('FM_DEV_SERVER') if use_dev else os.getenv('FM_SERVER')
    database_name = os.getenv('FM_DATABASE')  # This remains the same for both servers
    username = os.getenv('FM_DATABASE_USERNAME')
    password = os.getenv('FM_DATABASE_PASSWORD')

    # Dynamically set the JDBC path
    jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

    conn = None
    df = pd.DataFrame()

    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{server_ip}/{database_name}',
            [username, password],
            jdbc_path
        )
        print(f"Connection to {'Dev' if use_dev else 'Prod'} database successful!")
        print("Now Fetching Data (Expect ~10 minutes)")

        # Define the query to fetch 'object_id' and 'format_1' from the 'OBJECTS' table
        query = 'SELECT "object_id", "format_1" FROM OBJECTS'
        
        # If a record limit is provided, modify the query to include a LIMIT clause
        if record_limit:
            query += f" LIMIT {record_limit}"

        # Execute the query
        curs = conn.cursor()
        curs.execute(query)

        # Fetch the column descriptions and data
        columns = [desc[0] for desc in curs.description]
        data = [dict(zip(columns, row)) for row in curs.fetchall()]

        # Create a DataFrame from the fetched data
        df = pd.DataFrame(data)
        print("Data fetched successfully!")
        print(f"Total records fetched: {len(df)}")

        # Export the DataFrame to a CSV file on the desktop
        output_path = os.path.expanduser('~/Desktop/fetched_data.csv')
        df.to_csv(output_path, index=False)
        print(f"Data exported to CSV at {output_path}")
        
    except Exception as e:
        print(f"Failed to connect or execute query: {e}")

    finally:
        if conn:
            conn.close()
            print("Connection closed.")
    
    return df

def main():
    # Set up argument parsing to allow choosing between dev and prod, and setting record limit
    parser = argparse.ArgumentParser(description="Fetch data from FileMaker database.")
    parser.add_argument(
        "--use-dev", 
        action="store_true", 
        help="Use the development server instead of the production server."
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Limit the number of records to fetch (for testing purposes)."
    )
    
    args = parser.parse_args()

    # Call the data fetching function, passing the dev/prod flag and record limit
    df = fetch_data_from_jdbc(use_dev=args.use_dev, record_limit=args.limit)
    
    # If data is successfully fetched, proceed with other operations (e.g., plotting)
    if not df.empty:
        print("Data fetched and exported successfully.")
    else:
        print("No data was fetched.")

if __name__ == "__main__":
    main()
