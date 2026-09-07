# Luke CT sentiment feed

The MAR Desk Sentiment tab reads **`data/last_sentiment.json`**. No X API key
and no `XAI_API_KEY` are required on the paper box. xAI Grok search remains an
optional fallback only when that key exists *and* this file is missing or older
than 30 minutes.

Copy `data/last_sentiment.example.json` for the schema. Runtime file is gitignored.

## Atomic write

Never write the live path in place. A crash mid-write would give the API a
truncated JSON object and the tab would go empty.

```python
import json, os
from pathlib import Path

dest = Path("data/last_sentiment.json")
tmp = dest.with_name(dest.name + ".tmp")
dest.parent.mkdir(parents=True, exist_ok=True)
payload = json.dumps(snapshot, indent=2)
with tmp.open("w", encoding="utf-8") as fh:
    fh.write(payload)
    fh.flush()
    os.fsync(fh.fileno())
os.replace(tmp, dest)  # POSIX atomic replace on the same filesystem
```

`core.data.sentiment.persist_sentiment` is the same helper if you are in-process.

## Contract

| Field | Notes |
| --- | --- |
| `as_of` | ISO-8601. Freshness TTL is 30 minutes. |
| `source` | `luke_ct_scraper` |
| `model` | `ct-scraper` |
| `mood` | `risk_on` \| `risk_off` \| `chop` \| `greed` \| `fear` |
| `readings[].symbol` | Bybit linear, e.g. `BTCUSDT` |
| `readings[].score` | `-1` … `+1` |
| `readings[].hype_stage` | `building` \| `peaking` \| `exhausted` \| `fading` \| `absent` |
| `readings[].confidence` | `0` … `1` |

Invalid rows inside `readings` / `trending` / `influencers` are dropped; a bad
`mood` or `as_of` rejects the whole file and the desk falls back to SQLite.
