import os
import urllib.parse
from datetime import datetime

from auth import get_current_user
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from google_maps import get_time_matrix
from optimizer import optimize_routes
from storage import guardar_rutas_excel


# =========================
# ⏱️ CONFIGURACIÓN TIEMPOS
# =========================

BUFFER_REALISTA = 1.40        # 🔥 50% buffer
MAX_PARADAS_POR_MAPA = 10


def hora_str_a_segundos(hora_str: str) -> int:
    """Convierte '08:30' a segundos"""
    h, m = map(int, hora_str.split(":"))
    return h * 3600 + m * 60


def segundos_a_hora(segundos: int) -> str:
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    return f"{int(horas):02d}:{int(minutos):02d}"


# =========================
# 🚀 APP
# =========================

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.state.GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def form(request: Request, user: str = Depends(get_current_user)):
    return templates.TemplateResponse(
        "form.html",
        {"request": request, "user": user}
    )


# =========================
# 🚚 OPTIMIZAR
# =========================

@app.post("/optimize", response_class=HTMLResponse)
def optimize(
    request: Request,
    user: str = Depends(get_current_user),

    acopio: str = Form(...),
    vehiculos: int = Form(...),
    hora_salida: str = Form(...),

    direccion: list[str] = Form(...),
    hora_inicio: list[str] = Form(...),
    hora_fin: list[str] = Form(...),
    espera: list[int] = Form(...),
):

    # =========================
    # 🔹 PREPARAR DATOS
    # =========================

    HORA_INICIO = hora_str_a_segundos(hora_salida)

    addresses = [acopio] + direccion

    service_times = [0] + [e * 60 for e in espera]

    # Ventanas horarias personalizadas
    time_windows = [(0, 24 * 60 * 60)]  # acopio libre

    for hi, hf in zip(hora_inicio, hora_fin):
        inicio = hora_str_a_segundos(hi)
        fin = hora_str_a_segundos(hf)
        time_windows.append((inicio, fin))

    # =========================
    # 🗺️ MATRIZ DE TIEMPOS
    # =========================

    time_matrix = get_time_matrix(addresses)

    # =========================
    # 🔥 OPTIMIZAR
    # =========================

    resultado = optimize_routes(
        time_matrix,
        time_windows,
        service_times,
        vehiculos,
        HORA_INICIO
    )

    if resultado is None:
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": "No fue posible generar una ruta válida."
            }
        )

    rutas = []
    no_visitadas = []
    sugerencias = []

    # =========================
    # 🚚 CONSTRUIR RUTAS
    # =========================

    for v_id, ruta in enumerate(resultado["routes"], start=1):

        if len(ruta) <= 2:
            continue

        tiempo_actual = HORA_INICIO
        paradas = []

        for paso in ruta:

            idx = paso["node"]
            llegada = paso["arrival"]
            espera_seg = paso["service"]
            salida = llegada + espera_seg

            paradas.append({
                "direccion": addresses[idx],
                "llegada": segundos_a_hora(llegada),
                "espera": espera_seg // 60,
                "salida": segundos_a_hora(salida)
            })

        # =========================
        # 🔗 GENERAR TRAMOS MAPS
        # =========================

        mapas = []
        inicio = 0

        while inicio < len(paradas) - 1:
            fin = min(inicio + MAX_PARADAS_POR_MAPA, len(paradas))
            tramo = paradas[inicio:fin]

            encoded = [
                urllib.parse.quote(p["direccion"])
                for p in tramo
            ]

            mapas.append({
                "tramo": len(mapas) + 1,
                "desde": tramo[0]["direccion"],
                "hasta": tramo[-1]["direccion"],
                "url": "https://www.google.com/maps/dir/" + "/".join(encoded)
            })

            inicio = fin - 1

        rutas.append({
            "vehiculo": v_id,
            "paradas": paradas,
            "mapas": mapas
        })

    # =========================
    # 🔴 PARADAS NO ATENDIDAS
    # =========================

    for idx in resultado["unserved"]:
        if idx == 0:
            continue

        parada = {
            "direccion": addresses[idx]
        }

        no_visitadas.append(parada)

        sugerencias.append({
            "direccion": addresses[idx],
            "sugerencias": [
                "Ampliar ventana horaria",
                "Reducir tiempo de espera",
                "Asignar vehículo adicional"
            ]
        })

    guardar_rutas_excel(rutas, user)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "rutas": rutas,
            "no_visitadas": no_visitadas,
            "sugerencias": sugerencias
        }
    )


# =========================
# 📥 DESCARGAR HISTORIAL
# =========================

@app.get("/download/excel")
def download_excel(user: str = Depends(get_current_user)):

    file_path = "historial_rutas.xlsx"

    if not os.path.exists(file_path):
        return {"error": "No hay historial disponible"}

    return FileResponse(
        path=file_path,
        filename="historial_rutas.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
