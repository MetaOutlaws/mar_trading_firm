# Novelty and source audit

Verified the latest cumulative checkpoint's999 payload hashes and all six raw
minute/funding inputs. Available approved-rule protocols/FINDINGS explicitly defer
sampled exits. Earlier profit protection, entry delay and bracket-origin tests
retain intrabar stops/targets. No identical sampled-exit study appears in saved
history; absence of uncommitted external Grok runs cannot be certified.

Pinned runtime reviewed:core/execution/paper.py peek_exit_triggers,check_stops,
close_at_fill;core/execution/engine.py _manage_open_positions,_settle_paper_exit;
scripts/run_paper_trading.py waiting loop. Sampled paper stops also omit second
exit slippage, extending the earlier notes that singled out the OHLC contract.
Retain extra stop-exit slippage in every research arm here; document this explicit
remaining difference and audit it separately. No claim of full runtime parity.

Latest completed experiment:H-ENTRY-LATENCY-01. This experiment restores immediate
entries and changes only exit sampling. No combined delay/poll grid, new indicator
or production patch. Runtime source hashes are pinned before outcomes.
