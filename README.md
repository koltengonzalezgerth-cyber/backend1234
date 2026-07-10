# Pulse Backend

Ingests free/low-cost news + social sources, scores sentiment, and serves
the results over a REST API for the Pulse mobile app to consume.

## What's here
```
app/
  config.py           settings, tracked symbols, source lists
  database.py          SQLAlchemy engine/session
  models.py             Asset / Mention / SentimentSnapshot tables
  schemas.py            API response shapes
  sentiment.py           VADER-based scoring (+ finance lexicon boost)
  scheduler.py            runs ingestion every N minutes
  main.py                  FastAPI app — this is what the mobile app calls
  ingestion/
    rss_sources.py          free RSS feeds
    reddit_source.py          Reddit API (optional — see note below)
    newsapi_source.py          NewsAPI.org (needs free dev key)
    stocktwits_source.py        StockTwits public stream (no key needed)
    run_ingest.py                orchestrates all sources -> DB
```

## Deploying for free — Render

Render is currently the most genuinely free option for this kind of backend
(a real permanent free tier, no credit card required — Railway removed its
free tier in 2023, and Fly.io now only offers a 2-hour trial). The
trade-off: free web services spin down after 15 minutes of inactivity and
take 30–60 seconds to wake on the next request — fine for a prototype,
worth upgrading to a paid Starter instance (~$7/mo) once you have real users
who shouldn't see that delay.

Steps:
1. Push this `pulse-backend` folder to a GitHub repo.
2. Go to render.com → New → Blueprint → connect that repo. Render will read
   `render.yaml` in this folder and set up both the web service and a free
   Postgres database automatically.
3. Render will prompt you for the values marked `sync: false` in
   `render.yaml` (Reddit + NewsAPI credentials) — paste them in.
4. Once deployed, Render gives you a URL like
   `https://pulse-api-xxxx.onrender.com` — that's what you paste into the
   Pulse app's "Connect backend" panel.
5. Confirm it's alive: visit `https://your-url.onrender.com/health`.


```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / NEWSAPI_KEY in .env
# (RSS works with no keys at all — you'll get partial data without the others)

# run one ingestion cycle manually to sanity-check it works
python -m app.ingestion.run_ingest

# start the API (also starts the background scheduler)
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` for interactive API docs, or:
- `GET /mood` — overall market mood
- `GET /assets` — all tracked assets with latest score + history
- `GET /assets/AAPL` — one asset's detail, including recent mentions

## Keeping it awake for free (so ingestion actually runs on schedule)
Render's free web services spin down after 15 minutes with no incoming
requests — and the ingestion scheduler lives *inside* that same process, so
if it's asleep, ingestion doesn't run either. Fix this for free with an
uptime pinger that hits `/health` every 10 minutes, keeping the service
awake around the clock at no cost:

1. Sign up free at **uptimerobot.com** or **cron-job.org** (either works, no card needed)
2. Add a new monitor: URL = `https://your-app.onrender.com/health`, interval = 10 minutes
3. That's it — the ping keeps Render from spinning the service down, so the
   15-minute ingestion schedule fires reliably.

## Why 15 minutes is the shortest free refresh interval
Refresh cadence is bounded by NewsAPI's free 100 requests/day quota, since
that's the tightest limit among the sources (RSS and StockTwits have no
practical caps at this scale; Reddit is optional and off by default). The
backend now issues **one combined NewsAPI request per cycle** covering all
tracked assets (instead of one per symbol), so the math is:

```
requests/day = 24 * 60 / INGEST_INTERVAL_MINUTES
```

At 15 minutes: 96 requests/day — safely under the 100/day cap. At 10
minutes you'd hit 144/day and run out partway through the day. If you drop
NewsAPI entirely (RSS + StockTwits only, which is a perfectly good
combination), you can safely go as low as 5 minutes or even less — edit
`INGEST_INTERVAL_MINUTES` and remove the NewsAPI key
from `.env` to do that trade-off.

Note this is the *ingestion* interval (how often new data is fetched from
the internet) — the mobile/demo app can poll the backend's own `/assets`
and `/mood` endpoints as often as you like (e.g. every 30-60s) with zero
extra external API cost, since those just read your own database.

## Getting free API credentials

- **StockTwits**: no signup needed — it's a public, keyless endpoint,
  already wired up in `app/ingestion/stocktwits_source.py`. Bonus: many
  StockTwits messages carry an explicit user-tagged "Bullish"/"Bearish"
  label, which the scorer uses directly instead of guessing from text.
- **Finnhub** (live stock prices): free key at https://finnhub.io, no
  card required, 60 calls/min. Powers real price + day-change for stocks.
- **CoinGecko** (live crypto prices): no signup needed — public endpoint,
  already wired up in `app/ingestion/price_source.py`.
- **Reddit**: as of 2026, Reddit gates real API data access behind an
  explicit request/approval process rather than instant self-serve app
  creation — expect friction here. It's optional: leave
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` blank and the backend runs
  fine without it (RSS + NewsAPI + StockTwits still cover both stocks and
  crypto).
- **NewsAPI**: https://newsapi.org/register → free dev key (100 req/day, ~1 month lookback)
- **RSS**: no signup needed, already wired up in `config.py`

## Running with Docker (includes Postgres)
```bash
cp .env.example .env   # fill in keys
docker compose up --build
```

## Connecting the app (already wired up)
The `pulse-demo.jsx` app now polls this backend automatically once you
tell it where it's deployed:

1. Deploy this backend somewhere reachable (Render, Railway, Fly.io, a VPS, etc.)
2. Open the app, tap the status pill top-right ("DEMO"), and enter your
   backend's URL (e.g. `https://api.yourapp.com`) — no trailing slash needed
3. The app polls `/mood` and `/assets` every 60 seconds and switches its
   status pill to "LIVE"; opening an asset's detail sheet also pulls its
   live recent mentions from `/assets/{symbol}`
4. If the backend becomes unreachable, the app automatically shows
   "OFFLINE" and keeps working with the last known data

CORS is already open (`allow_origins=["*"]`) in `app/main.py` for this —
lock it down to your actual app's domain before a public launch.

Note: the backend supplies sentiment score, history, and mention counts —
it does supply live market price/day-change now via Finnhub (stocks) and
CoinGecko (crypto) — see the licensing caveat on Finnhub below before a
real public launch.

## Known limitations of this v1
- Sentiment scoring uses VADER, a general-purpose lexicon model — decent
  but not as accurate as a finance-tuned model like FinBERT. Swap it in
  `app/sentiment.py` when you need better accuracy.
- Asset-matching in RSS/Reddit is substring-based and will have false
  positives (e.g. "Amazon" the river). Fine for a v1, worth upgrading to
  proper entity recognition later.
- **Licensing status of free-tier data sources — check before a real
  public launch with paying users, not just before launch in general:**
  - NewsAPI's free tier is not licensed for production commercial apps at
    scale — read their terms and budget for their paid plan.
  - Finnhub's own FAQ frames its free tier as "test before purchasing"
    and directs commercial users to sales@finnhub.io for a license — email
    them directly to confirm before shipping a paid product on it.
  - CoinGecko and StockTwits' public endpoints didn't have an obvious
    commercial restriction in what's publicly documented, but neither was
    exhaustively verified — worth a final terms check of your own before
    launch, the same way you'd check any third-party data dependency.
- Single-process scheduler — move ingestion to its own worker/cron job
  once you have real traffic on the API.
