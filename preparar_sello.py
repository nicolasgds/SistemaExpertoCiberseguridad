"""
Prepara el sello para la app: quita el fondo negro, lo achica y lo guarda en static/sello.png.

Solo hace falta si se cambia el logo. Uso:
    python preparar_sello.py ruta/a/la/imagen.png
Después hay que subir el nuevo static/sello.png a GitHub.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parent / "static" / "sello.png"


def preparar(origen: Path) -> None:
    img = Image.open(origen).convert("RGBA")
    img.thumbnail((420, 420))
    w, h = img.size
    for esquina in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        r, g, b, a = img.getpixel(esquina)
        if a > 0 and r + g + b < 90:  # fondo negro (o casi) -> transparente
            ImageDraw.floodfill(img, esquina, (0, 0, 0, 0), thresh=60)
    DESTINO.parent.mkdir(exist_ok=True)
    img.save(DESTINO, optimize=True)
    print(f"Sello guardado en {DESTINO} ({DESTINO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python preparar_sello.py ruta/a/la/imagen.png")
    preparar(Path(sys.argv[1]))
