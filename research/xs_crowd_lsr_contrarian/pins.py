"""Frozen identities for xs_crowd_lsr_contrarian v2.

Document digests are the sha256 of the bytes shipped in this package,
except proposal 54ada927, whose bytes are not in the checkout. That pin
is the hash Munha and Garwe named. The run refuses if a shipped file's
digest does not match the constant beside it.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent

CELL = "xs_crowd_lsr_contrarian"

# Sha256 of the files in this package. COUNTERSIGN.md is hashed at run
# time from those bytes; the constant is the check, not a substitute.
PREREG_SHA256 = "8000c73384cbfb86b51e6f90d54febddb3f7bdc222ffc16764efb000ba042173"
COUNTERSIGN_SHA256 = "8c3bd709ee4a8a46d300fe4b6e254faab07d462c7f492249244e0790c936740a"
# Addendum d0cc64c8. Item 5 of the harness readings: 2026 is veto-only.
COUNTERSIGN_ADDENDUM_SHA256 = "d0cc64c84221ba9212b76fdc9361f74773d11b8415f8e92aca66dba7a321cea9"
LOCK_SHA256 = "f50257a1ca974ff6f2e3e9ee75e9a081e900d4c5e85060b2c4e8afbc81034515"
RULES_SHA256 = "5e1fac2c493ae45ab1fbd143896eb2f64291fd5ea13a97880d40e87c5c01b4e5"
SIZING_SHA256 = "5f6e436f83c66b08dff254a9ac091dfb8c15a2d19ec83889f27cb91f30888e0a"
PROPOSAL_LOCKED_SHA256 = "4c25ddedaea4fd9821a7e134e00a0d71e34ef8c2f5242203df4e9e467a85c153"
# Status-line fix only. Bytes are not in this checkout; the manifest pins the hash.
PROPOSAL_STATUS_FIX_SHA256 = "54ada92780b1c89ac84ed36032dcddc743f179dc9b25534af55e1cd28a73a795"
REGIME_LOSS_DEF_SHA256 = "c90d9e3ca3af4ad13e4d836cc56b10364bc8fc781e021da0bd569349a33b0d3b"

# Pre-run SUMS pins. Each is the sha256 of that tape's SHA256SUMS file.
LS_SUMS_SHA256 = "2787b82f6cbc903a4c1a4e727351256eb5c7bec3b6ff0dc0abc28a1d98e0c884"
TAPE_C_SUMS_SHA256 = "ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9"
N_TAPE_SUMS_SHA256 = "9c9916e2ec3e58a22a7b45f88ec957c12ffae9943fde48feda78bc6eb8b40f3c"
OI_SUMS_SHA256 = "63d4518c87a9fc45d4e4dc75fc926f3bd15f6d4b762e32844b0493145e47f596"

# Sizing is frozen. There is no knob.
GROSS = 1.18
LEG = 0.59
MIN_NAMES_PER_LEG = 10
STOP_PCT = 0.12
HOLD_DAYS = 7
MIN_HISTORY_DAYS = 31
MIN_CLOSED_RATIOS = 5
RATIO_WINDOW_DAYS = 7

# Binding cost. The proxy column is report-only.
OFFICIAL_LEG_COST = 0.0031
BTC_SAMPLER_RT = 0.00135
SOL_SAMPLER_RT = 0.00181
PROXY_LEG_COST = (BTC_SAMPLER_RT + SOL_SAMPLER_RT) / 2.0
PROXY_COST_LABEL = "proxy, likely optimistic for alts"

# Random book and the week-cluster bootstrap. Both seeds are the prereg's.
RANDOM_SEED = 20261016
N_RANDOM_DRAWS = 1000
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20261016
BEATS_RANDOM_ALPHA = 0.05

# Desk gates. assert_house_gates checks these against research.validate
# before a scored run, so a second copy cannot drift and a house edit
# cannot loosen this cell silently.
PF_MIN = 1.15
MIN_LEG_TRADES = 30
MIN_WEEK_CLUSTERS = 30
MIN_LEG_TRADES_PER_YEAR = 100.0
MAX_DRAWDOWN = 0.25  # strict < 25%, not <=
MIN_PROFITABLE_FOLDS = 4
N_FOLDS = 7
MIN_REGIME_WEEKS = 5
REGIME_BAND = 0.01

# Listing-status fallback cutoff from the prereg (N-tape pull cutoff).
LISTING_CUTOFF = "2026-10-16T10:00:00Z"
# No rebalance, feature, or regime decision is formed at or after this instant.
YEAR_2026 = "2026-01-01T00:00:00Z"

MAIN_FOLDS: tuple[str, ...] = (
    "2023Q4",
    "2024Q1",
    "2024Q2",
    "2024Q3",
    "2024Q4",
    "2025Q1",
    "2025Q2",
)

# V2 exclusion, also re-derived from the predicate in calendar.py.
DROPPED_MONDAYS: tuple[str, ...] = (
    "2025-05-05",
    "2025-05-12",
    "2025-05-19",
    "2025-05-26",
    "2025-06-02",
)

DOC_FILES: tuple[tuple[str, str], ...] = (
    ("PREREG.md", PREREG_SHA256),
    ("COUNTERSIGN.md", COUNTERSIGN_SHA256),
    ("COUNTERSIGN_ADDENDUM.md", COUNTERSIGN_ADDENDUM_SHA256),
    ("LOCK.md", LOCK_SHA256),
    ("PRESTATED_THRESHOLD_lsr_v2.md", RULES_SHA256),
    ("PRESTATED_SIZING_lsr_v2.md", SIZING_SHA256),
    ("PROPOSAL_PRE_STATUS_FIX.json", PROPOSAL_LOCKED_SHA256),
    ("REGIME_LOSS_DEF.md", REGIME_LOSS_DEF_SHA256),
)

# Engine bundle. The scorer is hashed on its own and is not imported by the
# blind run. Documents are hashed individually, not inside the bundle.
HARNESS_FILES: tuple[str, ...] = (
    "book.py",
    "calendar.py",
    "costs.py",
    "harness.py",
    "hashing.py",
    "paths.py",
    "pins.py",
    "random_book.py",
    "regime.py",
    "signal.py",
    "tape.py",
)
SCORER_FILES: tuple[str, ...] = ("scorer.py",)
RUNNER_FILES: tuple[str, ...] = ("__init__.py", "__main__.py")

DEFAULT_ROOT = Path("/workspace/research")
TAPE_C_DIRNAME = "universe96_full_history_20261016"
N_TAPE_DIRNAME = "new_listings_perp_20261016"
LS_TAPE_DIRNAME = "bybit_lsratio_20261020"
OI_TAPE_DIRNAME = "bybit_oi_1h_20261020"

# The command the box runs. PYTHONHASHSEED is set by the shell, not by
# assigning os.environ inside the interpreter (that does not disable hash
# randomization). The process refuses to start unless the variable is "0".
MAIN_COMMAND = (
    "PYTHONHASHSEED=0 python -m research.xs_crowd_lsr_contrarian run "
    "--root /workspace/research "
    "--window main "
    "--output /workspace/research/xs_crowd_lsr_contrarian_runs/main"
)
