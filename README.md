Aik Raudkats, Ivan Rozhanskiy, Kalju Yuan Pechter 12IT

Probleem: Noored ei huvitu investeerimismaailmast ning ei loe uudiseid.

Eeldatavad rollid:
Ivan - Tegeleb AI implementeerimisega, et tehisaru oskaks uudiseid lugeda ning saadud info põhjal tõsta või langetada aktisa hindu.
Aik - Tegeleb uudiste edastamisega programmile, et AI saaks neid lugeda.
Kalju - Tegeleb veebiliidesega.

Trello - https://trello.com/b/gRVTk453/stockgame
Figma - https://www.figma.com/design/0MRcNLdxJG45hOvvR3PZmS/Untitled?node-id=0-1&p=f&t=LYOMorXn7g8v1MfN-0

Stocks - Microsoft, Micron, Tesla, McDonalds, SpaceX, AstraZeneca, Pfiser, Sellas Life Science, Coca Cola, Rolls Royce, Apple, Volkswagen, Google, Nvidia, TSM, ASML, Lockheed Martin, Shell, Equinor, PayPal, Robinhood, Asus, COOP, Telia, Noctua, Caterpillar

<img width="1205" height="688" alt="Kuvatõmmis 2026-09-17 092231" src="https://github.com/user-attachments/assets/0f46ca51-1bdb-4954-83df-da0b0a08c5bd" />
<img width="1206" height="683" alt="Kuvatõmmis 2026-09-17 092248" src="https://github.com/user-attachments/assets/75e6db7b-8d8b-4549-ac17-fc65dbc61f86" />

## Running locally

The server uses Python's built-in SQLite support. User sessions and saves are stored in
`src/stockgame.db` by default.

1. Install the Python packages with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and replace `STOCKGAME_STORAGE_SECRET` with a
   long random value. This keeps browser sessions valid across server restarts.
3. Run `python src/client/main.py` and open `http://127.0.0.1:8080`.
