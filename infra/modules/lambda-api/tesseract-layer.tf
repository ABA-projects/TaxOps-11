# Layer de Tesseract OCR — necesario porque Amazon Linux 2023 (la base de las imágenes
# Lambda) no tiene Tesseract como paquete dnf, ni en los repos base ni en EPEL (verificado).
# El .zip se genera con scripts/build-tesseract-layer.sh (correrlo antes de "terraform apply"
# si build/tesseract-layer.zip no existe) — no se commitea a git, es un artefacto regenerable
# a partir de binarios precompilados de bweigel/aws-lambda-tesseract-layer (pineado a un commit
# fijo dentro del script) + el tessdata de español descargado aparte.
resource "aws_lambda_layer_version" "tesseract" {
  layer_name               = "taxops-tesseract"
  description              = "Tesseract 5.5.2 + Leptonica (AL2023, x86_64) — eng+deu+osd+spa"
  filename                 = "${path.module}/build/tesseract-layer.zip"
  source_code_hash         = filebase64sha256("${path.module}/build/tesseract-layer.zip")
  compatible_runtimes      = ["python3.12"]
  compatible_architectures = ["x86_64"]
}
