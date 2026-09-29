#!/usr/bin/env bash
set -euo pipefail
VERSION="${BLENDER_VERSION:-4.5.14}"
DIR="blender-${VERSION}-linux-x64"
URL="https://download.blender.org/release/Blender4.5/${DIR}.tar.xz"
curl -fL "$URL" -o blender.tar.xz
tar -xf blender.tar.xz
printf '%s\n' "$(pwd)/$DIR"
