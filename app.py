"""
Sistema experto para evaluación de riesgo de ciberseguridad en PyMEs.
Interfaz en Streamlit.

Ejecutar sin estética:   streamlit run app.py
Ejecutar con estética:   streamlit run streamlit_app.py   (punto de entrada de Streamlit Cloud)
"""
from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from historial import Historial, comparar
from motor import (CON_OBSERVACIONES, NO_DETERMINABLE, RANGO, SIN_OBSERVACIONES,
                   BaseConocimiento, MotorInferencia, listar_versiones, validar_base)
from reporte import generar_markdown

BASE_DIR = Path(__file__).resolve().parent
DIR_REGLAS = BASE_DIR / "reglas"
RUTA_DB = BASE_DIR / "datos" / "historial.db"

COLORES = {
    "Alto": "#C0392B", "Medio": "#D68910", "Bajo": "#1E8449",
    NO_DETERMINABLE: "#7F8C8D", CON_OBSERVACIONES: "#2E86C1", SIN_OBSERVACIONES: "#1E8449",
    "Observación": "#2E86C1",
}
ICONOS_EVOLUCION = {"Mejoró": "⬇️ Mejoró", "Empeoró": "⬆️ Empeoró", "Sin cambios": "➡️ Sin cambios"}

st.set_page_config(page_title="Diagnóstico de ciberseguridad PyME", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
.badge {display:inline-block;padding:2px 10px;border-radius:999px;color:#fff;
        font-size:0.78rem;font-weight:600;letter-spacing:.02em;}
.tarjeta {border-radius:12px;padding:14px 10px;text-align:center;height:100%;
          background:rgba(127,127,127,0.08);border-top:6px solid var(--c);}
.tarjeta .cat {font-size:0.92rem;font-weight:600;}
.tarjeta .niv {font-size:1.45rem;font-weight:800;color:var(--c);margin:4px 0;line-height:1.2;}
.tarjeta .niv.largo {font-size:1rem;}
.tarjeta .sub {font-size:0.75rem;opacity:.7;}
.general {border-radius:14px;padding:18px 22px;color:#fff;background:var(--c);margin-bottom:8px;}
.general .t {font-size:0.95rem;opacity:.9;}
.general .n {font-size:2.1rem;font-weight:800;line-height:1.15;}
.rec {padding:10px 14px;border-radius:10px;background:rgba(127,127,127,0.07);
      border-left:5px solid var(--c);margin-bottom:8px;}
.rec .meta {font-size:0.78rem;opacity:.75;margin-top:3px;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Recursos
# ---------------------------------------------------------------------------
@st.cache_resource
def cargar_base(ruta: str, _mtime: float) -> BaseConocimiento:
    return BaseConocimiento.desde_archivo(ruta)


@st.cache_resource
def obtener_historial() -> Historial:
    return Historial(RUTA_DB)


def badge(nivel: str) -> str:
    return f"<span class='badge' style='background:{COLORES.get(nivel, '#555')}'>{nivel}</span>"


def clave_widget(id_pregunta: str) -> str:
    return f"q_{id_pregunta}"


def reiniciar() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith("q_"):
            del st.session_state[k]
    for k in ("resultado", "respuestas_evaluadas", "guardado_id", "sector_evaluado"):
        st.session_state.pop(k, None)


def limpiar_valores_invalidos(base: BaseConocimiento) -> None:
    """Si se cambia de versión de reglas, descarta respuestas que ya no son opciones válidas."""
    for p in base.preguntas:
        k = clave_widget(p["id"])
        if p["tipo"] == "opcion" and k in st.session_state:
            if st.session_state[k] is not None and st.session_state[k] not in {o["valor"] for o in p["opciones"]}:
                del st.session_state[k]


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
versiones = listar_versiones(DIR_REGLAS)
if not versiones:
    st.error(f"No se encontraron archivos de reglas en {DIR_REGLAS}.")
    st.stop()

with st.sidebar:
    st.header("🛡️ Autodiagnóstico")
    idx_version = st.selectbox(
        "Versión de reglas", range(len(versiones)),
        format_func=lambda i: f"v{versiones[i]['version']}" + (" (más reciente)" if i == 0 else ""),
        help="Cada evaluación guarda la versión de reglas con la que se hizo (RF-12).")
    sector = st.text_input("Sector / área evaluada", placeholder="Ej.: Administración",
                           help="Se usa para agrupar el historial y comparar evaluaciones del mismo sector.")
    responsable = st.text_input("Responsable (opcional)", placeholder="Ej.: Socio fundador")
    guardar_auto = st.checkbox("Guardar cada evaluación en el historial", value=True)
    st.divider()
    st.caption("Uso orientativo basado en respuestas autorreportadas. No reemplaza una auditoría "
               "certificada ni realiza escaneos técnicos.")

ruta_version = versiones[idx_version]["ruta"]
try:
    base = cargar_base(str(ruta_version), ruta_version.stat().st_mtime)
except Exception as e:  # base inválida
    st.error(f"No se pudo cargar {ruta_version.name}: {e}")
    st.stop()

historial = obtener_historial()
limpiar_valores_invalidos(base)

st.title("Sistema experto de riesgo de ciberseguridad para PyMEs")
st.caption(f"Base de conocimiento v{base.version} · CIS Controls v8 IG1 · NIST CSF · ISO/IEC 27001 Anexo A")

tab_eval, tab_hist, tab_base, tab_glosario = st.tabs(
    ["📝 Evaluación", "🕓 Historial", "📚 Base de conocimiento", "📖 Glosario"])


# ---------------------------------------------------------------------------
# Pestaña: Evaluación
# ---------------------------------------------------------------------------
def render_pregunta(p: dict) -> None:
    k = clave_widget(p["id"])
    if p["tipo"] == "opcion":
        textos = {o["valor"]: o["texto"] for o in p["opciones"]}
        st.selectbox(p["texto"], list(textos), index=None, format_func=textos.get,
                     placeholder="Elegí una opción…", key=k, help=p.get("ayuda"))
    else:
        st.number_input(p["texto"], min_value=0, max_value=int(p.get("max", 100000)), value=None,
                        step=1, placeholder="Dejalo vacío si no sabés", key=k, help=p.get("ayuda"))
    if p.get("ayuda"):
        st.caption("ℹ️ " + p["ayuda"])


def render_resultado(res: dict, respuestas_actuales: dict) -> None:
    st.divider()
    st.header("📊 Resultado de la evaluación")
    if st.session_state.get("respuestas_evaluadas") != respuestas_actuales:
        st.info("Modificaste respuestas después de evaluar. Presioná **Evaluar riesgo** para actualizar el resultado.")
    if st.session_state.get("guardado_id"):
        st.caption(f"✅ Guardada en el historial como evaluación #{st.session_state['guardado_id']} "
                   f"del sector «{st.session_state.get('sector_evaluado', '')}».")

    g = res["general"]
    minimo = f" · como mínimo {g['nivel_minimo']}" if g.get("nivel_minimo") else ""
    st.markdown(
        f"<div class='general' style='--c:{COLORES.get(g['nivel'], '#555')}'>"
        f"<div class='t'>Nivel de riesgo general</div>"
        f"<div class='n'>{g['nivel'].upper()}{minimo}</div>"
        f"<div class='t'>Peor nivel entre las categorías críticas: {', '.join(base.categorias_criticas)}</div>"
        f"</div>", unsafe_allow_html=True)

    cats = list(res["categorias"].items())
    cols = st.columns(len(cats))
    for col, (cat, info) in zip(cols, cats):
        meta = base.categorias.get(cat, {})
        tipo = "Crítica" if info["critica"] else ("Solo observaciones" if info["solo_observacion"] else "Complementaria")
        nivel = info["nivel"] + (f"<br><small>mín. {info['nivel_minimo']}</small>" if info.get("nivel_minimo") else "")
        col.markdown(
            f"<div class='tarjeta' style='--c:{COLORES.get(info['nivel'], '#555')}'>"
            f"<div class='cat'>{meta.get('icono', '')} {cat}</div>"
            f"<div class='niv{' largo' if len(info['nivel']) > 6 else ''}'>{nivel}</div>"
            f"<div class='sub'>{tipo}</div></div>",
            unsafe_allow_html=True)

    for cat, info in res["categorias"].items():
        if info["nivel"] == NO_DETERMINABLE:
            faltan = ", ".join(f"«{base.etiqueta(h)}»" for h in info["datos_faltantes"])
            texto = f"**Riesgo no determinable en {cat}.** Falta: {faltan}."
            if info.get("nivel_minimo"):
                texto += f" Con lo respondido ya se detecta, como mínimo, riesgo **{info['nivel_minimo']}**."
            st.warning(texto)

    st.subheader("🛠️ Recomendaciones priorizadas")
    if not res["recomendaciones"]:
        st.success("No se activaron reglas de riesgo: no hay acciones correctivas pendientes.")
    for i, r in enumerate(res["recomendaciones"], 1):
        st.markdown(
            f"<div class='rec' style='--c:{COLORES[r['nivel']]}'>"
            f"<b>{i}.</b> {badge(r['nivel'])} <b>{r['rf']} → {r['recomendacion']}</b>"
            f"<div class='meta'>Regla {r['id']} · {r['categoria']} · Severidad {r['severidad']}/10 · "
            f"Fuente: {r['fuente']}</div></div>", unsafe_allow_html=True)

    if res["observaciones"]:
        st.subheader("📌 Observaciones")
        st.caption("No modifican el nivel general, pero conviene atenderlas.")
        for o in res["observaciones"]:
            st.markdown(
                f"<div class='rec' style='--c:{COLORES['Observación']}'>{badge('Observación')} "
                f"<b>{o['rf']} → {o['recomendacion']}</b>"
                f"<div class='meta'>Regla {o['id']} · {o['categoria']} · Fuente: {o['fuente']}</div></div>",
                unsafe_allow_html=True)

    st.subheader("🔎 Explicación y trazabilidad")
    st.caption("Cómo llegó el sistema a cada conclusión: datos ingresados → reglas activadas → nivel.")
    with st.expander(f"Nivel general — {g['nivel']}"):
        for linea in g["explicacion"]:
            st.markdown("- " + linea)
    for cat, info in res["categorias"].items():
        icono = base.categorias.get(cat, {}).get("icono", "")
        with st.expander(f"{icono} {cat} — {info['nivel']}"):
            for linea in info["explicacion"]:
                st.markdown("- " + linea)
    if res["no_evaluables"]:
        with st.expander(f"Reglas que no se pudieron evaluar por falta de datos ({len(res['no_evaluables'])})"):
            for ne in res["no_evaluables"]:
                faltan = ", ".join(f"«{base.etiqueta(h)}»" for h in ne["faltan"])
                st.markdown(f"- `{ne['id']}` ({ne['rf']}) {ne['descripcion']} — falta {faltan}")

    c1, c2 = st.columns(2)
    nombre = f"diagnostico_{(sector or 'empresa').strip().replace(' ', '_')}_{res['fecha'][:10]}"
    c1.download_button("⬇️ Descargar informe (Markdown)",
                       generar_markdown(res, base, sector, responsable),
                       file_name=f"{nombre}.md", mime="text/markdown")
    c2.download_button("⬇️ Descargar resultado (JSON)",
                       json.dumps(res, ensure_ascii=False, indent=2),
                       file_name=f"{nombre}.json", mime="application/json")


with tab_eval:
    st.markdown(
        "Respondé el cuestionario con lo que sepas. Si no conocés una respuesta, elegí **No sé** "
        "o dejala vacía: el sistema **no asume valores** y te va a indicar qué dato falta. "
        "Debajo de cada pregunta hay una breve explicación de los términos técnicos.")

    respuestas = {p["id"]: st.session_state.get(clave_widget(p["id"])) for p in base.preguntas}
    hechos_actuales, no_aplica = base.normalizar(respuestas)
    hechos_vis = {k: v for k, v in hechos_actuales.items()}
    respondidos, requeridos = base.progreso(hechos_actuales, no_aplica)
    st.progress(respondidos / requeridos if requeridos else 1.0,
                text=f"Datos clave respondidos: {respondidos} de {requeridos}")

    for cat, meta in base.categorias.items():
        with st.container(border=True):
            tipo = "categoría crítica" if meta.get("critica") else (
                "solo observaciones" if meta.get("solo_observacion") else "categoría complementaria")
            st.subheader(f"{meta.get('icono', '')} {cat}")
            st.caption(f"{meta.get('descripcion', '')} — _{tipo}_")
            for p in base.preguntas_de(cat):
                if not base.es_visible(p, hechos_vis):
                    st.caption(f"↳ «{p['etiqueta']}»: no aplica según la respuesta anterior.")
                    continue
                render_pregunta(p)

    c1, c2, _ = st.columns([1, 1, 3])
    evaluar = c1.button("🔍 Evaluar riesgo", type="primary")
    c2.button("🧹 Nueva evaluación", on_click=reiniciar)

    if evaluar:
        resultado = MotorInferencia(base).evaluar(respuestas)
        st.session_state["resultado"] = resultado
        st.session_state["respuestas_evaluadas"] = dict(respuestas)
        st.session_state["guardado_id"] = None
        if guardar_auto:
            if sector.strip():
                st.session_state["guardado_id"] = historial.guardar(sector, responsable, resultado)
                st.session_state["sector_evaluado"] = sector.strip()
                st.toast("Evaluación guardada en el historial", icon="✅")
            else:
                st.warning("Indicá el **sector / área evaluada** en la barra lateral para guardar "
                           "esta evaluación en el historial.")

    res_guardado = st.session_state.get("resultado")
    if res_guardado:
        if res_guardado["version_reglas"] != base.version:
            st.info(f"El último resultado se calculó con las reglas v{res_guardado['version_reglas']}. "
                    f"Presioná **Evaluar riesgo** para recalcular con la v{base.version}.")
        else:
            render_resultado(res_guardado, respuestas)


# ---------------------------------------------------------------------------
# Pestaña: Historial (RF-11)
# ---------------------------------------------------------------------------
def texto_hecho(hecho: str, valor) -> str:
    if hecho not in base.pregunta:
        return "(sin dato)" if valor is None else str(valor)
    return base.formatear_valor(hecho, valor)


with tab_hist:
    sectores = historial.sectores()
    if not sectores:
        st.info("Todavía no hay evaluaciones guardadas. Completá el cuestionario, indicá un sector en "
                "la barra lateral y presioná **Evaluar riesgo**.")
    else:
        idx = sectores.index(sector.strip()) if sector.strip() in sectores else 0
        sector_sel = st.selectbox("Sector", sectores, index=idx)
        evaluaciones = historial.listar(sector_sel)

        filas, largo = [], []
        for e in evaluaciones:
            r = e["resultado"]
            fecha = e["fecha"][:16].replace("T", " ")
            fila = {"#": e["id"], "Fecha": fecha, "Responsable": e["responsable"],
                    "Reglas": f"v{e['version_reglas']}", "General": r["general"]["nivel"]}
            etiqueta_x = f"#{e['id']} · {fecha}"
            largo.append({"Evaluación": etiqueta_x, "Serie": "General", "Nivel": RANGO.get(r["general"]["nivel"])})
            for cat, info in r["categorias"].items():
                fila[cat] = info["nivel"]
                if not info.get("solo_observacion"):
                    largo.append({"Evaluación": etiqueta_x, "Serie": cat, "Nivel": RANGO.get(info["nivel"])})
            filas.append(fila)

        st.subheader(f"Evaluaciones de «{sector_sel}» ({len(evaluaciones)})")
        st.dataframe(pd.DataFrame(filas), hide_index=True)

        df_largo = pd.DataFrame(largo).dropna(subset=["Nivel"])
        if len(evaluaciones) >= 2 and not df_largo.empty:
            st.subheader("Evolución del nivel de riesgo")
            orden_x = list(dict.fromkeys(d["Evaluación"] for d in largo))
            grafico = alt.Chart(df_largo).mark_line(point=True).encode(
                x=alt.X("Evaluación:N", sort=orden_x, title=None),
                y=alt.Y("Nivel:Q", scale=alt.Scale(domain=[0.5, 3.5]), title="Nivel de riesgo",
                        axis=alt.Axis(values=[1, 2, 3],
                                      labelExpr="datum.value == 1 ? 'Bajo' : datum.value == 2 ? 'Medio' : 'Alto'")),
                color=alt.Color("Serie:N", title=None),
                strokeWidth=alt.condition(alt.datum.Serie == "General", alt.value(4), alt.value(2)),
                tooltip=["Evaluación", "Serie"]).properties(height=320)
            st.altair_chart(grafico)
            st.caption("Las evaluaciones «No determinable» no se grafican.")

            st.subheader("Comparar dos evaluaciones")
            opciones = {e["id"]: f"#{e['id']} — {e['fecha'][:16].replace('T', ' ')} — {e['nivel_general']}"
                        for e in evaluaciones}
            ids = list(opciones)
            c1, c2 = st.columns(2)
            id_a = c1.selectbox("Evaluación anterior", ids, index=len(ids) - 2, format_func=opciones.get)
            id_b = c2.selectbox("Evaluación posterior", ids, index=len(ids) - 1, format_func=opciones.get)
            ea = next(e for e in evaluaciones if e["id"] == id_a)
            eb = next(e for e in evaluaciones if e["id"] == id_b)
            comp = comparar(ea["resultado"], eb["resultado"])
            if not comp["mismas_reglas"]:
                st.info(f"Ojo: se usaron versiones de reglas distintas (v{ea['version_reglas']} y "
                        f"v{eb['version_reglas']}); parte de la diferencia puede deberse al cambio de reglas.")
            df_comp = pd.DataFrame(comp["categorias"])
            df_comp["Evolución"] = df_comp["Evolución"].map(lambda x: ICONOS_EVOLUCION.get(x, x))
            st.dataframe(df_comp, hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ Riesgos resueltos**")
                if comp["riesgos_resueltos"]:
                    for d in comp["riesgos_resueltos"]:
                        st.markdown(f"- `{d['id']}` {d['descripcion']} ({d['nivel']})")
                else:
                    st.caption("Ninguno.")
            with c2:
                st.markdown("**⚠️ Riesgos nuevos**")
                if comp["riesgos_nuevos"]:
                    for d in comp["riesgos_nuevos"]:
                        st.markdown(f"- `{d['id']}` {d['descripcion']} ({d['nivel']})")
                else:
                    st.caption("Ninguno.")

            if comp["hechos_cambiados"]:
                st.markdown("**Controles que cambiaron**")
                st.dataframe(pd.DataFrame([
                    {"Control": base.etiqueta(h), "Anterior": texto_hecho(h, a), "Posterior": texto_hecho(h, b)}
                    for h, a, b in comp["hechos_cambiados"]]), hide_index=True)
            else:
                st.caption("Las respuestas de ambas evaluaciones son idénticas.")
        elif len(evaluaciones) < 2:
            st.caption("Con dos o más evaluaciones del mismo sector vas a ver la evolución y la comparación.")

        with st.expander("Administrar historial"):
            id_borrar = st.selectbox("Evaluación a eliminar", [e["id"] for e in evaluaciones],
                                     format_func=lambda i: f"#{i}")
            if st.button("🗑️ Eliminar evaluación seleccionada"):
                historial.eliminar(id_borrar)
                st.rerun()


# ---------------------------------------------------------------------------
# Pestaña: Base de conocimiento (RF-12)
# ---------------------------------------------------------------------------
with tab_base:
    st.markdown(f"**Versión:** {base.version} · **Fecha:** {base.fecha} · "
                f"**Preguntas:** {len(base.preguntas)} · **Reglas:** {len(base.reglas)}")
    st.write(base.descripcion)
    st.markdown("**Fuentes de conocimiento**")
    for f in base.fuentes:
        st.markdown(f"- {f}")
    st.markdown(f"**Regla de nivel general** — `{base.regla_general.get('id')}`: "
                f"{base.regla_general.get('descripcion')}")

    st.subheader("Categorías")
    st.dataframe(pd.DataFrame([
        {"Categoría": f"{m.get('icono', '')} {c}",
         "Tipo": "Crítica" if m.get("critica") else ("Solo observaciones" if m.get("solo_observacion") else "Complementaria"),
         "Descripción": m.get("descripcion", ""),
         "Datos clave": ", ".join(p["etiqueta"] for p in base.preguntas_de(c) if p.get("clave"))}
        for c, m in base.categorias.items()]), hide_index=True)

    st.subheader("Reglas")
    filtro = st.multiselect("Filtrar por categoría", list(base.categorias))
    st.dataframe(pd.DataFrame([
        {"ID": r["id"], "RF": r.get("rf", ""), "Categoría": r["categoria"],
         "SI": base.condicion_a_texto(r["si"]), "ENTONCES": r["entonces"]["nivel"],
         "Severidad": r.get("severidad", 0), "Recomendación": r.get("recomendacion") or "—",
         "Fuente": r.get("fuente", "")}
        for r in base.reglas if not filtro or r["categoria"] in filtro]), hide_index=True)

    st.download_button("⬇️ Descargar esta versión (JSON)",
                       json.dumps(base.datos, ensure_ascii=False, indent=2),
                       file_name=f"reglas_v{base.version}.json", mime="application/json")

    st.subheader("Publicar una nueva versión de reglas")
    st.caption("Descargá el JSON, editá preguntas o reglas, subí el número de versión (ej. 1.1.0) y "
               "cargalo acá. No hace falta tocar el código. Las evaluaciones anteriores conservan la "
               "versión con la que se hicieron.")
    archivo = st.file_uploader("Archivo JSON de reglas", type="json")
    if archivo is not None:
        try:
            datos_nuevos = json.loads(archivo.getvalue().decode("utf-8"))
        except Exception as e:
            st.error(f"El archivo no es un JSON válido: {e}")
        else:
            errores = validar_base(datos_nuevos)
            existentes = {v["version"] for v in versiones}
            if errores:
                st.error("La base de conocimiento tiene errores:\n\n" + "\n".join(f"- {x}" for x in errores))
            elif str(datos_nuevos["version"]) in existentes:
                st.error(f"Ya existe la versión {datos_nuevos['version']}. Incrementá el número de versión.")
            else:
                st.success(f"Versión {datos_nuevos['version']} válida: {len(datos_nuevos['preguntas'])} "
                           f"preguntas y {len(datos_nuevos['reglas'])} reglas.")
                if st.button("💾 Guardar como nueva versión"):
                    destino = DIR_REGLAS / f"reglas_v{datos_nuevos['version']}.json"
                    destino.write_text(json.dumps(datos_nuevos, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.rerun()


# ---------------------------------------------------------------------------
# Pestaña: Glosario
# ---------------------------------------------------------------------------
with tab_glosario:
    st.markdown("Términos usados en el cuestionario, explicados de forma simple.")
    busqueda = st.text_input("Buscar término", placeholder="Ej.: MFA").strip().lower()
    for item in base.glosario:
        if not busqueda or busqueda in item["termino"].lower() or busqueda in item["definicion"].lower():
            st.markdown(f"**{item['termino']}** — {item['definicion']}")
