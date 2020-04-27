#!/bin/bash

# 1. Discover directories names
# 2. Validate directories as bags
# 3. Log results

log_dir=$HOME

while getopts ':d:l:' flag; do
  case "${flag}" in
    d) dir_of_bags=${OPTARG} ;;
    l) log_dir=${OPTARG} ;;
    \?) echo "Invalid option: -$OPTARG" >&2
        exit 1;;
    :) echo "Option -$OPTARG requires an argument." >&2
       exit 1 ;;
  esac
done

if [[ -z $dir_of_bags ]]
then
  echo "-d flag required" >&2
  exit 2
fi

dateCreated=$(date "+%Y%m%d_%H%M%S")
bags=$(ls -1 -d $dir_of_bags/*/)
log_path="$log_dir/makeMd5Bags_$dateCreated.log"
i=0

for line in $bags; do
  echo $(date "+%H:%M:%S")": bagging" $line
  bagit.py --md5 $line 2>> $log_path
  ((i++))
  [ "$(($i % 10))" -eq 0 ] && echo $i "bags created"
done

echo $i "bags created. Results written to ${log_path}."
