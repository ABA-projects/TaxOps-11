#!/usr/bin/env bash
# Reproduce infra/modules/lambda-api/build/tesseract-layer.zip — Terraform lee ese archivo
# (aws_lambda_layer_version.tesseract, ver tesseract-layer.tf). Correr ANTES de terraform apply
# si el zip no existe todavía o si se quiere actualizar la versión de Tesseract/idiomas.
#
# Fuente: binarios precompilados de bweigel/aws-lambda-tesseract-layer (Amazon Linux 2023,
# x86_64 — mismo motivo que el resto del Chunk 4 usa x86_64, ver plan de migración Chunk 4).
# Pineado a un commit fijo para reproducibilidad, no a "main".
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/../build"
PINNED_COMMIT="0b2d91351b5c7536a0db9e4703e4b85419d7cfc8"
REPO_URL="https://github.com/bweigel/aws-lambda-tesseract-layer.git"

mkdir -p "$BUILD_DIR"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "→ Clonando aws-lambda-tesseract-layer @ ${PINNED_COMMIT}..."
git clone --quiet "$REPO_URL" "$WORKDIR/repo"
git -C "$WORKDIR/repo" checkout --quiet "$PINNED_COMMIT"

LAYER_SRC="$WORKDIR/repo/ready-to-use/amazonlinux-2023"

echo "→ Agregando tessdata en español (no viene en el paquete precompilado, solo eng/deu/osd)..."
curl -sL -o "$LAYER_SRC/tesseract/share/tessdata/spa.traineddata" \
  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/spa.traineddata"

echo "→ Empaquetando..."
(cd "$LAYER_SRC" && zip -r -X -q "$BUILD_DIR/tesseract-layer.zip" bin lib tesseract -x "*.gitkeep")

echo "✅ Listo: $BUILD_DIR/tesseract-layer.zip ($(du -h "$BUILD_DIR/tesseract-layer.zip" | cut -f1))"
