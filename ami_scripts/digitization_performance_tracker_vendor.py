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
    parser.add_argument('-p', '--previous-fiscal', action='store_true',
                    help='Analyze data from the previous fiscal year.')    
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
        query1 = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "mediaType", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type", "bibliographic.cmsCollectionID" FROM tbl_vendor_mediainfo'
        query2 = 'SELECT "bibliographic.primaryID", "technical.dateCreated", "technical.fileFormat", "technical.fileSize.measure", "technical.durationMilli.measure", "asset.fileRole", "digitizer.operator.lastName", "bibliographic.vernacularDivisionCode", "source.object.format", "source.object.type", "bibliographic.cmsCollectionID" FROM tbl_metadata'

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
            df1['source'] = 'Vendor'  
            df2['source'] = 'In-House'  
            df = pd.concat([df1, df2], ignore_index=True)
        else:
            df = df1
            df['source'] = 'Vendor'  # Default to Vendor if not combined

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

def display_monthly_output(df, args, fiscal=False, previous_fiscal=False):
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


    # Group by both month and source to differentiate the data
    output = df_pm.groupby(['month', 'source']).agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Convert 'month' to datetime and sort
    output['month'] = pd.to_datetime(output['month'])
    output = output.sort_values(['month', 'source'])

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

    # Calculate unique items per SPEC Collection ID
    spec_collection_usage = df_pm.groupby('bibliographic.cmsCollectionID')['bibliographic.primaryID'].nunique().reset_index()
    spec_collection_usage.columns = ['SPEC Collection ID', 'Unique Items']
    spec_collection_usage = spec_collection_usage.sort_values(by='Unique Items', ascending=False)    

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
    sns.lineplot(data=output, x='month', y='bibliographic.primaryID', hue='source', marker='o', linewidth=2)
    title = f'Monthly Output - (PM role only) - {year_label}'
    plt.title(title)
    plt.xlabel('')
    plt.ylabel('Items Digitized')
    plt.legend(title='Source')
    if args.historical:
        plt.xticks(rotation=90)  # Rotate ticks for better readability in historical view
    else:
        plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    return output, year_label, total_items_per_month_summed, total_file_size, total_media_counts, spec_collection_usage

def plot_object_format_counts(df, args, fiscal=False, previous_fiscal=False, top_n=10, formatted_file_size="", total_items_per_month_summed=0, media_counts=None):
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
    plt.title(f'Top {top_n} Counts of Source Object Formats in {year_label}', fontsize=16, fontweight='bold')
    plt.subplots_adjust(bottom=0.3)

    # Adding annotations for each bar
    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom', color='black', xytext=(0, 5), textcoords='offset points')

    media_text = ""
    for index, row in media_counts.iterrows():
        media_text += f"\n{row['media_type'].title()}: {row['Unique Items']}"

    # Display total count of all objects digitized and media type counts
    plt.text(0.95, 0.95, f"Total Items Digitized: {total_items_per_month_summed}\nTotal Data Generated: {formatted_file_size}{media_text}", transform=ax.transAxes, horizontalalignment='right',
             verticalalignment='top', fontsize=14, color='black', bbox=dict(facecolor='white', alpha=0.5))

    plt.tight_layout()
    plt.show()

    return format_counts

def plot_objects_by_division_code(df, year_label, min_percentage=1):
    df_pm = df[df['asset.fileRole'] == 'pm']
    objects_by_division_code = df_pm.groupby('bibliographic.vernacularDivisionCode').agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Define the combinations as a dictionary
    combine_dict = {
        'MUS + RHA': ['MUS', 'RHA', 'mym', 'myh'],
        'SCH': ['SCM', 'SCL', 'scb', 'scd'],
        'THE + TOFT': ['THE', 'TOFT', 'myt'],
        'DAN': ['DAN', 'myd']
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

def save_plot_to_pdf(line_data, bar_data, pie_data, args, total_items_per_month_summed, formatted_file_size, year_label, media_counts, spec_collection_usage):    
    # Determine the report type based on the args
    if args.historical:
        report_type = "Historical"
    elif args.fiscal:
        report_type = "Fiscal_Year"
    elif args.previous_fiscal:
        report_type = "Previous_Fiscal_Year"
    else:
        report_type = "Calendar_Year"
    
    if args.combined:
        pdf_filename = f"Combined_AMI_Digitization_Report_{year_label}.pdf"
    else:
        pdf_filename = f"Vendor_AMI_Digitization_Report_{year_label}.pdf"
    
    pdf_path = os.path.join(os.path.expanduser("~"), 'Desktop', pdf_filename)

    with PdfPages(pdf_path) as pdf:
        # Plot for line data
        fig, ax = plt.subplots(figsize=(18, 6) if args.historical else (10, 5))
        sns.lineplot(data=line_data, x='month', y='bibliographic.primaryID', hue='source', marker='o', linewidth=2, ax=ax)
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

        media_text = ""
        for index, row in media_counts.iterrows():
            media_text += f"\n{row['media_type'].title()}: {row['Unique Items']}"

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

    print(f"PDF report has been saved to {pdf_path}.")


def main():
    args = get_args()
    df = fetch_data_from_jdbc(args)
    df_processed = process_data(df, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal)
    line_data, year_label, total_items_per_month_summed, total_file_size, media_counts, spec_collection_usage = display_monthly_output(df_processed, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal)
    if line_data is None:
        print("Error: Missing data. Exiting the program.")
        return

    # Format the file size here
    formatted_file_size = format_file_size(total_file_size)

    pie_data = plot_objects_by_division_code(df_processed, year_label)

    # Now pass formatted_file_size to plot_object_format_counts
    bar_data = plot_object_format_counts(df_processed, args, fiscal=args.fiscal, previous_fiscal=args.previous_fiscal, formatted_file_size=formatted_file_size, total_items_per_month_summed=total_items_per_month_summed, media_counts=media_counts)
    if bar_data is None:
        print("Error: No data available for plotting format counts. Exiting the program.")
        return

    # Also pass formatted_file_size to save_plot_to_pdf
    save_plot_to_pdf(line_data, bar_data, pie_data, args, total_items_per_month_summed, formatted_file_size, year_label, media_counts, spec_collection_usage)

if __name__ == "__main__":
    main()