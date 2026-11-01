#!/bin/sh
# prints the make -j value: $JOBS if >0, else nproc
if [ "${JOBS:-0}" -gt 0 ] 2>/dev/null; then echo "$JOBS"; else nproc; fi
