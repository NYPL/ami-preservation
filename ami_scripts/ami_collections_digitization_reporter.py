#!/usr/bin/env python3

import jaydebeapi
import os
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap

def fetch_data_from_jdbc():
    # Load environment variables
    server_ip = os.getenv('FM_SERVER')
    database_name = os.getenv('AMI_DATABASE')
    username = os.getenv('AMI_DATABASE_USERNAME')
    password = os.getenv('AMI_DATABASE_PASSWORD')

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
        print("Connection to AMIDB successful!")
        print("Now Fetching Data (Expect 2-3 minutes)")

        # Modified query with CAST to ensure data types match
        query = '''SELECT CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                          CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                          CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                          CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle 
                   FROM tbl_vendor_mediainfo
                   UNION ALL
                   SELECT CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                          CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                          CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                          CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle 
                   FROM tbl_metadata'''

        curs = conn.cursor()
        curs.execute(query)
        columns = [desc[0] for desc in curs.description]
        data = [dict(zip(columns, row)) for row in curs.fetchall()]
        df = pd.DataFrame(data)

        print("Data fetched successfully!")
        print(f"Total records fetched: {len(df)}")

    except Exception as e:
        print(f"Failed to connect or execute query: {e}")
        df = pd.DataFrame()

    finally:
        if conn:
            conn.close()

    return df

def process_data(df):
    df['dateCreated'] = pd.to_datetime(df['dateCreated'], errors='coerce')
    
    # Calculate the start date as 18 months prior to the current date
    end_date = datetime.datetime.now()
    start_date = end_date - pd.DateOffset(months=18)
    
    df = df[df['dateCreated'] >= start_date].copy()

    spec_collection_usage = df.groupby('cmsCollectionTitle')['primaryID'].nunique().reset_index()
    spec_collection_usage.columns = ['SPEC Collection Title', 'Unique Items']
    spec_collection_usage = spec_collection_usage.sort_values(by='Unique Items', ascending=False)

    # Aggregate data by month to show recent trends
    df['month'] = df['dateCreated'].dt.to_period('M')
    monthly_trend = df.groupby(['month', 'cmsCollectionTitle']).size().unstack(fill_value=0)

    # Filter to only show data for the last three months
    last_three_months = monthly_trend.index[-3:]
    monthly_trend_filtered = monthly_trend.loc[last_three_months]

    # Filter out collections with fewer than 5 items across the last three months
    monthly_trend_filtered = monthly_trend_filtered.loc[:, monthly_trend_filtered.sum(axis=0) >= 5]

    # Extract start date month and year
    start_month_year = start_date.strftime("%B %Y")

    return spec_collection_usage, monthly_trend_filtered, start_month_year

def generate_pdf_report(spec_collection_usage, monthly_trend_filtered, start_month_year):
    # Get the user's desktop path
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    # Create dynamic report filename
    output_file = os.path.join(desktop_path, f'Digitized_AMI_Items_{start_month_year.replace(" ", "_")}_to_present.pdf')

    rows_per_page = 25  # Adjust this number based on the table size and page size

    # Custom color palette
    cmap = ListedColormap(["#386641", "#6a994e", "#a7c957"])

    with PdfPages(output_file) as pdf:
        # Title Page
        plt.figure(figsize=(11, 8.5))
        plt.text(0.5, 0.5, f'Digitized AMI Items per SPEC Collection\n({start_month_year} - Present)', 
                 ha='center', va='center', fontsize=24, color='#333333')
        plt.axis('off')
        pdf.savefig()
        plt.close()

        # Wider Trend Visualization Page (Last 3 Months)
        plt.figure(figsize=(24, 10))  # Increase the height to 10 inches to give more vertical space
        ax = monthly_trend_filtered.T.plot(kind='bar', stacked=True, figsize=(24, 10), colormap=cmap)  # Match the figure size
        plt.title('Recent AMI Digitization Activity (Last 3 Months)', fontsize=18, color='#333333')
        plt.xlabel('Collection', fontsize=14, color='#333333')
        plt.ylabel('Number of Items Digitized', fontsize=14, color='#333333')
        plt.xticks(rotation=45, ha='right', fontsize=12, color='#333333')  # Rotate and align the labels
        plt.yticks(fontsize=12, color='#333333')
        plt.grid(axis='y', linestyle='--', alpha=0.7)

        # Adjust layout to give more space to bars
        plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust the bottom margin

        # Align labels with bars
        ax.set_xticks(range(len(monthly_trend_filtered.columns)))
        ax.set_xticklabels(monthly_trend_filtered.columns, rotation=45, ha='right')
        
        # Place legend inside the top-right corner of the plot
        plt.legend(loc='upper right', bbox_to_anchor=(1, 1), frameon=False, fontsize=12)

        pdf.savefig()
        plt.close()

        # Paginated Table Pages
        for i in range(0, len(spec_collection_usage), rows_per_page):
            plt.figure(figsize=(11, 8.5))
            plt.axis('off')

            # Add a title to the first paginated table page
            if i == 0:
                plt.text(0.5, 0.95, f'Digitized AMI Items per SPEC Collection, {start_month_year} - Present, Ranked', 
                         ha='center', va='center', fontsize=18, color='#333333')

            # Adjusted column widths
            col_widths = [0.75, 0.15]  # Further reduce the width for the Unique Items column
            table = plt.table(cellText=spec_collection_usage.iloc[i:i+rows_per_page].values, 
                              colLabels=spec_collection_usage.columns, cellLoc='left', colWidths=col_widths, loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.3, 1.2)  # Keep the same scale for readability

            pdf.savefig()
            plt.close()

        print(f"PDF report generated successfully: {output_file}")

def main():
    df = fetch_data_from_jdbc()
    if not df.empty:
        spec_collection_usage, monthly_trend_filtered, start_month_year = process_data(df)
        generate_pdf_report(spec_collection_usage, monthly_trend_filtered, start_month_year)

if __name__ == "__main__":
    main()
