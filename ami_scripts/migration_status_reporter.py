#!/usr/bin/env python3

import argparse
import jaydebeapi
import os
import pandas as pd
import datetime

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

def get_args():
    parser = argparse.ArgumentParser(description='Fetch Migration Status Issues from AMIDB')
    parser.add_argument('-e', '--engineer', nargs='+', help='Filter output by specific engineers (last names).')
    return parser.parse_args()

def fetch_data_from_jdbc():
    server_ip = os.getenv('FM_SERVER')
    database_name = os.getenv('AMI_DATABASE')
    username = os.getenv('AMI_DATABASE_USERNAME')
    password = os.getenv('AMI_DATABASE_PASSWORD')
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
        print("Connection to AMIDB successful!")
        print("Now Fetching Data (Expect 2-3 minutes)")

        query = 'SELECT "bibliographic.primaryID", "__migrationExceptions", "__captureIssueNote", "__captureIssueCategory", "issue", "issue.Type", "digitizer.operator.lastName", "source.object.format", "source.object.type" FROM tbl_metadata'
        curs = conn.cursor()
        curs.execute(query)

        columns = [desc[0] for desc in curs.description]
        data = curs.fetchall()
        
        df = pd.DataFrame(data, columns=columns)
        print("Data fetched successfully!")
        print(f"Total records fetched: {len(df)}")
        
    except Exception as e:
        print(f"Failed to connect or execute query: {e}")

    finally:
        if conn:
            conn.close()
    
    return df

def clean_text(text):
    # Replace problematic characters and ensure consistent delimiter use for splitting later
    if text:
        text = text.replace('\r', '; ')  # Ensure every \r introduces a semicolon and a space
        text = text.replace('\n', ' ')  # Replace newlines with a space
        text = '; '.join([t.strip() for t in text.split(';') if t.strip()])  # Remove any empty resulting strings
    return text

def concatenate_issues(df):
    # Clean and split the '__captureIssueCategory' to handle multiple categories properly
    df['__captureIssueCategory'] = df['__captureIssueCategory'].apply(lambda x: clean_text(x) if x is not None else [])

    # Explode the DataFrame on the '__captureIssueCategory' to create a row for each category
    df = df.explode('__captureIssueCategory')

    # Remove duplicates and aggregate, ensuring consistent ordering if needed
    issues_agg = df.groupby('bibliographic.primaryID')['__captureIssueCategory'].agg(lambda x: '; '.join(sorted(set(x.dropna())))).reset_index()

    # Merge this back to the original DataFrame on 'bibliographic.primaryID'
    df = df.drop(columns=['__captureIssueCategory']).drop_duplicates('bibliographic.primaryID').merge(issues_agg, on='bibliographic.primaryID', how='left')
    return df

def main():
    args = get_args()
    df = fetch_data_from_jdbc()

    # Clean fields which may contain special characters or formatting issues
    df['__captureIssueCategory'] = df['__captureIssueCategory'].apply(lambda x: clean_text(x) if x is not None else x)
    df['__captureIssueNote'] = df['__captureIssueNote'].apply(lambda x: clean_text(x) if x is not None else x)

    df = concatenate_issues(df)

    # Define columns to check for blankness
    cols_to_check = ['__migrationExceptions', '__captureIssueNote', 'issue', 'issue.Type', '__captureIssueCategory']

    # Convert 'None' strings to actual None (if needed)
    df[cols_to_check] = df[cols_to_check].replace('None', pd.NA)

    # Filter out records where all specified fields are effectively blank
    df = df.dropna(subset=cols_to_check, how='all')

    # Alternative approach to explicitly check for blank entries if the above doesn't work
    df = df[~df[cols_to_check].fillna('').apply(lambda x: x.str.strip().eq('')).all(axis=1)]

    # Debugging specific primaryID after processing
    print("Processed record for primaryID 470016:")
    print(df[df['bibliographic.primaryID'] == '470016'])

    # Define the desired column order
    column_order = [
        'bibliographic.primaryID',
        'source.object.type',
        'source.object.format',
        '__migrationExceptions',
        'issue.Type',
        'issue',
        '__captureIssueCategory',
        '__captureIssueNote',
        'digitizer.operator.lastName'
    ]

    # Reorder the DataFrame columns
    df = df[column_order]

    # Sort the DataFrame first by '__migrationExceptions' and then by 'issue.Type'
    df = df.sort_values(by=['__migrationExceptions', 'issue.Type'])

    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.expanduser(f'~/Desktop/migration_status_{today_date}.csv')
    
    df.to_csv(file_path, index=False)
    print(f"Data exported successfully to {file_path}")

if __name__ == "__main__":
    main()
