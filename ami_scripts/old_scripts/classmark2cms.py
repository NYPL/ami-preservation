#!/usr/bin/env python3

import csv
import sys

fh = open(sys.argv[1], 'r')
reader = csv.reader(fh)

next(reader, None)

cms_list = []

for record in reader:
    if record[6]:
        classmark = record[6]
    else:
        continue
    if record[8]:
        cmsID = record[8]
        cmsID = cmsID.split('.')[0]
    else:
        continue
    cms_dict = {classmark: cmsID}
    cms_list.append(cms_dict)

fh = open(sys.argv[2])
text = fh.read()
lines = text.splitlines()

cms_pull = []
classmark_list = []

for cms_dict in cms_list:
    for item in cms_dict:
        if item in lines:
            cms_pull.append(cms_dict[item])
            classmark_list.append(item)


for item in lines:
    if item not in classmark_list:
        print(item)

cms_set = set(cms_pull)
print("You need to pull files for the following CMS Numbers: ")
for item in sorted(list(cms_set)):
    print(item)
print()
print("count:")
print(len(list(cms_set)))
print(len(lines))
