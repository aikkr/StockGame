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

## Setup
```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you do not already have one. The app creates a random `STOCKGAME_STORAGE_SECRET` in `.env` on first start if it is missing. Keep this value unchanged so browser sessions survive restarts.

### 1. Install Ollama
Download and install Ollama from the official website:

**https://ollama.com/download**


### 2. Download Gemma 4 E2B
Open your terminal (PowerShell on Windows) and run:

```bash
ollama pull gemma4:e2b
```

Keep Ollama running while playing. The default model is `gemma4:e2b`, the effective 2B variant of Gemma 4. The download is several GB. You can choose another installed model with `OLLAMA_MODEL` in `.env`.

## Start

```bash
python src/client/main.py
```

Open http://127.0.0.1:8080.

Set `DEBUG=true` in `.env` to enable manual price goals and event controls; `DEBUG=false` (the default) hides them and disables their API actions. Restart the app after changing this setting.
