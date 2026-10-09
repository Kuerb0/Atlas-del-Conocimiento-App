"""Herramientas para reentrenar el LLM con varias etiquetas: métricas, datos de entrenamiento, panel y exportación a Ollama (sin GPU: torch no se necesita para probarlas)."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "py"))
sys.path.insert(0, str(RAIZ / "herramientas"))
sys.path.insert(0, str(RAIZ / "herramientas" / "entrenador"))
from conocimiento import clasificador, importar  # noqa: E402
import metricas_etiquetas as me  # noqa: E402


def fila(g, pg, gs=None, pgs=None, s="", ps="", ss=None, pss=None):
    return {"rel": g + pg, "g": g, "pg": pg, "s": s, "ps": ps, "gs": gs or [g], "pgs": pgs or [pg], "ss": ss if ss is not None else ([[g, s]] if s else []), "pss": pss if pss is not None else ([[pg, ps]] if ps else [])}


def test_metricas_de_etiquetas_multiples():
    filas = [fila("historia", "historia", pgs=["historia", "economia"]),                         # acierta y añade una de más
             fila("novela", "ciencia", pgs=["ciencia", "novela"]),                                # el acierto top-1 falla pero la real está entre las predichas
             fila("economia", "politica"),                                                        # falla del todo
             fila("historia", "historia", gs=["historia", "economia"], pgs=["historia", "economia"])]    # dos reales, las dos predichas
    m = me.metricas(filas)["genero"]
    assert m["n"] == 4 and m["principal_en_conjunto"] == 3                                       # lo comparable con el acierto de antes
    assert m["pred_media"] == pytest.approx(7 / 4) and m["real_media"] == pytest.approx(5 / 4) and m["de_mas"] == pytest.approx(.5)
    assert m["precision"] == pytest.approx(4 / 7) and m["exhaustividad"] == pytest.approx(4 / 5)
    assert m["exacto"] == pytest.approx(1 / 4) and 0 < m["jaccard"] < 1 and 0 <= m["f1_macro"] <= 1
    lo, hi = m["ic_principal"]
    assert lo < 3 / 4 < hi
    em = me.etiquetas_multiples(filas)
    assert em["reales_multiples"] == 1 and em["predichas_multiples"] == 3 and em["coocurrencia"][("economia", "historia")] == 2


def test_las_filas_antiguas_sin_conjuntos_se_leen_como_una_etiqueta():
    f = {"rel": "a", "g": "historia", "pg": "historia", "s": "antigua", "ps": "medieval"}           # un resultado anterior a la 1.13
    c = me.conjuntos(f)
    assert c["g"] == {"historia"} and c["pg"] == {"historia"} and c["s"] == {("historia", "antigua")} and c["ps"] == {("historia", "medieval")}
    assert me.metricas([f])["genero"]["principal_en_conjunto"] == 1 and me.metricas([f])["subgenero"]["principal_en_conjunto"] == 0


def _embedder_falso(textos):
    """Vectores deterministas (por palabras) y normalizados: textos parecidos dan vectores parecidos."""
    out = []
    for t in textos:
        v = np.zeros(32)
        for w in set(t.lower().split()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 32] += 1
        out.append(v / (np.linalg.norm(v) or 1))
    return np.array(out)


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Un corpus de juguete: 8 apuntes (uno con dos géneros) con su split, y un embedder falso."""
    carpeta = tmp_path / "enes" / "corpus"
    (carpeta / "biblioteca" / "libros").mkdir(parents=True)
    temas = {"historia": "Roma antigua Julio César legiones república imperio Augusto", "economia": "mercados inflación política monetaria banca comercio crecimiento",
             "novela": "novela personajes trama amor misterio aventura detective"}
    meta = {}
    for i in range(8):
        g = ["historia", "economia", "novela"][i % 3]
        rel = f"libros/obra{i}.md"
        (carpeta / "biblioteca" / rel).write_text(f"# Obra {i}\n\n" + (temas[g] + " ") * 40, encoding="utf-8")
        gs = [g, "economia"] if i == 0 else [g]
        meta[rel] = {"titulo": f"Obra {i}", "galaxia": "libros", "genero": g, "subgenero": "antigua" if g == "historia" else "", "subtema": "General", "tipo": "apuntes", "hash": str(i), "origen": f"C:/x/Obra {i} - Autor Uno.md",
                     "capitulos": [{"titulo": "Uno", "pagina": 1}], "generos": [{"id": x, "peso": 1.0} for x in gs]}
    (carpeta / "biblioteca" / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    (tmp_path / "enes" / "split.json").write_text(json.dumps({"prueba": ["libros/obra7.md"], "entrenamiento": sorted(meta)[:-1]}), encoding="utf-8")
    monkeypatch.setattr(clasificador, "_embedder", lambda nombre, carpeta=None: _embedder_falso)
    return tmp_path


def test_construir_datos_genera_ejemplos_con_el_prompt_real_y_varias_etiquetas(corpus, monkeypatch):
    import construir_datos as cd
    monkeypatch.setattr(sys, "argv", ["construir_datos.py", str(corpus), "--val", "0.2", "--vecinos", "3"])
    cd.main()
    d = corpus / "enes" / "entrenamiento" / "datos"
    train = [json.loads(x) for x in (d / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    val = [json.loads(x) for x in (d / "val.jsonl").read_text(encoding="utf-8").splitlines()]
    res = json.loads((d / "resumen.json").read_text(encoding="utf-8"))
    assert res["obras"] == 7 and res["con_varias_etiquetas"] == 1 and "obra7" not in json.dumps(train + val)       # la obra de prueba no entra
    assert not {x["rel"] for x in train} & {x["rel"] for x in val}                                                   # la validación se parte por obra
    g = [x for x in train + val if x["tarea"] == "genero"]
    assert all(x["messages"][0]["role"] == "user" and x["messages"][1]["role"] == "assistant" for x in g)
    multi = next(x for x in train + val if x["rel"] == "libros/obra0.md" and x["tarea"] == "genero")
    assert json.loads(multi["messages"][1]["content"])["generos"] == ["historia", "economia"]                       # las dos etiquetas reales, la principal primero
    assert "Obra 0" in multi["messages"][0]["content"] and "máximo 3" in multi["messages"][0]["content"]
    assert "Obra 0" not in multi["messages"][0]["content"].split("Ahora este:")[0]                                  # el ejemplo no se enseña a sí mismo entre los vecinos
    assert any(x["tarea"] == "subgenero" and json.loads(x["messages"][1]["content"])["subgeneros"] == ["antigua"] for x in train + val)
    assert res["por_tarea"]["genero"] >= 1 and res["vecinos"] == 3


def test_el_prompt_de_los_datos_es_el_mismo_que_usa_el_programa(corpus):
    from conocimiento import llm
    p = llm.prompt_generos("T", [], "texto", [], importar.GENEROS, "", [])
    assert "Géneros:" in p and "Ejemplos resueltos" in p and p.rstrip().endswith("}.")                                # (construir_datos llama a esta misma función)
    s = llm.prompt_subgeneros("T", [], "texto", "Historia", [("antigua", "Antigua", "roma", "rome")], "", [])
    assert "antigua" in s and '"subgeneros"' in s


def _cargar_panel(tmp, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["panel_progreso.py", str(tmp)])
    spec = importlib.util.spec_from_file_location("panel_test", RAIZ / "herramientas" / "panel_progreso.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_el_panel_lee_resultados_con_etiquetas_y_el_entrenamiento(tmp_path, monkeypatch):
    res = tmp_path / "enes" / "resultados"; res.mkdir(parents=True)
    filas = [dict(fila("historia", "historia", pgs=["historia", "economia"]), titulo="a", tipo="libro", metodo="llm", conf=.3, margen=.2, msub=None, revisar=False, seg=1.0) for _ in range(5)]
    (res / "v1.json").write_text(json.dumps({"nombre": "v1", "sets": [], "llm": True, "modelo_llm": "qwen2.5:7b", "filas": filas, "hilos": 1}), encoding="utf-8")
    (res / "v0.json").write_text(json.dumps({"nombre": "v0", "sets": [], "llm": False, "modelo_llm": "", "filas": [{k: v for k, v in x.items() if k not in ("gs", "pgs", "ss", "pss")} for x in filas], "hilos": 1}), encoding="utf-8")
    ent = tmp_path / "enes" / "entrenamiento"
    (ent / "datos").mkdir(parents=True); (ent / "ft1").mkdir()
    (ent / "datos" / "resumen.json").write_text(json.dumps({"obras": 7}), encoding="utf-8")
    (ent / "ft1" / "estado.json").write_text(json.dumps({"fase": "entrenando", "paso": 3, "pasos_total": 10, "t": time.time()}), encoding="utf-8")
    (ent / "ft1" / "registro.jsonl").write_text("\n".join(json.dumps(x) for x in [{"tipo": "paso", "paso": 1, "loss": 1.2, "vram_mb": 5000}, {"tipo": "eval", "paso": 1, "eval_loss": 1.3}, {"tipo": "paso", "paso": 2, "loss": 1.0, "vram_mb": 5100}]), encoding="utf-8")
    p = _cargar_panel(tmp_path, monkeypatch)
    et = p.etiquetas_res()
    assert [e["nombre"] for e in et] == ["v1"]                                                       # el resultado antiguo (sin conjuntos) no aparece en este cuadro
    assert et[0]["genero"]["principal_en_conjunto"] == 5 and et[0]["hist"] == {2: 5} and et[0]["pares"][0][:2] == ["economia", "historia"]
    en = p.entrenamiento()
    assert en["datos"]["obras"] == 7 and en["runs"][0]["nombre"] == "ft1" and en["runs"][0]["pasos"] == [[1, 1.2], [2, 1.0]] and en["runs"][0]["evals"] == [[1, 1.3]] and en["runs"][0]["estado"]["activo"]
    json.dumps({"etiquetas": et, "entrenamiento": en})                                              # lo que sirve el panel tiene que poder serializarse


def test_exportar_ollama_funde_convierte_y_crea_el_modelo_con_la_plantilla_del_base(tmp_path, monkeypatch):
    import exportar_ollama as ex
    (tmp_path / "adaptador").mkdir()
    (tmp_path / "adaptador" / "adapter_model.safetensors").write_bytes(b"x")
    (tmp_path / "estado.json").write_text(json.dumps({"modelo": "Qwen/Qwen2.5-3B-Instruct"}), encoding="utf-8")
    conv = tmp_path / "convert_hf_to_gguf.py"
    conv.write_text("", encoding="utf-8")
    llamadas = []

    class R:
        def __init__(self, out=""):
            self.returncode, self.stdout, self.stderr = 0, out, ""

    def falso(cmd, **k):
        llamadas.append(cmd)
        if cmd[1:3] == ["show", "--modelfile"]:
            return R("\n".join(['# Modelfile generated', 'FROM C:/blobs/sha256-abc', 'TEMPLATE """{{ .Prompt }}"""', 'PARAMETER stop "<|im_end|>"', 'PARAMETER temperature 0.7', '']))
        if str(conv) in cmd:
            Path(cmd[cmd.index("--outfile") + 1]).write_bytes(b"gguf")
        return R()
    monkeypatch.setattr(ex.subprocess, "run", falso)
    monkeypatch.setattr(ex, "fusionar", lambda ad, base, dest: (dest.mkdir(), (dest / "model.safetensors").write_bytes(b"w")))
    monkeypatch.setattr(sys, "argv", ["exportar_ollama.py", str(tmp_path), "--nombre", "mi-clasificador", "--convertidor", str(conv)])
    ex.main()
    mf = (tmp_path / "Modelfile").read_text(encoding="utf-8")
    assert "FROM C:/blobs" not in mf and "modelo-q8_0.gguf" in mf and "TEMPLATE" in mf and 'PARAMETER stop "<|im_end|>"' in mf       # la plantilla y la parada son las del base de Ollama
    assert mf.count("temperature") == 1 and mf.rstrip().endswith("PARAMETER temperature 0")
    assert [c[1] for c in llamadas if c[0].endswith("ollama") or "ollama" in c[0].lower()][-1] == "create" and "mi-clasificador" in llamadas[-1]
    assert any(c[1:3] == ["show", "--modelfile"] and c[3] == "qwen2.5:3b" for c in llamadas)                                    # el base de Ollama sale del modelo con el que se entrenó


def test_exportar_sin_convertidor_explica_que_hacer(tmp_path, monkeypatch):
    import exportar_ollama as ex
    (tmp_path / "adaptador").mkdir()
    (tmp_path / "adaptador" / "adapter_model.safetensors").write_bytes(b"x")
    monkeypatch.setattr(ex, "fusionar", lambda ad, base, dest: (dest.mkdir(), (dest / "model.safetensors").write_bytes(b"w")))
    monkeypatch.setattr(sys, "argv", ["exportar_ollama.py", str(tmp_path), "--convertidor", str(tmp_path / "no_existe.py")])
    with pytest.raises(SystemExit) as e:
        ex.main()
    assert "convert_hf_to_gguf.py" in str(e.value) and "fusionado" in str(e.value)


def test_el_entrenamiento_usa_la_plantilla_de_ollama_sin_mensaje_de_sistema():
    import entrenar
    assert entrenar.formato_ollama("hola") == "<|im_start|>user\nhola<|im_end|>\n<|im_start|>assistant\n"


def test_entrenar_sin_gpu_ni_librerias_falla_con_un_mensaje_claro(tmp_path, monkeypatch, capsys):
    import entrenar
    assert entrenar.opciones([])["modelo"] == "Qwen/Qwen2.5-3B-Instruct" and entrenar.opciones(["--epocas", "3", "--rango", "8"])["epocas"] == 3
    monkeypatch.setitem(sys.modules, "torch", None)                                                  # como si torch no estuviera instalado
    monkeypatch.setattr(sys, "argv", ["entrenar.py", str(tmp_path), str(tmp_path / "out")])
    with pytest.raises(SystemExit) as e:
        entrenar.main()
    assert "Falta una librería" in str(e.value)


def test_servidor_hf_habla_como_ollama_y_llm_py_lo_usa(tmp_path, monkeypatch):
    """El servidor del modelo reentrenado responde a /api/tags y /api/chat con el formato de Ollama y recibe el prompt con la plantilla de entrenamiento."""
    import threading
    from http.server import ThreadingHTTPServer
    import servidor_hf as sh
    from conocimiento import llm
    vistos = []

    def generar(prompt, max_tokens):
        vistos.append(prompt)
        return json.dumps({"generos": ["historia", "economia"], "motivo": "x"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), sh.crear(generar, "arbol-ft"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://localhost:{srv.server_address[1]}"
    try:
        monkeypatch.setattr(llm, "ACTIVO", True)
        monkeypatch.setattr(llm, "URL", url)
        monkeypatch.setattr(llm, "MODELO", "arbol-ft")
        monkeypatch.delenv("ARBOL_LLM", raising=False)
        llm._estado.clear()
        assert llm.disponible(tmp_path)
        r = llm.clasificar("Historia de la banca", [], "texto", [], importar.GENEROS, tmp_path)
        assert r["generos"] == ["historia", "economia"] and r["genero"] == "historia"
        assert vistos[0].startswith("<|im_start|>user\n") and vistos[0].endswith("<|im_start|>assistant\n") and "Historia de la banca" in vistos[0]
    finally:
        srv.shutdown()
        llm._estado.clear()
