"""Generación del informe descargable (Markdown) de una evaluación."""
from __future__ import annotations

from motor import BaseConocimiento


def generar_markdown(res: dict, base: BaseConocimiento, sector: str = "", responsable: str = "") -> str:
    g = res["general"]
    lineas = [
        "# Informe de autodiagnóstico de ciberseguridad",
        "",
        f"- **Fecha:** {res['fecha'].replace('T', ' ')}",
        f"- **Sector evaluado:** {sector or '(no indicado)'}",
        f"- **Responsable:** {responsable or '(no indicado)'}",
        f"- **Versión de reglas:** {res['version_reglas']}",
        "",
        f"## Nivel de riesgo general: {g['nivel'].upper()}"
        + (f" (como mínimo {g['nivel_minimo']})" if g.get("nivel_minimo") else ""),
        "",
    ]
    lineas += [f"- {x}" for x in g["explicacion"]]
    lineas += ["", "## Nivel por categoría", "", "| Categoría | Nivel | Tipo |", "|---|---|---|"]
    for cat, info in res["categorias"].items():
        tipo = "Crítica" if info["critica"] else ("Observación" if info["solo_observacion"] else "Complementaria")
        nivel = info["nivel"] + (f" (mín. {info['nivel_minimo']})" if info.get("nivel_minimo") else "")
        lineas.append(f"| {cat} | {nivel} | {tipo} |")

    faltantes = [(c, i) for c, i in res["categorias"].items() if i["datos_faltantes"]]
    if faltantes:
        lineas += ["", "## Datos faltantes", ""]
        for cat, info in faltantes:
            lineas.append(f"- **{cat}:** " + ", ".join(base.etiqueta(h) for h in info["datos_faltantes"]))

    lineas += ["", "## Recomendaciones priorizadas", ""]
    if res["recomendaciones"]:
        for i, r in enumerate(res["recomendaciones"], 1):
            lineas.append(f"{i}. **[{r['nivel']}] {r['rf']} → {r['recomendacion']}**  ")
            lineas.append(f"   Regla {r['id']} · {r['categoria']} · Fuente: {r['fuente']}")
    else:
        lineas.append("No hay recomendaciones: no se activaron reglas de riesgo.")

    if res["observaciones"]:
        lineas += ["", "## Observaciones (no modifican el nivel general)", ""]
        for o in res["observaciones"]:
            lineas.append(f"- **{o['rf']} ({o['id']})** {o['recomendacion']} _Fuente: {o['fuente']}_")

    lineas += ["", "## Trazabilidad por categoría", ""]
    for cat, info in res["categorias"].items():
        lineas += [f"### {cat} — {info['nivel']}", ""]
        lineas += [f"- {x}" for x in info["explicacion"]]
        lineas.append("")

    lineas += ["---",
               "_Este informe se basa en respuestas autorreportadas. No reemplaza una auditoría de "
               "seguridad certificada ni un análisis técnico (escaneo, pentesting)._"]
    return "\n".join(lineas)
