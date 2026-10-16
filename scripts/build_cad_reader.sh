#!/usr/bin/env bash
# Build the pinned official reader on Linux; no native executables enter Git.
set -euo pipefail
DEST="$(mkdir -p "${1:-cad-runtime}" && cd "${1:-cad-runtime}" && pwd)"
SOURCE_URL='https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14.tar.xz'
SOURCE_SHA='62ebb73b984f865960f20ed26619ea5f8789d5e3fd088fa40a2598384da81275'
BUILD="$(mktemp -d)"
# Only remove the exact temporary directory created above.
trap 'rm -rf -- "$BUILD"' EXIT
curl --fail --location --retry 2 --max-time 120 "$SOURCE_URL" -o "$BUILD/source.tar.xz"
printf '%s  %s\n' "$SOURCE_SHA" "$BUILD/source.tar.xz" | sha256sum --check --status
tar -xJf "$BUILD/source.tar.xz" -C "$BUILD"
cd "$BUILD/libredwg-0.14"
CFLAGS="-O1 -g0" ./configure --disable-bindings --disable-docs --disable-shared --disable-json --prefix="$DEST"
make -j2 -C src
make -j2 -C programs dwg2dxf
mkdir -p "$DEST/bin"
install -m 755 programs/dwg2dxf "$DEST/bin/dwg2dxf"
install -m 644 COPYING "$DEST/COPYING"
printf 'GNU LibreDWG 0.14\n%s\nSHA256: %s\n' "$SOURCE_URL" "$SOURCE_SHA" > "$DEST/SOURCE.txt"
"$DEST/bin/dwg2dxf" --version
