"""
Historial de evaluaciones (RF-11) en SQLite.

Cada evaluación guarda: fecha, sector, responsable, versión de reglas usada (RF-12),
las respuestas y el resultado completo, para poder compararlas en el tiempo.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from motor import RANGO

ESQUEMA = """
CREATE TABLE IF NOT EXISTS evaluaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT NOT NULL,
    sector          TEXT NOT NULL,
    responsable     TEXT,
    version_reglas  TEXT NOT NULL,
    nivel_general   TEXT NOT NULL,
    hechos          TEXT NOT NULL,
    resultado       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eval_sector ON evaluaciones(sector, fecha);
"""


class Historial:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as con:
            con.executescript(ESQUEMA)

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        return con

    def guardar(self, sector: str, responsable: str, resultado: dict) -> int:
        sector = sector.strip()
        if not sector:
            raise ValueError("El sector es obligatorio para guardar en el historial.")
        with self._conectar() as con:
            cur = con.execute(
                "INSERT INTO evaluaciones (fecha, sector, responsable, version_reglas, nivel_general, hechos, resultado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (resultado.get("fecha") or datetime.now().isoformat(timespec="seconds"),
                 sector, (responsable or "").strip(), resultado["version_reglas"],
                 resultado["general"]["nivel"],
                 json.dumps(resultado["hechos"], ensure_ascii=False),
                 json.dumps(resultado, ensure_ascii=False)))
            return int(cur.lastrowid)

    @staticmethod
    def _fila(f: sqlite3.Row) -> dict:
        return {"id": f["id"], "fecha": f["fecha"], "sector": f["sector"],
                "responsable": f["responsable"], "version_reglas": f["version_reglas"],
                "nivel_general": f["nivel_general"], "hechos": json.loads(f["hechos"]),
                "resultado": json.loads(f["resultado"])}

    def sectores(self) -> list[str]:
        with self._conectar() as con:
            return [f[0] for f in con.execute("SELECT DISTINCT sector FROM evaluaciones ORDER BY sector")]

    def listar(self, sector: str) -> list[dict]:
        with self._conectar() as con:
            filas = con.execute("SELECT * FROM evaluaciones WHERE sector = ? ORDER BY fecha, id", (sector,))
            return [self._fila(f) for f in filas]

    def obtener(self, id_eval: int) -> Optional[dict]:
        with self._conectar() as con:
            f = con.execute("SELECT * FROM evaluaciones WHERE id = ?", (id_eval,)).fetchone()
            return self._fila(f) if f else None

    def eliminar(self, id_eval: int) -> None:
        with self._conectar() as con:
            con.execute("DELETE FROM evaluaciones WHERE id = ?", (id_eval,))


def _evolucion(antes: str, despues: str) -> str:
    if antes not in RANGO or despues not in RANGO:
        return "—" if antes != despues else "Sin cambios"
    if RANGO[despues] < RANGO[antes]:
        return "Mejoró"
    if RANGO[despues] > RANGO[antes]:
        return "Empeoró"
    return "Sin cambios"


def comparar(res_a: dict, res_b: dict) -> dict:
    """Compara dos resultados (A = anterior, B = posterior)."""
    cats = list(dict.fromkeys(list(res_a["categorias"]) + list(res_b["categorias"])))
    filas = [{"Categoría": "Nivel general",
              "Anterior": res_a["general"]["nivel"], "Posterior": res_b["general"]["nivel"],
              "Evolución": _evolucion(res_a["general"]["nivel"], res_b["general"]["nivel"])}]
    for c in cats:
        a = res_a["categorias"].get(c, {}).get("nivel", "—")
        b = res_b["categorias"].get(c, {}).get("nivel", "—")
        filas.append({"Categoría": c, "Anterior": a, "Posterior": b, "Evolución": _evolucion(a, b)})

    hechos_a, hechos_b = res_a.get("hechos", {}), res_b.get("hechos", {})
    cambios: list[tuple[str, Any, Any]] = [
        (h, hechos_a.get(h), hechos_b.get(h))
        for h in dict.fromkeys(list(hechos_a) + list(hechos_b))
        if hechos_a.get(h) != hechos_b.get(h)]

    ids_a = {d["id"] for d in res_a.get("disparadas", [])}
    ids_b = {d["id"] for d in res_b.get("disparadas", [])}
    riesgo_a = {d["id"]: d for d in res_a.get("disparadas", []) if d["nivel"] in ("Medio", "Alto")}
    riesgo_b = {d["id"]: d for d in res_b.get("disparadas", []) if d["nivel"] in ("Medio", "Alto")}
    return {
        "categorias": filas,
        "hechos_cambiados": cambios,
        "riesgos_resueltos": [riesgo_a[i] for i in sorted(set(riesgo_a) - set(riesgo_b))],
        "riesgos_nuevos": [riesgo_b[i] for i in sorted(set(riesgo_b) - set(riesgo_a))],
        "mismas_reglas": res_a.get("version_reglas") == res_b.get("version_reglas"),
        "reglas_en_comun": len(ids_a & ids_b),
    }
