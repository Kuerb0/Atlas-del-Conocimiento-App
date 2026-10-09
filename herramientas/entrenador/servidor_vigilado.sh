#!/bin/bash
# Mantiene vivo servidor_hf.py: si se cierra (error de CUDA irrecuperable por falta de memoria de la GPU) lo vuelve a arrancar a los 15 s.
# Uso: servidor_vigilado.sh SALIDA_DIR [opciones de servidor_hf.py]
AQUI="$(cd "$(dirname "$0")" && pwd)"
SALIDA="$1"; shift
while true; do
  PYTHONIOENCODING=utf-8 "$AQUI/.venv/Scripts/python.exe" "$AQUI/servidor_hf.py" "$SALIDA" "$@" >> "$SALIDA.servidor.log" 2>&1
  echo "[vigilante] el servidor se cerró; lo arranco de nuevo en 15 s" >> "$SALIDA.servidor.log"
  sleep 15
done
