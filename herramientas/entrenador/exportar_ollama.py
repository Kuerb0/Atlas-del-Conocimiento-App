"""Convierte el adaptador entrenado por `entrenar.py` en un modelo de Ollama que el programa puede usar.

    python herramientas/entrenador/exportar_ollama.py SALIDA_DIR [--nombre arbol-clasificador] [--base qwen2.5:3b] [--tipo q8_0] [--convertidor RUTA] [--usar]

Ollama 0.40 ya no acepta adaptadores LoRA («LoRA adapters are no longer supported») ni importa Qwen2 desde safetensors («unsupported MLX architecture»), así que la vía es:
  1. FUSIONAR el adaptador con el modelo base de Hugging Face con el que se entrenó (bf16) → `SALIDA_DIR/fusionado/`.
  2. CONVERTIR esa carpeta a GGUF con `convert_hf_to_gguf.py` de llama.cpp (`--tipo q8_0`: ~3,3 GB para el 3B; f16 y bf16 también valen). El script NO viene con el programa: descárgalo tú de
     https://github.com/ggml-org/llama.cpp (fichero convert_hf_to_gguf.py, y `pip install gguf` en el entorno del entrenador) y pásalo con --convertidor, o déjalo en
     `herramientas/entrenador/llama_cpp/convert_hf_to_gguf.py`.
  3. `ollama create` con ese GGUF y la PLANTILLA del modelo base de Ollama (`ollama show --modelfile qwen2.5:3b`): el modelo se entrenó con exactamente esa plantilla (sin mensaje de sistema).
Necesita el entorno del entrenador (`entrenar_llm.bat exportar CORPUS NOMBRE`). El 3B se fusiona sin problema; el 7B (15 GB en bf16) no cabe en 16 GB de RAM sin cerrar todo.
Con `--usar` apunta `conocimiento/ajustes.json` al modelo nuevo ({"llm": {"modelo": nombre}}); sin él, pruébalo con ARBOL_LLM=nombre o con
`evaluar_corpus.py CORPUS nombre --set 'llm.MODELO="nombre"'`. Para volver al de siempre: borra "modelo" de ajustes.json.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
AQUI = Path(__file__).resolve().parent
BASES = {"Qwen/Qwen2.5-3B-Instruct": "qwen2.5:3b", "Qwen/Qwen2.5-7B-Instruct": "qwen2.5:7b", "Qwen/Qwen2.5-0.5B-Instruct": "qwen2.5:0.5b"}


def fusionar(adaptador: Path, base: str, destino: Path) -> None:
    """Fusiona el adaptador LoRA con el modelo base y guarda el resultado (pesos + tokenizador) en `destino`."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    modelo = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
    modelo = PeftModel.from_pretrained(modelo, str(adaptador)).merge_and_unload()
    destino.mkdir(parents=True, exist_ok=True)
    modelo.save_pretrained(destino, safe_serialization=True)
    AutoTokenizer.from_pretrained(base).save_pretrained(destino)


def modelfile_de(base: str, gguf: Path, exe: str) -> str:
    """El Modelfile del modelo base de Ollama (plantilla, parada, parámetros) con el FROM cambiado por nuestro GGUF y la temperatura a 0."""
    r = subprocess.run([exe, "show", "--modelfile", base], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"No encuentro el modelo base «{base}» en Ollama (ollama pull {base}): {r.stderr.strip()[:200]}")
    lineas = [x for x in r.stdout.splitlines() if not x.startswith("#")]
    texto = "\n".join(lineas)
    texto = re.sub(r"(?m)^FROM .*$", f"FROM {gguf.resolve().as_posix()}", texto, count=1)
    texto = re.sub(r"(?m)^PARAMETER temperature .*\n?", "", texto)
    return texto.strip() + "\nPARAMETER temperature 0\n"


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(1)
    salida = Path(a[0])
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    adaptador = salida / "adaptador"
    if not (adaptador / "adapter_model.safetensors").exists():
        sys.exit(f"No hay adaptador en {adaptador}: ¿terminó el entrenamiento?")
    estado = json.loads((salida / "estado.json").read_text(encoding="utf-8")) if (salida / "estado.json").exists() else {}
    hf = estado.get("modelo", "Qwen/Qwen2.5-3B-Instruct")
    base, nombre, tipo = opt("--base", BASES.get(hf, "qwen2.5:3b")), opt("--nombre", "arbol-clasificador"), opt("--tipo", "q8_0")
    fusionado, gguf = salida / "fusionado", salida / f"modelo-{tipo}.gguf"
    if not list(fusionado.glob("*.safetensors")):
        print(f"fusionando {adaptador.name} con {hf} …", flush=True)
        fusionar(adaptador, hf, fusionado)
    if not gguf.exists():
        conv = Path(opt("--convertidor", AQUI / "llama_cpp" / "convert_hf_to_gguf.py"))
        if not conv.exists():
            sys.exit(f"Falta el convertidor de llama.cpp ({conv}). Descarga convert_hf_to_gguf.py de https://github.com/ggml-org/llama.cpp, instala `pip install gguf` y pásalo con --convertidor.\n"
                     f"El modelo fusionado ya está listo en {fusionado}.")
        print("convirtiendo a GGUF …", flush=True)
        r = subprocess.run([sys.executable, str(conv), str(fusionado), "--outfile", str(gguf), "--outtype", tipo], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode or not gguf.exists():
            sys.exit("La conversión a GGUF falló:\n" + (r.stderr or r.stdout)[-1500:])
    exe = which("ollama") or str(Path.home() / "AppData/Local/Programs/Ollama/ollama.exe")
    modelfile = salida / "Modelfile"
    modelfile.write_text(modelfile_de(base, gguf, exe), encoding="utf-8")
    print("ollama create", nombre, "…", flush=True)
    r = subprocess.run([exe, "create", nombre, "-f", str(modelfile)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-400:], (r.stderr or "")[-600:])
    if r.returncode:
        sys.exit("Ollama no pudo crear el modelo (mira el mensaje de arriba).")
    if "--usar" in a:
        f = AQUI.parents[1] / "conocimiento" / "ajustes.json"
        aj = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        aj.setdefault("llm", {})["modelo"] = nombre
        f.write_text(json.dumps(aj, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{f} apunta ahora a {nombre}")
    print(f"Listo. Pruébalo con ARBOL_LLM={nombre}  ·  mídelo con evaluar_corpus.py CORPUS ft_{nombre} --val --set 'llm.MODELO=\"{nombre}\"'")


if __name__ == "__main__":
    main()
