# Historical preflight attempts

preflight_v1 stopped before historical trade simulation: runtime context validation
requires all five BTC OHLCV columns, but the first adapter supplied only close.
The full trace and exact runner are preserved in preflight_v1.log and
preflight_v1/run_attempt.py. No 2026 features or outcomes were computed.

preflight_v2 supplies complete BTC OHLCV to the unchanged runtime adapter. No signal,
exit, cost, admission or analysis rule was changed. This successful historical
preflight must precede the new 2026 scoring freeze. See its VERIFICATION.json.
