#!/bin/bash
# Repite evaluar_corpus.py hasta que escribe su resultado final (sigue por donde iba gracias al fichero _parcial_*.json). Uso: evaluar_vigilado.sh CORPUS NOMBRE [opciones de evaluar_corpus.py]
AQUI="$(cd "$(dirname "$0")" && pwd)"
CORPUS="$1"; NOMBRE="$2"; shift 2
for i in $(seq 1 30); do
  PYTHONIOENCODING=utf-8 python "$AQUI/evaluar_corpus.py" "$CORPUS" "$NOMBRE" "$@" >> "$CORPUS/../../eval_$NOMBRE.log" 2>&1
  [ -f "$CORPUS/../resultados/$NOMBRE.json" ] && exit 0
  sleep 20
done
