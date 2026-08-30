# Security remediation

## ACTION REQUIRED: rotate these credentials now

The predecessor project (`../mar_trading_bot`) has API credentials hardcoded in
source files. That directory has **no `.gitignore`**, and a git repository was
detected at `C:/Users/PC` (the parent), so these values may have been committed
into your home-directory repo history.

**Treat all of the following as compromised and rotate them.**

| Credential | Exposed in | How to rotate |
|---|---|---|
| Bybit API key + secret (live, `testnet=False`) | `new_multi_indicator.py` ~L3313, `check_active_positions.py` L21-22, `new_multi_indicator_backup_20251026_010306.py`, `app/api/positions/route.ts` L38-39 | Bybit → API Management → delete the key → create a new one |
| DeepSeek API key | `config/agent.ts` L5, `modules/agent/deepseek.ts` L4 | DeepSeek platform → API keys → revoke → reissue |
| Gemini API key (fallback literal) | `modules/agent/gemini.ts` L11 | Google AI Studio → API keys → delete → create |

### Bybit rotation checklist

1. Log in to Bybit → **API Management**.
2. **Delete** the existing key (do not just edit it — assume the secret leaked).
3. Create a **testnet** key first. Put it in `.env` as `BYBIT_TESTNET_API_KEY` /
   `BYBIT_TESTNET_API_SECRET`.
4. Do **not** create a live key yet. Leave `BYBIT_LIVE_*` blank until the
   go-live gates in the plan pass.
5. When you eventually create the live key, restrict it:
   - Permissions: **Contract trading only**. No withdrawal, ever.
   - **IP allowlist** it to the machine that runs the firm.
6. Verify no key material is in this repo: `git grep -nEi "api_?key\s*=\s*[\"'][A-Za-z0-9]{16,}"`

## How this repo prevents a repeat

- **No literals.** All credentials load through `config/settings.py` only. No
  module reads `os.environ` for a secret, and no key appears in source.
- **Separate key pairs.** `BYBIT_TESTNET_*` and `BYBIT_LIVE_*` are distinct
  fields. A mode misconfiguration cannot silently point testnet logic at real
  money, because the live credentials are not even loaded outside live mode.
- **Two-key ignition.** Reaching `TRADING_MODE=live` additionally requires
  `GO_LIVE_CONFIRMED=I_ACCEPT_THE_RISK`. Without it, `Settings` raises at
  startup rather than trading.
- **Default is safe.** With no `.env` at all, the firm runs in `paper` mode,
  which submits no orders and needs no credentials.
- **`.gitignore` from commit one**, covering `.env`, `*.key`, `*.pem`, and
  service-account JSON patterns.
- **API auth.** State-changing endpoints (kill switch, proposal approval) require
  the `API_TOKEN` bearer secret.

## Reporting

This is a single-operator system with no external users. If you find an exposure,
rotate first, then fix the source.
