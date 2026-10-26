"""Freeze portfolio-config hashes and the code SHA before warmup.

The freeze file is written before any warmup bar is requested. Once warmup
has begun, a missing freeze or a hash mismatch marks the run VOID, persists
that mark, and disables entries. A VOID run stays VOID.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .config import ROOT, frozen_config, require_primary
from .seed import atomic_json
from .storage import disable_entries

FREEZE_NAME = 'config_freeze.json'
VOID_NAME = 'void.json'
PORTFOLIO_LOOKS = 'The 16 portfolios are 16 looks at one idea, not 16 tests.'
VOID_BANNER = (
    'VOID: portfolio config or code hash does not match the freeze recorded '
    'before warmup. Entries are disabled. This run is not evidence.'
)
_IDENTITY_FIELDS = (
    'primary', 'primary_portfolio', 'primary_config_sha256',
    'portfolio_hashes', 'portfolio_order', 'code_sha', 'sources_sha256', 'protocol_sha256',
)
COST_ORDER = ('desk031', 'baseline', 'moderate', 'severe')


class ExperimentVoid(RuntimeError):
    """Warmup must stop. The VOID mark is already on disk."""


def digest(value) -> str:
    """Same canonical hash the ledger uses for config identity."""
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _source_paths() -> list[Path]:
    paths = sorted((ROOT / 'research' / 'cipher_forward').glob('*.py'))
    paths.append(ROOT / 'docs' / 'cipher-forward' / 'protocol.json')
    paths.append(ROOT / 'scripts' / 'run_cipher_forward_paper.py')
    return paths


def code_identity() -> dict:
    """Release SHA when the image recorded one, otherwise git HEAD, plus bytes."""
    release = ROOT / 'CIPHER_RELEASE_SHA'
    code_sha = ''
    if release.is_file():
        code_sha = release.read_text().strip()
    if not code_sha:
        try:
            code_sha = subprocess.check_output(
                ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            code_sha = 'unpublished'
    blob = hashlib.sha256()
    for path in _source_paths():
        blob.update(path.relative_to(ROOT).as_posix().encode())
        blob.update(b'\0')
        blob.update(path.read_bytes())
        blob.update(b'\0')
    protocol = ROOT / 'docs' / 'cipher-forward' / 'protocol.json'
    return dict(
        code_sha=code_sha,
        sources_sha256=blob.hexdigest(),
        protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
    )


def portfolio_specs() -> list[dict]:
    """One config body per internal simulated portfolio, in fixed order.

    Order is cost, then I, IC, IM, IF. It is not a performance sort.
    """
    cfg = frozen_config()
    protocol = json.loads((ROOT / 'docs' / 'cipher-forward' / 'protocol.json').read_text())
    specs = []
    for cost in COST_ORDER:
        for arm in ('I', 'IC', 'IM', 'IF'):
            specs.append(dict(
                portfolio=f'{cost}:{arm}',
                cost=cost,
                arm=arm,
                cost_pair=[str(x) for x in cfg['costs'][cost]],
                fee_each_leg=cfg['fee_each_leg'],
                starting_equity_usdt=cfg['starting_equity_usdt'],
                gross_fraction=cfg['gross_fraction'],
                risk_fraction=cfg['risk_fraction'],
                position_fraction=cfg['position_fraction'],
                drawdown_fraction=cfg['drawdown_fraction'],
                daily_realised_loss=cfg['daily_realised_loss'],
                max_open_positions=cfg['max_open_positions'],
                per_sector=cfg['per_sector'],
                daily_entries=cfg['daily_entries'],
                book=protocol['books'][arm],
            ))
    return specs


def current_identity() -> dict:
    specs = portfolio_specs()
    protocol = json.loads((ROOT / 'docs' / 'cipher-forward' / 'protocol.json').read_text())
    arm = require_primary(protocol)
    primary_portfolio = f'desk031:{arm}'
    by_name = {row['portfolio']: row for row in specs}
    if primary_portfolio not in by_name:
        raise ValueError('PRIMARY portfolio is not in the frozen spec list')
    return dict(
        primary=arm,
        primary_portfolio=primary_portfolio,
        primary_config_sha256=digest(by_name[primary_portfolio]),
        portfolio_hashes={row['portfolio']: digest(row) for row in specs},
        portfolio_order=[row['portfolio'] for row in specs],
        **code_identity(),
    )


def _public(identity: dict | None) -> dict | None:
    if not identity:
        return None
    return {key: identity.get(key) for key in _IDENTITY_FIELDS}


def identity_matches(stored: dict, current: dict) -> bool:
    return _public(stored) == _public(current)


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'unreadable {path.name}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{path.name} is not an object')
    return value


def warmup_begun(state_dir: Path) -> bool:
    """True once a freeze exists or a warmup receipt has been written."""
    state = Path(state_dir)
    if (state / FREEZE_NAME).is_file() or (state / VOID_NAME).is_file():
        return True
    receipt = state / 'warmup.json'
    return receipt.is_file()


def mark_void(state_dir: Path, reason: str, stored: dict | None, current: dict, now_ms: int) -> dict:
    """Persist VOID and disable entries. Later calls keep the first reason."""
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    path = state / VOID_NAME
    if path.is_file():
        prior = _read_json(path)
        if prior.get('void'):
            disable_entries(state)
            return prior
    payload = dict(
        void=True,
        reason=reason,
        banner=VOID_BANNER,
        entries_disabled=True,
        at_ms=int(now_ms),
        expected=_public(stored),
        observed=_public(current),
    )
    atomic_json(path, payload)
    disable_entries(state)
    print(f'ERROR cipher-forward VOID: {VOID_BANNER} {reason}', flush=True)
    return payload


def load_sticky_void(state_dir: Path) -> dict | None:
    path = Path(state_dir) / VOID_NAME
    if not path.is_file():
        return None
    prior = _read_json(path)
    if prior.get('void'):
        disable_entries(state_dir)
        return prior
    return None


def freeze_before_warmup(state_dir: Path, now_ms: int) -> dict:
    """Write the freeze if this is the start of warmup. Do not touch bars here.

    A second warmup with the same hashes keeps the original file. A different
    hash voids the run and returns the VOID record.
    """
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    sticky = load_sticky_void(state)
    if sticky:
        return sticky
    current = current_identity()
    path = state / FREEZE_NAME
    if path.is_file():
        stored = _read_json(path)
        if identity_matches(stored, current):
            return stored
        return mark_void(
            state, 'config or code hash changed after warmup had begun', stored, current, now_ms)
    record = dict(
        version=1,
        frozen_before_warmup=True,
        recorded_at_ms=int(now_ms),
        statement=PORTFOLIO_LOOKS,
        **current,
    )
    atomic_json(path, record)
    return record


def enforce_identity(state_dir: Path, now_ms: int = 0) -> dict:
    """Startup and cycle check. Missing or mismatched identity after warmup is VOID."""
    state = Path(state_dir)
    sticky = load_sticky_void(state)
    if sticky:
        return sticky
    if not warmup_begun(state):
        return dict(void=False, warmup_begun=False, entries_disabled=(state / 'entries_disabled').exists())
    current = current_identity()
    path = state / FREEZE_NAME
    if not path.is_file():
        return mark_void(state, 'warmup began without a config freeze', None, current, now_ms)
    stored = _read_json(path)
    if not identity_matches(stored, current):
        return mark_void(
            state, 'config or code hash mismatch after warmup began', stored, current, now_ms)
    return dict(
        void=False,
        warmup_begun=True,
        entries_disabled=(state / 'entries_disabled').exists(),
        banner='',
        freeze=_public(stored),
    )


def entries_halted(state_dir: Path, now_ms: int = 0) -> tuple[bool, dict]:
    """True when the operator halt file is set or the run is VOID."""
    status = enforce_identity(state_dir, now_ms)
    halted = bool(status.get('void')) or (Path(state_dir) / 'entries_disabled').exists()
    return halted, status
