#!/usr/bin/env python3

import os
import sys

root_dir = sys.argv[1]

cms_set = set()
file_set = set()

for root, dirs, files in os.walk(root_dir):
  for file in files:
      if file.endswith(('.mov', '.wav')):
          file_set.add(file)
          cms = file.split('_')[1]
          cms_set.add(cms)

print(len(file_set))
print(len(cms_set))

for item in sorted(list(cms_set)):
    print(item)
