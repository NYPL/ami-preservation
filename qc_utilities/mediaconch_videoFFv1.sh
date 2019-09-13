#!/bin/bash

dir_of_bags=$PWD
log_dir=$HOME

while getopts 'd:l:' flag; do
  case "${flag}" in
    d) dir_of_bags=${OPTARG} ;;
    l) log_dir=${OPTARG} ;;
    *) error "Unexpected option ${flag}" ;;
  esac
done

dateCreated=$(date "+%Y%m%d_%H%M")
log_path="$log_dir/mediaconch_videoPM_$dateCreated.csv"
i=0

for line in $dir_of_bags; do
find Video/ -name "*.mkv" -exec mediaconch -p /Users/genevievehavemeyerking/ami-preservation/qc_utilities/MediaconchPolicies/MediaConch_NYPL_FFV1MKV.xml {} ';' > /Users/genevievehavemeyerking/Documents/tests/test.csv

done

