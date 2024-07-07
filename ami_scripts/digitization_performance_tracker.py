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
    parser = argparse.ArgumentParser(description='Generate Production Stats & Visualizations from AMIDB')
    parser.add_argument('-f', '--fiscal', action='store_true',
                        help='organize stats and visualizations by fiscal year instead of calendar year')
    parser.add_argument('-e', '--engineer', nargs='+',
                        help='Filter output by specific engineers (last names).')
    parser.add_argument('-H', '--historical', action='store_true',
                        help='Analyze data from all years instead of just the current year.')
    parser.add_argument('-p', '--previous-fiscal', action='store_true',
                    help='Analyze data from the previous fiscal year.')
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

        query = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "digitizer.operator.lastName", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type", "digitizationProcess.playbackDevice.model", "digitizationProcess.playbackDevice.serialNumber", "bibliographic.cmsCollectionID" FROM tbl_metadata'
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

def process_data(df, args, fiscal=False, previous_fiscal=False):
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

    current_date = datetime.datetime.now()
    current_fiscal_year = get_fiscal_year(current_date)
    previous_fiscal_year = f"FY{int(current_fiscal_year[2:]) - 1}"

    if previous_fiscal:
        df = df[df['fiscal_year'] == previous_fiscal_year].copy()
    elif not args.historical:
        if fiscal:
            df = df[df['fiscal_year'] == current_fiscal_year].copy()
        else:
            df = df[df['calendar_year'] == current_date.year].copy()

    return df

def classify_media_types(df):
    # Create a new DataFrame to avoid modifying the original while it's being sliced
    df_copy = df.copy()

    # Initialize an empty list to store the media types
    media_type = []

    # Iterate over each row in the 'source.object.type' column to classify media types
    for row in df_copy['source.object.type']:
        if row in ['video cassette analog', 'video cassette digital', 'video optical disc', 'video reel']:
            media_type.append('video')
        elif row == 'film':
            media_type.append('film')
        elif row == 'data optical disc':
            media_type.append('data')
        else:
            media_type.append('audio')

    # Assign the list of media types to the 'media_type' column using .loc to ensure proper handling
    df_copy.loc[:, 'media_type'] = media_type

    # Return the modified DataFrame
    return df_copy

def display_monthly_output_by_operator(df, args, fiscal=False, previous_fiscal=False):
    df_pm = df[df['asset.fileRole'] == 'pm']
    df_pm = classify_media_types(df_pm) 

    current_date = datetime.datetime.now()
    current_fiscal_year = get_fiscal_year(current_date)
    previous_fiscal_year = f"FY{int(current_fiscal_year[2:]) - 1}"

    if previous_fiscal:
        df_filtered = df[df['fiscal_year'] == previous_fiscal_year]
        df_pm = df_pm[df_pm['fiscal_year'] == previous_fiscal_year]
        year_label = previous_fiscal_year
    elif args.historical:
        df_filtered = df
        df_pm = df_pm
        year_label = "All Years"
    elif fiscal:
        df_filtered = df[df['fiscal_year'] == current_fiscal_year]
        df_pm = df_pm[df_pm['fiscal_year'] == current_fiscal_year]
        year_label = current_fiscal_year
    else:
        df_filtered = df[df['calendar_year'] == current_date.year]
        df_pm = df_pm[df_pm['calendar_year'] == current_date.year]
        year_label = str(current_date.year)

    # Group by media type and month, count unique IDs
    monthly_media_counts = df_pm.groupby(['media_type', 'month']).agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Rename columns for clarity
    monthly_media_counts.rename(columns={'bibliographic.primaryID': 'Unique Items'}, inplace=True)

    # Summing across months for total per media type
    total_media_counts = monthly_media_counts.groupby('media_type').agg({
        'Unique Items': 'sum'
    }).reset_index()

    total_unique_items = total_media_counts['Unique Items'].sum()  # Calculate the total sum of unique items across all media types
    print(f"Total unique items per media type across {year_label}:")
    print(total_media_counts)
    print(f"Total of all media types: {total_unique_items}")

    # Equipment Usage
    equipment_usage = df_pm.groupby(['digitizationProcess.playbackDevice.model', 'digitizationProcess.playbackDevice.serialNumber'])['bibliographic.primaryID'].nunique().reset_index()
    equipment_usage.columns = ['Device Model', 'Serial Number', 'Unique Items']
    equipment_usage = equipment_usage.sort_values(by='Unique Items', ascending=False)

     # Calculate unique items per SPEC Collection ID
    spec_collection_usage = df_pm.groupby('bibliographic.cmsCollectionID')['bibliographic.primaryID'].nunique().reset_index()
    spec_collection_usage.columns = ['SPEC Collection ID', 'Unique Items']
    spec_collection_usage = spec_collection_usage.sort_values(by='Unique Items', ascending=False)

    # Grouping data by operator and month, and aggregating unique IDs and average duration
    output_by_operator = df_pm.groupby(['digitizer.operator.lastName', 'month']).agg({
        'bibliographic.primaryID': 'nunique',
        'technical.durationMilli.measure': 'mean'  # Calculate average duration
    }).reset_index()

    total_pm_summed = df_pm['bibliographic.primaryID'].nunique()
    print(f"Total digitized items (unique pm across all years): {total_pm_summed}")

    output_by_operator['month'] = pd.to_datetime(output_by_operator['month'])
    output_by_operator = output_by_operator.sort_values('month')

    output_sum = output_by_operator.groupby('digitizer.operator.lastName').agg({
        'bibliographic.primaryID': 'sum',
        'technical.durationMilli.measure': 'mean'
    }).reset_index()
    output_sum['month'] = 'Total'
    output_by_operator_summed = pd.concat([output_by_operator, output_sum], ignore_index=True)

    output_by_operator_summed['formatted_avg_duration'] = pd.to_timedelta(output_by_operator_summed['technical.durationMilli.measure'], unit='ms').dt.components.apply(
        lambda x: f"{int(x['hours']):02}:{int(x['minutes']):02}:{int(x['seconds']):02}", axis=1)

    total_items_per_month_summed = output_sum['bibliographic.primaryID'].sum()
    print(f"Total digitized items (summed across months): {total_items_per_month_summed}")

    df_filtered['technical.fileSize.measure'] = pd.to_numeric(df_filtered['technical.fileSize.measure'], errors='coerce')
    total_file_size = df_filtered['technical.fileSize.measure'].sum()
    formatted_file_size = size(total_file_size, system=si)
    print('\nTotal file size from all records: {}'.format(formatted_file_size))
    print(output_by_operator_summed)

    sns.set_style("whitegrid")
    plt.figure(figsize=(12, 6) if not args.historical else (18, 6))
    sns.lineplot(data=output_by_operator, x='month', y='bibliographic.primaryID', hue='digitizer.operator.lastName', marker='o', linewidth=2)
    title = f'Monthly Digitization Output by Operator (PM role only) - {year_label}'
    plt.title(title)
    plt.xlabel('')
    plt.ylabel('Items Digitized')
    if args.historical:
        plt.xticks(rotation=90)
    else:
        plt.xticks(rotation=45)
    plt.tight_layout()
    plt.legend(title='Digitizer')
    plt.show()

    return output_by_operator, year_label, total_items_per_month_summed, total_file_size, total_media_counts, equipment_usage, spec_collection_usage

def plot_object_format_counts(df, args, fiscal=False, previous_fiscal=False, top_n=10, formatted_file_size="", total_items_per_month_summed=0, media_counts=None):
    if 'digitizer.operator.lastName' not in df.columns:
        print("\nThe 'digitizer.operator.lastName' field is not present in the DataFrame. Skipping the function.\n")
        return

    df_pm = df[df['asset.fileRole'] == 'pm']

    current_date = datetime.datetime.now()
    current_fiscal_year = get_fiscal_year(current_date)
    previous_fiscal_year = f"FY{int(current_fiscal_year[2:]) - 1}"

    if previous_fiscal:
        df_pm = df_pm[df_pm['fiscal_year'] == previous_fiscal_year]
        year_label = previous_fiscal_year
    elif args.historical:
        year_label = "All Years"
    elif fiscal:
        df_pm = df_pm[df_pm['fiscal_year'] == current_fiscal_year]
        year_label = current_fiscal_year
    else:
        df_pm = df_pm[df_pm['calendar_year'] == current_date.year]
        year_label = str(current_date.year)
    
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
    plt.title(f'Top {top_n} Counts of Source Object Formats in {year_label}', fontsize=16, fontweight='bold')
    plt.subplots_adjust(bottom=0.3)

    # Adding annotations
    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')
    
    media_text = ""
    for index, row in media_counts.iterrows():
        media_text += f"\n{row['media_type'].title()}: {row['Unique Items']}"

    # Display total count of all objects digitized and media type counts
    plt.text(0.95, 0.95, f"Total Items Digitized: {total_items_per_month_summed}\nTotal Data Generated: {formatted_file_size}{media_text}", transform=ax.transAxes, horizontalalignment='right',
             verticalalignment='top', fontsize=14, color='black', bbox=dict(facecolor='white', alpha=0.5))
    
    plt.show()

    return format_counts

def plot_objects_by_division_code(df, year_label, min_percentage=1):
    df_pm = df[df['asset.fileRole'] == 'pm']
    objects_by_division_code = df_pm.groupby('bibliographic.vernacularDivisionCode').agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Define the combinations as a dictionary
    combine_dict = {
        'MUS + RHA': ['MUS', 'RHA'],
        'SCM + SCL': ['SCM', 'SCL'],
        'THE + TOFT': ['THE', 'TOFT']
    }

    # Iterate over the dictionary to combine the codes
    for new_code, old_codes in combine_dict.items():
        combined_count = objects_by_division_code.loc[objects_by_division_code['bibliographic.vernacularDivisionCode'].isin(old_codes), 'bibliographic.primaryID'].sum()
        # Remove the old codes rows
        objects_by_division_code = objects_by_division_code.loc[~objects_by_division_code['bibliographic.vernacularDivisionCode'].isin(old_codes)]
        # Add a new row for the combined codes
        new_row = pd.DataFrame({
            'bibliographic.vernacularDivisionCode': [new_code],
            'bibliographic.primaryID': [combined_count]
        })
        objects_by_division_code = pd.concat([objects_by_division_code, new_row], ignore_index=True)

    # Calculate the total and percentage
    total_objects = objects_by_division_code['bibliographic.primaryID'].sum()
    objects_by_division_code['Percentage'] = objects_by_division_code['bibliographic.primaryID'] / total_objects * 100

    # Filter based on the minimum percentage
    objects_by_division_code = objects_by_division_code[objects_by_division_code['Percentage'] >= min_percentage]
    others_count = total_objects - objects_by_division_code['bibliographic.primaryID'].sum()

    if others_count > 0:
        others_row = pd.DataFrame({
            'bibliographic.vernacularDivisionCode': ['Others'],
            'bibliographic.primaryID': [others_count]
        })
        objects_by_division_code = pd.concat([objects_by_division_code, others_row], ignore_index=True)

    # Generating a custom Cubehelix palette
    colors = sns.cubehelix_palette(start=1.5, rot=-1, dark=0.3, light=0.8, reverse=False, n_colors=len(objects_by_division_code))

    plt.figure(figsize=(10, 10))
    plt.pie(objects_by_division_code['bibliographic.primaryID'], labels=objects_by_division_code['bibliographic.vernacularDivisionCode'], autopct='%1.1f%%', startangle=90, colors=colors)
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.title(f'Objects Digitized by Division Code in {year_label}', fontsize=16)
    plt.show()

    return objects_by_division_code
    
def save_plot_to_pdf(data, bar_data, pie_data, args, total_items_per_month_summed, formatted_file_size, year_label, media_counts, equipment_usage, spec_collection_usage):
    engineer_name = "_".join(args.engineer) if args.engineer else ""
    
    # Determine the report type based on the args
    if args.historical:
        report_type = "Historical"
    elif args.fiscal:
        report_type = "Fiscal_Year"
    elif args.previous_fiscal:
        report_type = "Previous_Fiscal_Year"
    else:
        report_type = "Calendar_Year"
    
    # Generate the filename
    if engineer_name:
        pdf_filename = f"Digitization_Report_{engineer_name}_{report_type}_{year_label}.pdf"
    else:
        pdf_filename = f"Digitization_Report_{report_type}_{year_label}.pdf"
    
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
        
        media_text = ""
        for index, row in media_counts.iterrows():
            media_text += f"\n{row['media_type'].title()}: {row['Unique Items']}"
        
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
        # Display total count of all objects digitized, not just those in the chart
        plt.text(0.95, 0.95, f"Total Items Digitized: {total_items_per_month_summed}\nTotal Data Generated: {formatted_file_size}{media_text}", transform=ax.transAxes, horizontalalignment='right',
                verticalalignment='top', fontsize=14, color='black', bbox=dict(facecolor='white', alpha=0.5))
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Pie chart for division codes
        colors = sns.cubehelix_palette(start=1.5, rot=-1, dark=0.3, light=0.8, reverse=False, n_colors=len(pie_data))
        fig, ax = plt.subplots(figsize=(10, 10))
        # Update here: use 'bibliographic.primaryID' instead of 'Count' and 'bibliographic.vernacularDivisionCode' instead of 'DivisionCode'
        ax.pie(pie_data['bibliographic.primaryID'], labels=pie_data['bibliographic.vernacularDivisionCode'], autopct='%1.1f%%', startangle=90, colors=colors)
        ax.set_title(f'Objects Digitized by Division Code in {year_label}', fontsize=16)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        pdf.savefig(fig)
        plt.close(fig)

        #Items Digitized Per SPEC Collection ID
        top_collections = spec_collection_usage.sort_values(by='Unique Items', ascending=False).head(15)  # Display top 15 collections
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.barplot(x='Unique Items', y='SPEC Collection ID', data=top_collections, palette='muted', ax=ax)
        plt.title('Top SPEC Collections Digitized', fontsize=16)
        plt.xlabel('Number of Unique Items')
        plt.ylabel('Collection ID')
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Equipment usage visualization
        top_equipment = equipment_usage.head(15)  # Adjust to display top 10 or 15 as needed
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.barplot(x='Unique Items', y='Device Model', data=top_equipment, palette='viridis', ax=ax)
        plt.title('Top Equipment Used', fontsize=16)
        plt.xlabel('Number of Unique Items Processed')
        plt.ylabel('Equipment Model')
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    print(f"PDF report has been saved to {pdf_path}.")

def main():
    args = get_args()
    df = fetch_data_from_jdbc()
    df_processed = process_data(df, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal)
    line_data, year_label, total_items_per_month_summed, total_file_size, media_counts, equipment_usage, spec_collection_usage = display_monthly_output_by_operator(df_processed, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal)
    if line_data is None:
        print("Error: Missing data. Exiting the program.")
        return
    
    # Format the file size here
    formatted_file_size = format_file_size(total_file_size)

    pie_data = plot_objects_by_division_code(df_processed, year_label)

    bar_data = plot_object_format_counts(df_processed, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal, formatted_file_size=formatted_file_size, total_items_per_month_summed=total_items_per_month_summed, media_counts=media_counts)
    save_plot_to_pdf(line_data, bar_data, pie_data, args, total_items_per_month_summed, formatted_file_size, year_label, media_counts, equipment_usage, spec_collection_usage)

if __name__ == "__main__":
    main()
