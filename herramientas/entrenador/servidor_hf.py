"""Sirve el modelo reentrenado (modelo base en 4 bits + adaptador LoRA) con la misma interfaz mínima que Ollama, para medirlo sin convertirlo a GGUF.

    python herramientas/entrenador/servidor_hf.py SALIDA_DIR [--base Qwen/Qwen2.5-3B-Instruct] [--nombre arbol-ft] [--puerto 11500] [--pausa 0]

Responde a `GET /api/tags` y `POST /api/chat` (lo único que usa `py/conocimiento/llm.py`), con el mismo texto de entrada que ve el modelo al entrenar (`entrenar.formato_ollama`) y decodificación
voraz. Para medirlo con el resto del programa: `evaluar_corpus.py CORPUS nombre --set 'llm.URL="http://localhost:11500"' --set 'llm.MODELO="arbol-ft"'`.
Diferencia con Ollama: aquí NO se fuerza el formato JSON con el esquema (el modelo lo aprendió: en validación devuelve JSON válido el 100 % de las veces) y `llm._ids` descarta lo que no sea un género
o subgénero de la lista. Solo escucha en localhost y atiende de una en una (la GPU es una).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from entrenar import formato_ollama  # noqa: E402


def crear(generar, nombre: str, pausa: float = 0.0):
    """Manejador HTTP al estilo de Ollama que usa `generar(prompt, max_tokens) -> texto`."""
    cerrojo = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, d: dict, codigo: int = 200) -> None:
            c = json.dumps(d, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(c)))
            self.end_headers()
            self.wfile.write(c)

        def do_GET(self):
            self._json({"models": [{"name": nombre}]} if self.path.startswith("/api/tags") else {"error": "no encontrado"}, 200 if self.path.startswith("/api/tags") else 404)

        def do_POST(self):
            if not self.path.startswith("/api/chat"):
                return self._json({"error": "no encontrado"}, 404)
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
            usuario = [m["content"] for m in d.get("messages", []) if m.get("role") == "user"]
            if not usuario:
                return self._json({"error": "sin mensaje de usuario"}, 400)
            try:
                with cerrojo:
                    texto = generar(formato_ollama(usuario[-1]), int(d.get("options", {}).get("num_predict", 100)))
                    time.sleep(pausa)                                          # descanso de la GPU entre peticiones: con --pausa el ordenador sigue siendo usable mientras se mide
            except Exception as e:
                self._json({"error": f"{type(e).__name__}: {e}"[:300]}, 500)
                if "CUDA error" in str(e):                                   # un error de CUDA deja el contexto inservible: se cierra y el vigilante lo vuelve a arrancar
                    print("error de CUDA irrecuperable; me cierro", flush=True)
                    threading.Timer(0.5, lambda: os._exit(3)).start()
                return
            self._json({"model": nombre, "message": {"role": "assistant", "content": texto}, "done": True})
    return H


def cargar(salida: Path, base: str):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(base)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    modelo = AutoModelForCausalLM.from_pretrained(base, quantization_config=bnb, device_map={"": 0}, torch_dtype=torch.bfloat16)
    modelo = PeftModel.from_pretrained(modelo, str(salida / "adaptador")).eval()

    def generar_una_vez(prompt: str, max_tokens: int) -> str:
        ids = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            sal = modelo.generate(**ids, max_new_tokens=min(max_tokens, 160), do_sample=False, pad_token_id=tok.eos_token_id)
        return tok.decode(sal[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)

    def generar(prompt: str, max_tokens: int) -> str:
        """La GPU se comparte con otras aplicaciones: si se queda sin memoria se espera y se repite (no se vacía la caché de PyTorch: lo que ya tiene reservado es lo que le permite seguir)."""
        for _ in range(10):
            try:
                return generar_una_vez(prompt, max_tokens)
            except torch.cuda.OutOfMemoryError:
                time.sleep(6)
        raise RuntimeError("sin memoria en la GPU tras 10 intentos")
    generar_una_vez(formato_ollama("palabra " * 1800), 4)                     # calentamiento con un prompt largo: reserva la memoria que luego hará falta antes de que otra aplicación la ocupe
    return generar


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(1)
    salida = Path(a[0])
    opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    estado = json.loads((salida / "estado.json").read_text(encoding="utf-8")) if (salida / "estado.json").exists() else {}
    base, nombre, puerto = opt("--base", estado.get("modelo", "Qwen/Qwen2.5-3B-Instruct")), opt("--nombre", "arbol-ft"), int(opt("--puerto", 11500))
    generar = cargar(salida, base)
    print(f"{nombre} listo en http://localhost:{puerto}  (base {base} + adaptador de {salida})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", puerto), crear(generar, nombre, float(opt("--pausa", 0)))).serve_forever()


if __name__ == "__main__":
    main()
