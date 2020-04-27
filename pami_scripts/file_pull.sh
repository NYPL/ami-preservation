#!/bin/bash

IFS=$'\n' read -d '' -r -a files < $1

for i in "${files[@]}" ; do find ./ $2 -name *$i*sc.mp4 -exec rsync -rtv --progress {} $3 ';' ; done
for i in "${files[@]}" ; do find ./ $2 -name *$i*em.wav -exec rsync -rtv --progress {} $3 ';' ; done

cd $3
for file in *wav ; do ffmpeg -i "$file" -c:a aac -b:a 192k -dither_method rectangular -ar 44100 "${file%.*}.mp4" ; done
for file in *wav ; do rm $file ; done

echo ""
echo "========================================================="
echo "====================Summary Stats========================"
echo ""
echo "Total Files Pulled:" $(ls | wc -l)
echo ""
ls
