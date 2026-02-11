import os
import json
import hashlib
import random
from datetime import datetime, timedelta
import googlemaps
from dotenv import load_dotenv

load_dotenv()

USE_GOOGLE = os.getenv("USE_GOOGLE_MAPS", "false").lower() == "true"
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

CACHE_DIR = "cache_matrices"
os.makedirs(CACHE_DIR, exist_ok=True)


# ======================================================
# 🚦 FUNCIÓN PRINCIPAL
# ======================================================

def get_time_matrix(addresses):

    if not USE_GOOGLE:
        print("🟢 MODO MOCK")
        return fake_time_matrix(len(addresses))

    print("🔴 Google Maps REAL (con cache)")

    cache_file = get_cache_filename(addresses)

    # 🔹 1️⃣ Si existe cache → usarlo
    if os.path.exists(cache_file):
        print("📦 Usando matriz desde CACHE")
        with open(cache_file, "r") as f:
            data = json.load(f)
            return data["matrix"]

    # 🔹 2️⃣ Si no existe → consultar Google
    try:
        matrix = real_google_time_matrix(addresses)

        # Guardar cache
        with open(cache_file, "w") as f:
            json.dump({
                "addresses": addresses,
                "matrix": matrix
            }, f)

        print("💾 Matriz guardada en CACHE")
        return matrix

    except Exception as e:
        print("⚠️ Error Google:", e)

        # 🔹 3️⃣ Si falla Google pero existe cache viejo → usarlo
        if os.path.exists(cache_file):
            print("📦 Usando cache anterior por seguridad")
            with open(cache_file, "r") as f:
                data = json.load(f)
                return data["matrix"]

        raise e


# ======================================================
# 🟢 MATRIZ MOCK
# ======================================================

def fake_time_matrix(n):
    return [
        [
            0 if i == j else random.randint(600, 3600)
            for j in range(n)
        ]
        for i in range(n)
    ]


# ======================================================
# 🔴 MATRIZ REAL GOOGLE (con bloques 10x10)
# ======================================================

def real_google_time_matrix(addresses):

    gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

    n = len(addresses)
    matrix = [[0]*n for _ in range(n)]

    block_size = 10  # evita MAX_ELEMENTS_EXCEEDED

    for i in range(0, n, block_size):
        for j in range(0, n, block_size):

            origins = addresses[i:i+block_size]
            destinations = addresses[j:j+block_size]

            print(f"Consultando bloque: {len(origins)}x{len(destinations)}")

            response = gmaps.distance_matrix(
                origins=origins,
                destinations=destinations,
                mode="driving",
                departure_time=datetime.now().replace(
                    hour=6, minute=0, second=0, microsecond=0
                ) + timedelta(days=1),
                traffic_model="best_guess"
            )

            for oi, row in enumerate(response["rows"]):
                for di, element in enumerate(row["elements"]):
                    matrix[i+oi][j+di] = element["duration"]["value"]

    return matrix


# ======================================================
# 🔐 GENERADOR DE HASH PARA CACHE
# ======================================================

def get_cache_filename(addresses):
    joined = "|".join(sorted(addresses))
    hash_name = hashlib.md5(joined.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{hash_name}.json")
