"""Arbol de la estadística: funciones estadísticas reutilizables (origen en trabajos de consultoría; máster).

Ramas: preprocesado, seleccion, modelos, diagnostico, clustering, contrastes, descriptiva, multivariante, ml, actuarial, finanzas, simulacion, diseno y graficos
(graficos se importa aparte para no cargar matplotlib si no se usa).
Mapa completo en INDEX.md; reglas de uso para Claude en CLAUDE.md.
"""
from . import (actuarial, clustering, contrastes, descriptiva, diagnostico, diseno, finanzas, ml, modelos, multivariante,
               preprocesado, seleccion, simulacion)

__all__ = ["actuarial", "clustering", "contrastes", "descriptiva", "diagnostico", "finanzas", "ml", "modelos", "multivariante", "preprocesado", "seleccion",
           "simulacion", "diseno"]
__version__ = "1.5.1"
