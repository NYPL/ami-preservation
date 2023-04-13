#!/usr/bin/env python3

import argparse
from csv import excel
import os
import subprocess
import glob
import pandas as pd
from openpyxl.utils.dataframe import dataframe_to_rows

def get_args():
    parser = argparse.ArgumentParser(description='Prep CMS Excel for Import into AMIDB')
    parser.add_argument('-s', '--source',
                        help = 'path to the source XLSX', required=True)
    parser.add_argument('-w', '--workorder',
                        help = 'Work Order ID to apply to new XLSX', required=False)
    parser.add_argument('-d', '--destination',
                        help = 'path to the output directory', required=False)
    args = parser.parse_args()
    return args

def cleanup_excel(args):
    if args.source:
        excel_name = os.path.basename(args.source)
        clean_name = os.path.splitext(excel_name)[0] + '_CLEAN.xlsx'

        df = pd.read_excel(args.source)

        #drop filename reference, replace with asset.fileRole
        df = df.drop('Filename (reference)', axis=1)
        df = df.drop('MMS Collection ID', axis=1)

        df['asset.fileRole'] = 'pm'

        #schema fix
        df.loc[df['asset.schemaVersion'] == 2, 'asset.schemaVersion'] = '2.0.0'

        #video face fix:
        df.loc[df['source.object.type'] == 'video cassette', 'source.subObject.faceNumber'] = ''
        df.loc[df['source.object.type'] == 'video reel', 'source.subObject.faceNumber'] = ''
        df.loc[df['source.object.type'] == 'video optical', 'source.subObject.faceNumber'] = ''

        #video cassette analog fixes
        df.loc[df['source.object.format'] == 'Betacam', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'Betacam SP', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'Betacam Oxide', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'Betamax', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'Hi8', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'MII', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'S-VHS', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'S-VHS-C', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'U-matic', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'U-matic S', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'U-matic SP', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'VCR', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'VHS', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'VHS-C', 'source.object.type'] = 'video cassette analog'
        df.loc[df['source.object.format'] == 'Video8', 'source.object.type'] = 'video cassette analog'

        #video cassette digital fixes
        df.loc[df['source.object.format'] == 'Betacam SX', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'D-1', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'D-2', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'D-3', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'D-5', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'D-9', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'Digital Betacam', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'Digital8', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'DVCam', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'DVCPRO', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'DVCPRO 50', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'DVCPRO HD', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'HDCAM', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'HDCAM SR', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'HDV', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'MiniDV', 'source.object.type'] = 'video cassette digital'
        df.loc[df['source.object.format'] == 'MPEG IMX', 'source.object.type'] = 'video cassette digital'

        #audio reel analog fixes
        df.loc[df['source.object.format'] == 'half-inch open-reel audio', 'source.object.type'] = 'audio reel analog'
        df.loc[df['source.object.format'] == 'one-inch open-reel audio', 'source.object.type'] = 'audio reel analog'
        df.loc[df['source.object.format'] == 'quarter-inch open-reel audio', 'source.object.type'] = 'audio reel analog'
        df.loc[df['source.object.format'] == 'quarter-inch open-reel audio with Pilottone', 'source.object.type'] = 'audio reel analog'
        df.loc[df['source.object.format'] == 'two-inch open-reel audio', 'source.object.type'] = 'audio reel analog'
        df.loc[df['source.object.format'] == 'eighth-inch open-reel audio', 'source.object.type'] = 'audio reel analog'

        #audio reel digital fixes
        df.loc[df['source.object.format'] == 'ProDigi', 'source.object.type'] = 'audio reel digital'
        df.loc[df['source.object.format'] == 'DASH', 'source.object.type'] = 'audio reel digital'
        df.loc[df['source.object.format'] == 'NAGRA-D', 'source.object.type'] = 'audio reel digital'
        df.loc[df['source.object.format'] == 'half-inch open-reel audio, digital', 'source.object.type'] = 'audio reel digital'

        #audio cassette analog fixes
        df.loc[df['source.object.format'] == '8-track', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Compact cassette', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Microcassette', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Minicassette', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Fidelipac Cartridge', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'RCA Cartridge', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'NAB Cartridge', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Elcaset', 'source.object.type'] = 'audio cassette analog'
        df.loc[df['source.object.format'] == 'Philips Norelco Cartridge', 'source.object.type'] = 'audio cassette analog'

        #audio cassette digital fixes
        df.loc[df['source.object.format'] == 'ADAT', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'DAT', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'DA-88', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'Digital Compact Cassette', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'Betamax/PCM', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'U-matic/PCM', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'VHS/PCM', 'source.object.type'] = 'audio cassette digital'
        df.loc[df['source.object.format'] == 'Hi8/PCM', 'source.object.type'] = 'audio cassette digital'

        #audio optical fix
        df.loc[df['source.object.type'] == 'audio optical', 'source.object.type'] = 'audio optical disc'

        #video optical fix
        df.loc[df['source.object.type'] == 'video optical', 'source.object.type'] = 'video optical disc'


        if args.workorder:

            df['WorkOrderId'] = args.workorder
            #rename column headers
            #df = df.rename(columns={'oldName1': 'newName1', 'oldName2': 'newName2'})
            #df.replace({r'\r\n': ''}, regex=True)
            #df = df.reindex(sorted(df.columns), axis=1)
    if args.destination:
        if os.path.exists(args.destination):
            writer = pd.ExcelWriter(clean_name, engine='xlsxwriter')
            df.to_excel(writer, sheet_name='Sheet1')
            writer.save()

            #output_path = os.path.join(args.destination, clean_name) 
            #df.to_excel(output_path, sheet_name='Sheet1', index=False)



def main():
    arguments = get_args()
    xlsx = cleanup_excel(arguments)


if __name__ == '__main__':
    main()
    exit(0)
