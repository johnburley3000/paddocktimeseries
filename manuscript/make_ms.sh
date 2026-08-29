#!/bin/bash
set -euo pipefail

MSDIR="manuscript/Burley_et_al_PaddockTS_20260827"
OUTFILE="Burley_et_al_PaddockTS_preprint_20260827.pdf"

echo "Building PaddockTS preprint..."

docker run --rm \
  --platform linux/amd64 \
  -v "$PWD:/data" \
  -w "/data/$MSDIR" \
  pandoc/latex:latest \
  paper.md \
  --citeproc \
  -M link-citations=true \
  --pdf-engine=xelatex \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V papersize=letter \
  -V colorlinks=true \
  -V linkcolor=blue \
  -V urlcolor=blue \
  -V citecolor=blue \
  -V author='John T. Burley$^{1,*}$, Yasar Adeel Ansari$^{1}$, Christopher Bradley$^{1}$, Alex Norton$^{1,2}$, Justin Borevitz$^{1}$\\[0.5em]$^1$ Research School of Biology, Australian National University, Acton, ACT 2601, Australia\\$^2$ CSIRO Environment, Aspendale, VIC, Australia\\[0.5em]\small $^*$ Corresponding author: john.burley3000@gmail.com' \
  -o "$OUTFILE"

echo
echo "Done:"
echo "$MSDIR/$OUTFILE"
