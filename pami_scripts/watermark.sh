#!/usr/bin/env bash

# Add watermark, burnt in timecode and filename to access copy

# Parameters:
# $1: Getopts selection, -p for FFplay, -s for FFmpeg
# $2: Input File
# $3: NYPL Filename
# $4: Image to Watermark Top Right
# $5: Image to Watermark Bottom Left

_usage(){
cat <<EOF
$(basename "${0}")
  Usage
   $(basename "${0}") [OPTIONS] INPUT_FILE NYPL_FILENAME INPUT_WATERMARK_1 INPUT_WATERMARK_2
  Options
   -h  display this help
   -p  previews in FFplay
   -s  saves to file with FFmpeg

  Notes
  Parameters:
  INPUT_FILE_1 Input File
  NYPL_FILENAME Timestamp of the input video to start the output video (HH:MM:SS)
  INPUT_WATERMARK_1 JPG or PNG for top right watermark
  INPUT_WATERMARK_2 JPG or PNG for bottom left watermark


  Outcome
   Adds watermark, running timecode, and filename to access copy
   dependencies: ffmpeg 4.3 or later
EOF
}

filter_complex="drawtext=fontfile=/System/Library/Fonts/Supplemental/Verdana.ttf: text='%{pts \\: hms}': x=w-tw-20:y=h-th-20: fontsize=25: fontcolor=white:alpha=0.4: box=1: boxcolor=black@0.6, drawtext=fontfile=/System/Library/Fonts/Supplemental/Verdana.ttf:fontsize=25:text=${3}:fontcolor=white:alpha=0.4:x=20:y=20, overlay=main_w-overlay_w-20:20, overlay=20:main_h-overlay_h-20"
print_filter_complex="drawtext=fontfile=/System/Library/Fonts/Supplemental/Verdana.ttf: text='%%{pts \\\: hms}': x=w-tw-20:y=h-th-20: fontsize=25: fontcolor=white:alpha=0.4: box=1: boxcolor=black@0.6, drawtext=fontfile=/System/Library/Fonts/Supplemental/Verdana.ttf:fontsize=25:text=${3}:fontcolor=white:alpha=0.4:x=20:y=20, overlay=main_w-overlay_w-20:20, overlay=20:main_h-overlay_h-20"

while getopts "ps" OPT ; do
    case "${OPT}" in
      p)
         ffplay -hide_banner -i "${2}" -i $4 -i $5 -filter_complex "${filter_complex}"
         printf "\n\n*******START FFPLAY COMMANDS*******\n" >&2
         printf "ffplay -hide_banner -i "$2" -i $4 -i $5 -filter_complex "${filter_complex}" \n" >&2
         printf "********END FFPLAY COMMANDS********\n\n " >&2
        ;;
      s)
         ffmpeg -hide_banner -i "${2}" -i $4 -i $5 -filter_complex "${filter_complex}" -c:v libx264 -c:a aac -map 0:a -map 0:v "${2%.*}_watermark.mp4"
         printf "\n\n*******START FFMPEG COMMANDS*******\n" >&2
         printf "ffmpeg -i '$2' -i $4 -i $5 -filter_complex \"${print_filter_complex}\" -c:v libx264 -c:a aac -map 0:a -map 0:v '${2%.*}_watermark.mp4' \n" >&2
         printf "********END FFMPEG COMMANDS********\n\n " >&2
        ;;
    esac
  done
