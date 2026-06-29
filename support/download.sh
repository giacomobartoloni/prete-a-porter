#!/usr/bin/env bash
set -euo pipefail

BIBLE_ZIP_URL="https://gliscritti.it/dchiesa/files/bcei2008_v02.zip"
CATECHISM_PDF_URL="https://www.preghiamo.org/download/biblioteca/catechismo-della-chiesa-cattolica.pdf"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_BIBLE="$SCRIPT_DIR/bibbia2008"
TARGET_CATECHISM="$SCRIPT_DIR/catechismo"

echo "--- Bibbia CEI 2008 ---"
mkdir -p "$TARGET_BIBLE"
curl -fL "$BIBLE_ZIP_URL" -o /tmp/bcei2008_v02.zip
unzip -o /tmp/bcei2008_v02.zip -d "$TARGET_BIBLE"
rm /tmp/bcei2008_v02.zip
echo "✓ Bibbia CEI 2008 -> $TARGET_BIBLE"

echo ""
echo "--- Catechismo della Chiesa Cattolica ---"
mkdir -p "$TARGET_CATECHISM"
curl -fL "$CATECHISM_PDF_URL" -o "$TARGET_CATECHISM/catechismo-della-chiesa-cattolica.pdf"
echo "✓ Catechismo -> $TARGET_CATECHISM/catechismo-della-chiesa-cattolica.pdf"

echo ""
echo "Fatto."
