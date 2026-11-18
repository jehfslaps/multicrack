#!/bin/bash
# Build the Windows release (needs makensis and zip):
#   tools/package_windows.sh <Xenakis.exe> <Xenakis.vst3 folder> <Xenakis.clap> [outdir]
# Makes, in outdir (default out/):
#   Xenakis_v<version>_Windows.zip   Install Xenakis.exe, the "Windows warning" picture, README.txt,
#                                    licenses/, and "manual install/" (the plain plug-in files)
#   Install-Xenakis.exe              the same installer on its own (the app's updater downloads it)
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
APP=$(realpath "$1"); VST3=$(realpath "$2"); CLAP=$(realpath "$3")
OUT=$(mkdir -p "${4:-$ROOT/out}" && cd "${4:-$ROOT/out}" && pwd)
VER=$(tr -d ' \r\n' < "$ROOT/VERSION")
NUM="$VER"; while [ "$(echo "$NUM" | tr -cd . | wc -c)" -lt 3 ]; do NUM="$NUM.0"; done

STAGE=$(mktemp -d)
P="$STAGE/payload"; Z="$STAGE/Xenakis"
mkdir -p "$P/licenses" "$Z/licenses" "$Z/manual install/VST3" "$Z/manual install/CLAP"
cp "$APP" "$P/Xenakis.exe"
cp -R "$VST3" "$P/Xenakis.vst3"
cp "$CLAP" "$P/Xenakis.clap"
cp "$ROOT/package/README.txt" "$P/"
cp "$ROOT"/package/licenses/* "$P/licenses/"

(cd "$ROOT/installer" && makensis -V2 -DVERSION="$VER" -DNUMVER="$NUM" -DSTAGE="$P" \
   -DOUTFILE="$Z/Install Xenakis.exe" xenakis.nsi)

cp "$ROOT/package/README.txt" "$Z/"
cp "$ROOT/package/Windows warning - how to install.png" "$Z/"
cp "$ROOT"/package/licenses/* "$Z/licenses/"
cp -R "$VST3" "$Z/manual install/VST3/Xenakis.vst3"
cp "$CLAP" "$Z/manual install/CLAP/Xenakis.clap"

NAME="Xenakis_v${VER}_Windows.zip"
rm -f "$OUT/$NAME" "$OUT/Install-Xenakis.exe"
(cd "$STAGE" && zip -q -r -y -9 "$OUT/$NAME" Xenakis)
cp "$Z/Install Xenakis.exe" "$OUT/Install-Xenakis.exe"
rm -rf "$STAGE"
ls -l "$OUT/$NAME" "$OUT/Install-Xenakis.exe"
