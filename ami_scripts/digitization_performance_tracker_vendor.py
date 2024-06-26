#!/usr/bin/env python3

import argparse
import jaydebeapi
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from hurry.filesize import size, si
import numpy as np
import datetime
from matplotlib.backends.backend_pdf import PdfPages

# Setup display options for better readability in the output
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

def get_args():
    parser = argparse.ArgumentParser(description='Generate Production Stats & Cool Visualizations from AMIDB')
    parser.add_argument('-f', '--fiscal', action='store_true',
                        help='organize stats and visualizations by fiscal year instead of calendar year')
    parser.add_argument('-H', '--historical', action='store_true',
                        help='Analyze data from all years instead of just the current year.')
    parser.add_argument('-c', '--combined', action='store_true',
                        help='Combine data from multiple sources into the analysis.')
    return parser.parse_args()

def fetch_data_from_jdbc(args):
    # Load environment variables
    server_ip = os.getenv('FM_SERVER')
    database_name = os.getenv('AMI_DATABASE')
    username = os.getenv('AMI_DATABASE_USERNAME')
    password = os.getenv('AMI_DATABASE_PASSWORD')

    # Dynamically set the JDBC path
    jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

    conn = None
    df = pd.DataFrame()  # Default empty DataFrame in case of issues

    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{server_ip}/{database_name}',
            [username, password],
            jdbc_path
        )
        print("Connection to AMIDB successful!")
        print("Now Fetching Data (Expect 2-3 minutes)")

        # Define your queries
        query1 = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "mediaType", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type" FROM tbl_vendor_mediainfo'
        query2 = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "digitizer.operator.lastName", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type" FROM tbl_metadata'

        # Execute the first query always
        curs = conn.cursor()
        curs.execute(query1)
        columns = [desc[0] for desc in curs.description]
        data1 = [dict(zip(columns, row)) for row in curs.fetchall()]
        df1 = pd.DataFrame(data1)

        # If combined flag is set, execute the second query and combine
        if args.combined:
            curs.execute(query2)
            columns = [desc[0] for desc in curs.description]
            data2 = [dict(zip(columns, row)) for row in curs.fetchall()]
            df2 = pd.DataFrame(data2)
            df = pd.concat([df1, df2], ignore_index=True)
        else:
            df = df1

        print("Data fetched successfully!")
        print(f"Total records fetched: {len(df)}")  

    except Exception as e:
        print(f"Failed to connect or execute query: {e}")
        df = pd.DataFrame()  # Return an empty DataFrame on failure

    finally:
        if conn:
            conn.close()

    return df

def format_file_size(total_bytes):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB"]
    size = total_bytes
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{size:.0f} {units[unit_index]}"  # No decimal places for bytes
    else:
        return f"{size:.2f} {units[unit_index]}"  # Two decimal places for all other units

def get_fiscal_year(date):
    year = date.year
    month = date.month

    if month >= 7:
        fiscal_year = year + 1
    else:
        fiscal_year = year

    return f"FY{str(fiscal_year)[2:]}"

def process_data(df, args, fiscal=False):
    def convert_date(date_str):
        if "-" in str(date_str):
            # YYYY-MM-DD format
            return pd.to_datetime(date_str, format='%Y-%m-%d', errors='coerce')
        else:
            # M/D/Y format
            return pd.to_datetime(date_str, format='%m/%d/%Y', errors='coerce')

    # Apply the function to the date column
    df['technical.dateCreated'] = df['technical.dateCreated'].apply(convert_date)

    # Assigning calendar year, fiscal year, and month using .loc to avoid SettingWithCopyWarning
    df.loc[:, 'calendar_year'] = df['technical.dateCreated'].dt.year
    df.loc[:, 'fiscal_year'] = df['technical.dateCreated'].apply(get_fiscal_year)
    df.loc[:, 'month'] = df['technical.dateCreated'].dt.strftime('%Y-%m')  # Year-Month format

    return df

def display_monthly_output(df, args, fiscal=False):
    df_pm = df[df['asset.fileRole'] == 'pm']
    year_column = 'fiscal_year' if fiscal else 'calendar_year'
    current_year = get_fiscal_year(datetime.datetime.now()) if fiscal else datetime.datetime.now().year

    # Filter data based on the historical flag
    if not args.historical:
        df_filtered = df[df[year_column] == current_year]
        df_pm = df_pm[df_pm[year_column] == current_year]
    else:
        df_filtered = df  # Use the whole dataset if historical is True

    output = df_pm.groupby(['month']).agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Convert month to datetime and sort
    output['month'] = pd.to_datetime(output['month'])
    output = output.sort_values('month')

    # Calculate yearly totals
    total_pm_summed = df_pm['bibliographic.primaryID'].nunique()
    print(f"Total digitized items (unique pm across all years): {total_pm_summed}")
    total_items_per_month_summed = output['bibliographic.primaryID'].sum()
    print(f"Total digitized items (summed across months): {total_items_per_month_summed}")

    # Sum up all the unique bibliographic.primaryID counts into one total and create a single-row DataFrame for it
    total_row = pd.DataFrame({'month': ['Total'], 'bibliographic.primaryID': [output['bibliographic.primaryID'].sum()]})

    # Append the total row to the output DataFrame
    output_summed = pd.concat([output, total_row], ignore_index=True)
    print(output_summed)

    # Convert fileSize to numeric and compute the total
    df_filtered['technical.fileSize.measure'] = pd.to_numeric(df_filtered['technical.fileSize.measure'], errors='coerce')
    total_file_size = df_filtered['technical.fileSize.measure'].sum()
    formatted_file_size = format_file_size(total_file_size)
    print('\nTotal file size from all records: {}'.format(formatted_file_size))

    # Visualize data
    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6) if not args.historical else (18, 6))
    sns.lineplot(data=output, x='month', y='bibliographic.primaryID', marker='o', linewidth=2)
    title = f'Monthly Output - {"Historical" if args.historical else ("Fiscal" if fiscal else "Calendar")} Year: {current_year if not args.historical else "All Years"}'
    plt.title(title)
    plt.xlabel('')
    plt.ylabel('Items Digitized')
    if args.historical:
        plt.xticks(rotation=90)  # Rotate ticks for better readability in historical view
    else:
        plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    return output, current_year if not args.historical else "All Years", total_items_per_month_summed, total_file_size

def plot_object_format_counts(df, args, fiscal=False, top_n=10, formatted_file_size="", total_items_per_month_summed=0):
    df_pm = df[df['asset.fileRole'] == 'pm']
    year_column = 'fiscal_year' if fiscal else 'calendar_year'
    current_year = get_fiscal_year(datetime.datetime.now()) if fiscal else datetime.datetime.now().year

    # Apply year filter conditionally based on the historical flag
    if not args.historical:
        df_pm = df_pm[df_pm[year_column] == current_year]

    # Calculate total count of all digitized items before filtering to top_n
    total_count = df_pm['bibliographic.primaryID'].nunique()

    # Get top n formats
    format_counts = df_pm.groupby('source.object.format')['bibliographic.primaryID'].nunique().nlargest(top_n).reset_index()
    format_counts.columns = ['Format', 'Count']

    # Plotting with annotations
    fig, ax = plt.subplots(figsize=(15, 6))
    sns.barplot(x='Format', y='Count', data=format_counts, palette='viridis', ax=ax)
    plt.xticks(rotation=45)
    plt.xlabel('Format')
    plt.ylabel('Count')
    plt.title(f'Top {top_n} Counts of Source Object Formats in {"All Years" if args.historical else current_year}', fontsize=16, fontweight='bold')
    plt.subplots_adjust(bottom=0.3)

    # Adding annotations for each bar
    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')

    # Display total count of all objects digitized in the top right corner or another suitable location
    plt.text(0.95, 0.95, f'Total Items Digitized: {total_items_per_month_summed}\nTotal Data Generated: {formatted_file_size}', transform=ax.transAxes, horizontalalignment='right',
             verticalalignment='top', fontsize=14, color='black', bbox=dict(facecolor='white', alpha=0.5))

    plt.tight_layout()
    plt.show()

    return format_counts


def save_plot_to_pdf(line_data, bar_data, total_items_per_month_summed, formatted_file_size, args, year_label):    
    if args.combined:
        pdf_filename = f"Combined_AMI_Digitization_Report_{year_label}.pdf"
    else:
        pdf_filename = f"Vendor_AMI_Digitization_Report_{year_label}.pdf"
    
    pdf_path = os.path.join(os.path.expanduser("~"), 'Desktop', pdf_filename)


    with PdfPages(pdf_path) as pdf:
        # Plot for line data
        fig, ax = plt.subplots(figsize=(18, 6) if args.historical else (10, 5))
        sns.lineplot(data=line_data, x='month', y='bibliographic.primaryID', marker='o', linewidth=2, ax=ax)
        plt.title(f'Monthly AMI Digitization Output - {year_label}')
        plt.xlabel('')
        plt.ylabel('Items Digitized')
        plt.xticks(rotation=90 if args.historical else 45)
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Data table for summary by month and year
        if args.historical:
            # Additional adjustments for historical data
            years = line_data['month'].dt.year.unique()
            for year in sorted(years):
                year_data = line_data[line_data['month'].dt.year == year]
                summary_df = year_data.groupby('month').agg({'bibliographic.primaryID': 'sum'}).reset_index()
                summary_df.columns = ['Month', 'Total Items Digitized']
                summary_df['Month'] = summary_df['Month'].dt.strftime('%Y-%m')  # Format month
                yearly_total = pd.DataFrame([{'Month': 'Year Total', 'Total Items Digitized': summary_df['Total Items Digitized'].sum()}])
                summary_df = pd.concat([summary_df, yearly_total], ignore_index=True)

                fig, ax = plt.subplots(figsize=(12, len(summary_df) * 0.5))  # Dynamic height based on number of rows
                ax.axis('off')
                table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, loc='center', cellLoc='center')
                table.auto_set_font_size(True)
                table.scale(1.2, 1.5)  # Adjust scaling for better readability
                pdf.savefig(fig)
                plt.close(fig)
        else:
            # For non-historical data
            summary_df = line_data.groupby('month').agg({'bibliographic.primaryID': 'sum'}).reset_index()
            summary_df.columns = ['Month', 'Total Items Digitized']
            summary_df['Month'] = summary_df['Month'].dt.strftime('%Y-%m')  # Format month
            yearly_total = pd.DataFrame([{'Month': 'Year Total', 'Total Items Digitized': summary_df['Total Items Digitized'].sum()}])
            summary_df = pd.concat([summary_df, yearly_total], ignore_index=True)

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.axis('off')
            table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, loc='center', cellLoc='center')
            table.auto_set_font_size(True)
            table.scale(1.2, 1.2)
            pdf.savefig(fig)
            plt.close(fig)

        # Bar plot with annotations for object format counts
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.barplot(x='Format', y='Count', data=bar_data, palette='viridis', ax=ax)
        plt.xticks(rotation=45)
        plt.xlabel('Format')
        plt.ylabel('Count')
        plt.title(f'Top {len(bar_data)} Counts of AMI Digitized in {year_label}', fontsize=16)
        plt.subplots_adjust(bottom=0.3)

        # Annotate each bar with its height value
        for p in ax.patches:
            height = int(p.get_height())
            ax.annotate(f'{height}', (p.get_x() + p.get_width() / 2., height),
                        ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')

        # Display total count of all objects digitized, not just those in the chart
        plt.text(0.95, 0.95, f'Total Items Digitized: {total_items_per_month_summed}\nTotal Data Generated: {formatted_file_size}', transform=ax.transAxes, horizontalalignment='right',
                 verticalalignment='top', fontsize=14, color='black', bbox=dict(facecolor='white', alpha=0.5))

        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    print(f"PDF report has been saved to {pdf_path}.")


def main():
    args = get_args()
    df = fetch_data_from_jdbc(args)
    df_processed = process_data(df, args, fiscal=args.fiscal)
    line_data, year_label, total_items_per_month_summed, total_file_size = display_monthly_output(df_processed, args, fiscal=args.fiscal)
    if line_data is None:
        print("Error: Missing data. Exiting the program.")
        return

    # Format the file size here
    formatted_file_size = format_file_size(total_file_size)

    # Now pass formatted_file_size to plot_object_format_counts
    bar_data = plot_object_format_counts(df_processed, args, fiscal=args.fiscal, formatted_file_size=formatted_file_size, total_items_per_month_summed=total_items_per_month_summed)
    if bar_data is None:
        print("Error: No data available for plotting format counts. Exiting the program.")
        return

    # Also pass formatted_file_size to save_plot_to_pdf
    save_plot_to_pdf(line_data, bar_data, total_items_per_month_summed, formatted_file_size, args, year_label)

if __name__ == "__main__":
    main()
