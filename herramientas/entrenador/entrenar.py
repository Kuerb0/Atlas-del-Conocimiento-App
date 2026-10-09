"""Reentrena el LLM que clasifica con QLoRA (modelo base en 4 bits + adaptador LoRA): aprende a devolver varios géneros y subgéneros con el prompt exacto del programa.

    python herramientas/entrenador/entrenar.py DATOS_DIR SALIDA_DIR [--modelo Qwen/Qwen2.5-3B-Instruct] [--epocas 2] [--lr 2e-4] [--rango 16] [--acum 16] [--largo 2048]
                                              [--n-val 80] [--cada 20] [--max-ejemplos N] [--reanudar]

DATOS_DIR es la salida de `construir_datos.py` (train.jsonl, val.jsonl). Escribe en SALIDA_DIR:
  · registro.jsonl  una línea por evento (paso, pérdida, tasa de aprendizaje, VRAM, evaluación…): lo lee el panel (`panel_progreso.py`, sección «Entrenamiento del LLM»)
  · estado.json     el estado actual (fase, paso, de cuántos, minutos que quedan…)
  · adaptador/      el adaptador LoRA (se guarda cada --cada pasos y al acabar); `exportar_ollama.py` lo convierte en un modelo de Ollama
  · resultado.json  al acabar: formato JSON válido y acierto de etiquetas en la validación (generación libre, sin restricción de formato)
Necesita una GPU NVIDIA y las librerías de `requisitos.txt` (torch con CUDA, transformers, peft, bitsandbytes, accelerate); las instala `entrenar_llm.bat` en un entorno aparte
(`herramientas/entrenador/.venv`) para no tocar el Python de la aplicación. Con 12 GB de VRAM, el modelo de 3B cabe de sobra; el de 7B (`--modelo Qwen/Qwen2.5-7B-Instruct`) exige cerrar las
demás aplicaciones que usen la GPU. Se entrena solo sobre la respuesta (no sobre el prompt) y los logits solo se calculan para ella (el vocabulario de Qwen tiene 151 000 palabras: calcularlos para todo el prompt cuesta ~2 GB de VRAM).
Si se corta (p. ej. por falta de memoria de la GPU, que comparte con otras aplicaciones), `--reanudar` sigue desde el último adaptador guardado; un ejemplo que no cabe en memoria se salta y se anota.
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def opciones(a: list[str]) -> dict:
    def g(n, d):
        return type(d)(a[a.index(n) + 1]) if n in a else d
    return {"modelo": g("--modelo", "Qwen/Qwen2.5-3B-Instruct"), "epocas": g("--epocas", 2), "lr": g("--lr", 2e-4), "rango": g("--rango", 16), "acum": g("--acum", 16), "largo": g("--largo", 2048),
            "reanudar": "--reanudar" in a, "n_val": g("--n-val", 80), "cada": g("--cada", 20), "max_ejemplos": g("--max-ejemplos", 0)}


def formato_ollama(prompt: str) -> str:
    """El texto exacto que ve el modelo cuando Ollama atiende un mensaje de usuario sin mensaje de sistema (plantilla de qwen2.5 en Ollama). La plantilla de Hugging Face añade un
    «You are Qwen…» por defecto que Ollama NO añade: entrenar con él y servir sin él cambiaría lo que ve el modelo."""
    return "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n"


def vram_mb(torch) -> int:
    try:
        libre, total = torch.cuda.mem_get_info()
        return round((total - libre) / 2**20)
    except Exception:
        return 0


def main() -> None:
    a = sys.argv[1:]
    if len(a) < 2:
        print(__doc__)
        sys.exit(1)
    datos, salida, op = Path(a[0]), Path(a[1]), opciones(a)
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup
    except ImportError as e:
        sys.exit(f"Falta una librería ({e.name}). Instálalas con entrenar_llm.bat o: pip install -r herramientas/entrenador/requisitos.txt")
    if not torch.cuda.is_available():
        sys.exit("No hay GPU con CUDA: este entrenamiento necesita una NVIDIA (en CPU tardaría días).")
    salida.mkdir(parents=True, exist_ok=True)
    reg, t0 = salida / "registro.jsonl", time.time()
    cabeza = {"modelo": op["modelo"], **{k: v for k, v in op.items() if k != "modelo"}, "datos": str(datos), "gpu": torch.cuda.get_device_name(0), "inicio": time.strftime("%Y-%m-%d %H:%M:%S")}
    previo = json.loads((salida / "estado.json").read_text(encoding="utf-8")) if op["reanudar"] and (salida / "estado.json").exists() and (salida / "adaptador" / "adapter_model.safetensors").exists() else {}
    paso0 = int(previo.get("paso_guardado", 0))                      # el último paso del que hay adaptador guardado
    if not previo:
        reg.write_text("", encoding="utf-8")

    def log(**d) -> None:
        d = {"t": round(time.time() - t0, 1), "vram_mb": vram_mb(torch), **d}
        with reg.open("a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def estado(**d) -> None:
        (salida / "estado.json").write_text(json.dumps({**cabeza, "t": time.time(), "seg": round(time.time() - t0), **d}, ensure_ascii=False, indent=1), encoding="utf-8")

    estado(fase="cargando el modelo")
    tok = AutoTokenizer.from_pretrained(op["modelo"])
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    modelo = AutoModelForCausalLM.from_pretrained(op["modelo"], quantization_config=bnb, device_map={"": 0}, torch_dtype=torch.bfloat16)      # (en las versiones nuevas se llama «dtype»; torch_dtype sigue valiendo)
    modelo = prepare_model_for_kbit_training(modelo, use_gradient_checkpointing=True)
    if previo:
        from peft import PeftModel
        modelo = PeftModel.from_pretrained(modelo, str(salida / "adaptador"), is_trainable=True)
        print(f"reanudando desde el paso {paso0}", flush=True)
    else:
        modelo = get_peft_model(modelo, LoraConfig(r=op["rango"], lora_alpha=2 * op["rango"], lora_dropout=0.05, task_type="CAUSAL_LM",
                                                   target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    entrenables = sum(p.numel() for p in modelo.parameters() if p.requires_grad)
    print(f"{op['modelo']}: {entrenables / 1e6:.1f} M parámetros entrenables · VRAM {vram_mb(torch)} MB", flush=True)

    def tokenizar(fila: dict) -> dict | None:
        """input_ids y labels (solo la respuesta cuenta); None si no cabe en --largo."""
        prompt = formato_ollama(fila["messages"][0]["content"])
        p, r = tok(prompt, add_special_tokens=False)["input_ids"], tok(fila["messages"][1]["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
        if len(p) + len(r) > op["largo"]:
            return None
        return {"ids": p + r, "labels": [-100] * len(p) + r, "n": len(r), "tarea": fila["tarea"]}

    def cargar(nombre: str, tope: int = 0) -> tuple[list[dict], int]:
        filas = [json.loads(x) for x in (datos / nombre).read_text(encoding="utf-8").splitlines() if x.strip()]
        if tope:
            filas = filas[:tope]
        tk = [tokenizar(f) for f in filas]
        return [t for t in tk if t], sum(t is None for t in tk)

    train, descartadas = cargar("train.jsonl", op["max_ejemplos"])
    val, _ = cargar("val.jsonl", op["n_val"])
    pasos_total = max(1, math.ceil(len(train) * op["epocas"] / op["acum"]))
    print(f"{len(train)} ejemplos de entrenamiento ({descartadas} descartados por largos) · {len(val)} de validación · {pasos_total} pasos", flush=True)
    cabeza.update(ejemplos=len(train), descartados=descartadas, ejemplos_val=len(val), pasos_total=pasos_total)

    opt = torch.optim.AdamW([p for p in modelo.parameters() if p.requires_grad], lr=op["lr"], weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, max(1, pasos_total // 20), pasos_total)

    def perdida(ej: dict):
        """Pérdida solo sobre la respuesta, que va al final: se piden los logits de las últimas n+1 posiciones (no los de todo el prompt)."""
        ids = torch.tensor([ej["ids"]], device="cuda")
        n = ej["n"]
        with torch.autocast("cuda", dtype=torch.bfloat16):
            lg = modelo(input_ids=ids, attention_mask=torch.ones_like(ids), logits_to_keep=n + 1).logits[0, :-1].float()
        return torch.nn.functional.cross_entropy(lg, ids[0, -n:])

    def evaluar() -> float:
        modelo.eval()
        with torch.no_grad():
            v = sum(float(perdida(e)) for e in val) / max(len(val), 1)
        modelo.train()
        return v

    def guardar(paso_: int) -> None:
        modelo.save_pretrained(salida / "adaptador")
        tok.save_pretrained(salida / "adaptador")
        cabeza["paso_guardado"] = paso_                                  # para --reanudar

    modelo.train()
    rng, paso, micro, reciente, saltados, t_bucle = random.Random(42), 0, 0, [], 0, time.time()
    if not previo:
        log(tipo="eval", paso=0, eval_loss=evaluar() if val else None)
    for _ in range(paso0):
        sched.step()                                                     # (el optimizador vuelve a empezar sin memoria de los pasos anteriores; el calendario de la tasa de aprendizaje sí se conserva)
    paso, micro = paso0, paso0 * op["acum"]
    for epoca in range(op["epocas"]):
        orden = list(range(len(train)))
        rng.shuffle(orden)                                               # (mismo orden en cada reanudación: la semilla es fija)
        for k, i in enumerate(orden):
            if epoca * len(train) + k < paso0 * op["acum"]:
                continue                                                 # ya visto antes de cortarse
            try:
                l = perdida(train[i])
                (l / op["acum"]).backward()
            except torch.cuda.OutOfMemoryError:                          # la GPU se comparte con otras aplicaciones: se salta el ejemplo en vez de perder horas de entrenamiento
                saltados += 1
                torch.cuda.empty_cache()
                log(tipo="aviso", texto="sin memoria en la GPU: ejemplo saltado", saltados=saltados)
                continue
            reciente.append(float(l))
            micro += 1
            if micro % op["acum"] == 0:
                torch.nn.utils.clip_grad_norm_([p for p in modelo.parameters() if p.requires_grad], 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                paso += 1
                media = sum(reciente[-op["acum"]:]) / min(len(reciente), op["acum"])
                resto = (time.time() - t_bucle) / max(paso - paso0, 1) * (pasos_total - paso)            # por el ritmo de los pasos de esta sesión (sin contar la carga del modelo)
                log(tipo="paso", paso=paso, epoca=epoca + 1, loss=round(media, 4), lr=sched.get_last_lr()[0], ejemplos=micro)
                estado(fase="entrenando", paso=paso, paso_guardado=cabeza.get("paso_guardado", paso0), saltados=saltados, pasos_total=pasos_total, epoca=epoca + 1, epocas=op["epocas"], loss=round(media, 4), quedan_min=round(resto / 60, 1), ejemplos=micro)
                if paso % op["cada"] == 0 or paso == pasos_total:
                    ev = evaluar() if val else None
                    log(tipo="eval", paso=paso, eval_loss=ev)
                    guardar(paso)
                    print(f"  paso {paso}/{pasos_total}  pérdida {media:.4f}  validación {ev if ev is None else round(ev, 4)}  quedan ~{resto / 60:.0f} min", flush=True)
    guardar(paso)
    estado(fase="comprobando la validación", paso=paso, pasos_total=pasos_total)

    # comprobación final: generación libre sobre la validación (sin forzar el formato) para ver si aprendió a devolver JSON válido y las etiquetas correctas
    modelo.eval()
    filas = [json.loads(x) for x in (datos / "val.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    random.Random(7).shuffle(filas)
    ok_json = ok_prin = ok_conj = n = 0
    for f in filas[:60]:
        prompt = formato_ollama(f["messages"][0]["content"])
        ids = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        if ids["input_ids"].shape[1] > op["largo"]:
            continue
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            sal = modelo.generate(**ids, max_new_tokens=100, do_sample=False)
        txt = tok.decode(sal[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        real = json.loads(f["messages"][1]["content"])
        clave = "generos" if f["tarea"] == "genero" else "subgeneros"
        n += 1
        try:
            pred = json.loads(txt)[clave]
            ok_json += 1
            ok_prin += bool(pred) and pred[0] == real[clave][0]
            ok_conj += set(pred) == set(real[clave])
        except Exception:
            pass
    res = {"ejemplos": n, "json_valido": ok_json / max(n, 1), "principal": ok_prin / max(n, 1), "conjunto_exacto": ok_conj / max(n, 1), "minutos": round((time.time() - t0) / 60, 1)}
    (salida / "resultado.json").write_text(json.dumps({**cabeza, **res}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(tipo="final", **res)
    estado(fase="terminado", paso=paso, pasos_total=pasos_total, **res)
    print("Terminado:", json.dumps(res, ensure_ascii=False), "\nSiguiente: python herramientas/entrenador/exportar_ollama.py", salida, flush=True)


if __name__ == "__main__":
    main()
