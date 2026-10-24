"""Casos de prueba del motor de inferencia (criterios de aceptación del pliego)."""
import copy
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from historial import Historial, comparar  # noqa: E402
from motor import (NO_DETERMINABLE, BaseConocimiento, MotorInferencia,  # noqa: E402
                   evaluar_condicion, validar_base)

RUTA = RAIZ / "reglas" / "reglas_v1.0.0.json"

TODO_BIEN = {
    "antivirus_estado": "actualizado", "dias_actualizacion_so": 10, "dias_actualizacion_apps": 15,
    "actualizaciones_automaticas": "si", "contrasenas_longitud": "exigida", "contrasenas_distintas": "si",
    "mfa_correo": "todos", "mfa_criticos": "todos", "backup_frecuencia": "diaria", "backup_externo": "nube",
    "backup_probado": "reciente", "backup_automatico": "automatico", "firewall": "si",
    "router_clave": "cambiada", "wifi_invitados": "separada", "capacitacion_phishing": "ultimo_anio",
    "incidentes_phishing": 2, "plan_incidentes": "documentado",
}

# Caso del relevamiento de agosto 2026 (sección 7 del pliego). Los datos no relevados
# (días de actualización, longitud de contraseñas, prueba de backup) se completan con
# valores supuestos y se indican con comentarios.
CASO_GRUPO_JOTA = {
    "antivirus_estado": "sin_verificar",        # antivirus activos, estado no auditado
    "dias_actualizacion_so": 45,                # supuesto
    "dias_actualizacion_apps": 60,              # supuesto
    "contrasenas_longitud": "no_existe",        # supuesto
    "contrasenas_distintas": "mayoria_repite",  # 60 % repite contraseñas
    "mfa_correo": "no",                         # nadie tiene MFA en el correo
    "mfa_criticos": "no",                       # supuesto
    "backup_frecuencia": "semanal",             # el dueño, una vez por semana
    "backup_externo": "no",                     # sin copia externa
    "backup_probado": "nunca",                  # supuesto
    "backup_automatico": "manual",              # manual
    "firewall": "solo_router",                  # sin firewall perimetral propio
    "router_clave": "de_fabrica",               # router sin configuración adicional
    "capacitacion_phishing": "nunca",           # tras el phishing solo se compró antivirus
    "incidentes_phishing": 1,                   # intento de marzo 2026
    "plan_incidentes": "no",
}


@pytest.fixture(scope="module")
def base():
    return BaseConocimiento.desde_archivo(RUTA)


@pytest.fixture(scope="module")
def motor(base):
    return MotorInferencia(base)


def niveles(res):
    return {c: i["nivel"] for c, i in res["categorias"].items()}


def test_base_valida(base):
    assert validar_base(base.datos) == []
    assert set(base.categorias_criticas) == {"Endpoint", "Accesos", "Continuidad"}


def test_caso_grupo_jota(motor):
    res = motor.evaluar(CASO_GRUPO_JOTA)
    n = niveles(res)
    assert n["Accesos"] == "Alto"
    assert n["Continuidad"] == "Alto"
    assert n["Endpoint"] == "Medio"
    assert n["Red"] == "Medio"
    assert n["Factor humano"] == "Medio"
    assert res["general"]["nivel"] == "Alto"
    # RF-10: primero lo más severo; MFA del correo (severidad 10) encabeza
    recs = res["recomendaciones"]
    assert recs[0]["id"] == "ACC-07"
    rangos = [{"Alto": 3, "Medio": 2, "Bajo": 1}[r["nivel"]] for r in recs]
    assert rangos == sorted(rangos, reverse=True)
    # ejemplo del pliego: RF-04 → backup con copia externa
    assert any(r["rf"] == "RF-04" and "copia externa" in r["recomendacion"] for r in recs)
    # RF-08: el plan faltante es observación y no aparece entre las recomendaciones
    assert any(o["id"] == "INC-01" for o in res["observaciones"])
    assert all(r["id"] != "INC-01" for r in recs)


def test_todo_bien_es_bajo(motor):
    res = motor.evaluar(TODO_BIEN)
    assert res["general"]["nivel"] == "Bajo"
    assert all(n in ("Bajo", "Sin observaciones") for n in niveles(res).values())
    assert res["recomendaciones"] == []


def test_trazabilidad(motor):
    res = motor.evaluar(CASO_GRUPO_JOTA)
    acc = res["categorias"]["Accesos"]
    assert {"ACC-01", "ACC-04", "ACC-07", "ACC-10"} <= set(acc["reglas_disparadas"])
    assert any("ACC-07" in linea for linea in acc["explicacion"])
    for r in res["recomendaciones"]:
        assert r["id"] and r["rf"] and r["fuente"] and r["condicion"]


def test_dato_faltante_no_se_asume(motor):
    datos = dict(TODO_BIEN)
    del datos["mfa_correo"]
    res = motor.evaluar(datos)
    acc = res["categorias"]["Accesos"]
    assert acc["nivel"] == NO_DETERMINABLE
    assert acc["datos_faltantes"] == ["mfa_correo"]
    assert res["general"]["nivel"] == NO_DETERMINABLE


def test_no_se_equivale_a_faltante(motor):
    datos = dict(TODO_BIEN, antivirus_estado="no_se")
    res = motor.evaluar(datos)
    assert res["categorias"]["Endpoint"]["nivel"] == NO_DETERMINABLE
    assert "antivirus_estado" in res["categorias"]["Endpoint"]["datos_faltantes"]


def test_minimo_conocido_con_faltantes(motor):
    datos = dict(TODO_BIEN, contrasenas_distintas="algunos_repiten")
    del datos["mfa_correo"]
    res = motor.evaluar(datos)
    assert res["categorias"]["Accesos"]["nivel"] == NO_DETERMINABLE
    assert res["categorias"]["Accesos"]["nivel_minimo"] == "Medio"
    assert res["general"]["nivel_minimo"] == "Medio"


def test_alto_es_definitivo_aunque_falten_datos(motor):
    datos = dict(TODO_BIEN, backup_frecuencia="no_se_realiza")
    for k in ("backup_externo", "backup_probado", "backup_automatico"):
        datos.pop(k)
    res = motor.evaluar(datos)
    assert res["categorias"]["Continuidad"]["nivel"] == "Alto"
    assert res["categorias"]["Continuidad"]["datos_faltantes"] == []  # no aplican
    assert res["general"]["nivel"] == "Alto"

    datos = dict(TODO_BIEN, mfa_correo="no")
    del datos["contrasenas_longitud"]
    res = motor.evaluar(datos)
    assert res["categorias"]["Accesos"]["nivel"] == "Alto"
    assert res["general"]["nivel"] == "Alto"


@pytest.mark.parametrize("dias,esperado", [(30, "Bajo"), (90, "Bajo"), (91, "Medio"), (180, "Medio"), (181, "Alto")])
def test_umbral_actualizaciones_rf05(motor, dias, esperado):
    res = motor.evaluar(dict(TODO_BIEN, dias_actualizacion_so=dias))
    assert res["categorias"]["Endpoint"]["nivel"] == esperado


def test_categorias_no_criticas_no_alteran_general(motor):
    datos = dict(TODO_BIEN, firewall="solo_router", capacitacion_phishing="nunca", plan_incidentes="no")
    res = motor.evaluar(datos)
    assert res["categorias"]["Red"]["nivel"] == "Medio"
    assert res["categorias"]["Factor humano"]["nivel"] == "Medio"
    assert res["general"]["nivel"] == "Bajo"


@pytest.mark.parametrize("campo,valor,regla", [
    ("antivirus_estado", "desactualizado", "END-02"),   # RF-01
    ("contrasenas_longitud", "no_existe", "ACC-01"),     # RF-02
    ("mfa_correo", "no", "ACC-07"),                      # RF-03
    ("backup_probado", "nunca", "CON-03"),               # RF-04
])
def test_criterios_must_dan_alto(motor, campo, valor, regla):
    res = motor.evaluar(dict(TODO_BIEN, **{campo: valor}))
    assert regla in [d["id"] for d in res["disparadas"]]
    assert res["general"]["nivel"] == "Alto"


def test_logica_tres_valores():
    h = {"a": 1, "b": None}
    assert evaluar_condicion({"cualquiera": [{"hecho": "a", "op": "==", "valor": 1},
                                             {"hecho": "b", "op": "==", "valor": 1}]}, h) is True
    assert evaluar_condicion({"todos": [{"hecho": "a", "op": "==", "valor": 1},
                                        {"hecho": "b", "op": "==", "valor": 1}]}, h) is None
    assert evaluar_condicion({"todos": [{"hecho": "a", "op": "==", "valor": 2},
                                        {"hecho": "b", "op": "==", "valor": 1}]}, h) is False
    assert evaluar_condicion({"no": {"hecho": "b", "op": "==", "valor": 1}}, h) is None


def test_validacion_detecta_errores(base):
    datos = copy.deepcopy(base.datos)
    datos["version"] = "uno"
    datos["reglas"][0]["si"] = {"hecho": "inexistente", "op": "==", "valor": "x"}
    datos["reglas"][1]["entonces"] = {"nivel": "Crítico"}
    datos["reglas"][2]["si"] = {"hecho": "antivirus_estado", "op": "==", "valor": "otro"}
    errores = validar_base(datos)
    assert len(errores) == 4


def test_historial_y_comparacion(tmp_path, motor):
    hist = Historial(tmp_path / "h.db")
    r1 = motor.evaluar(CASO_GRUPO_JOTA)
    r2 = motor.evaluar(dict(CASO_GRUPO_JOTA, mfa_correo="todos", backup_externo="nube"))
    hist.guardar("Administración", "Socio", r1)
    hist.guardar("Administración", "Socio", r2)
    hist.guardar("Ventas", "", r1)
    assert hist.sectores() == ["Administración", "Ventas"]
    evs = hist.listar("Administración")
    assert len(evs) == 2 and evs[0]["version_reglas"] == "1.0.0"
    comp = comparar(evs[0]["resultado"], evs[1]["resultado"])
    resueltos = {d["id"] for d in comp["riesgos_resueltos"]}
    assert {"ACC-07", "CON-02"} <= resueltos
    assert {h for h, _, _ in comp["hechos_cambiados"]} == {"mfa_correo", "backup_externo"}
    assert json.dumps(evs[1]["resultado"])  # serializable
