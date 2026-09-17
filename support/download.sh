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
TMP_EXTRACT="$(mktemp -d)"
unzip -q -o /tmp/bcei2008_v02.zip -d "$TMP_EXTRACT"
rm /tmp/bcei2008_v02.zip
# The archive ships its own top-level bibbia2008/ directory: hoist the contents so the
# resulting layout matches the ingest_corpus.py default ($TARGET_BIBLE/bcei2008/*.htm).
if [ -d "$TMP_EXTRACT/bibbia2008" ]; then
  cp -R "$TMP_EXTRACT/bibbia2008/." "$TARGET_BIBLE/"
else
  cp -R "$TMP_EXTRACT/." "$TARGET_BIBLE/"
fi
rm -rf "$TMP_EXTRACT"
echo "✓ Bibbia CEI 2008 -> $TARGET_BIBLE"

echo ""
echo "--- Catechismo della Chiesa Cattolica ---"
mkdir -p "$TARGET_CATECHISM"
curl -fL "$CATECHISM_PDF_URL" -o "$TARGET_CATECHISM/catechismo-della-chiesa-cattolica.pdf"
echo "✓ Catechismo -> $TARGET_CATECHISM/catechismo-della-chiesa-cattolica.pdf"

echo ""
echo "Fatto."
