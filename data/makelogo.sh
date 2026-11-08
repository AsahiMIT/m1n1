#!/usr/bin/env sh
# SPDX-License-Identifier: MIT
set -eu
cd "$(dirname "$0")"

for size in 48 128 256; do
    rsvg-convert -w "$size" -h "$size" hikari-linux.svg -o "bootlogo_$size.png"
    magick "bootlogo_$size.png" -background black -flatten -depth 8 "rgba:bootlogo_$size.bin"
done
