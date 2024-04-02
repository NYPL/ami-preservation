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
log_path="$log_dir/mediaconch_8-16mm_filmPM_$dateCreated.csv"
i=0

for line in $dir_of_bags; do
find $PWD -name "*.mkv" -exec mediaconch -p /$log_dir/ami-preservation/qc_utilities/MediaconchPolicies/MediaConch_NYPL_8-16mmFilmPM.xml {} ';' > $log_path

done
