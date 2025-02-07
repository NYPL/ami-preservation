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
import seaborn as sns  # NEW: Import seaborn for the new chart


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

        # UPDATED QUERY: Add source.object.format to both parts of the UNION.
        query = '''
            SELECT 
                CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle,
                CAST("bibliographic.vernacularDivisionCode" AS VARCHAR(255)) AS vernacularDivisionCode,
                CAST("source.object.format" AS VARCHAR(255)) AS format,
                'Programmatic Digitization' AS projectType
            FROM tbl_vendor_mediainfo
            UNION ALL
            SELECT 
                CAST("asset.referenceFilename" AS VARCHAR(255)) AS referenceFilename, 
                CAST("bibliographic.primaryID" AS VARCHAR(255)) AS primaryID, 
                CAST("technical.dateCreated" AS VARCHAR(50)) AS dateCreated, 
                CAST("cmsCollectionTitle" AS VARCHAR(255)) AS cmsCollectionTitle,
                CAST("bibliographic.vernacularDivisionCode" AS VARCHAR(255)) AS vernacularDivisionCode,
                CAST("source.object.format" AS VARCHAR(255)) AS format,
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
    - overall_months: how many months to include for the table ranking and overall aggregations.
    - recent_months : how many months to include for the recent-activity bar chart.
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

    # 9) Project Type Distribution: count unique items by projectType
    project_type_counts = (
        df.groupby('projectType')['primaryID']
          .nunique()
          .reset_index(name='Unique Items')
          .sort_values('Unique Items', ascending=False)
    )

    # 10) Items Digitized by Format for the overall timeframe (top 10 formats)
    top_n = 10
    format_counts = (
        df.groupby('format')['primaryID']
          .nunique()
          .nlargest(top_n)
          .reset_index()
          .rename(columns={'format': 'Format', 'primaryID': 'Count'})
    )

    # 11) Chronological Table: Merge overall counts with the most recent digitization date per collection.
    if not spec_collection_usage.empty:
        recent_activity = (
            df.groupby('cmsCollectionTitle')['dateCreated']
              .max()
              .reset_index()
              .rename(columns={'cmsCollectionTitle': 'SPEC Collection Title', 'dateCreated': 'Most Recent Date'})
        )
        chronological_table = pd.merge(spec_collection_usage, recent_activity, on='SPEC Collection Title')
        chronological_table = chronological_table.sort_values(by='Most Recent Date', ascending=False)
    else:
        chronological_table = pd.DataFrame()

    return spec_collection_usage, monthly_trend_filtered, start_month_year, project_type_counts, format_counts, chronological_table


def generate_pdf_report(
    spec_collection_usage, 
    monthly_trend_filtered, 
    start_month_year, 
    project_type_counts,
    format_counts,
    chronological_table,
    division=None
):
    # 1) Decide the PDF output path
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if division:
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

    rows_per_page = 25

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
            num_recent_months = len(monthly_trend_filtered.index)
            if num_recent_months <= 3:
                recent_colors = ["#386641", "#6a994e", "#a7c957"]
            elif num_recent_months <= 6:
                recent_colors = ["#386641", "#6a994e", "#a7c957", "#F4D35E", "#EE964B", "#F95738"][:num_recent_months]
            else:
                cmap_dynamic = plt.get_cmap("tab20")
                recent_colors = [cmap_dynamic(i) for i in range(num_recent_months)]
            
            plt.figure(figsize=(24, 10))
            ax = monthly_trend_filtered.T.plot(
                kind='bar', stacked=True, figsize=(24, 10), color=recent_colors
            )
            plt.title('Recent AMI Digitization Activity (Last Few Months)', fontsize=18, color='#333333')
            plt.xlabel('Collection', fontsize=14, color='#333333', labelpad=10)
            plt.ylabel('Number of Items Digitized', fontsize=14, color='#333333')
            plt.xticks(rotation=45, ha='right', fontsize=12, color='#333333')
            plt.yticks(fontsize=12, color='#333333')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.subplots_adjust(bottom=0.05)
            plt.tight_layout(rect=[0.02, 0.02, 1, 0.95])

            # Update the x-axis labels to include total counts per collection
            collection_sums = monthly_trend_filtered.sum(axis=0).astype(int)
            new_labels = [f"{col} ({collection_sums[col]})" for col in monthly_trend_filtered.columns]
            ax.set_xticks(range(len(monthly_trend_filtered.columns)))
            ax.set_xticklabels(new_labels, rotation=45, ha='right')

            plt.legend(loc='best', frameon=False, fontsize=12)
            pdf.savefig()
            plt.close()
        else:
            plt.figure(figsize=(11, 8.5))
            plt.text(0.5, 0.5, 'No recent data to display.', ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # C) Horizontal Bar Chart: Project Type Distribution
        if not project_type_counts.empty:
            plt.figure(figsize=(15, 8.5))
            plt.title(f'Project Type Distribution ({start_month_year} - Present)', fontsize=18, color='#333333', pad=20)
            pt_sorted = project_type_counts.sort_values(by='Unique Items', ascending=True)
            labels = pt_sorted['projectType']
            sizes = pt_sorted['Unique Items']

            base_project_type_colors = ["#003f5c", "#58508d", "#bc5090", "#ff6361", "#ffa600", "#ff8c42"]
            num_project_types = len(pt_sorted)
            project_type_colors = base_project_type_colors[:num_project_types]

            bars = plt.barh(range(len(pt_sorted)), sizes, color=project_type_colors, edgecolor='white')
            plt.yticks(range(len(pt_sorted)), labels, fontsize=12, color='#333333')
            plt.xlabel('Number of Unique Items', fontsize=14, color='#333333')

            for i, bar in enumerate(bars):
                width = bar.get_width()
                plt.text(width + max(sizes)*0.01, bar.get_y() + bar.get_height()/2,
                         f'{sizes.iloc[i]}', va='center', fontsize=12, color='#333333')
            
            plt.subplots_adjust(right=0.95)
            plt.tight_layout()
            pdf.savefig()
            plt.close()
        else:
            plt.figure(figsize=(15, 8.5))
            plt.text(0.5, 0.5, 'No project type data to display.', ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # D) Items Digitized by Format (Overall Months)
        if not format_counts.empty:
            plt.figure(figsize=(15, 8.5))
            ax = sns.barplot(x='Format', y='Count', data=format_counts, palette='viridis',
                             hue='Format', dodge=False, legend=False)
            plt.xticks(rotation=45, ha='right', fontsize=12, color='#333333')
            plt.xlabel('Format', fontsize=14, color='#333333')
            plt.ylabel('Count', fontsize=14, color='#333333')
            plt.title(f'Top {len(format_counts)} Formats Digitized ({start_month_year} - Present)', fontsize=18, color='#333333')
            plt.subplots_adjust(bottom=0.35, top=0.9)
            current_ylim = ax.get_ylim()
            ax.set_ylim(0, current_ylim[1] * 1.10)
            for p in ax.patches:
                ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                            ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')
            plt.tight_layout()
            pdf.savefig()
            plt.close()
        else:
            plt.figure(figsize=(15, 6))
            plt.text(0.5, 0.5, 'No digitized format data to display.', ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # E) Paginated Table: Overall Count by Collection (Ranked)
        if not spec_collection_usage.empty:
            for i in range(0, len(spec_collection_usage), rows_per_page):
                plt.figure(figsize=(11, 8.5))
                plt.axis('off')
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
            plt.text(0.5, 0.5, 'No data available to display.', ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        # F) Chronological Table: Chronological View of Digitized Items
        if not chronological_table.empty:
            # Format the Most Recent Date column to display only YYYY-MM-DD
            chronological_table['Most Recent Date'] = pd.to_datetime(chronological_table['Most Recent Date']) \
                                                       .dt.strftime('%Y-%m-%d')
            for i in range(0, len(chronological_table), rows_per_page):
                plt.figure(figsize=(11, 8.5))
                plt.axis('off')
                if i == 0:
                    # Build the title on multiple lines to avoid cutting off the Division text.
                    title_text = f"Chronological View of Digitized AMI Items\n({start_month_year} - Present)"
                    if division:
                        title_text += f"\nDivision: {division}"
                    plt.text(0.5, 0.95, title_text, ha='center', va='center', fontsize=18, color='#333333')
                # Adjust column widths: widen the SPEC Collection Title column a bit less and narrow the other columns.
                col_widths = [0.55, 0.15, 0.15]
                table = plt.table(
                    cellText=chronological_table.iloc[i:i+rows_per_page].values,
                    colLabels=chronological_table.columns,
                    cellLoc='left',
                    colWidths=col_widths,
                    loc='center'
                )
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                # Reduce the horizontal scaling factor to ensure the right border is visible.
                table.scale(1.1, 1.2)
                plt.tight_layout()
                pdf.savefig()
                plt.close()
        else:
            plt.figure(figsize=(11, 8.5))
            plt.text(0.5, 0.5, 'No chronological data to display.', ha='center', va='center', fontsize=16)
            plt.axis('off')
            pdf.savefig()
            plt.close()

        print(f"PDF report generated successfully: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate AMI PDF report")
    parser.add_argument(
        '-d', '--division',
        help='Only generate report for the specified division (one of: DAN, MSS, MUS + RHA, SCH, THE + TOFT).',
        type=str,
        choices=["DAN", "MSS", "MUS + RHA", "SCH", "THE + TOFT"],
        default=None
    )
    parser.add_argument(
        '--all',
        help='Generate separate reports for all divisions (DAN, MSS, MUS + RHA, SCH, THE + TOFT).',
        action='store_true'
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
    # Option to supply a CSV as input, bypassing the JDBC fetch.
    parser.add_argument(
        '--input_csv',
        help='Path to a CSV file to use as input instead of fetching from the database.',
        type=str,
        default=None
    )
    # Option to output the fetched data as CSV for future testing.
    parser.add_argument(
        '--output_csv',
        help='Path to output the fetched database data as CSV (only applicable if --input_csv is not used).',
        type=str,
        default=None
    )
    args = parser.parse_args()

    # If an input CSV is provided, load data from that file.
    if args.input_csv:
        print(f"Using input CSV: {args.input_csv}")
        df = pd.read_csv(args.input_csv)
    else:
        df = fetch_data_from_jdbc()
        # If output_csv is specified and we fetched from the database, write the DataFrame to CSV.
        if not df.empty and args.output_csv:
            df.to_csv(args.output_csv, index=False)
            print(f"CSV output written to: {args.output_csv}")

    if df.empty:
        print("No data returned. Exiting.")
        return

    # If --all flag is used, generate a separate report for each division.
    if args.all:
        divisions = ["DAN", "MSS", "MUS + RHA", "SCH", "THE + TOFT"]
        for div in divisions:
            print(f"Generating report for division: {div}")
            (spec_collection_usage, 
             monthly_trend_filtered, 
             start_month_year, 
             project_type_counts,
             format_counts,
             chronological_table) = process_data(
                df,
                division=div,
                overall_months=args.overall_months,
                recent_months=args.recent_months
            )
            generate_pdf_report(
                spec_collection_usage, 
                monthly_trend_filtered, 
                start_month_year,
                project_type_counts,
                format_counts,
                chronological_table,
                division=div
            )
    else:
        # Otherwise, generate a single report (for the specified division or for all data if no division is given)
        division = args.division
        (spec_collection_usage, 
         monthly_trend_filtered, 
         start_month_year, 
         project_type_counts,
         format_counts,
         chronological_table) = process_data(
            df,
            division=division,
            overall_months=args.overall_months,
            recent_months=args.recent_months
        )
        generate_pdf_report(
            spec_collection_usage, 
            monthly_trend_filtered, 
            start_month_year,
            project_type_counts,
            format_counts,
            chronological_table,
            division=division
        )


if __name__ == "__main__":
    main()
