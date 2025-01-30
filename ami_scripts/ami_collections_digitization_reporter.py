#!/usr/bin/env python3

import jaydebeapi
import os
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap
import argparse
import re  
import itertools


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

        # Modified query - add projectType
        query = '''
            SELECT 
                CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle,
                CAST("bibliographic.vernacularDivisionCode" AS VARCHAR(255)) AS vernacularDivisionCode,
                'Programmatic Digitization' AS projectType
            FROM tbl_vendor_mediainfo
            UNION ALL
            SELECT 
                CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle,
                CAST("bibliographic.vernacularDivisionCode" AS VARCHAR(255)) AS vernacularDivisionCode,
                CAST("projectType" AS VARCHAR(255)) AS projectType
            FROM tbl_metadata
        '''

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

def combine_division_codes(df):
    """
    Combine the vernacular division codes into broader categories, in-place.
    For example:
        'MUS + RHA': ['MUS', 'RHA', 'mym', 'myh']
        etc.
    Adjust this dictionary as needed for your data.
    """
    combine_dict = {
        'MUS + RHA': ['MUS', 'RHA', 'mym', 'myh'],
        'SCH': ['SCM', 'SCL', 'scb', 'scd'],
        'THE + TOFT': ['THE', 'TOFT', 'myt'],
        'DAN': ['DAN', 'myd'],
        'MSS': ['MSS', 'mao']
    }

    # Create a new column for "combined" codes so we don’t lose the original
    df['combinedDivisionCode'] = df['vernacularDivisionCode']

    for new_label, old_labels in combine_dict.items():
        df.loc[df['combinedDivisionCode'].isin(old_labels), 'combinedDivisionCode'] = new_label

    return df

def process_data(df, division=None, overall_months=18, recent_months=3):
    """
    Filters and aggregates data based on user-selected months.
    - overall_months: how many months to include for the table ranking
    - recent_months : how many months to include for the recent-activity bar chart
    """
    # 1) Convert dateCreated to datetime
    df['dateCreated'] = pd.to_datetime(df['dateCreated'], errors='coerce')

    # 2) Combine the division codes
    df = combine_division_codes(df)

    # 3) Filter by division (if given)
    if division:
        df = df[df['combinedDivisionCode'] == division]

    # 4) Filter to the overall timeframe (default 18 months)
    end_date = datetime.datetime.now()
    start_date = end_date - pd.DateOffset(months=overall_months)
    df = df[df['dateCreated'] >= start_date].copy()

    # 5) Summary table: Unique items by collection
    spec_collection_usage = (
        df.groupby('cmsCollectionTitle')['primaryID']
          .nunique()
          .reset_index()
          .rename(columns={'cmsCollectionTitle': 'SPEC Collection Title', 
                           'primaryID': 'Unique Items'})
          .sort_values(by='Unique Items', ascending=False)
    )

    # 6) Recent trend: unique items per (month, collection)
    df['month'] = df['dateCreated'].dt.to_period('M')
    monthly_trend = df.groupby(['month', 'cmsCollectionTitle'])['primaryID'].nunique().unstack(fill_value=0)

    # 7) Filter to last N months for the bar chart
    if not monthly_trend.empty:
        last_n_months = monthly_trend.index[-recent_months:]
        monthly_trend_filtered = monthly_trend.loc[last_n_months]
        monthly_trend_filtered = monthly_trend_filtered.loc[
            :, monthly_trend_filtered.sum(axis=0) >= 5
        ]
    else:
        monthly_trend_filtered = pd.DataFrame()

    # 8) Build a friendly month-year label for the PDF filename/title
    start_month_year = start_date.strftime("%B %Y")

    # 9) For the new pie chart: group by projectType
    #    We use nunique of primaryID to get the # of unique items
    project_type_counts = (
        df.groupby('projectType')['primaryID']
          .nunique()
          .reset_index(name='Unique Items')
          .sort_values('Unique Items', ascending=False)
    )

    return spec_collection_usage, monthly_trend_filtered, start_month_year, project_type_counts

def generate_pdf_report(
    spec_collection_usage, 
    monthly_trend_filtered, 
    start_month_year, 
    project_type_counts,
    division=None
):
    # 1) Decide the PDF output path
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if division:
        # Use regex to turn "MUS + RHA" -> "MUS_RHA", etc.
        safe_division = re.sub(r"\s*\+\s*", "_", division.strip())
        safe_division = re.sub(r"\s+", "_", safe_division)
        output_file = os.path.join(
            desktop_path, 
            f'Digitized_AMI_Items_{safe_division}_{start_month_year.replace(" ", "_")}_to_present.pdf'
        )
    else:
        output_file = os.path.join(
            desktop_path, 
            f'Digitized_AMI_Items_{start_month_year.replace(" ", "_")}_to_present.pdf'
        )

    # 2) Create PDF pages
    rows_per_page = 25
    cmap = ListedColormap(["#386641", "#6a994e", "#a7c957"])

    with PdfPages(output_file) as pdf:
        # A) Title Page
        plt.figure(figsize=(11, 8.5))
        title_text = (f'Digitized AMI Items per SPEC Collection\n({start_month_year} - Present)' 
                      + (f'\nDivision: {division}' if division else ''))
        plt.text(0.5, 0.5, title_text, ha='center', va='center', fontsize=24, color='#333333')
        plt.axis('off')
        pdf.savefig()
        plt.close()

        # B) Recent Trend Visualization
        if not monthly_trend_filtered.empty:
            plt.figure(figsize=(26, 10))
            ax = monthly_trend_filtered.T.plot(
                kind='bar', stacked=True, figsize=(24, 10), colormap=cmap
            )
            plt.title('Recent AMI Digitization Activity (Last Few Months)', 
                      fontsize=18, color='#333333')
            plt.xlabel('Collection', fontsize=14, color='#333333')
            plt.ylabel('Number of Unique Items Digitized', fontsize=14, color='#333333')
            plt.xticks(rotation=45, ha='right', fontsize=12, color='#333333')
            plt.yticks(fontsize=12, color='#333333')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout(rect=[0, 0, 1, 0.95])

            # 1) Compute total items for each collection across recent months
            collection_sums = monthly_trend_filtered.sum(axis=0).astype(int)

            # 2) Build custom labels: "collection (count)"
            new_labels = [f"{col} ({collection_sums[col]})" for col in monthly_trend_filtered.columns]

            # 3) Apply these labels to the x-axis
            ax.set_xticks(range(len(monthly_trend_filtered.columns)))
            ax.set_xticklabels(new_labels, rotation=45, ha='right')

            plt.legend(loc='best', frameon=False, fontsize=12)
            pdf.savefig()
            plt.close()
        else:
            # If there's no data to visualize
            plt.figure(figsize=(11, 8.5))
            plt.text(0.5, 0.5, 'No recent data to display.', 
                     ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # C) New Pie Chart: Project Type Distribution (overall timeframe)
        if not project_type_counts.empty:
            plt.figure(figsize=(11, 8.5))
            plt.title(
                f'Project Type Distribution ({start_month_year} - Present)',
                fontsize=18,
                color='#333333',
                pad=20
            )

            # Grab data from the project_type_counts DataFrame
            sizes = project_type_counts['Unique Items']
            labels = project_type_counts['projectType']

            # ---- Optionally, sort slices by size (descending or ascending) ----
            #    If you want to see slices in order of largest→smallest around the pie:
            # project_type_counts_sorted = project_type_counts.sort_values(
            #     by='Unique Items', ascending=False
            # ).reset_index(drop=True)
            #
            # sizes = project_type_counts_sorted['Unique Items']
            # labels = project_type_counts_sorted['projectType']

            # Reuse your custom ListedColormap, cycling if needed
            colors = list(itertools.islice(itertools.cycle(cmap.colors), len(labels)))

            # Compute fraction of each slice wrt the total
            total = sizes.sum()
            fractions = sizes / total

            # We'll define a base explode (for large slices) and an additional explode for smaller slices
            base_explode = 0.03  # minimal explode
            max_extra = 0.12     # how much more we explode the smallest slice(s)

            # For each fraction, the explode is base + (some fraction of max_extra)
            # smaller fraction => bigger explode
            # (1 - fraction) makes small slices get a bigger chunk of max_extra
            explode = [base_explode + max_extra * (1 - frac) for frac in fractions]

            patches, texts, autotexts = plt.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=140,
                textprops={'color': '#333333', 'fontsize': 12},
                labeldistance=1.4,  # Move the slice labels further out 
                pctdistance=0.8,    # Move the % labels inward
                wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
                explode=explode
            )

            # Optionally change the color of the percentage text
            for autotext in autotexts:
                autotext.set_color('white')

            plt.axis('equal')  # Make sure the pie is a circle
            pdf.savefig()
            plt.close()
        else:
            # No project type data to display
            plt.figure(figsize=(11, 8.5))
            plt.text(0.5, 0.5, 'No project type data to display.', 
                    ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # D) Paginated Table (existing logic)
        if not spec_collection_usage.empty:
            for i in range(0, len(spec_collection_usage), rows_per_page):
                plt.figure(figsize=(11, 8.5))
                plt.axis('off')
                # Title for the first page
                if i == 0:
                    t = (f'Digitized AMI Items per SPEC Collection, {start_month_year} - Present, Ranked'
                         + (f'\nDivision: {division}' if division else ''))
                    plt.text(0.5, 0.95, t, ha='center', va='center', fontsize=18, color='#333333')

                col_widths = [0.75, 0.15]
                table = plt.table(
                    cellText=spec_collection_usage.iloc[i:i+rows_per_page].values,
                    colLabels=spec_collection_usage.columns,
                    cellLoc='left',
                    colWidths=col_widths,
                    loc='center'
                )
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1.3, 1.2)
                
                pdf.savefig()
                plt.close()
        else:
            plt.figure(figsize=(11, 8.5))
            plt.text(0.5, 0.5, 'No data available to display.', 
                     ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        print(f"PDF report generated successfully: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate AMI PDF report"
    )
    parser.add_argument(
        '-d', '--division',
        help='Only generate report for the specified division (one of: DAN, MSS, MUS + RHA, SCH, THE + TOFT).',
        type=str,
        choices=["DAN", "MSS", "MUS + RHA", "SCH", "THE + TOFT"],
        default=None
    )
    parser.add_argument(
        '--recent_months',
        help='Number of months to include in the "Recent Activity" bar chart (default: 3).',
        type=int,
        default=3
    )
    parser.add_argument(
        '--overall_months',
        help='Number of months to include in the overall usage listing (default: 18).',
        type=int,
        default=18
    )
    args = parser.parse_args()

    df = fetch_data_from_jdbc()
    if not df.empty:
        (spec_collection_usage, 
         monthly_trend_filtered, 
         start_month_year, 
         project_type_counts) = process_data(
            df,
            division=args.division,
            overall_months=args.overall_months,
            recent_months=args.recent_months
        )
        generate_pdf_report(
            spec_collection_usage, 
            monthly_trend_filtered, 
            start_month_year,
            project_type_counts,   # <--- pass it here
            division=args.division
        )
    else:
        print("No data returned from the database. Exiting.")

if __name__ == "__main__":
    main()
