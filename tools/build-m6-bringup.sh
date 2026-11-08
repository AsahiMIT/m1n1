#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
cd "$(dirname "$0")/.."

stage="${1:-minimal}"
extra_cflags='-DBRINGUP -DTARGET=T8152'
suffix=''

if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [minimal|aic|mmu]" >&2
    exit 1
fi

case "$stage" in
    minimal) ;;
    aic)
        extra_cflags="$extra_cflags -DBRINGUP_AIC"
        suffix='-aic'
        ;;
    mmu)
        extra_cflags="$extra_cflags -DBRINGUP_AIC -DBRINGUP_MMU"
        suffix='-mmu'
        ;;
    *)
        echo "Usage: $0 [minimal|aic|mmu]" >&2
        exit 1
        ;;
esac

export M1N1_VERSION_TAG="$(git describe --tags --always --dirty)-m6-bringup$suffix"

make clean
make -j"${JOBS:-8}" RELEASE=0 CHAINLOADING=0 EXTRA_CFLAGS="$extra_cflags"
