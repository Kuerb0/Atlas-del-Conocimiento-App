#!/bin/bash
# Lanza entrenar.py y, si se corta (la GPU se comparte con otras aplicaciones y a veces se queda sin memoria), lo reanuda desde el último adaptador guardado.
# Uso: entrenar_vigilado.sh DATOS_DIR SALIDA_DIR [opciones de entrenar.py]   (hasta 20 intentos, 60 s de pausa entre ellos)
AQUI="$(cd "$(dirname "$0")" && pwd)"
DATOS="$1"; SALIDA="$2"; shift 2
PY="$AQUI/.venv/Scripts/python.exe"
for intento in $(seq 1 20); do
  if [ -f "$SALIDA/adaptador/adapter_model.safetensors" ] && [ -f "$SALIDA/estado.json" ]; then EXTRA="--reanudar"; else EXTRA=""; fi
  PYTHONIOENCODING=utf-8 "$PY" "$AQUI/entrenar.py" "$DATOS" "$SALIDA" "$@" $EXTRA >> "$SALIDA.log" 2>&1
  [ -f "$SALIDA/resultado.json" ] && exit 0
  echo "[vigilante] intento $intento cortado; reanudo en 60 s" >> "$SALIDA.log"
  sleep 60
done
