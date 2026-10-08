import errno
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import deploy_hourly_connors as repair
from scripts.enable_hourly_connors import desired_records
from scripts.enable_hourly_compression import desired_records as retired_records


def test_host_merge_preserves_existing_records_and_backups(tmp_path):
    path = tmp_path/'approved.json'
    original = {'other:BTCUSDT:LONG:1h': {'approved': True, 'params': {'stop_loss_pct': .07}}, '_meta': 'preserve'}
    before = json.dumps(original).encode();path.write_bytes(before);path.chmod(0o640)
    inode = path.stat().st_ino
    result = repair.atomic_host_update(path, desired_records(), retired_records())
    saved = json.loads(path.read_bytes())
    assert all(saved[k] == v for k,v in original.items())
    assert len(saved) == len(original)+6
    assert Path(result['backup']).read_bytes() == before
    assert path.stat().st_ino != inode and path.stat().st_mode & 0o777 == 0o640
    repeat = repair.atomic_host_update(path, desired_records(), retired_records())
    assert repeat['changed'] is False
    assert len(list(tmp_path.glob('*.before-hourly-host-*'))) == 1


def test_conflicting_record_aborts_without_overwrite(tmp_path):
    path=tmp_path/'approved.json'; original={next(iter(desired_records())): {'approved': True}}
    path.write_text(json.dumps(original)); before=path.read_bytes()
    with pytest.raises(RuntimeError, match='Conflicting'):
        repair.atomic_host_update(path, desired_records(), retired_records())
    assert path.read_bytes() == before


def test_stops_readers_before_update_and_resumes_api_first(monkeypatch):
    calls=[]
    monkeypatch.setattr(repair,'docker',lambda *args,**kw:calls.append(args) or '')
    monkeypatch.setattr(repair,'inspect',lambda names:[{'State':{'Running':False}} for _ in names])
    def update():
        assert calls == [('stop','--time','30',repair.PAPER),('stop','--time','30',repair.API)]
        calls.append(('update',));return 7
    assert repair.stop_update_resume({repair.PAPER,repair.API},update) == 7
    assert calls[-2:] == [('start',repair.API),('start',repair.PAPER)]


def test_resumes_original_consumers_even_if_write_fails(monkeypatch):
    calls=[]
    monkeypatch.setattr(repair,'docker',lambda *args,**kw:calls.append(args) or '')
    monkeypatch.setattr(repair,'inspect',lambda names:[{'State':{'Running':False}} for _ in names])
    def update():raise OSError('disk full')
    with pytest.raises(OSError,match='disk full'):
        repair.stop_update_resume({repair.PAPER,repair.API},update)
    assert calls[-2:] == [('start',repair.API),('start',repair.PAPER)]


def test_does_not_write_if_consumer_remains_running(monkeypatch):
    calls=[]
    monkeypatch.setattr(repair,'docker',lambda *args,**kw:calls.append(args) or '')
    monkeypatch.setattr(repair,'inspect',lambda names:[{'State':{'Running':True}}])
    with pytest.raises(RuntimeError,match='remains running'):
        repair.stop_update_resume({repair.PAPER},lambda:pytest.fail('must not write'))
    assert calls[-1] == ('start',repair.PAPER)


def test_detects_file_and_parent_directory_consumers(tmp_path):
    source=tmp_path/'approved.json';source.write_text('{}')
    rows=[{'Name':'/'+repair.PAPER,'Mounts':[{'Type':'bind','Source':str(source)}]},
          {'Name':'/'+repair.API,'Mounts':[{'Type':'bind','Source':str(tmp_path)}]},
          {'Name':'/unrelated','Mounts':[]}]
    assert repair.readers_of(source,rows)=={repair.PAPER,repair.API}
    mount={'Mounts':[{'Destination':'/app/config/approved_strategies.json','Type':'bind','Source':str(source),'RW':True}]}
    assert repair.source_for_file_mount(mount,'/app/config/approved_strategies.json')==source
    mount['Mounts'][0]['RW']=False
    with pytest.raises(RuntimeError,match='writable'):
        repair.source_for_file_mount(mount,'/app/config/approved_strategies.json')


def test_paper_check_rejects_nonpaper_result(monkeypatch):
    monkeypatch.setattr(repair,'container_python',lambda *args:'HOURLY_JSON={"mode":"live"}\n')
    with pytest.raises(RuntimeError,match='mode'):
        repair.require_paper([repair.PAPER])


def test_busy_error_keeps_original_book_and_host_applied_repeat_needs_no_rename(tmp_path,monkeypatch):
    from scripts import enable_hourly_connors as command
    from config.settings import get_settings
    import config.universe as universe
    path=tmp_path/'approved.json';path.write_text('{"_keep": {"a": 1}}')
    before=path.read_bytes()
    monkeypatch.setattr(universe,'APPROVALS_PATH',path)
    monkeypatch.setattr(command,'verify_plan',lambda:6)
    monkeypatch.setenv('TRADING_MODE','paper');get_settings.cache_clear()
    monkeypatch.setattr('sys.argv',['enable','--apply'])
    real_replace=command.os.replace
    def busy(*args):raise OSError(errno.EBUSY,'Device or resource busy')
    monkeypatch.setattr(command.os,'replace',busy)
    with pytest.raises(RuntimeError,match='host-side repair'):
        command.main()
    assert path.read_bytes()==before
    assert not list(tmp_path.glob('.hourly-*'))
    assert list(tmp_path.glob('*.before-hourly-*'))
    path.write_text(json.dumps({'_keep':{'a':1},**desired_records()}))
    inode=path.stat().st_ino
    command.main()  # skips rename because host has already installed exact records
    assert path.stat().st_ino==inode
    assert json.loads((tmp_path/'hourly_compression_connors_v1_activation.json').read_text())['sleeves']==6
    get_settings.cache_clear();universe.get_universe.cache_clear()


def test_complete_host_repair_flow_checks_remounted_bytes(tmp_path,monkeypatch,capsys):
    import hashlib
    source=tmp_path/'approved.json';source.write_text(json.dumps({'_existing':'keep',**retired_records()}))
    names=[repair.PAPER,repair.API]; running={n:True for n in names}; calls=[]
    def inspect(names):
        return [{'Name':'/'+n,'State':{'Running':running[n]},'Mounts':[
            {'Type':'bind','RW':True,'Source':str(source),'Destination':'/app/config/approved_strategies.json'}]} for n in names]
    def docker(*args,**kwargs):
        calls.append(args)
        if args[:2]==('ps','-q'):return '\n'.join(names)
        if args[0]=='stop':running[args[-1]]=False;return ''
        if args[0]=='start':running[args[-1]]=True;return ''
        if args[0]=='exec':
            assert all(running.values())
            assert json.loads(source.read_bytes())=={'_existing':'keep',**desired_records()}
            return '{"status":"installed_awaiting_cycle","sleeves":6}'
        raise AssertionError(args)
    def python(name,code):
        compile(code,'generated-container-command','exec')
        if 'critical=' in code:
            result={'approval_path':'/app/config/approved_strategies.json',
                    'approval_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'records':desired_records(),'retired':retired_records()}
        elif 'expected PAPER mode' in code:result={'mode':'paper'}
        elif "print('Code update prepared')" in code:return 'Code update prepared'
        else:
            assert all(running.values())
            result={'sha':hashlib.sha256(source.read_bytes()).hexdigest()}
        return 'HOURLY_JSON='+json.dumps(result)
    monkeypatch.setattr(repair,'inspect',inspect)
    monkeypatch.setattr(repair,'docker',docker)
    monkeypatch.setattr(repair,'container_python',python)
    repair.main({}, {})
    assert 'installed_awaiting_cycle' in capsys.readouterr().out
    assert all(running.values())
    assert ('stop','--time','30',repair.PAPER) in calls and ('start',repair.API) in calls
