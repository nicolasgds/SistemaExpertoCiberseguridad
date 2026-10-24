"""
Motor de inferencia del sistema experto de riesgo de ciberseguridad para PyMEs.

Arquitectura clásica de sistema experto:
  * Base de conocimiento (archivo JSON en /reglas): preguntas, categorías y reglas
    SI <condición> ENTONCES <nivel de riesgo>, cada una con su fuente (CIS v8, NIST, ISO).
  * Memoria de trabajo: los hechos que ingresa el usuario en el cuestionario.
  * Motor de inferencia (este módulo): encadenamiento hacia adelante en tres fases
      1. Equiparación: cada regla se evalúa contra los hechos (lógica de tres valores:
         verdadero / falso / desconocido). Una regla solo se dispara si su condición
         es VERDADERA; si depende de un dato faltante queda como "no evaluable".
      2. Agregación por categoría: peor nivel entre las reglas disparadas.
         Si falta un dato clave, la categoría es "No determinable" (no se asume nada),
         salvo que ya haya una regla en Alto (el máximo posible: conclusión definitiva).
      3. Nivel general (regla GEN-01): peor nivel entre las categorías críticas (Must).
  * Módulo de explicación: cada conclusión guarda las reglas que la originaron.

La lógica de este archivo no depende del contenido de las reglas: para cambiar el
conocimiento se publica una nueva versión del JSON (RF-12).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

NIVELES = ["Bajo", "Medio", "Alto"]
RANGO = {"Bajo": 1, "Medio": 2, "Alto": 3}
OBSERVACION = "Observación"
NO_DETERMINABLE = "No determinable"
CON_OBSERVACIONES = "Con observaciones"
SIN_OBSERVACIONES = "Sin observaciones"

OPERADORES = {"==", "!=", "en", "no_en", ">", ">=", "<", "<="}
OPERADORES_NUMERICOS = {">", ">=", "<", "<="}
OPS_TEXTO = {"==": "es", "!=": "no es", "en": "es", "no_en": "no es",
             ">": ">", ">=": "≥", "<": "<", "<=": "≤"}
NIVELES_REGLA = set(NIVELES) | {OBSERVACION}


class BaseInvalidaError(ValueError):
    """La base de conocimiento no respeta el formato esperado."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("Base de conocimiento inválida:\n- " + "\n- ".join(errores))


# ---------------------------------------------------------------------------
# Evaluación de condiciones (lógica de tres valores)
# ---------------------------------------------------------------------------
def _comparar(op: str, valor: Any, referencia: Any) -> bool:
    if op == "==":
        return valor == referencia
    if op == "!=":
        return valor != referencia
    if op == "en":
        return valor in referencia
    if op == "no_en":
        return valor not in referencia
    try:
        v, r = float(valor), float(referencia)
    except (TypeError, ValueError):
        return False
    return {">": v > r, ">=": v >= r, "<": v < r, "<=": v <= r}[op]


def evaluar_condicion(cond: dict, hechos: dict) -> Optional[bool]:
    """Devuelve True, False o None (desconocido por falta de datos)."""
    if "todos" in cond:
        res = [evaluar_condicion(c, hechos) for c in cond["todos"]]
        if any(r is False for r in res):
            return False
        if any(r is None for r in res):
            return None
        return True
    if "cualquiera" in cond:
        res = [evaluar_condicion(c, hechos) for c in cond["cualquiera"]]
        if any(r is True for r in res):
            return True
        if any(r is None for r in res):
            return None
        return False
    if "no" in cond:
        r = evaluar_condicion(cond["no"], hechos)
        return None if r is None else not r
    valor = hechos.get(cond["hecho"])
    if valor is None:
        return None
    return _comparar(cond["op"], valor, cond["valor"])


def hechos_de_condicion(cond: dict) -> list[str]:
    """Lista (sin repetidos, en orden) de los hechos que usa una condición."""
    salida: list[str] = []
    if "todos" in cond or "cualquiera" in cond:
        for c in cond.get("todos", cond.get("cualquiera", [])):
            salida.extend(hechos_de_condicion(c))
    elif "no" in cond:
        salida.extend(hechos_de_condicion(cond["no"]))
    elif "hecho" in cond:
        salida.append(cond["hecho"])
    return list(dict.fromkeys(salida))


# ---------------------------------------------------------------------------
# Validación de la base de conocimiento (se usa al cargar y al subir versiones)
# ---------------------------------------------------------------------------
def _validar_condicion(cond: Any, preguntas: dict, ctx: str, errores: list[str]) -> None:
    if not isinstance(cond, dict):
        errores.append(f"{ctx}: la condición debe ser un objeto.")
        return
    for compuesto in ("todos", "cualquiera"):
        if compuesto in cond:
            sub = cond[compuesto]
            if not isinstance(sub, list) or not sub:
                errores.append(f"{ctx}: '{compuesto}' debe ser una lista no vacía.")
                return
            for i, c in enumerate(sub):
                _validar_condicion(c, preguntas, f"{ctx}.{compuesto}[{i}]", errores)
            return
    if "no" in cond:
        _validar_condicion(cond["no"], preguntas, f"{ctx}.no", errores)
        return
    hecho, op = cond.get("hecho"), cond.get("op")
    if hecho not in preguntas:
        errores.append(f"{ctx}: el hecho '{hecho}' no corresponde a ninguna pregunta.")
        return
    if op not in OPERADORES:
        errores.append(f"{ctx}: operador '{op}' no válido (usar {sorted(OPERADORES)}).")
        return
    if "valor" not in cond:
        errores.append(f"{ctx}: falta 'valor'.")
        return
    p = preguntas[hecho]
    valor = cond["valor"]
    if op in ("en", "no_en") and not isinstance(valor, list):
        errores.append(f"{ctx}: con '{op}' el valor debe ser una lista.")
        return
    if p["tipo"] == "opcion":
        if op in OPERADORES_NUMERICOS:
            errores.append(f"{ctx}: '{hecho}' es de opciones; no admite '{op}'.")
            return
        validos = {o["valor"] for o in p.get("opciones", [])}
        for v in (valor if isinstance(valor, list) else [valor]):
            if v not in validos:
                errores.append(f"{ctx}: el valor '{v}' no es una opción de '{hecho}'.")
    elif p["tipo"] == "numero":
        for v in (valor if isinstance(valor, list) else [valor]):
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errores.append(f"{ctx}: '{hecho}' es numérico; el valor '{v}' no es un número.")


def validar_base(datos: Any) -> list[str]:
    """Devuelve la lista de errores (vacía si la base es válida)."""
    errores: list[str] = []
    if not isinstance(datos, dict):
        return ["El archivo debe contener un objeto JSON."]
    for clave in ("version", "categorias", "preguntas", "reglas"):
        if clave not in datos:
            errores.append(f"Falta la sección obligatoria '{clave}'.")
    if errores:
        return errores
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(datos["version"])):
        errores.append("La versión debe tener el formato X.Y.Z (ej.: 1.1.0).")

    categorias = datos["categorias"]
    if not isinstance(categorias, dict) or not categorias:
        errores.append("'categorias' debe ser un objeto no vacío.")
        categorias = {}
    for nombre, meta in categorias.items():
        if not isinstance(meta, dict) or not isinstance(meta.get("critica"), bool):
            errores.append(f"Categoría '{nombre}': falta 'critica' (true/false).")

    preguntas: dict[str, dict] = {}
    for i, p in enumerate(datos["preguntas"] if isinstance(datos["preguntas"], list) else []):
        ctx = f"Pregunta #{i + 1} ({p.get('id', '?') if isinstance(p, dict) else '?'})"
        if not isinstance(p, dict):
            errores.append(f"{ctx}: debe ser un objeto.")
            continue
        for campo in ("id", "categoria", "tipo", "etiqueta", "texto"):
            if campo not in p:
                errores.append(f"{ctx}: falta '{campo}'.")
        if p.get("id") in preguntas:
            errores.append(f"{ctx}: id repetido.")
        if p.get("categoria") not in categorias:
            errores.append(f"{ctx}: la categoría '{p.get('categoria')}' no existe.")
        if p.get("tipo") not in ("opcion", "numero"):
            errores.append(f"{ctx}: 'tipo' debe ser 'opcion' o 'numero'.")
        if p.get("tipo") == "opcion":
            ops = p.get("opciones")
            if not isinstance(ops, list) or not ops or not all(
                    isinstance(o, dict) and "valor" in o and "texto" in o for o in ops):
                errores.append(f"{ctx}: 'opciones' debe ser una lista de {{valor, texto}}.")
        if "id" in p:
            preguntas[p["id"]] = p
    if not isinstance(datos["preguntas"], list):
        errores.append("'preguntas' debe ser una lista.")

    for p in preguntas.values():
        if "mostrar_si" in p:
            _validar_condicion(p["mostrar_si"], preguntas, f"Pregunta {p['id']}.mostrar_si", errores)

    ids: set[str] = set()
    reglas = datos["reglas"] if isinstance(datos["reglas"], list) else []
    if not isinstance(datos["reglas"], list):
        errores.append("'reglas' debe ser una lista.")
    for i, r in enumerate(reglas):
        if not isinstance(r, dict):
            errores.append(f"Regla #{i + 1}: debe ser un objeto.")
            continue
        ctx = f"Regla {r.get('id', '#' + str(i + 1))}"
        for campo in ("id", "categoria", "si", "entonces"):
            if campo not in r:
                errores.append(f"{ctx}: falta '{campo}'.")
        if r.get("id") in ids:
            errores.append(f"{ctx}: id repetido.")
        ids.add(r.get("id"))
        if r.get("categoria") not in categorias:
            errores.append(f"{ctx}: la categoría '{r.get('categoria')}' no existe.")
        nivel = (r.get("entonces") or {}).get("nivel") if isinstance(r.get("entonces"), dict) else None
        if nivel not in NIVELES_REGLA:
            errores.append(f"{ctx}: 'entonces.nivel' debe ser uno de {sorted(NIVELES_REGLA)}.")
        sev = r.get("severidad", 0)
        if not isinstance(sev, int) or isinstance(sev, bool) or not 0 <= sev <= 10:
            errores.append(f"{ctx}: 'severidad' debe ser un entero entre 0 y 10.")
        if "si" in r:
            _validar_condicion(r["si"], preguntas, f"{ctx}.si", errores)
    return errores


# ---------------------------------------------------------------------------
# Base de conocimiento
# ---------------------------------------------------------------------------
class BaseConocimiento:
    def __init__(self, datos: dict, origen: str = ""):
        errores = validar_base(datos)
        if errores:
            raise BaseInvalidaError(errores)
        self.datos = datos
        self.origen = origen
        self.version: str = datos["version"]
        self.fecha: str = datos.get("fecha", "")
        self.descripcion: str = datos.get("descripcion", "")
        self.fuentes: list[str] = datos.get("fuentes", [])
        self.categorias: dict[str, dict] = datos["categorias"]
        self.preguntas: list[dict] = datos["preguntas"]
        self.pregunta: dict[str, dict] = {p["id"]: p for p in self.preguntas}
        self.reglas: list[dict] = datos["reglas"]
        self.regla_general: dict = datos.get("regla_general", {
            "id": "GEN-01", "rf": "RF-09",
            "descripcion": "Nivel general = peor nivel entre categorías críticas."})
        self.glosario: list[dict] = datos.get("glosario", [])
        self.valores_desconocidos = set(datos.get("valores_desconocidos", ["no_se"]))

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> "BaseConocimiento":
        ruta = Path(ruta)
        with ruta.open(encoding="utf-8") as f:
            return cls(json.load(f), origen=str(ruta))

    # --- consultas -------------------------------------------------------
    @property
    def categorias_criticas(self) -> list[str]:
        return [c for c, m in self.categorias.items() if m.get("critica")]

    def preguntas_de(self, categoria: str) -> list[dict]:
        return [p for p in self.preguntas if p["categoria"] == categoria]

    def etiqueta(self, hecho: str) -> str:
        p = self.pregunta.get(hecho)
        return p["etiqueta"] if p else hecho

    def texto_opcion(self, hecho: str, valor: Any) -> str:
        p = self.pregunta.get(hecho)
        if p and p["tipo"] == "opcion":
            for o in p["opciones"]:
                if o["valor"] == valor:
                    return o["texto"]
        return str(valor)

    def formatear_valor(self, hecho: str, valor: Any) -> str:
        if valor is None:
            return "(sin dato)"
        p = self.pregunta.get(hecho)
        if p and p["tipo"] == "opcion":
            if isinstance(valor, list):
                return " o ".join(f"«{self.texto_opcion(hecho, v)}»" for v in valor)
            return f"«{self.texto_opcion(hecho, valor)}»"
        unidad = p.get("unidad", "") if p else ""
        return f"{valor} {unidad}".strip()

    def condicion_a_texto(self, cond: dict) -> str:
        def interno(c: dict, nivel: int) -> str:
            if "todos" in c or "cualquiera" in c:
                conector = " Y " if "todos" in c else " O "
                partes = [interno(x, nivel + 1) for x in c.get("todos", c.get("cualquiera"))]
                texto = conector.join(partes)
                return f"({texto})" if nivel > 0 else texto
            if "no" in c:
                return f"NO ({interno(c['no'], nivel + 1)})"
            return (f"{self.etiqueta(c['hecho'])} {OPS_TEXTO[c['op']]} "
                    f"{self.formatear_valor(c['hecho'], c['valor'])}")
        return interno(cond, 0)

    # --- memoria de trabajo ----------------------------------------------
    def normalizar(self, crudos: dict) -> tuple[dict, list[str]]:
        """Convierte las respuestas en hechos. 'No sé' y vacíos quedan como None
        (desconocido): nunca se reemplazan por un valor por defecto.
        Devuelve (hechos, preguntas que no aplican por 'mostrar_si')."""
        hechos: dict[str, Any] = {}
        for p in self.preguntas:
            v = crudos.get(p["id"])
            if v is None or v == "" or (not isinstance(v, (int, float)) and v in self.valores_desconocidos):
                v = None
            elif p["tipo"] == "numero":
                try:
                    v = float(v)
                    v = int(v) if v.is_integer() else v
                    if v < 0:
                        v = None
                except (TypeError, ValueError):
                    v = None
            elif v not in {o["valor"] for o in p["opciones"]}:
                v = None
            hechos[p["id"]] = v
        no_aplica = []
        for p in self.preguntas:
            cond = p.get("mostrar_si")
            if cond and evaluar_condicion(cond, hechos) is False:
                hechos[p["id"]] = None
                no_aplica.append(p["id"])
        return hechos, no_aplica

    def es_visible(self, pregunta: dict, hechos: dict) -> bool:
        cond = pregunta.get("mostrar_si")
        return not cond or evaluar_condicion(cond, hechos) is not False

    def datos_clave_faltantes(self, categoria: str, hechos: dict, no_aplica: list[str]) -> list[str]:
        return [p["id"] for p in self.preguntas_de(categoria)
                if p.get("clave") and p["id"] not in no_aplica and hechos.get(p["id"]) is None]

    def progreso(self, hechos: dict, no_aplica: list[str]) -> tuple[int, int]:
        requeridos = [p["id"] for p in self.preguntas if p.get("clave") and p["id"] not in no_aplica]
        respondidos = [h for h in requeridos if hechos.get(h) is not None]
        return len(respondidos), len(requeridos)


def listar_versiones(directorio: str | Path) -> list[dict]:
    """Versiones de reglas disponibles, de la más nueva a la más vieja."""
    salida = []
    for ruta in sorted(Path(directorio).glob("*.json")):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            version = str(datos["version"])
            clave = tuple(int(x) for x in version.split("."))
        except Exception:
            continue
        salida.append({"version": version, "ruta": ruta, "clave": clave, "fecha": datos.get("fecha", "")})
    salida.sort(key=lambda d: d["clave"], reverse=True)
    return salida


def _peor(niveles: list[str]) -> Optional[str]:
    niveles = [n for n in niveles if n in RANGO]
    return max(niveles, key=RANGO.get) if niveles else None


# ---------------------------------------------------------------------------
# Motor de inferencia
# ---------------------------------------------------------------------------
class MotorInferencia:
    def __init__(self, base: BaseConocimiento):
        self.base = base

    def _registrar(self, regla: dict, hechos: dict) -> dict:
        usados = {h: hechos.get(h) for h in hechos_de_condicion(regla["si"])}
        return {
            "id": regla["id"],
            "rf": regla.get("rf", ""),
            "categoria": regla["categoria"],
            "descripcion": regla.get("descripcion", ""),
            "nivel": regla["entonces"]["nivel"],
            "severidad": regla.get("severidad", 0),
            "recomendacion": regla.get("recomendacion"),
            "explicacion": regla.get("explicacion", ""),
            "fuente": regla.get("fuente", ""),
            "condicion": self.base.condicion_a_texto(regla["si"]),
            "hechos": usados,
        }

    def evaluar(self, respuestas: dict) -> dict:
        b = self.base
        hechos, no_aplica = b.normalizar(respuestas)

        # Fase 1 — equiparación de reglas contra la memoria de trabajo
        disparadas: list[dict] = []
        no_evaluables: list[dict] = []
        for regla in b.reglas:
            r = evaluar_condicion(regla["si"], hechos)
            if r is True:
                disparadas.append(self._registrar(regla, hechos))
            elif r is None:
                faltan = [h for h in hechos_de_condicion(regla["si"])
                          if hechos.get(h) is None and h not in no_aplica]
                if faltan:
                    no_evaluables.append({"id": regla["id"], "rf": regla.get("rf", ""),
                                          "categoria": regla["categoria"],
                                          "descripcion": regla.get("descripcion", ""),
                                          "faltan": faltan})

        # Fase 2 — nivel por categoría
        categorias: dict[str, dict] = {}
        for cat, meta in b.categorias.items():
            propias = [d for d in disparadas if d["categoria"] == cat]
            de_riesgo = [d for d in propias if d["nivel"] in RANGO]
            observaciones = [d for d in propias if d["nivel"] == OBSERVACION]
            faltantes = b.datos_clave_faltantes(cat, hechos, no_aplica)
            peor = _peor([d["nivel"] for d in de_riesgo])
            responsables = [d["id"] for d in de_riesgo if d["nivel"] == peor]
            nivel_minimo = None

            explicacion = []
            datos_txt = []
            for p in b.preguntas_de(cat):
                val = "(no aplica)" if p["id"] in no_aplica else b.formatear_valor(p["id"], hechos[p["id"]])
                datos_txt.append(f"{p['etiqueta']}: {val}")
            explicacion.append("**Datos ingresados:** " + " · ".join(datos_txt))
            for d in propias:
                efecto = "observación" if d["nivel"] == OBSERVACION else f"riesgo {d['nivel']}"
                explicacion.append(
                    f"`{d['id']}` ({d['rf']}) **SI** {d['condicion']} **ENTONCES** {efecto}. "
                    f"{d['explicacion']} _[{d['fuente']}]_")
            etiquetas_falt = ", ".join(f"«{b.etiqueta(h)}»" for h in faltantes)

            if meta.get("solo_observacion"):
                if observaciones:
                    nivel = CON_OBSERVACIONES
                    concl = f"{cat}: se registran observaciones; no modifican el nivel general."
                elif faltantes:
                    nivel = NO_DETERMINABLE
                    concl = f"No determinable en {cat}: falta {etiquetas_falt}."
                else:
                    nivel = SIN_OBSERVACIONES
                    concl = f"{cat}: sin observaciones."
            elif peor == "Alto":
                nivel = "Alto"
                concl = (f"{cat} = **Alto** (peor nivel entre las reglas activadas: "
                         f"{', '.join(responsables)}).")
                if faltantes:
                    concl += (f" Aunque falta {etiquetas_falt}, el nivel ya es el máximo "
                              f"posible y no puede cambiar.")
            elif faltantes:
                nivel = NO_DETERMINABLE
                nivel_minimo = peor if peor and peor != "Bajo" else None
                concl = f"Riesgo no determinable en {cat}: falta {etiquetas_falt}. No se asume ningún valor."
                if nivel_minimo:
                    concl += f" Con lo respondido ya hay, como mínimo, riesgo {nivel_minimo}."
            elif peor:
                nivel = peor
                concl = f"{cat} = **{peor}** (peor nivel entre las reglas activadas: {', '.join(responsables)})."
            else:
                nivel = "Bajo"
                concl = (f"{cat} = **Bajo**: con todos los datos clave completos, "
                         f"no se activó ninguna regla de riesgo.")
            explicacion.append("**Conclusión:** " + concl)

            categorias[cat] = {
                "nivel": nivel,
                "nivel_minimo": nivel_minimo,
                "critica": bool(meta.get("critica")),
                "solo_observacion": bool(meta.get("solo_observacion")),
                "reglas_disparadas": [d["id"] for d in propias],
                "datos_faltantes": faltantes,
                "explicacion": explicacion,
            }

        # Fase 3 — nivel general (GEN-01)
        criticas = b.categorias_criticas
        altos = [c for c in criticas if categorias[c]["nivel"] == "Alto"]
        indeterminadas = [c for c in criticas if categorias[c]["nivel"] == NO_DETERMINABLE]
        conocidos = [categorias[c]["nivel"] for c in criticas if categorias[c]["nivel"] in RANGO]
        minimos = [categorias[c]["nivel_minimo"] for c in indeterminadas if categorias[c]["nivel_minimo"]]
        rg = b.regla_general
        resumen = ", ".join(f"{c} = {categorias[c]['nivel']}" for c in criticas)
        no_criticas = [c for c, m in b.categorias.items() if not m.get("critica")]
        expl_general = [
            f"`{rg.get('id', 'GEN-01')}` ({rg.get('rf', 'RF-09')}) {rg.get('descripcion', '')}",
            f"**Categorías críticas:** {resumen}.",
        ]
        general_min = None
        if altos:
            general = "Alto"
            expl_general.append(f"**Conclusión:** {', '.join(altos)} en Alto → nivel general **Alto**"
                                + (f" (aunque {', '.join(indeterminadas)} no sea determinable)." if indeterminadas else "."))
        elif indeterminadas:
            general = NO_DETERMINABLE
            general_min = _peor(conocidos + minimos)
            expl_general.append(
                f"**Conclusión:** no determinable, porque faltan datos clave en {', '.join(indeterminadas)}"
                + (f"; como mínimo el riesgo es {general_min}." if general_min else "."))
        else:
            general = _peor(conocidos) or "Bajo"
            expl_general.append(f"**Conclusión:** peor nivel entre categorías críticas → **{general}**.")
        if no_criticas:
            expl_general.append(f"{', '.join(no_criticas)} se informan por separado y no modifican el "
                                f"nivel general (requisitos Should/Could del pliego).")

        # Fase 4 — recomendaciones priorizadas y observaciones
        criticas_set = set(criticas)
        recomendaciones = sorted(
            (d for d in disparadas if d.get("recomendacion") and d["nivel"] in RANGO),
            key=lambda d: (-RANGO[d["nivel"]], -d["severidad"], d["categoria"] not in criticas_set, d["id"]))
        observaciones = sorted(
            (d for d in disparadas if d["nivel"] == OBSERVACION),
            key=lambda d: (-d["severidad"], d["id"]))

        return {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "version_reglas": b.version,
            "hechos": hechos,
            "no_aplica": no_aplica,
            "general": {"nivel": general, "nivel_minimo": general_min, "explicacion": expl_general},
            "categorias": categorias,
            "disparadas": disparadas,
            "no_evaluables": no_evaluables,
            "recomendaciones": recomendaciones,
            "observaciones": observaciones,
        }
