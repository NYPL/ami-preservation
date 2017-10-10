#!/usr/bin/env python3

import bs4 as bs
import sys

source = open(sys.argv[1]).read()
soup = bs.BeautifulSoup(source,'lxml')

file_list = []
size_list = []

for filename in soup.find_all('filename'):
    file_list.append(filename.text)

for smallerthanexpected in soup.find_all('smallerthanexpected'):
    size_list.append(smallerthanexpected.text)

size_dict = dict(zip(file_list, size_list))

smallerthanexpected= []

for item in size_dict:
    if size_dict[item] == "True":
        smallerthanexpected.append(item)

if smallerthanexpected:
    print("The following ISOs are smaller than expected:")
    for item in smallerthanexpected:
        print('  {}'.format(item))
else:
    print('Youyr ISOs are A-Okay!')
