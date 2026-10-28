"""Prove the cipher-forward paper installer dry-run writes nothing.

Allowed stub invocations: none. Preflight uses the ``command -v`` builtin,
which searches PATH and does not execute docker, git, systemctl, pip, or curl.
The dry-run process may run these read-only host commands, and no others:
``hostname``, ``id -u``, ``date -u``, ``command -v flock``, and
``python3 -B -I`` to read ``docs/cipher-forward/config_freeze.json``.

The sandbox roots are installer filesystem paths only. They are not passed
into the paper containers.
"""
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'deploy_cipher_forward_paper.sh'
DOCKERFILE = ROOT / 'docker' / 'cipher-forward.Dockerfile'
REQUIREMENTS = ROOT / 'docker' / 'cipher-forward-requirements.txt'
FREEZE = ROOT / 'docs' / 'cipher-forward' / 'config_freeze.json'
PINNED_SHA = '2eddd55383467a3bf31b3d497fd86689ee18bc5f'
IC_FREEZE = 'f8894f0389cb844603e5d991290759d68f6be869a48f4081e1761805128149a2'
# Dockerfile bytes before the single installer COPY line was added.
DOCKERFILE_BEFORE = '241b8f8ebe7f9450c07113a89bee5a78bb8b898aac56aab706ba21abac646a9d'
REQUIREMENTS_SHA = '32bdda3b94a887cd6e335a21408050e796cc985b82eb93d17f89f35d1c17fff1'
INSTALLER_COPY = (
    'COPY scripts/deploy_cipher_forward_paper.sh '
    '/app/scripts/deploy_cipher_forward_paper.sh\n'
)
STUBS = ('docker', 'systemctl', 'git', 'pip', 'curl')
# Container -e names the real install already passes. Sandbox roots are not here.
CONTAINER_ENV = frozenset({
    'CIPHER_FORWARD_MAIN_PAPER_DB',
    'CIPHER_FORWARD_MIN_FREE_BYTES',
    'CIPHER_FORWARD_LEDGER_MAX_BYTES',
    'CIPHER_FORWARD_LEDGER_MAX_AGE_MS',
})
ROOT_ENV = (
    'CIPHER_FORWARD_INSTALL_ROOT',
    'CIPHER_FORWARD_STATE_ROOT',
    'CIPHER_FORWARD_SYSTEMD_DIR',
)
DEFAULT_PATHS = (
    Path('/opt/mar-cipher-forward'),
    Path('/data/state/cipher-forward-v1'),
    Path('/etc/systemd/system/mar-cipher-forward-prepare.service'),
    Path('/etc/systemd/system/mar-cipher-forward-paper.service'),
    Path('/var/lock/mar-cipher-forward-install.lock'),
)
# Command text the installer must not gain, including on echo lines of a dry-run.
FORBIDDEN_OUTPUT = (
    'systemctl enable',
    'systemctl start',
    'ExecStartPost',
    '--initialize',
    'start_time_utc',
    '--warmup',
    'enable',
    'start',
    'initialize',
)


def _manifest(root: Path):
    """Content hash of every file under root, plus directory names."""
    rows = []
    if not root.exists():
        return rows
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            rows.append((rel, 'symlink', os.readlink(path)))
        elif stat.S_ISDIR(info.st_mode):
            rows.append((rel, 'dir', info.st_mode))
        elif stat.S_ISREG(info.st_mode):
            rows.append((rel, 'file', hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mode))
        else:
            rows.append((rel, 'other', info.st_mode))
    return rows


def _identity(path: Path):
    if not path.exists():
        return None
    info = path.stat()
    return (info.st_mtime_ns, info.st_size, info.st_mode)


def _invoke(tmp_path: Path, args, *, overrides=True):
    """Run the installer with failing PATH stubs and an optional sandbox."""
    sandbox = tmp_path / 'sandbox'
    bindir = tmp_path / 'bin'
    log = tmp_path / 'invocations.log'
    bindir.mkdir()
    install_root = sandbox / 'opt' / 'mar-cipher-forward'
    state_root = sandbox / 'state' / 'cipher-forward-v1'
    unit_dir = sandbox / 'systemd'
    scratch = sandbox / 'tmp'
    for path in (install_root, state_root, unit_dir, scratch):
        path.mkdir(parents=True)
        (path / 'SENTINEL').write_text('sentinel\n')
    for name in STUBS:
        stub = bindir / name
        # Record every execution, then fail. command -v must not reach this.
        stub.write_text(
            '#!/bin/sh\n'
            f'printf "%s\\n" "{name} $*" >> "{log}"\n'
            'exit 99\n'
        )
        stub.chmod(0o755)
    env = os.environ.copy()
    env['PATH'] = str(bindir) + os.pathsep + env.get('PATH', '')
    env['TMPDIR'] = str(scratch)
    env.pop('CIPHER_FORWARD_TAPE_DIR', None)
    if overrides:
        env['CIPHER_FORWARD_INSTALL_ROOT'] = str(install_root)
        env['CIPHER_FORWARD_STATE_ROOT'] = str(state_root)
        env['CIPHER_FORWARD_SYSTEMD_DIR'] = str(unit_dir)
    else:
        for name in ROOT_ENV:
            env.pop(name, None)
    before = {
        'sandbox': _manifest(sandbox),
        'defaults': {str(path): _identity(path) for path in DEFAULT_PATHS},
    }
    completed = subprocess.run(
        ['bash', str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    after = {
        'sandbox': _manifest(sandbox),
        'defaults': {str(path): _identity(path) for path in DEFAULT_PATHS},
    }
    invocations = log.read_text() if log.exists() else ''
    return completed, before, after, invocations, install_root, state_root, unit_dir


def _output(completed):
    return completed.stdout + completed.stderr


def test_bash_n_accepts_the_installer():
    completed = subprocess.run(
        ['bash', '-n', str(SCRIPT)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_dry_run_writes_nothing_and_prints_the_plan(tmp_path):
    completed, before, after, invocations, install_root, state_root, unit_dir = _invoke(
        tmp_path, [PINNED_SHA, '--dry-run'])
    output = _output(completed)
    assert completed.returncode == 0, output
    assert completed.stderr == ''
    # No stub ran. Preflight does not need git --version or docker --version.
    assert invocations == ''
    assert before == after
    assert f'pinned-sha: {PINNED_SHA}' in output
    assert f'image-tag: mar-cipher-forward:{PINNED_SHA}' in output
    assert f'install-root: {install_root}' in output
    assert f'state-root: {state_root}' in output
    assert f'systemd-dir: {unit_dir}' in output
    assert 'would-run: git init --bare ' in output
    assert 'fetch --no-tags origin ' in output
    assert 'not a work-tree clone' in output
    assert 'would-run: docker build --pull ' in output
    assert 'python -m pytest -q -p no:cacheprovider ' in output
    assert 'tests/test_cipher_forward_ruling.py' in output
    assert 'would-run: systemctl daemon-reload' in output
    assert 'would-run: touch ' in output and 'entries_disabled' in output
    assert 'would-write: ' in output and output.count('deployment.json') >= 1
    assert re.search(r'install-\d{8}T\d{6}Z', output)
    assert 'mar-cipher-forward-prepare.service' in output
    assert 'mar-cipher-forward-paper.service' in output
    assert 'would-write: /var/lock/mar-cipher-forward-install.lock' in output
    assert 'note: ledger not touched' in output
    assert 'note: warmup not run' in output
    assert 'note: clock field not written' in output
    assert 'note: dry-run wrote nothing' in output
    # The plan uses the sandbox roots, not the historical hardcoded ones.
    assert 'install-root: /opt/mar-cipher-forward\n' not in output
    assert 'state-root: /data/state/cipher-forward-v1\n' not in output
    assert 'systemd-dir: /etc/systemd/system\n' not in output


def test_dry_run_wins_when_no_start_is_also_set(tmp_path):
    completed, before, after, invocations, *_rest = _invoke(
        tmp_path, ['--no-start', PINNED_SHA, '--dry-run'])
    output = _output(completed)
    assert completed.returncode == 0, output
    assert invocations == ''
    assert before == after
    assert 'precedence: dry-run' in output
    assert 'note: dry-run wrote nothing' in output
    # The install path's --no-start summary is not the dry-run.
    assert '--no-start dry run:' not in output


def test_printed_freeze_hash_matches_desk031_ic(tmp_path):
    freeze = json.loads(FREEZE.read_text())
    expected = freeze['portfolio_hashes']['desk031:IC']
    assert expected == freeze['primary_config_sha256']
    assert expected == IC_FREEZE
    assert freeze['primary_portfolio'] == 'desk031:IC'
    completed, before, after, invocations, *_rest = _invoke(
        tmp_path, [PINNED_SHA, '--dry-run'])
    assert completed.returncode == 0, _output(completed)
    assert invocations == ''
    assert before == after
    assert f'freeze-hash: desk031:IC {expected}' in completed.stdout


def test_dry_run_output_has_no_enable_start_or_initialize(tmp_path):
    completed, *_rest = _invoke(tmp_path, [PINNED_SHA, '--dry-run'])
    output = _output(completed)
    assert completed.returncode == 0, output
    for token in FORBIDDEN_OUTPUT:
        assert token not in output, token
    # Same rule the ruling test enforces on the script, so this file cannot
    # weaken it. Echo, printf, and comments stay allowed there.
    text = SCRIPT.read_text()
    forbidden = ('systemctl enable', 'systemctl start', 'ExecStartPost', '--initialize')
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('echo ') or stripped.startswith('printf '):
            continue
        for token in forbidden:
            assert token not in stripped, f'{lineno}: {stripped}'


def test_dry_run_default_roots_match_the_hardcoded_paths(tmp_path):
    completed, before, after, invocations, *_rest = _invoke(
        tmp_path, [PINNED_SHA, '--dry-run'], overrides=False)
    output = _output(completed)
    assert completed.returncode == 0, output
    assert invocations == ''
    assert before == after
    assert 'install-root: /opt/mar-cipher-forward' in output
    assert 'state-root: /data/state/cipher-forward-v1' in output
    assert 'systemd-dir: /etc/systemd/system' in output


def test_bad_sha_exits_before_any_write(tmp_path):
    completed, before, after, invocations, *_rest = _invoke(
        tmp_path, ['--dry-run', 'not-a-sha'])
    assert completed.returncode == 2
    assert invocations == ''
    assert before == after
    assert 'would-run:' not in completed.stdout


def test_dry_run_returns_before_the_mutating_block():
    text = SCRIPT.read_text()
    dry = text.index('if [[ "$dry_run" == 1 ]]; then')
    exit_at = text.index('\n    exit 0\n', dry)
    guard = text.index('[[ "$dry_run" == 0 ]]', exit_at)
    lock = text.index('exec 9>"$lock_path"', guard)
    mkdir_at = text.index('mkdir -p "$base/releases"', lock)
    assert dry < exit_at < guard < lock < mkdir_at
    # The wrappers are the only mutation gate. The mutating block does not
    # grow its own dry-run branches.
    mutating = text[guard:]
    assert 'if [[ "$dry_run"' not in mutating
    assert 'def run' not in text
    assert text.count('if [[ "$dry_run" == 1 ]]; then') == 3


def test_sandbox_roots_are_not_passed_into_containers():
    text = SCRIPT.read_text()
    dockerfile = DOCKERFILE.read_text()
    for name in ROOT_ENV:
        assert f'{name}:-' in text
        assert f'-e {name}' not in text
        assert name not in dockerfile
    assert 'CIPHER_FORWARD_TAPE_DIR' not in text
    assert 'CIPHER_FORWARD_TAPE_DIR' not in dockerfile
    assert 'fixed_2026_window' not in text
    assert 'operator_approved' not in text
    assert 'start_time_utc' not in text
    assert 'TRADING_MODE' not in text
    assert 'export ' not in text
    # The pre-existing audit snippet reads this name inside the paper
    # container. The installer does not set it or pass it in.
    assert '-e GO_LIVE_CONFIRMED' not in text
    assert 'export GO_LIVE_CONFIRMED' not in text
    found = set(re.findall(r'-e ([A-Z0-9_]+)', text))
    assert found == CONTAINER_ENV
    assert dockerfile.count('ENV ') == 1
    assert 'ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TRADING_MODE=paper' in dockerfile


def test_dockerfile_copy_set_includes_the_installer():
    text = DOCKERFILE.read_text()
    copies = []
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line.startswith('COPY '):
            continue
        parts = line.split()
        copies.append((parts[1:-1], parts[-1]))
    installer = [
        (sources, dest) for sources, dest in copies
        if 'scripts/deploy_cipher_forward_paper.sh' in sources
    ]
    assert installer == [(
        ['scripts/deploy_cipher_forward_paper.sh'],
        '/app/scripts/deploy_cipher_forward_paper.sh',
    )]
    # Removing that one line restores the Dockerfile that was reviewed at the pin.
    restored = text.replace(INSTALLER_COPY, '', 1)
    assert hashlib.sha256(restored.encode()).hexdigest() == DOCKERFILE_BEFORE
    assert hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest() == REQUIREMENTS_SHA
    assert 'numpy==2.3.5' in REQUIREMENTS.read_text()
    assert 'pandas==2.2.3' in REQUIREMENTS.read_text()
    assert 'pyarrow' not in REQUIREMENTS.read_text()
