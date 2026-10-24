# Sistema experto de riesgo de ciberseguridad para PyMEs

Implementación del pliego técnico (BRIEF) de **Grupo Jota** — v1.0, 18/09/2026.
Python + Streamlit, publicado en Streamlit Community Cloud desde GitHub.

## Estructura

```
sistema_experto_ciber/
├── streamlit_app.py        Punto de entrada (Streamlit Cloud): ejecuta app.py y le agrega la estética
├── app.py                  Interfaz Streamlit (cuestionario, resultado, historial, base de conocimiento, glosario)
├── motor.py                Motor de inferencia + carga/validación de la base de conocimiento
├── historial.py            Historial de evaluaciones en SQLite y comparación (RF-11)
├── reporte.py              Informe descargable en Markdown
├── preparar_sello.py       Utilidad para cambiar el logo (genera static/sello.png)
├── .streamlit/
│   └── config.toml         Tema azul policía / amarillo + servicio de archivos estáticos
├── static/
│   └── sello.png           Sello de Grupo I S.A. (fondo transparente)
├── reglas/
│   └── reglas_v1.0.0.json  Base de conocimiento versionada (preguntas, reglas, fuentes, glosario)
├── datos/                  Se crea historial.db al guardar la primera evaluación
├── tests/
│   ├── test_motor.py       Casos de prueba del motor (incluye el caso del relevamiento de agosto 2026)
│   └── test_app.py         Pruebas de la interfaz y del punto de entrada
├── requirements.txt        Dependencias que instala Streamlit Cloud
├── GUIA_DESPLIEGUE.md      Paso a paso para publicar en GitHub + Streamlit Community Cloud
└── README.md
```

## Cómo ejecutarlo

### En Streamlit Community Cloud (publicación)
Seguí **[GUIA_DESPLIEGUE.md](GUIA_DESPLIEGUE.md)**. El archivo principal que hay que indicar es
`streamlit_app.py`.

### En una computadora (pruebas)
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
Se abre en http://localhost:8501 (`streamlit run app.py` abre la versión sin estética).

### Correr los casos de prueba
```bash
pip install -r requirements.txt pytest
python -m pytest -q tests
```

## Arquitectura del sistema experto

| Componente | Dónde | Qué hace |
|---|---|---|
| Base de conocimiento | `reglas/*.json` | 18 preguntas, 6 categorías y 43 reglas **SI condición ENTONCES nivel**, cada una con su RF, severidad, recomendación, justificación y fuente (CIS v8 IG1, NIST CSF 2.0, ISO 27001:2022 Anexo A). |
| Memoria de trabajo | `motor.normalizar()` | Respuestas del cuestionario. «No sé» y vacíos quedan como *desconocido*: nunca se completan con un valor por defecto. |
| Motor de inferencia | `motor.MotorInferencia` | Encadenamiento hacia adelante en 4 fases: equiparación de reglas (lógica de tres valores: verdadero/falso/desconocido) → nivel por categoría → nivel general (GEN-01) → recomendaciones priorizadas. |
| Módulo de explicación | resultado `explicacion` | Para cada categoría: datos ingresados → reglas activadas → conclusión. |
| Interfaz | `app.py` | Cuestionario guiado con explicación de cada término, resultado, historial, editor de versiones y glosario. |

### Reglas de decisión clave
- **Nivel por categoría** = peor nivel entre las reglas disparadas en esa categoría.
- **Datos faltantes**: si falta un dato clave, la categoría queda *«Riesgo no determinable en [categoría]»*
  indicando qué dato falta y, si ya hay evidencia, el **nivel mínimo** detectado.
  Excepción lógica: si ya se disparó una regla en **Alto** (máximo posible), la conclusión es definitiva.
- **Nivel general (GEN-01)** = peor nivel entre categorías críticas (Endpoint, Accesos, Continuidad: requisitos Must).
  Red y Factor humano (Should) se informan sin alterarlo; Respuesta a incidentes (Could) solo genera observaciones.
- **Prioridad de recomendaciones (RF-10)**: nivel de riesgo → severidad (0–10) → categoría crítica primero.
- Preguntas condicionales: si «No se realiza» backup, las preguntas de copia externa / prueba / automatización no aplican.

## Trazabilidad con el pliego

| RF | Prioridad | Implementación |
|---|---|---|
| RF-01 Antivirus/EDR | Must | Pregunta `antivirus_estado`; reglas END-01 a END-04 (no instalado/desactualizado → Alto en Endpoint) |
| RF-02 Contraseñas | Must | `contrasenas_longitud`, `contrasenas_distintas`; ACC-01 a ACC-06 (sin longitud mínima → Alto en Accesos) |
| RF-03 MFA | Must | `mfa_correo`, `mfa_criticos`; ACC-07 a ACC-12 con recomendación de activación |
| RF-04 Backups | Must | Frecuencia + copia externa + prueba + automatización; CON-01 a CON-07 (sin backup / no probado / sin copia externa → Alto) |
| RF-05 Actualizaciones | Must | Días desde la última actualización de SO y apps; > 90 días → Medio, > 180 → Alto (END-05 a END-13) |
| RF-06 Firewall/segmentación | Should | `firewall`, `router_clave`, `wifi_invitados`; RED-01 a RED-04 (máximo Medio) |
| RF-07 Phishing | Should | Capacitación + cantidad de intentos reportados; FH-01 a FH-04 |
| RF-08 Plan de incidentes | Could | INC-01 a INC-03 → observación, no bloquea el nivel general |
| RF-09 Nivel por categoría y general | Must | Fases 2 y 3 del motor, con trazabilidad completa |
| RF-10 Priorización | Should | Fase 4 del motor; cada recomendación muestra regla, RF y fuente |
| RF-11 Historial | Should | SQLite por sector; tabla, gráfico de evolución y comparación de dos evaluaciones (riesgos resueltos/nuevos, controles que cambiaron) |
| RF-12 Versionado de reglas | Could | Las reglas viven en JSON; se publica una nueva versión desde la pestaña *Base de conocimiento* (con validación) sin tocar el código. Cada evaluación guarda la versión usada. |

## Cómo actualizar las reglas (RF-12)
1. Pestaña **Base de conocimiento** → *Descargar esta versión (JSON)*.
2. Editá preguntas o reglas y subí el número de `version` (ej. `1.1.0`).
3. Cargá el archivo en *Publicar una nueva versión de reglas*: se valida (hechos existentes, operadores,
   opciones válidas, niveles, ids únicos) antes de guardarse en `reglas/`.
4. Elegí la versión en la barra lateral.

Formato de una regla:
```json
{
  "id": "CON-02", "rf": "RF-04", "categoria": "Continuidad",
  "descripcion": "Backup sin copia externa",
  "si": {"todos": [
    {"hecho": "backup_frecuencia", "op": "!=", "valor": "no_se_realiza"},
    {"hecho": "backup_externo", "op": "==", "valor": "no"}
  ]},
  "entonces": {"nivel": "Alto"}, "severidad": 9,
  "recomendacion": "Activar backup con copia externa…",
  "explicacion": "Un ransomware… puede destruir los datos y la copia local.",
  "fuente": "CIS v8 11.3 / 11.4 (IG1) · ISO 27001 A.8.13 · NIST CSF PR.DS-11"
}
```
Operadores: `==`, `!=`, `en`, `no_en`, `>`, `>=`, `<`, `<=`; combinadores `todos` (Y), `cualquiera` (O), `no`.
Niveles: `Bajo`, `Medio`, `Alto`, `Observación`.

## Caso de prueba del relevamiento (agosto 2026)
Con los datos del pliego (antivirus sin auditar, 60 % repite contraseñas, sin MFA en el correo,
backup semanal manual sin copia externa, sin firewall propio, intento de phishing en marzo) el sistema
devuelve: **Accesos Alto, Continuidad Alto, Endpoint Medio, Red Medio, Factor humano Medio → General Alto**,
y encabeza las recomendaciones con *activar MFA en el correo corporativo* (CIS 6.3). Los datos no
relevados (días de actualización, longitud de contraseñas, prueba de backup) se completaron con valores
supuestos, marcados en `tests/test_motor.py`.

## Fuera de alcance (sección 8 del pliego)
No realiza escaneos técnicos, pentesting ni análisis de logs; no reemplaza una auditoría certificada;
no cubre infraestructura compleja. El resultado depende de las respuestas autorreportadas.
