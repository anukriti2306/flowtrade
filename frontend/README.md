# flowtrade frontend

React + Vite + Tailwind UI for triggering and viewing flowtrade backtests.

## Setup

```bash
npm install
npm run dev
```

Opens at http://localhost:5173

## Requirements

The FastAPI backend must be running separately on http://127.0.0.1:8000:

```bash
# from the main flowtrade repo
uvicorn api.main:app --reload
```

CORS must be enabled on the backend for localhost:5173 - see the main
flowtrade README for the required api/main.py change.

## What's here

- Backtest tab: submit a symbol + date range, polls for results, renders
  metrics and an equity curve chart once the run completes
- Live tab: placeholder explaining the two-terminal live mode workflow
  (simulate_live_feed.py + day6_live_mode.py) - not yet wired to a
  WebSocket endpoint
