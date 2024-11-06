#!/bin/bash

# Default directory as current if none provided
directory="."

# Parse command-line arguments
while getopts "d:" opt; do
  case ${opt} in
    d ) # Specify directory
      directory=$OPTARG
      ;;
    \? ) echo "Usage: cmd [-d directory]"
      exit 1
      ;;
  esac
done

# Loop through each .mp4 file in the specified directory, sorted alphabetically
find "$directory" -type f -name "*.mp4" | sort | while read -r file; do
  echo "File: $file"
  
  # Use mediainfo to extract the video details
  mediainfo --Inform="Video;%Width% %Height% %DisplayAspectRatio% %PixelAspectRatio% %FrameRate%" "$file" | 
  awk '{print "Video Width:", $1, "\nVideo Height:", $2, "\nDisplay Aspect Ratio:", $3, "\nPixel Aspect Ratio:", $4, "\nFrame Rate:", $5}'
  
  echo ""
done
