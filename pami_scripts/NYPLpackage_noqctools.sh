#!/bin/bash

for file in *.mkv *.xml.gz; do
  mv -i "${file}" "${file/_ffv1/}"
done
for file in *.mkv ; do
  ffmpeg -i "$file" -map 0:v -map 0:a -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000 -y -s 720x486 -aspect 4:3 "${file%.*}_sc.mp4" ;
done

for file in *.dv ; do
  ffmpeg -i "$file" -map 0:v -map 0:a -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 320000 -ar 48000 -y -s 720x486 -aspect 4:3 "${file%.*}_sc.mp4" ;
done

mkdir PreservationMasters
mkdir ServiceCopies
mkdir V210
mkdir AuxiliaryFiles

mv *.mkv *.framemd5 *.xml.gz *.dv PreservationMasters
mv *.log AuxiliaryFiles

for file in *.mov ; do
  ffmpeg -i "$file" -map 0 -dn -c:v ffv1 -level 3 -g 1 -slicecrc 1 -slices 24 -field_order bt -vf setfield=bff,setdar=4/3 -color_primaries smpte170m -color_range tv -color_trc bt709 -colorspace smpte170m -c:a copy "${file%.*}.mkv" ;
  ffmpeg -i "$file" -map 0 -dn -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf yadif -c:a aac -strict -2 -b:a 192000 -ar 48000 -y -s 720x486 -aspect 4:3 "${file%.*}_sc.mp4"
done
for file in *.mkv ; do
  ffmpeg -i "$file" -f framemd5 -an "${file%*}.framemd5" ;
done
for file in *.mp4 ; do
  mv -i "${file}" "${file/_pm/}"
done
mv *.mov V210
mv *.mkv *.framemd5 *.xml.gz PreservationMasters
mv *.mp4 ServiceCopies
