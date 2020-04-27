#!/usr/bin/env python3

import pandas as pd
import sys
from hurry.filesize import size, si

df = pd.read_excel(sys.argv[1], sheet_name='Sheet1')
pd.options.display.max_rows = 999999

print('\n------Overall Stats------')
print('\nTotal number of files: {}'.format(df['technical.fileFormat'].count()))
print('Total number of objects: {}'.format(df['primaryID'].nunique()))

totaldata = df['technical.fileSize.measure'].sum()
print('\nTotal data: {}'.format(size(totaldata, system=si)))
avgsize = df['technical.fileSize.measure'].mean()
print('Average file size: {}'.format(size(avgsize, system=si)))

print('\nTotal data by media type: ')
print(df.groupby(['media-type'])['technical.fileSize.measure'].sum())

avgaudiocassette = df['technical.fileSize.measure'][df['media-type'] == 'audio cassette analog'].sum()
print('\nTotal audiocassette analog data: {}'.format(size(avgaudiocassette, system=si)))


avgwav = df['technical.fileSize.measure'][df['technical.extension'] == 'wav'].mean()
print('\nAverage WAV size: {}'.format(size(avgwav, system=si)))
avgmkv = df['technical.fileSize.measure'][df['technical.extension'] == 'mkv'].mean()
print('Average MKV size: {}'.format(size(avgmkv, system=si)))

totaltime = df['technical.durationMilli.measure'].sum()
hours = totaltime // 3600000
minutes = (totaltime % 3600000) // 60000
seconds = (totaltime % 60000) // 1000
ms = totaltime % 1000
human_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(hours), int(minutes), int(seconds), int(ms))
print('\nTotal duration (HH:MM:SS:MS): {}'.format(human_duration))
avgtime = df['technical.durationMilli.measure'].mean()
minutes = (avgtime % 3600000) // 60000
print('Average duration (min): {}'.format(minutes))

avgwavduration = df['technical.durationMilli.measure'][df['technical.extension'] == 'wav'].mean()
avgmkvduration = df['technical.durationMilli.measure'][df['technical.extension'] == 'mkv'].mean()

avgwavhours = avgwavduration // 3600000
avgwavminutes = (avgwavduration % 3600000) // 60000
avgwavseconds = (avgwavduration % 60000) // 1000
avgwavms = avgwavduration % 1000
avgwav_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(avgwavhours), int(avgwavminutes), int(avgwavseconds), int(avgwavms))
print('Average WAV duration: {}'.format((avgwav_duration)))

avgmkvhours = avgmkvduration // 3600000
avgmkvminutes = (avgmkvduration % 3600000) // 60000
avgmkvseconds = (avgmkvduration % 60000) // 1000
avgmkvms = avgmkvduration % 1000
avgmkv_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(avgmkvhours), int(avgmkvminutes), int(avgmkvseconds), int(avgmkvms))
print('Average MKV duration: {}'.format((avgmkv_duration)))

print('\nTotal duration by media type: ')
print(df.groupby(['media-type'])['technical.durationMilli.measure'].sum())

print('\nObjects by Type: \n')
print(df.groupby(['media-type'])['primaryID'].nunique())

#print('\nObjects by Format: \n')
#print(df.groupby(['format'])['primaryID'].nunique())

print('\n------Format & Role Breakdown------\n')
print(df.groupby(['technical.fileFormat'])['primaryID'].count())

print('')
print(df.groupby(['role', 'media-type'])['technical.fileFormat'].count())

print('\n------Division Breakdown------\n')
print('Files: ')
print(df.groupby(['division'])['asset.referenceFilename'].nunique())
print('\nObjects: ')
print(df.groupby(['division'])['primaryID'].nunique())
print('\nObjects by division and type')
print(df.groupby(['division', 'media-type'])['primaryID'].nunique())



print('\n------CMS Collection Breakdown------\n')
"""
print('Files by CMS Collection: \n')
print(df.groupby(['cms-collection', 'role'])['asset.referenceFilename'].nunique())
"""
print('\nObjects by Collection: \n')
print(df.groupby(['cms-collection'])['primaryID'].nunique())
print('Total objects:')
print(sum(df.groupby(['cms-collection'])['primaryID'].nunique().tolist()))
#print(df.groupby(['cms-collection'].nunique().tolist()))

cms_groups = df.groupby(['cms-collection'])['primaryID'].nunique()
cms_tups = list(zip(cms_groups,cms_groups.index))
for number, collection in cms_tups:
    print(collection)



duration_groups = df.groupby(['cms-collection', 'role'])['technical.durationMilli.measure'].sum()
print(duration_groups)
duration_tups = list(zip(duration_groups, duration_groups.index))
duration_total = []
for duration, cmsnumber in duration_tups:
    if cmsnumber[1] == 'em':
        #duration_total.append(duration)
        hours = duration // 3600000
        minutes = (duration % 3600000) // 60000
        seconds = (duration % 60000) // 1000
        ms = duration % 1000
        human_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(hours), int(minutes), int(seconds), int(ms))
        #print(human_duration)
for duration, cmsnumber in duration_tups:
    if cmsnumber[1] == 'sc':
        duration_total.append(duration)
        hours = duration // 3600000
        minutes = (duration % 3600000) // 60000
        seconds = (duration % 60000) // 1000
        ms = duration % 1000
        human_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(hours), int(minutes), int(seconds), int(ms))
        print(human_duration)
viewing_total = sum(duration_total)
viewing_hours = viewing_total // 3600000
viewing_minutes = (viewing_total % 3600000) // 60000
viewing_seconds = (viewing_total % 60000) // 1000
viewing_ms = viewing_total % 1000
viewing_human_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(viewing_hours), int(viewing_minutes), int(viewing_seconds), int(viewing_ms))
#print(viewing_human_duration)





'''
duration_groups = df.groupby(['cms-collection', 'role'])['technical.durationMilli.measure'].sum().reset_index(name = 'duration')
print(cms_groups)

ex_writer = pd.ExcelWriter('../exceltest.xlsx')
duration_groups.to_excel(ex_writer, 'test')
ex_writer.save()

duration_groups.to_csv('../csvtest.csv')
duration_groups['hours'] = duration_groups.duration.divide(3600000)
duration_groups['minutes'] = duration_groups.duration.mod(3600000).divide(60000)
duration_groups['seconds'] = duration_groups.duration.mod(60000).divide(1000)
duration_groups['ms'] = duration_groups.duration.mod(1000)
duration_groups['humantime'] = duration_groups.hours.round(0).astype(str) + ":" + duration_groups.minutes.round(0).astype(str) + ":" + duration_groups.seconds.round(0).astype(str)
duration_groups.to_csv('../csvtest.csv', index = False)

ex_writer = pd.ExcelWriter('../exceltest.xlsx')
duration_groups.to_excel(ex_writer, 'test', index = False)
ex_writer.save()

#duration_tups = list(zip(duration_groups, duration_groups.index))
#for duration, cmsnumber in duration_tups:
    #print(cmsnumber)

#for duration, cmsnumber in duration_tups:
    hours = duration // 3600000
    minutes = (duration % 3600000) // 60000
    seconds = (duration % 60000) // 1000
    ms = duration % 1000
    duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(hours), int(minutes), int(seconds), int(ms))
    #print(duration)
'''
size_groups = df.groupby(['cms-collection'])['technical.fileSize.measure'].sum()
size_tups = list(zip(size_groups, size_groups.index))

for cmssize, cmsnumber in size_tups:
    gb = size(cmssize, system=si)
    print(gb)

#cms_tups = cms_groups.apply(lambda x: pd.Series([tuple(i) for i in x.values]))
#print(cms_tups)
"""
print('\n------CMS Project Breakdown------\n')
print('Files by CMS Project: \n')
print(df.groupby(['cms-project'])['primaryID'].count())
print('\nBreakdown by File Format and Role: \n')
print(df.groupby(['cms-project', 'division', 'role'])['primaryID'].count())

print('\n------PAMI Staff Breakdown------\n')
print('Files created: \n')
print(df.groupby(['digitizer.operator.lastName'])['primaryID'].count())
print('Objects transferred: \n')
print(df.groupby(['digitizer.operator.lastName'])['primaryID'].nunique())

print('\n------PAMI Equipment Breakdown------\n')
print(df.groupby(['digitizationProcess.playbackDevice.model', 'digitizationProcess.playbackDevice.serialNumber'])['primaryID'].count())
"""
