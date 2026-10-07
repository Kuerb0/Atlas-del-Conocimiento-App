import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # gráficos sin ventana en los tests
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def datos_bin():
    """Dataset sintético binario: 2 numéricas, 1 categórica, objetivo logit conocido."""
    rng = np.random.default_rng(0)
    n = 4000
    df = pd.DataFrame({
        "x1": rng.normal(size=n),
        "x2": rng.normal(size=n),
        "region": rng.choice(["N", "S", "E"], size=n),
        "ruido": rng.normal(size=n),
    })
    eta = -0.3 + 1.0 * df.x1 - 0.5 * df.x2 + df.region.map({"N": 0.0, "S": 0.6, "E": -0.4})
    df["y"] = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(int)
    return df


@pytest.fixture(scope="session")
def datos_multi():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n),
                       "g": rng.choice(["a", "b"], size=n)})
    e = np.column_stack([np.zeros(n), 1.2 * df.x1 + 0.3, -1.0 * df.x2 + (df.g == "b") * 0.8])
    p = np.exp(e) / np.exp(e).sum(axis=1, keepdims=True)
    u = rng.random(n)[:, None]
    df["clase"] = np.array(["base", "media", "alta"])[(u > p.cumsum(axis=1)).sum(axis=1).clip(0, 2)]
    return df


@pytest.fixture(autouse=True)
def _sin_modelo_de_embeddings(monkeypatch):
    """Los tests no descargan ni usan el modelo real del clasificador por parecido (test_clasificador.py lo prueba con uno falso)."""
    from conocimiento import clasificador
    monkeypatch.setattr(clasificador, "ACTIVO", False)
    monkeypatch.setattr(clasificador, "WEB", False)
    from conocimiento import llm
    monkeypatch.setattr(llm, "ACTIVO", False)
