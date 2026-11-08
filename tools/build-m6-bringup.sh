#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
cd "$(dirname "$0")/.."

export M1N1_VERSION_TAG="$(git describe --tags --always --dirty)-m6-bringup"

make clean
make -j"${JOBS:-8}" RELEASE=0 CHAINLOADING=0 EXTRA_CFLAGS='-DBRINGUP -DTARGET=T8152'
