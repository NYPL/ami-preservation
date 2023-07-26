#!/usr/bin/env python3

import os
import argparse
import pandas as pd
from hurry.filesize import size, si
import matplotlib.pyplot as plt
from matplotlib import dates
import seaborn as sns

def getYear(s):
  return s.split("-")[0]

def getMonth(s):
  return s.split("-")[1]

def getDay(s):
  return s.split("-")[2]

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

def get_args():
    parser = argparse.ArgumentParser(description='Generate Production Stats & Cool Visualizations from AMIDB MER file')
    parser.add_argument('-s', '--source',
                        help = 'path to the source MER file', required=True)
    args = parser.parse_args()
    return args

def generate_stats(args):
    df = pd.read_csv(args.source, encoding="mac_roman")
    df.dropna(axis=1, how='all')

    
    media_type = []

    for row in df['source.object.type']:
        if row in ['video cassette analog', 'video cassette digital', 'video optical disc', 'video reel']:
            media_type.append('video')
        elif row in ['film']:
           media_type.append('film')
        else:
            media_type.append('audio')
    df['media_type'] = media_type
    
    print('\n------Overall Stats------')
    print('\nTotal number of files created: {}'.format(df['technical.fileFormat'].count()))
    print('Total number of objects digitzed: {}'.format(df['bibliographic.primaryID'].nunique()))

    totaldata = df['technical.fileSize.measure'].sum()
    print('\nTotal data: {}'.format(size(totaldata, system=si)))
    avgsize = df['technical.fileSize.measure'].mean()
    print('Average file size: {}'.format(size(avgsize, system=si)))

    df['date'] = df['technical.dateCreated'].astype(str)
    df['date'].dropna(how ='all')
    df['month']= df['date'].apply(lambda x: getMonth(x))
    df['year']= df['date'].apply(lambda x: getYear(x))

    print('\nFiles by Type/Month: \n')
    print(df.groupby(['month', 'media_type'])['bibliographic.primaryID'].count())
    print('\nObjects by Type/Month: \n')
    print(df.groupby(['month', 'media_type'])['bibliographic.primaryID'].nunique())
    print('\nObjects by Type/Year: \n')
    print(df.groupby(['year', 'media_type'])['bibliographic.primaryID'].nunique())

    #print(df[df['asset.fileRole'].isin(['em', 'sc'])])


    print('\n------PAMI Staff Breakdown------\n')
    print('Objects transferred: \n')
    print(df.groupby(['digitizer.operator.lastName'])['bibliographic.primaryID'].nunique())
    print('By Month: \n')
    print(df.groupby(['digitizer.operator.lastName', 'month'])['bibliographic.primaryID'].nunique())


    """
    month_breakdown = df.groupby(['month'])['bibliographic.primaryID'].unique()
    for item in sorted(month_breakdown['12']):
        print(item)
    """

    df['technical.dateCreated'] = pd.to_datetime(df['technical.dateCreated'], format='%Y-%m-%d', errors='coerce')
    data = df.groupby(pd.Grouper(key='technical.dateCreated', freq='M')).agg(
        {'bibliographic.primaryID': lambda x: x.nunique()})


    # to aggregate stats
    print('\n------Objects by Year------\n')
    print(df.groupby('year').agg(
        {'bibliographic.primaryID': lambda x: x.nunique(),
         'asset.referenceFilename': lambda x: x.count(),
         'technical.durationMilli.measure': 'sum'
        }))


    print('\n------PM Objects + Duration------\n')
    print(df[df['asset.fileRole'].isin(['pm'])].groupby(['year']).agg(
        {'technical.durationMilli.measure': 'sum'
        }))

    print(df.groupby(['asset.fileRole'])['bibliographic.primaryID'].nunique())

    print('\n------Objects by Month------\n')
    print(df.groupby('month').agg(
        {'bibliographic.primaryID': lambda x: x.nunique(),
         'asset.referenceFilename': lambda x: x.count(),
         'technical.fileSize.measure': 'sum'
        }))

    print('\n------PM Objects by Month------\n')
    print(df[df['asset.fileRole'].isin(['pm'])].groupby(['month']).agg(
        {'bibliographic.primaryID': lambda x: x.nunique(),
         'asset.referenceFilename': lambda x: x.count(),
         'technical.fileSize.measure': 'sum'
        }))

    
    print('\n------Objects by Type and Format------\n')
    print(df.groupby(['source.object.type'])['bibliographic.primaryID'].nunique().nlargest(20))
    print(df.groupby(['source.object.format'])['bibliographic.primaryID'].nunique().nlargest(20))
    months = df.groupby(['month'])['bibliographic.primaryID'].nunique().reset_index()


def main():
  arguments = get_args()
  stats = generate_stats(arguments)



if __name__ == '__main__':
  main()
  exit(0)
