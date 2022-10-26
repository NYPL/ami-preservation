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
log_path="$log_dir/rawcooked-check_$dateCreated.csv"
i=0

for line in $dir_of_bags; do
find $dir_of_bags/ -name "*.mkv" -exec rawcooked --check {} ';' > $log_path

done