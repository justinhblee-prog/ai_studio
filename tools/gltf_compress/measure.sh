#!/usr/bin/env bash
# Measures glTF-Transform compression on the SYNTHETIC samples. Usage: measure.sh <dir with .glb> <out dir>   (run from tools/gltf_compress after `npm ci`)
set -euo pipefail
in="$1"; out="$2"; mkdir -p "$out"
GT="npx --no-install gltf-transform"
size() { stat -c %s "$1"; }
echo "| sample | variant | bytes | % of original | seconds |"
echo "|---|---|---:|---:|---:|"
for f in "$in"/*.glb; do
  name=$(basename "$f" .glb); base=$(size "$f")
  echo "| $name | original | $base | 100.0 | - |"
  run() { # label, args...
    label="$1"; shift; dst="$out/${name}__${label}.glb"; t0=$(date +%s.%N)
    if $GT "$@" "$f" "$dst" >"$out/${name}__${label}.log" 2>&1; then
      t1=$(date +%s.%N); s=$(size "$dst")
      printf "| %s | %s | %s | %.1f | %.1f |\n" "$name" "$label" "$s" "$(echo "$s*100/$base" | bc -l)" "$(echo "$t1-$t0" | bc -l)"
    else
      echo "| $name | $label | FAILED | - | - |"; tail -3 "$out/${name}__${label}.log" | sed 's/^/    log: /' >&2
    fi
  }
  # NOTE: `optimize` simplifies (drops triangles) BY DEFAULT; every row below except *_simplify passes --simplify false so the geometry is not reduced.
  run prune_dedup  optimize --simplify false --compress false --texture-compress false
  run meshopt      optimize --simplify false --compress meshopt --texture-compress false
  run meshopt_webp optimize --simplify false --compress meshopt --texture-compress webp
  run draco        optimize --simplify false --compress draco --texture-compress false
  run quantize     optimize --simplify false --compress quantize --texture-compress false
  run webp_only    optimize --simplify false --compress false --texture-compress webp
  run meshopt_webp_simplify optimize --compress meshopt --texture-compress webp
done
