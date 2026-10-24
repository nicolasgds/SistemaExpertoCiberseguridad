"""Prueba de humo de la interfaz Streamlit (sin navegador) con streamlit.testing."""
import shutil
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from test_motor import CASO_GRUPO_JOTA  # noqa: E402


def preparar(tmp_path):
    for nombre in ("app.py", "motor.py", "historial.py", "reporte.py"):
        shutil.copy(RAIZ / nombre, tmp_path / nombre)
    shutil.copytree(RAIZ / "reglas", tmp_path / "reglas")
    return AppTest.from_file(str(tmp_path / "app.py"), default_timeout=30)


def test_app_carga_y_evalua(tmp_path):
    at = preparar(tmp_path).run()
    assert not at.exception
    at.sidebar.text_input[0].set_value("Administración")
    for k, v in CASO_GRUPO_JOTA.items():
        clave = f"q_{k}"
        widget = next((w for w in list(at.selectbox) + list(at.number_input) if w.key == clave), None)
        assert widget is not None, clave
        widget.set_value(v)
    at.run()
    boton = next(b for b in at.button if "Evaluar" in b.label)
    boton.click().run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "ALTO" in html
    assert "Activar backup con copia externa" in html
    assert at.session_state["guardado_id"] == 1


def test_faltan_datos_muestra_aviso(tmp_path):
    at = preparar(tmp_path).run()
    boton = next(b for b in at.button if "Evaluar" in b.label)
    boton.click().run()
    assert not at.exception
    avisos = " ".join(w.value for w in at.warning)
    assert "Riesgo no determinable en Endpoint" in avisos
    assert "sector" in avisos  # pide sector para guardar


def test_streamlit_app_con_estetica(tmp_path):
    """Punto de entrada de Streamlit Cloud: ejecuta app.py y agrega el estilo con el sello."""
    for nombre in ("streamlit_app.py", "app.py", "motor.py", "historial.py", "reporte.py"):
        shutil.copy(RAIZ / nombre, tmp_path / nombre)
    shutil.copytree(RAIZ / "reglas", tmp_path / "reglas")
    shutil.copytree(RAIZ / "static", tmp_path / "static")
    at = AppTest.from_file(str(tmp_path / "streamlit_app.py"), default_timeout=30).run()
    assert not at.exception
    estilos = " ".join(m.value for m in at.markdown)
    assert "app/static/sello.png" in estilos
    assert any("Evaluar" in b.label for b in at.button)
