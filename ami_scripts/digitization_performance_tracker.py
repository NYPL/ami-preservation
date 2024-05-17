#!/usr/bin/env python3

import argparse
import jaydebeapi
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from hurry.filesize import size
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
    parser.add_argument('-e', '--engineer', nargs='+',
                        help='Filter output by specific engineers (last names).')
    parser.add_argument('-H', '--historical', action='store_true',
                        help='Analyze data from all years instead of just the current year.')
    return parser.parse_args()

def fetch_data_from_jdbc():
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

        query = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "digitizer.operator.lastName", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type" FROM tbl_metadata'
        curs = conn.cursor()
        curs.execute(query)

        columns = [desc[0] for desc in curs.description]
        data = [dict(zip(columns, row)) for row in curs.fetchall()]

        df = pd.DataFrame(data)
        print("Data fetched successfully!")
        print(f"Total records fetched: {len(df)}")  
        
    except Exception as e:
        print(f"Failed to connect or execute query: {e}")

    finally:
        if conn:
            conn.close()
    
    return df

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

    # Filter by engineer if specified
    if args.engineer:
        df = df[df['digitizer.operator.lastName'].isin(args.engineer)].copy()

    # Assigning calendar year, fiscal year, and month using .loc to avoid SettingWithCopyWarning
    df.loc[:, 'calendar_year'] = df['technical.dateCreated'].dt.year
    df.loc[:, 'fiscal_year'] = df['technical.dateCreated'].apply(get_fiscal_year)
    df.loc[:, 'month'] = df['technical.dateCreated'].dt.strftime('%Y-%m')  # Year-Month format

    return df

def display_monthly_output_by_operator(df, args, fiscal=False):
    df_pm = df[df['asset.fileRole'] == 'pm']
    year_column = 'fiscal_year' if fiscal else 'calendar_year'
    current_year = get_fiscal_year(datetime.datetime.now()) if fiscal else datetime.datetime.now().year

    # Filter data based on the historical flag
    if not args.historical:
        df_pm = df_pm[df_pm[year_column] == current_year]

    # Grouping data by operator and month, and aggregating unique IDs and average duration
    output_by_operator = df_pm.groupby(['digitizer.operator.lastName', 'month']).agg({
        'bibliographic.primaryID': 'nunique',
        'technical.durationMilli.measure': 'mean'  # Calculate average duration
    }).reset_index()

    # Convert month to datetime and sort
    output_by_operator['month'] = pd.to_datetime(output_by_operator['month'])
    output_by_operator = output_by_operator.sort_values('month')

    # Calculating total items and average duration per operator
    output_sum = output_by_operator.groupby('digitizer.operator.lastName').agg({
        'bibliographic.primaryID': 'sum',
        'technical.durationMilli.measure': 'mean'  # Average of monthly averages
    }).reset_index()
    output_sum['month'] = 'Total'

    # Concatenating monthly data with summary data
    output_by_operator_summed = pd.concat([output_by_operator, output_sum], ignore_index=True)

    # Adding a new column for formatted average duration
    output_by_operator_summed['formatted_avg_duration'] = pd.to_timedelta(output_by_operator_summed['technical.durationMilli.measure'], unit='ms').dt.components.apply(
        lambda x: f"{int(x['hours']):02}:{int(x['minutes']):02}:{int(x['seconds']):02}", axis=1)

    print(output_by_operator_summed)

    # Visualize data
    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6) if not args.historical else (18, 6))
    sns.lineplot(data=output_by_operator, x='month', y='bibliographic.primaryID', hue='digitizer.operator.lastName', marker='o', linewidth=2)
    title = f'Monthly Digitization Output by Operator (PM role only) - {"Historical" if args.historical else ("Fiscal" if fiscal else "Calendar")} Year: {current_year if not args.historical else "All Years"}'
    plt.title(title)
    plt.xlabel('')
    plt.ylabel('Items Digitized')
    if args.historical:
        plt.xticks(rotation=90)  # Rotate ticks for better readability in historical view
    else:
        plt.xticks(rotation=45)
    plt.tight_layout()
    plt.legend(title='Digitizer')
    plt.show()

    return output_by_operator, current_year if not args.historical else "All Years"


def plot_object_format_counts(df, args, fiscal=False, top_n=10):
    if 'digitizer.operator.lastName' not in df.columns:
        print("\nThe 'digitizer.operator.lastName' field is not present in the DataFrame. Skipping the function.\n")
        return

    df_pm = df[df['asset.fileRole'] == 'pm']
    year_column = 'fiscal_year' if fiscal else 'calendar_year'
    current_year = get_fiscal_year(datetime.datetime.now()) if fiscal else datetime.datetime.now().year

    # Apply year filter conditionally based on the historical flag
    if not args.historical:
        df_pm = df_pm[df_pm[year_column] == current_year]
    
    if args.engineer:
        df_pm = df_pm[df_pm['digitizer.operator.lastName'].isin(args.engineer)]

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

    # Adding annotations
    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')

    plt.show()

    return format_counts

def save_plot_to_pdf(data, bar_data, args, year_label):
    engineer_name = "_".join(args.engineer) if args.engineer else ""
    pdf_filename = f"Digitization_Report_{engineer_name}_{year_label}.pdf" if engineer_name else f"Digitization_Report_{year_label}.pdf"
    pdf_path = os.path.join(os.path.expanduser("~"), 'Desktop', pdf_filename)

    with PdfPages(pdf_path) as pdf:
        # Adjust plot size based on historical flag
        fig_size = (18, 6) if args.historical else (10, 5)
        xticks_rotation = 90 if args.historical else 45

        # Plot for line data
        fig, ax = plt.subplots(figsize=fig_size)
        sns.lineplot(data=data, x='month', y='bibliographic.primaryID', hue='digitizer.operator.lastName', marker='o', linewidth=2, ax=ax)
        plt.title(f'Monthly Digitization Output by Operator - {year_label}')
        plt.xlabel('')
        plt.ylabel('Items Digitized')
        plt.xticks(rotation=xticks_rotation)
        plt.legend(title='Digitizer')
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Data table for summary by month and year
        if args.historical:
            # Additional adjustments for historical data
            years = data['month'].dt.year.unique()
            for year in sorted(years):
                year_data = data[data['month'].dt.year == year]
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
            summary_df = data.groupby('month').agg({'bibliographic.primaryID': 'sum'}).reset_index()
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
        plt.title(f'Top {len(bar_data)} Counts of Source Object Formats in {year_label}', fontsize=16)
        plt.subplots_adjust(bottom=0.3)
        for p in ax.patches:
            ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    print(f"PDF report has been saved to {pdf_path}.")

def main():
    args = get_args()
    df = fetch_data_from_jdbc()
    df_processed = process_data(df, args, fiscal=args.fiscal)
    line_data, year_label = display_monthly_output_by_operator(df_processed, args, fiscal=args.fiscal)
    if line_data is None:  # Check if line_data is None before proceeding
        print("Error: Missing data. Exiting the program.")
        return
    bar_data = plot_object_format_counts(df_processed, args, fiscal=args.fiscal)
    save_plot_to_pdf(line_data, bar_data, args, year_label)

if __name__ == "__main__":
    main()
