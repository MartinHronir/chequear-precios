"""
Chequea el precio de varios productos en tiendadelinternas.ar (Tiendanube)
y avisa por Telegram si alguno bajó respecto de la última vez que se
controló.

Los pedidos se hacen de a uno, en orden (nunca en simultáneo), reusando
la misma conexión (requests.Session) y con una pausa entre cada uno, para
comportarse como un chequeo esporádico y no como una ráfaga de tráfico.
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
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
        previous_price = state.get(url, {}).get("price")

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

        state[url] = {
            "price": current_price,
            "last_checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    save_state(state)

    if not any_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
