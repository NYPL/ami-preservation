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
log_path="$log_dir/mediaconch_audioAnalog_$dateCreated.csv"
i=0

for line in $dir_of_bags; do
find Audio/ -name "*.wav" -exec mediaconch -p /Volumes/video_repository/Working_Storage/Tools/Mediaconch/Conformance_Policies/v2.0/NYPL-PAMI_v2_audioAnalog_PM.xml {} ';' > $log_path

done

