# Monitor de precios

Chequea el precio de uno o más productos en tiendas Tiendanube (por ahora, tiendadelinternas.ar) y avisa por Telegram si alguno bajó respecto de la última vez que se controló. Corre en los servidores de GitHub, no en tu compu.

## Archivos y dónde van

```
monitor-precio/
├── check_price.py
├── requirements.txt
├── price_state.json
├── README.md
└── .github/
    └── workflows/
        └── check_price.yml
```

Los primeros cuatro van sueltos en la raíz del repo. `check_price.yml` tiene que quedar exactamente dentro de `.github/workflows/` — es la única carpeta donde GitHub detecta workflows.

## 1. Cargar tus productos
Editá `check_price.py` y completá la lista `PRODUCT_URLS` con los links de los productos que querés vigilar (ya tiene uno de ejemplo cargado).

## 2. Los Secrets de Telegram
Como ya tenés el bot creado (del otro proyecto), no hace falta crear uno nuevo — pero los Secrets de un repo no se comparten con otro, así que hay que volver a cargarlos acá. En este repo: `Settings > Secrets and variables > Actions > New repository secret`:
- `TELEGRAM_BOT_TOKEN`: el mismo token de siempre.
- `TELEGRAM_CHAT_ID`: el mismo chat_id de siempre.

## 3. Probarlo (y establecer la referencia inicial)
En la pestaña **Actions**, elegí el workflow "Chequear precio" y usá **Run workflow** para dispararlo a mano. Esta primera corrida no te va a avisar nada por ningún producto — solo guarda el precio actual de cada uno como referencia. Revisá los logs para confirmar que dice "Primera corrida" para cada producto, sin errores.

## Notas
- El workflow corre una vez al día (12:00 UTC = 09:00hs Argentina). Se puede ajustar el cron en `check_price.yml` si preferís otra frecuencia.
- Los pedidos a cada producto se hacen de a uno, con una pausa variable entre cada uno — nunca todos a la vez.
- Repo público o privado: acá no hay ninguna razón de privacidad para preferir uno sobre otro (a diferencia del repo del trámite), así que la decisión pasa solo por si te interesa que el código quede visible o no.
