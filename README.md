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

## Simulation timing and balance

Market prices update every 15 seconds, even when nobody has the page open. Yahoo news is checked for every configured stock about once per minute. Unused headlines are queued and released one at a time every five seconds across the whole market. Headline history is saved, so the same headline cannot reappear after restarting, on another stock, or with a different date. Previously stored news reports are included in this history when upgrading. If Yahoo runs out of unused articles, the feed waits for more. The initial headlines for each stock are background information and do not change its goal. After that, genuinely new headlines are sent to Gemma when released.

Gemma first checks whether an article is directly relevant to the stock and whether the same event has already been covered. Repeated and unrelated stories do not change the goal. For new relevant stories, Gemma picks good, bad, really good or bad, extremely good or bad, or neutral; the code chooses the percentage from the configured range.

Accumulated news goals are limited to 15% above or below the stock's reference price. News pressure fades gradually, and random short-term movement can move the actual price in either direction. Existing saved goals above this range are brought into range at the first market update after upgrading. Cash and holdings remain saved. This is a simulation, not a forecast.

On the home page, Start New Simulation asks before clearing this browser player's saved cash, holdings, watchlist, and settings. Continue Current Session loads them. Market prices are shared and continue running.

## Market event pop-ups

The Trump event starts automatically after a random five-to-ten-minute wait, including with debug disabled. Each event ends automatically after 50 seconds, then another random wait begins. With `DEBUG=true`, **TRIGGER EVENT** and **END EVENT** also control it manually. Everyone viewing the market receives compact, dismissible pop-ups saying **TRUMP HAS WAKEN UP!!!!** and **Trump went sleep.** Closing a pop-up lets you keep trading while the event continues.

During the event, news fetching, headline releases, and AI goal changes pause, and regular price movement stops. Every second, each stock rolls a new goal relative to its current price: 75% unchanged, 24% up or down by 3–7%, and 1% up or down by 20–40%. If every goal would stay unchanged, one randomly chosen stock gets a 5% goal change instead. Prices move a quarter of the distance toward these goals each second; the percentages describe goals, not instant price jumps. Prices stay between $0.01 and $1,000,000.

The automatic timeout or **END EVENT** restores the previous goals, resumes news processing, and returns to 15-second updates. Queued news waits until the event ends. Restarting the app also ends the event, retaining the latest prices and restoring normal goals.
