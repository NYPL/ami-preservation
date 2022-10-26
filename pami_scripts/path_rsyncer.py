#!/usr/bin/env python3

import csv
import sys
import re
import subprocess

fh = open(sys.argv[1], 'r')
reader = csv.reader(fh)

next(reader, None)

cms_list = []

for record in reader:
    cmsID = record[0]
    cms_list.append(cmsID)

fh = open(sys.argv[2])
text = fh.read()
path_list = text.splitlines()

rsync_list = []

for item in cms_list:
    r = re.compile(item)
    newlist = list(filter(r.search, path_list))
    rsync_list.append(newlist)

flat_list = [item for sublist in rsync_list for item in sublist]


for full_path in flat_list:
    if full_path.endswith(('sc.mp4', 'em.flac')):
        rsync_call = ["rsync", "-rtv", "--progress",
	    full_path, '/Users/benjaminturkus/Desktop/graham']
        subprocess.call(rsync_call)
