#!/bin/sh
# vsim-fetch URL DEST_DIR [FALLBACK_URL...]
# Download with retries to a file, then unpack (strip 1 level) into DEST_DIR. Tries each URL in order.
set -eu
url=$1; dest=$2; shift 2
f=$(mktemp /tmp/vsim-fetch.XXXXXX)
trap 'rm -f "$f"' EXIT
for u in "$url" "$@"; do
  # offline/flaky-network path: a pre-downloaded file in /opt/vsim/dl (build context dl/) wins over curl
  loc="/opt/vsim/dl/${u##*/}"
  if [ -f "$loc" ]; then echo "using local $loc"; cp "$loc" "$f"; got=1
  elif curl -fsSL --retry 4 --retry-all-errors --retry-delay 5 --connect-timeout 30 -o "$f" "$u"; then got=1
  else got=0; fi
  if [ "$got" = 1 ]; then
    sum=$(sha256sum "$f" | cut -d' ' -f1)
    echo "fetched $u sha256=$sum"
    want=$(awk -v n="${u##*/}" '$1 !~ /^#/ && $2 == n {print $1}' "${VSIM_CHECKSUMS:-/opt/vsim/checksums.txt}" 2>/dev/null || true)
    if [ -n "$want" ] && [ "$want" != "$sum" ]; then
      echo "CHECKSUM MISMATCH for ${u##*/}: expected $want" >&2; exit 2
    elif [ -z "$want" ]; then
      echo "note: no pinned checksum for ${u##*/}" >&2
    fi
    mkdir -p "$dest"
    tar -xz --strip-components=1 -C "$dest" -f "$f"
    exit 0
  fi
  echo "fetch failed: $u" >&2
done
echo "all sources failed for $dest" >&2
exit 1
