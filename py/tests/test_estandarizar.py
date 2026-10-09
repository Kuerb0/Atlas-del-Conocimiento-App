"""Material de estudio (apuntes, ejercicios, exámenes), géneros «actuarial» y «burocracia» y privacidad de la burocracia."""
import json

from conocimiento import importar, taxonomia


def test_tipo_docente_reconoce_apuntes_ejercicios_y_examenes():
    td = importar.tipo_docente
    assert td("Examen 20180523", "ELEMENTOS DE CONTABILIDAD") == "examen" and td("Examen resuelto", "") == "examen"
    assert td("Tareas1", "") == "ejercicios" and td("5 Hoja 4 corregidos", "") == "ejercicios" and td("Relación 4 25-26 Soluciones", "") == "ejercicios"
    assert td("Tema 4", "Tema 4. Tablas de Mortalidad") == "apuntes" and td("Lección 3 presentación 2025", "") == "apuntes"
    assert td("paper", "Abstract: we study the estimator. Keywords: bayes") is None                       # un artículo con resumen y palabras clave sigue siendo un artículo
    assert td("Prácticas Curriculares", "normativa") is None                                              # un formulario no es material de estudio


def test_titulo_estandar_saca_la_cabecera_del_tema():
    te = importar.titulo_estandar
    assert te("Tema 4. Tablas de Mortalidad 1. Introducción: Definición y orígenes", "Tema 4") == "Tema 4 · Tablas de Mortalidad"
    assert te("1 TEMA 5. LOS PARÁMETROS DE COBERTURA DE LAS OPCIONES (LETRAS GRIEGAS) 5.1 INTRODUCCIÓN Una", "tema 5").startswith("Tema 5 · Los parámetros de cobertura")
    assert te("Texto sin cabecera de tema", "Hoja 3 corregidos") == "Hoja 3 corregidos"


def test_los_generos_nuevos_tienen_sus_subgeneros():
    assert {s[0] for s in taxonomia.subgeneros("actuarial")} == {"demografia", "vida", "no_vida", "pensiones", "solvencia"}
    assert {s[0] for s in taxonomia.subgeneros("burocracia")} == {"academico", "legal", "financiero", "laboral"}
    assert "actuarial" in importar.GENEROS and "burocracia" in importar.GENEROS and {"ejercicios", "examen"} <= set(importar.TIPOS)


def test_la_burocracia_no_viaja_en_referencias(tmp_path):
    meta = {"notas/a.pdf": {"titulo": "Apuntes", "genero": "actuarial", "origen": "C:/x/a.pdf", "hash": "1"},
            "notas/b.pdf": {"titulo": "Solicitud de beca", "genero": "burocracia", "origen": "C:/x/b.pdf", "hash": "2", "capitulos": [{"titulo": "dato personal"}]}}
    importar._guardar(tmp_path, meta)
    local = json.loads((tmp_path / "biblioteca" / "metadatos.json").read_text(encoding="utf-8"))
    viaja = json.loads((tmp_path / "biblioteca" / "referencias.json").read_text(encoding="utf-8"))
    assert set(local) == {"notas/a.pdf", "notas/b.pdf"}                                      # en tu equipo está todo
    assert set(viaja) == {"notas/a.pdf"} and "origen" not in viaja["notas/a.pdf"]            # lo que sube a GitHub no lleva la burocracia ni las rutas
