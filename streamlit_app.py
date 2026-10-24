"""
Punto de entrada para Streamlit Community Cloud.

Ejecuta la aplicación (app.py) sin modificarla y le agrega la estética de Grupo I S.A.:
fondo azul policía, detalles en amarillo y el sello en la barra lateral y como marca de agua.

  * El tema base (colores de botones, campos, etc.) está en .streamlit/config.toml
  * El sello se sirve desde static/sello.png (para cambiarlo: python preparar_sello.py <imagen>)

Ejecutar localmente:  streamlit run streamlit_app.py
"""
import runpy
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent
AZUL_POLICIA = "#062448"
AMARILLO = "#FEE800"

runpy.run_path(str(BASE / "app.py"), run_name="__main__")

css_sello = ""
if (BASE / "static" / "sello.png").exists():
    css_sello = """
[data-testid="stAppViewContainer"]::before {
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background: url("app/static/sello.png") no-repeat center 55% / min(55vw, 520px);
  opacity: .07;
}
[data-testid="stSidebarUserContent"]::before {
  content: ""; display: block; height: 170px; margin: -1.5rem 0 .5rem;
  background: url("app/static/sello.png") no-repeat center / contain;
  filter: drop-shadow(0 4px 10px rgba(0,0,0,.45));
}"""

st.markdown(f"""<style>
[data-testid="stAppViewContainer"] {{
  background: radial-gradient(ellipse at 50% -10%, #12407F 0%, {AZUL_POLICIA} 50%, #03152C 100%);
}}
[data-testid="stMain"] {{ position: relative; z-index: 1; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #082C58 0%, #03152C 100%);
  border-right: 3px solid {AMARILLO};
}}
h1 {{ color: {AMARILLO} !important; }}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] p {{
  color: {AZUL_POLICIA} !important; font-weight: 700;
}}
.tarjeta, .rec {{ background: rgba(255,255,255,.06) !important; }}
.tarjeta .niv {{ filter: brightness(1.45) saturate(1.1); }}
[data-testid="stExpander"] details {{ background: rgba(255,255,255,.03); }}
{css_sello}
</style>""", unsafe_allow_html=True)
