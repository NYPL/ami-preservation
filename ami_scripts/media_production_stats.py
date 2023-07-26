#!/usr/bin/env python3

import argparse
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from hurry.filesize import size
import datetime
import numpy as np


pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)


def get_args():
    parser = argparse.ArgumentParser(description='Generate Production Stats & Cool Visualizations from AMIDB MER file')
    parser.add_argument('-s', '--source',
                        help='path to the source MER file', required=True)
    parser.add_argument('-f', '--fiscal', action='store_true',
                        help='organize stats and visualizations by fiscal year instead of calendar year')
    args = parser.parse_args()
    return args


def get_fiscal_year(date):
    year = date.year
    month = date.month

    if month >= 7:
        fiscal_year = year + 1
    else:
        fiscal_year = year

    return f"FY{str(fiscal_year)[2:]}"


def process_data(args):
    df = pd.read_csv(args.source, encoding="mac_roman")
    df['technical.dateCreated'] = pd.to_datetime(df['technical.dateCreated'], format='%Y-%m-%d', errors='coerce')
    df['calendar_year'] = df['technical.dateCreated'].dt.year
    df['fiscal_year'] = df['technical.dateCreated'].apply(get_fiscal_year)
    df['month'] = df['technical.dateCreated'].dt.month  
    
    # Create a unique identifier for each object and fiscal/calendar year combination
    df['unique_object_year'] = df['bibliographic.primaryID'].astype(str) + '_' + df['calendar_year'].astype(str)
    df['unique_object_fiscal_year'] = df['bibliographic.primaryID'].astype(str) + '_' + df['fiscal_year'].astype(str)


    return df


# Function to calculate and print summary statistics
def display_summary_stats(df, groupby_column):
    summary_stats = df.loc[df['asset.fileRole'] == 'pm'].groupby(groupby_column).agg({
        'bibliographic.primaryID': 'nunique',
        'technical.fileFormat': 'count',
        'technical.fileSize.measure': 'sum',
        'technical.durationMilli.measure': 'sum'
    })

    # Convert the file size to a human-readable format
    summary_stats['technical.fileSize.measure'] = summary_stats['technical.fileSize.measure'].apply(size)

    # Convert the duration from milliseconds to hours
    summary_stats['technical.durationMilli.measure'] = summary_stats['technical.durationMilli.measure'].apply(
        lambda x: round(x / 3600000, 2)
    )

    print(summary_stats)


def plot_total_digitization_output(df, year_type):
    # Calculate the monthly digitization output
    total_output = df.loc[df['asset.fileRole'] == 'pm'].groupby([year_type, 'month']).agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Adjust x-axis labels and data based on the year_type
    if year_type == 'fiscal_year':
        total_output['month'] = (total_output['month'] + 5) % 12 + 1
        x_labels = [datetime.date(1900, m, 1).strftime('%b') for m in range(7, 13)] + [datetime.date(1900, m, 1).strftime('%b') for m in range(1, 7)]
    else:
        x_labels = [datetime.date(1900, m, 1).strftime('%b') for m in range(1, 13)]

    # Create the line chart with a larger size
    plt.figure(figsize=(15, 8))
    sns.lineplot(data=total_output, x='month', y='bibliographic.primaryID', marker='o', linewidth=2)

    # Set title and labels
    plt.title('Total Monthly Digitization Output')
    plt.xlabel('Month')
    plt.ylabel('Number of Objects Transferred')

    # Customize the x-axis ticks
    plt.xticks(range(1, 13), x_labels)

    # Show the chart
    plt.show()


def display_monthly_output_by_operator(df, year_type):
    # Calculate the monthly digitization output by operator
    output_by_operator = df.loc[df['asset.fileRole'] == 'pm'].groupby(['digitizer.operator.lastName', 'month']).agg({
        'bibliographic.primaryID': 'nunique'
    })

    output_by_operator = output_by_operator['bibliographic.primaryID']

    # Calculate total output for each operator
    total_output_by_operator = output_by_operator.groupby(level=0).sum()
    
    # Add an additional level to make it compatible with output_by_operator
    total_output_by_operator.index = pd.MultiIndex.from_product([total_output_by_operator.index, ['Total']])

    # Combine the series into a DataFrame
    output_with_totals = pd.concat([output_by_operator, total_output_by_operator]).sort_index()

    print('\nMonthly Digitization Output by Operator:\n')
    print(output_with_totals)


def plot_digitization_output_by_operator(df, year_type):
    # Calculate the monthly digitization output by operator
    output_by_operator = df.loc[df['asset.fileRole'] == 'pm'].groupby([year_type, 'digitizer.operator.lastName', 'month']).agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Adjust x-axis labels and data based on the year_type
    if year_type == 'fiscal_year':
        output_by_operator['month'] = (output_by_operator['month'] + 5) % 12 + 1
        x_labels = [datetime.date(1900, m, 1).strftime('%b') for m in range(7, 13)] + [datetime.date(1900, m, 1).strftime('%b') for m in range(1, 7)]
    else:
        x_labels = [datetime.date(1900, m, 1).strftime('%b') for m in range(1, 13)]

    # Calculate total output for each operator
    total_output_by_operator = output_by_operator.groupby('digitizer.operator.lastName').agg({
        'bibliographic.primaryID': 'sum'
    })

    # Find the five highest producers
    top_producers = total_output_by_operator.nlargest(5, 'bibliographic.primaryID').index

    # Filter the DataFrame to include only the five top producers
    output_by_operator_filtered = output_by_operator[output_by_operator['digitizer.operator.lastName'].isin(top_producers)]

    # Create the line chart with a larger size
    plt.figure(figsize=(15, 8))
    sns.lineplot(data=output_by_operator_filtered, x='month', y='bibliographic.primaryID', hue='digitizer.operator.lastName', marker='o', linewidth=2)

    # Set title and labels
    plt.title('Monthly Digitization Output by Operator (Top Producers)')
    plt.xlabel('Month')
    plt.ylabel('Number of Objects Transferred')

    # Customize the x-axis ticks
    plt.xticks(range(1, 13), x_labels)

    # Show the chart
    plt.show()


def autopct_generator(limit):
    def inner_autopct(pct):
        return f"{pct:.1f}%" if pct > limit else ""
    return inner_autopct


def plot_objects_by_division_code(df, year_type, min_percentage=1):
    objects_by_division_code = df.loc[df['asset.fileRole'] == 'pm'].groupby('bibliographic.vernacularDivisionCode').agg({
        'bibliographic.primaryID': 'nunique'
    }).reset_index()

    # Combine MUS and RHA
    mus_rha_combined = objects_by_division_code.loc[objects_by_division_code['bibliographic.vernacularDivisionCode'].isin(['MUS', 'RHA']), 'bibliographic.primaryID'].sum()
    objects_by_division_code = objects_by_division_code.loc[~objects_by_division_code['bibliographic.vernacularDivisionCode'].isin(['MUS', 'RHA'])]
    
    new_row = pd.DataFrame({
        'bibliographic.vernacularDivisionCode': ['MUS + RHA'],
        'bibliographic.primaryID': [mus_rha_combined]
    })
    objects_by_division_code = pd.concat([objects_by_division_code, new_row], ignore_index=True)

    total_objects = objects_by_division_code['bibliographic.primaryID'].sum()

    objects_by_division_code = objects_by_division_code[objects_by_division_code['bibliographic.primaryID'] / total_objects * 100 >= min_percentage]

    others_count = total_objects - objects_by_division_code['bibliographic.primaryID'].sum()
    if others_count > 0:
        others_row = pd.DataFrame({
            'bibliographic.vernacularDivisionCode': ['Others'],
            'bibliographic.primaryID': [others_count]
        })
        objects_by_division_code = pd.concat([objects_by_division_code, others_row], ignore_index=True)

    color_palette = sns.color_palette("rocket", n_colors=len(objects_by_division_code))
    color_palette[0] = sns.dark_palette("#905d36", n_colors=2)[0]  # Slightly less dark first color

    labels_with_counts = [f"{division_code} ({count})" for division_code, count in zip(objects_by_division_code['bibliographic.vernacularDivisionCode'], objects_by_division_code['bibliographic.primaryID'])]

    plt.figure(figsize=(12, 12))
    wedges, texts, autotexts = plt.pie(objects_by_division_code['bibliographic.primaryID'],
                                       labels=labels_with_counts,
                                       autopct=autopct_generator(1),
                                       colors=color_palette,
                                       pctdistance=0.85,
                                       startangle=90,
                                       explode=np.ones(len(objects_by_division_code)) * 0.1,
                                       shadow=False)

    centre_circle = plt.Circle((0, 0), 0.60, fc='white')
    fig = plt.gcf()
    fig.gca().add_artist(centre_circle)

    title = plt.title('Objects Digitized by Division Code', fontsize=24, fontfamily='Arial')
    title.set_weight('bold')

    for text in texts + autotexts:
        text.set_fontsize(12)

    plt.show()


def plot_object_format_counts(df, year_type, top_n=20):
    format_counts = df.loc[df['asset.fileRole'] == 'pm'].groupby('source.object.format')['bibliographic.primaryID'].nunique().reset_index().sort_values('bibliographic.primaryID', ascending=False).head(top_n)
    format_counts.columns = ['source.object.format', 'count']

    fig, ax = plt.subplots(figsize=(15, 6))
    sns.barplot(x='source.object.format', y='count', data=format_counts, palette='mako', ax=ax)
    plt.title(f'Top {top_n} Counts of Source Object Formats', fontsize=16, fontweight='bold')
    plt.xlabel('Source Object Format')
    plt.ylabel('Count')
    plt.xticks(rotation=90)
    plt.subplots_adjust(bottom=0.3) 
    plt.show()


def display_pivot_table(df, year_type):
    # Drop duplicates based on the unique identifier
    if year_type == 'calendar_year':
        df = df.drop_duplicates(subset='unique_object_year')
    else:
        df = df.drop_duplicates(subset='unique_object_fiscal_year')

    # Create a pivot table for objects transferred by media type and year_type (calendar or fiscal year)
    pivot_table = pd.pivot_table(df, index='media_type', columns=year_type, values='bibliographic.primaryID', aggfunc='nunique')
    pivot_table = pivot_table.fillna(0).astype(int)  # Fill NaN with 0 and convert to integers

    print_title = ' '.join([word.capitalize() for word in year_type.split('_')])  # This will capitalize the first letter of each word and join them with a space
    
    print(f'\nObjects Transferred by Media Type and {print_title}:\n')
    print(pivot_table)


def compare_monthly_object_counts(df):
    # Filter DataFrame to include only rows with asset.fileRole == 'pm'
    df_filtered = df[df['asset.fileRole'] == 'pm']

    # Keep only the earliest dateCreated per bibliographic.primaryID
    df_filtered = df_filtered.sort_values('technical.dateCreated').drop_duplicates(subset=['bibliographic.primaryID'], keep='first')

    # Convert 'fiscal_year' column to the format 'FY23', 'FY24' etc.
    df_filtered['fiscal_year'] = df_filtered['technical.dateCreated'].apply(get_fiscal_year)

    # Calendar Year Pivot Table
    calendar_year_pivot = pd.pivot_table(df_filtered, index='month', columns='calendar_year', values='bibliographic.primaryID', aggfunc='nunique')
    calendar_year_pivot = calendar_year_pivot.fillna(0).astype(int)

    # Fiscal Year Pivot Table
    df_filtered['fiscal_month'] = (df_filtered['month'] - 7) % 12 + 1  # Convert calendar months to fiscal months
    fiscal_year_pivot = pd.pivot_table(df_filtered, index='fiscal_month', columns='fiscal_year', values='bibliographic.primaryID', aggfunc='nunique')
    fiscal_year_pivot = fiscal_year_pivot.fillna(0).astype(int)

    print('\nMonthly Objects Transferred by Calendar Year:\n')
    print(calendar_year_pivot)
    print('\nMonthly Objects Transferred by Fiscal Year:\n')
    print(fiscal_year_pivot)


def main():
    args = get_args()
    df = process_data(args)

    year_type = 'fiscal_year' if args.fiscal else 'calendar_year'

    print(f'\nSummary Statistics by {year_type.capitalize()}:\n')
    display_summary_stats(df, year_type)

    media_type = []
    for row in df['source.object.type']:
        if row in ['video cassette analog', 'video cassette digital', 'video optical disc', 'video reel']:
            media_type.append('video')
        elif row in ['film']:
            media_type.append('film')
        else:
            media_type.append('audio')
    df['media_type'] = media_type


    # Display and plot the monthly digitization output
    display_monthly_output_by_operator(df, year_type)
    plot_total_digitization_output(df, year_type)
    plot_digitization_output_by_operator(df, year_type)  

    plot_objects_by_division_code(df, year_type)
    plot_object_format_counts(df, year_type)
    display_pivot_table(df, year_type)
    compare_monthly_object_counts(df)

    
if __name__ == '__main__':
    main()
