"""
Chequea el precio de varios productos en tiendadelinternas.ar (Tiendanube)
y avisa por Telegram si alguno bajó respecto del último precio registrado.

Además del precio actual, guarda un historial con fecha por producto en
price_state.json (para poder calcular variaciones y alimentar el
dashboard más adelante). Si encuentra el formato anterior del archivo
(solo "price" + "last_checked", sin historial), lo migra solo la
primera vez que corre.

Los pedidos se hacen de a uno, en orden (nunca en simultáneo), reusando
la misma conexión (requests.Session) y con una pausa entre cada uno, para
comportarse como un chequeo esporádico y no como una ráfaga de tráfico.
"""

import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Configuración ────────────────────────────────────────────────────────
# Agregá acá cada producto que quieras vigilar.
PRODUCT_URLS = [
    "https://tiendadelinternas.ar/productos/acebeam-pokelit-aa/",
    "https://tiendadelinternas.ar/productos/wuben-e7/",
    "https://tiendadelinternas.ar/productos/wuben-g5/",
]

PRICE_META_PROPERTY = "tiendanube:price"
NAME_META_PROPERTY = "og:title"

# Pausa (en segundos) entre pedido y pedido, con algo de variación para
# no ser un intervalo perfectamente regular.
DELAY_RANGE_SECONDS = (2, 5)

# Cuántos días de historial conservar por producto, para que el JSON no
# crezca sin límite.
MAX_HISTORY_DAYS = 90
# ─────────────────────────────────────────────────────────────────────────

STATE_FILE = Path(__file__).parent / "price_state.json"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_page(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def get_price_and_name(html: str, url: str):
    soup = BeautifulSoup(html, "html.parser")

    price_tag = soup.find("meta", attrs={"property": PRICE_META_PROPERTY})
    if price_tag is None or not price_tag.get("content"):
        raise ValueError("No se encontró la meta-etiqueta del precio")
    price = float(price_tag["content"])

    name_tag = soup.find("meta", attrs={"property": NAME_META_PROPERTY})
    name = name_tag["content"] if name_tag and name_tag.get("content") else url

    return price, name


def format_ars(amount: float) -> str:
    return f"${amount:,.2f}".translate(str.maketrans(",.", ".,"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def record_price(state: dict, url: str, name: str, price: float, today: date = None):
    """
    Agrega el precio de hoy al historial del producto (una entrada por día)
    y devuelve el precio previo, o None si es la primera vez que se ve
    este producto.

    Si el producto viene del formato anterior (solo "price" +
    "last_checked", sin "history"), lo migra a un historial de una
    entrada antes de seguir.
    """
    today = today or date.today()
    today_str = today.isoformat()

    product = state.setdefault(url, {})
    if "history" not in product:
        history = []
        if "price" in product:
            last_checked = product.get("last_checked")
            entry_date = (
                datetime.fromisoformat(last_checked).date().isoformat()
                if last_checked
                else today_str
            )
            history = [{"date": entry_date, "price": product["price"]}]
        product = {"name": name, "history": history}
        state[url] = product

    product["name"] = name  # por si cambió el nombre en la tienda
    history = product["history"]

    previous_price = history[-1]["price"] if history else None

    if history and history[-1]["date"] == today_str:
        # Corrida repetida el mismo día: actualiza en vez de duplicar
        history[-1]["price"] = price
    else:
        history.append({"date": today_str, "price": price})

    cutoff = (today - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    product["history"] = [h for h in history if h["date"] >= cutoff]
    product["last_checked"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return previous_price


def notify_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID; no se pudo avisar.")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        api_url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=20
    )
    resp.raise_for_status()


def main() -> None:
    state = load_state()
    any_success = False

    session = requests.Session()
    session.headers.update(HEADERS)

    for i, url in enumerate(PRODUCT_URLS):
        if i > 0:
            # Pausa entre pedido y pedido: nunca se descargan todos a la
            # vez, uno por uno con este espacio variable en el medio.
            time.sleep(random.uniform(*DELAY_RANGE_SECONDS))

        try:
            html = fetch_page(session, url)
            current_price, name = get_price_and_name(html, url)
        except (requests.RequestException, ValueError) as exc:
            print(f"Error al chequear {url}: {exc}", file=sys.stderr)
            continue

        any_success = True
        previous_price = record_price(state, url, name, current_price)

        if previous_price is None:
            print(f"Primera corrida de '{name}': referencia {format_ars(current_price)}")
        elif current_price < previous_price:
            notify_telegram(
                f"¡{name} bajó de precio! {format_ars(previous_price)} → "
                f"{format_ars(current_price)}\n{url}"
            )
            print(f"Baja detectada en '{name}': {previous_price} -> {current_price}")
        else:
            print(f"Sin baja en '{name}'. Precio actual: {format_ars(current_price)}")

    save_state(state)

    if not any_success:
        sys.exit(1)


if __name__ == "__main__":
    main()