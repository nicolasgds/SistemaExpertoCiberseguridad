# Guía de despliegue: GitHub + Streamlit Community Cloud

Esta guía publica el sistema experto en internet con una URL del tipo
`https://nombre-que-elijas.streamlit.app`. No hace falta instalar nada en la computadora:
todo se hace desde el navegador. Tiempo estimado: 15 a 20 minutos.

**Qué se necesita**
- Esta carpeta (`sistema_experto_ciber`), descomprimida.
- Una cuenta de GitHub (gratis): https://github.com/signup
- La misma cuenta de GitHub sirve para entrar a Streamlit Community Cloud.

---

## Paso 1 — Crear el repositorio en GitHub

1. Entrá a https://github.com con tu cuenta.
2. Arriba a la derecha, botón **+** → **New repository**.
3. Completá:
   - **Repository name:** por ejemplo `sistema-experto-ciberseguridad`.
   - **Public** o **Private**: cualquiera de los dos funciona. Si es público, cualquiera puede ver el código.
   - **No** marques "Add a README file" ni agregues `.gitignore` o licencia (ya vienen en la carpeta).
4. Clic en **Create repository**.

## Paso 2 — Subir los archivos

> ⚠️ **Lo más importante de toda la guía:** los archivos tienen que quedar en la **raíz** del
> repositorio. Al abrir el repositorio en GitHub tenés que ver directamente `streamlit_app.py`,
> `app.py`, `requirements.txt`, etc. **No** tiene que aparecer una carpeta `sistema_experto_ciber`
> que los contenga. Por eso se sube el **contenido** de la carpeta, no la carpeta.

### Opción A — Desde el navegador (la más simple)
1. En la página del repositorio recién creado, hacé clic en el enlace **uploading an existing file**
   (o **Add file → Upload files**).
2. Abrí la carpeta `sistema_experto_ciber` en tu computadora y **arrastrá todo su contenido**
   (archivos y carpetas) a la página de GitHub.
3. Abajo, en "Commit changes", dejá el mensaje que aparece y hacé clic en **Commit changes**.
4. **Verificá** que en el repositorio aparezcan las carpetas **`.streamlit`** y **`static`**
   (ver el aviso de abajo).

> **Carpeta `.streamlit` oculta:** los nombres que empiezan con punto son ocultos en macOS y a veces
> en Windows, y pueden no subirse al arrastrar.
> - **Mac:** en el Finder apretá `Cmd + Shift + .` para ver los archivos ocultos antes de arrastrar.
> - **Windows:** en el Explorador, menú **Ver → Mostrar → Elementos ocultos**.
>
> Si igual no aparece en GitHub, crealo a mano: **Add file → Create new file**, escribí como nombre
> `.streamlit/config.toml` (al escribir la barra `/` GitHub crea la carpeta) y pegá este contenido:
> ```toml
> [theme]
> base = "dark"
> primaryColor = "#FEE800"
> backgroundColor = "#062448"
> secondaryBackgroundColor = "#0D3570"
> textColor = "#FFFFFF"
>
> [server]
> enableStaticServing = true
>
> [browser]
> gatherUsageStats = false
> ```
> Después, **Commit changes**.

### Opción B — Con Git, desde la terminal (si ya lo usás)
```bash
cd sistema_experto_ciber
git init
git add .
git commit -m "Sistema experto de ciberseguridad"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/sistema-experto-ciberseguridad.git
git push -u origin main
```

### Cómo tiene que quedar el repositorio
```
.streamlit/config.toml
datos/.gitkeep
reglas/reglas_v1.0.0.json
static/sello.png
tests/test_app.py
tests/test_motor.py
.gitignore
GUIA_DESPLIEGUE.md
README.md
app.py
historial.py
motor.py
preparar_sello.py
reporte.py
requirements.txt
streamlit_app.py
```

## Paso 3 — Publicar en Streamlit Community Cloud

1. Entrá a https://share.streamlit.io y elegí **Continue with GitHub**. La primera vez pide
   autorizar a Streamlit para acceder a tus repositorios: aceptá. Si el repositorio es privado,
   en ese paso tenés que darle acceso a los repositorios privados.
2. Arriba a la derecha, clic en **Create app**.
3. Cuando pregunte si ya tenés una app, elegí **Yup, I have an app**.
4. Completá:
   | Campo | Valor |
   |---|---|
   | **Repository** | `TU_USUARIO/sistema-experto-ciberseguridad` |
   | **Branch** | `main` |
   | **Main file path** | `streamlit_app.py` ← **este, no `app.py`** |
   | **App URL** (opcional) | por ejemplo `grupo-is-ciberseguridad` |
5. (Opcional) **Advanced settings → Python version:** dejá la que viene por defecto (3.12). → **Save**.
6. Clic en **Deploy**.
7. Esperá unos minutos: a la derecha se ven los registros mientras instala las dependencias.
   Cuando termina, la app se abre sola.

## Paso 4 — Verificar que todo funcione

- [ ] Fondo azul con el sello arriba en la barra lateral y como marca de agua.
- [ ] Título en amarillo y botón **Evaluar riesgo** amarillo.
- [ ] Completar el sector en la barra lateral, responder algunas preguntas y apretar **Evaluar riesgo**:
      aparece el nivel de riesgo, las recomendaciones y la explicación.
- [ ] Pestañas **Historial**, **Base de conocimiento** y **Glosario** abren sin error.

Para compartir la app, copiá la URL de la barra del navegador.

---

## Para tener en cuenta

**El historial no es permanente en la nube.** Streamlit Community Cloud no guarda los archivos que
la app crea mientras funciona: el historial de evaluaciones se borra cuando la app se reinicia, se
actualiza o "se duerme" por inactividad. Para conservar una evaluación, descargala con los botones
**Descargar informe** / **Descargar resultado (JSON)** que aparecen debajo del resultado.

**Nuevas versiones de reglas.** Lo que se carga desde la pestaña *Base de conocimiento* también es
temporal. Para que una versión nueva quede fija: descargá el JSON, editalo, y subilo a la carpeta
`reglas/` del repositorio en GitHub (**Add file → Upload files** dentro de `reglas`). La app se
actualiza sola en uno o dos minutos.

**La app se duerme.** Si nadie la usa por varios días, Streamlit la pone en pausa. Al entrar aparece
un botón para despertarla (**Yes, get this app back up!**); tarda menos de un minuto.

**Cambios en el código.** Cualquier cambio que se suba a GitHub (editando un archivo con el lápiz ✏️
o subiendo uno nuevo) se refleja automáticamente en la app.

**Cambiar el logo.** En una computadora con Python:
`pip install pillow` → `python preparar_sello.py ruta/al/logo.png` → subir el nuevo
`static/sello.png` a GitHub (reemplazando el anterior).

## Si algo falla

| Síntoma | Solución |
|---|---|
| "Error installing requirements" / `ModuleNotFoundError` | Verificá que `requirements.txt` esté en la raíz del repositorio. |
| `FileNotFoundError` con `app.py` o `reglas` | Los archivos quedaron dentro de una carpeta. Tienen que estar en la raíz (ver Paso 2). |
| La app funciona pero el fondo es blanco/gris y no se ve el sello | Falta `.streamlit/config.toml` o `static/sello.png` en el repositorio (ver el aviso del Paso 2). Después de agregarlos, en share.streamlit.io: menú **⋮** de la app → **Reboot**. |
| Pantalla "Oh no. Error running app" | Abajo a la derecha de la app: **Manage app** → mirá los registros (logs) para ver el error. |
| No aparece el repositorio al crear la app | En GitHub: **Settings → Applications → Streamlit** y dale acceso al repositorio. |
