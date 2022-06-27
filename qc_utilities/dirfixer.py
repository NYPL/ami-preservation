#!/usr/bin/env python3

# A little script for batch fixing Bag names that don't match NYPL specs, 
# with comments to clarify steps in case others want to use this in the future.

import os
import pwd
import re

# path containing bad dir names must be cwd 
path = os.getcwd()

# generate list of bad dir names within path
dirlist = os.listdir(path)

# loop through list and slice first six digits from each item 
for item in dirlist:
    # filter out good directory names  
    if not re.match(r'^\d{6}$', item): 
     
        # look for potential ID in directory name
        newid = re.match(r'\d{6}', item)
        # if potential ID found
        if newid:
            # print directory and what was found
            print(f'old id: {item}, new id: {newid.group(0)}')
            # replace old dirname (src) with new dirname (dst)
            os.rename(os.path.join(path, item), os.path.join(path, newid.group(0)))

print("directories renamed!")


# ideas for improvement:
    # search cwd for any dirs that don't match 6-digit pattern, list bad dirs prior to fixing
