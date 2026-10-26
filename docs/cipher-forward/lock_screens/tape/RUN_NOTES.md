# PR #174 LOCK screens, box run (SEEN, planning/disqualifier only)
Repo: MetaOutlaws/mar_trading_firm @ 59acdde1be6510fbcf63d8ae3e5aed0858de1107 (detached, /workspace/pr174_lockrun/repo, unmodified)
Tape: /workspace/pr174_lockrun/tape built by /workspace/pr174_lockrun/tools/build_tape.py from audited_cache/*_1m.parquet only (audit.json never opened).
Attempt 1 (system python): all three scripts failed at import (ModuleNotFoundError: httpx) -> attempt1_import_error/.
Attempt 2 (venv with requirements.txt, network-isolated via `unshare -rn`): clone_screen 772.8s, planning 834.6s, regime_weeks 7.5s, all exit 0.
