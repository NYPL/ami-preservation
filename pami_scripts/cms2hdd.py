#!/usr/bin/env python3

import csv
import sys

fh = open(sys.argv[1], 'r')
reader = csv.reader(fh)

next(reader, None)

cms_list = []

for record in reader:
    path = record[0]
    if path.startswith('/'):
        hdd = path.split('/')[2]
    if record[11]:
        cmsID = record[11]
    else:
        cmsID = None
    cms_dict = {cmsID: hdd}
    cms_list.append(cms_dict)

fh = open(sys.argv[2])
text = fh.read()
lines = text.splitlines()

hdd_pull = []

for cms_dict in cms_list:
    for item in cms_dict:
        if item in lines:
            hdd_pull.append(cms_dict[item])

hdd_set = set(hdd_pull)
print("You need to pull the following drives: ")
for item in hdd_set:
    print(item)
