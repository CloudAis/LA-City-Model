#!/usr/bin/env python3
"""Unified entry: read the specification/state first; preserve evidence and real exit status."""
import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command_version(cmd):
    try:
        p = subprocess.run(cmd,text=True,capture_output=True,timeout=25)
        return {'command':cmd,'exit_code':p.returncode,'version':(p.stdout+p.stderr).strip().splitlines()[0]}
    except (OSError,subprocess.TimeoutExpired,IndexError) as e:
        return {'command':cmd,'exit_code':None,'error':str(e)}


def environment(cfg):
    effective_cpus = len(os.sched_getaffinity(0))
    quota = None
    try:
        q,p = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if q != 'max': quota = int(q)/int(p)
    except (OSError,ValueError):pass
    info = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    memory_total = int(info['MemTotal'].split()[0])*1024
    mem_limit = None
    try:
        s = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if s != 'max': mem_limit = int(s)
    except (OSError,ValueError):pass
    effective_memory = min(memory_total, mem_limit or memory_total)
    disk = shutil.disk_usage(ROOT)
    cpu_model = next((l.split(':',1)[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')), 'unknown')
    gpu = {'hardware_model':'unknown','vram_bytes':None,'reliable_hardware_measurement':False,
           'nvidia_smi_present': bool(shutil.which('nvidia-smi')),
           'dri_device_present':Path('/dev/dri').exists(),
           'note':'No usable hardware GPU/VRAM telemetry; software WebGL does not establish a hardware GPU.'}
    if shutil.which('nvidia-smi'):
        r = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'],text=True,capture_output=True)
        if r.returncode == 0:
            gpu.update({'hardware_model_and_vram_mib':r.stdout.strip(),'reliable_hardware_measurement':True})
    tools = {name:command_version(cmd) for name,cmd in {
        'blender':[cfg['build']['blender_executable'],'--version'],
        'python':[sys.executable,'--version'],'node':['node','--version'],
        'npm':['npm','--version'],'git':['git','--version'],
        'uv':['uv','--version'],'chromium':['chromium','--version']}.items()}
    from importlib.metadata import version
    packages = {n:version(n) for n in ['PyYAML','pyproj','shapely','Pillow','numpy','certifi','playwright','pyshp','rasterio','matplotlib','pyogrio','osmium','requests']}
    report = {'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'passed' if all(t['exit_code']==0 for t in tools.values()) else 'failed',
        'os':platform.platform(),'os_release':Path('/etc/os-release').read_text(),
        'architecture':platform.machine(),'cpu_model':cpu_model,
        'cpu_affinity_count':effective_cpus,'cpu_cgroup_quota_cores':quota,
        'effective_cpu_cores':min(effective_cpus,quota or effective_cpus),
        'memory_total_bytes':memory_total,'memory_cgroup_limit_bytes':mem_limit,
        'effective_memory_bytes':effective_memory,
        'memory_available_host_bytes':int(info['MemAvailable'].split()[0])*1024,
        'disk_total_bytes':disk.total,'disk_free_bytes':disk.free,'gpu':gpu,
        'tools':tools,'python_packages':packages,'python_executable':sys.executable,
        'blender_executable':shutil.which('blender'),
        'display_present':bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')),
        'stage01_evidence':{}}
    for key,path in {'blender':'work/reports/scene_check.json','browser':'work/reports/browser.json'}.items():
        p=ROOT/path
        report['stage01_evidence'][key] = json.loads(p.read_text()) if p.exists() else {'status':'not_run'}
    if report['effective_cpu_cores'] < cfg['build']['threads']:
        raise RuntimeError('Configured Blender threads exceed observed CPU quota')
    if disk.free < cfg['build']['disk_headroom_gib']*1024**3:
        raise RuntimeError('Disk free space below configured safe headroom')
    if cfg['quality']['high']['ram_budget_mib']*1024**2 > effective_memory*(1-cfg['build']['memory_headroom_fraction']):
        raise RuntimeError('High profile RAM budget exceeds safe memory limit')
    dump(ROOT/'work/reports/environment.json',report)
    print(f"ENVIRONMENT_{report['status'].upper()}: CPU={report['effective_cpu_cores']:g} cores, RAM={effective_memory/1024**3:.2f} GiB, disk_free={disk.free/1024**3:.2f} GiB, GPU={gpu['hardware_model']}")
    if report['status']!='passed':raise RuntimeError('A required tool failed its version check')
    return report


def fingerprint(cfg, region, quality):
    paths = [ROOT/'config/project.yaml', *sorted((ROOT/'config').glob('*.json')), ROOT/'requirements.lock', *sorted((ROOT/'scripts').glob('*.py')),
             *sorted(p for p in (ROOT/'data/raw').glob('*') if p.is_file())]
    h=hashlib.sha256()
    for p in paths:
        h.update(str(p.relative_to(ROOT)).encode());h.update(p.read_bytes())
    h.update(json.dumps({'region':region,'quality':quality,'blender':command_version([cfg['build']['blender_executable'],'--version'])},sort_keys=True).encode())
    return h.hexdigest()


def verify_manifest(path):
    m=json.loads(path.read_text())
    for item in m['artifacts']:
        p=ROOT/item['path']
        if not p.exists() or sha(p)!=item['sha256']:
            raise RuntimeError(f'Artifact missing or changed: {p}; preserve user edits before rebuilding')
    return m


def run_blender(cmd, log, label):
    with log.open('a') as f:
        f.write('\n'+label+'\n'+json.dumps(cmd)+'\n');f.flush()
        p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,cwd=ROOT)
        f.write(f'\nEXIT_CODE={p.returncode}\n')
    if p.returncode:raise RuntimeError(f'{label} failed with exit code {p.returncode}; log={log}')
    print(label+'_OK', flush=True)


def artifact_check(blend, render, scene_report, cfg, quality):
    from PIL import Image, ImageStat
    if blend.read_bytes()[:7]!=b'BLENDER':raise RuntimeError('Invalid .blend header')
    r=json.loads(scene_report.read_text())
    if r['status']!='passed' or not all(c['passed'] for c in r['checks']):raise RuntimeError('Blender check report failed')
    q=cfg['quality'][quality]['render']
    with Image.open(render) as im:
        im.verify()
    with Image.open(render) as im:
        expected=(q['width'],q['height'])
        if im.size!=expected:raise RuntimeError('Rendered PNG size mismatch')
        deviation=ImageStat.Stat(im.convert('RGB')).stddev
        if max(deviation)<5:raise RuntimeError('Rendered PNG is nearly blank')
    return {'dimensions_px':list(expected),'channel_stddev':deviation,'valid_png':True,'nonblank':True}


def stage01(cfg, region, quality):
    from geo_scopes import prepare
    from browser_probe import probe
    if cfg['project']['stage']>=2:
        frozen=ROOT/'work/reports/stage01_calibration_medium.job.json'
        cfg=json.loads(frozen.read_text())['config']
        print('STAGE01_FROZEN_V1_CONFIG: current city data stays in stage02; calibration uses its saved original contract.',flush=True)
    print(f'STAGE01_SCOPE_SELECTION_ONLY: region={region}; synthetic calibration at project origin, no real city mesh generation.',flush=True)
    env=environment(cfg)
    scope=prepare(ROOT,cfg)
    fp=fingerprint(cfg,region,quality)
    key=f'stage01_{region}_{quality}'
    blend=ROOT/'scenes'/f'{key}.blend'
    render=ROOT/'work/previews'/f'{key}.png'
    report=ROOT/'work/reports'/f'{key}.json'
    manifest=ROOT/'outputs'/f'{key}.manifest.json'
    if manifest.exists():
        old=verify_manifest(manifest)
        if old['fingerprint']==fp:
            artifact_check(blend,render,report,cfg,quality)
            # This browser test must still execute; processes cannot be restored from a snapshot.
            probe(ROOT,render)
            old['status']='passed'
            for p in [ROOT/'work/previews'/(key+'_browser.png'),ROOT/'work/previews'/(key+'_review.html'),ROOT/'work/previews'/(key+'_review.dom.html'),ROOT/'work/logs'/(key+'_browser.log'),ROOT/'work/reports'/(key+'_browser.json')]:
                item={'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
                old['artifacts']=[a for a in old['artifacts'] if a['path']!=item['path']]+[item]
            dump(manifest,old)
            shutil.copy2(report,ROOT/'work/reports/scene_check.json')
            environment(cfg)
            print('INCREMENTAL_CACHE_VERIFIED: saved scene/render unchanged; no Blender rebuild needed')
            return old
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        archive=ROOT/'work/history'/f'{key}_{stamp}_{uuid.uuid4().hex[:6]}'
        for item in old['artifacts']:
            p=ROOT/item['path'];dst=archive/item['path']
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
        shutil.copy2(manifest,archive/manifest.name)
        print('ARCHIVED_PRIOR_GENERATED_OUTPUTS',archive)
    elif any(p.exists() for p in (blend,render,report)):
        raise RuntimeError('Existing outputs lack manifest; preserve them explicitly before building')
    runid=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    job={'config':cfg,'quality':quality,'region':region,'fingerprint':fp,
         'blend_path':str(blend),'render_path':str(render),'check_path':str(report),
         'origin':scope['origin']}
    jobpath=ROOT/'work/reports'/f'{key}.job.json';dump(jobpath,job)
    log=ROOT/'work/logs'/f'{key}_{runid}.log'
    exe=cfg['build']['blender_executable'];script=ROOT/'scripts/blender_stage01.py'
    common=[exe,'--background','--threads',str(cfg['build']['threads']),'--python-exit-code','1']
    run_blender(common+['--factory-startup','--python',str(script),'--','--job',str(jobpath),'--mode','build'],log,'SAVE_AND_EXIT')
    # Separate completed subprocess proves the original Blender process closed before reopen.
    run_blender(common+[str(blend),'--python',str(script),'--','--job',str(jobpath),'--mode','verify-render'],log,'REOPEN_MEASURE_RENDER_AND_EXIT')
    image=artifact_check(blend,render,report,cfg,quality)
    shutil.copy2(report,ROOT/'work/reports/scene_check.json')
    core=[blend,render,report,jobpath,log]
    artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in core]
    m={'stage':1,'status':'core_passed_browser_pending','region':region,'quality':quality,'fingerprint':fp,
       'geometry_class':'artistic_synthetic','real_city_geometry_built':False,
       'saved_and_reopened_in_distinct_processes':True,'render_check':image,
       'scope_report':'work/reports/scopes.json','browser_report':'work/reports/browser.json',
       'artifacts':artifacts,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    dump(manifest,m)
    browser=probe(ROOT,render)
    m['status']='passed'
    # Preserve the per-profile browser evidence while shared aliases may be refreshed.
    for p in [ROOT/'work/previews'/(key+'_browser.png'),ROOT/'work/previews'/(key+'_review.html'),ROOT/'work/previews'/(key+'_review.dom.html'),ROOT/'work/logs'/(key+'_browser.log'),ROOT/'work/reports'/(key+'_browser.json')]:
        m['artifacts'].append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)})
    dump(manifest,m)
    environment(cfg)
    print('STAGE01_ACCEPTANCE_PASSED',manifest)
    return m


def main():
    # Every invocation reads the actual current project contract and human status.
    for name in ['PROJECT_SPEC.md','STATUS.md']:
        if not (ROOT/name).is_file():raise RuntimeError('Required project file missing: '+name)
        (ROOT/name).read_text()
    cfg=yaml.safe_load((ROOT/'config/project.yaml').read_text())
    regions=['calibration','city','downtown']+[c['id'] for c in cfg['geography']['closeups']]
    parser=argparse.ArgumentParser(description='LA city pipeline. Stages01–10 with actual acceptance gates. Stage09 city/medium builds a local viewer. Stage10 city/medium verifies the final version1.0.0 handoff; overall model acceptance remains partial. Viewer runtime has three quality modes.')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('env',help='Measure this machine, check tools, report actual evidence')
    for action in ['run','check','export']:
        p=sub.add_parser(action)
        p.add_argument('--stage',type=int,choices=range(1,11),required=True)
        p.add_argument('--region',choices=regions,default='calibration')
        p.add_argument('--quality',choices=['low','medium','high'],default=cfg['quality']['default'])
        p.add_argument('--refresh-network',action='store_true',help='After a confirmed network configuration change, retry blocked stage02 research endpoints')
    a=parser.parse_args()
    if a.command=='env':environment(cfg);return 0
    if a.stage not in [1,2,3,4,5,6,7,8,9,10] or (a.command=='export' and a.stage not in [9,10]):
        print(f'未实现 / NOT IMPLEMENTED: command={a.command}, stage={a.stage}. No success result or city model generated.',file=sys.stderr)
        return 3
    if a.stage==10:
        from stage10 import execute,check
        return check(ROOT,a.region,a.quality) if a.command=='check' else execute(ROOT,a.region,a.quality,a.command=='export')
    if a.stage==2:
        from stage02 import execute,check
        return execute(ROOT,a.region,a.quality,a.refresh_network) if a.command=='run' else check(ROOT)
    if a.stage==6:
        from stage06 import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.stage==7:
        from stage07_final import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.stage==8:
        from stage08 import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.stage==9:
        from stage09 import execute,check
        return check(ROOT,a.region,a.quality) if a.command=='check' else execute(ROOT,a.region,a.quality,a.command=='export')
    if a.stage==5:
        from stage05 import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.stage==4:
        from stage04 import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.stage==3:
        from stage03 import execute,check
        return execute(ROOT,a.region,a.quality) if a.command=='run' else check(ROOT,a.region,a.quality)
    if a.command=='run':stage01(cfg,a.region,a.quality);return 0
    manifest=ROOT/'outputs'/f'stage01_{a.region}_{a.quality}.manifest.json'
    m=verify_manifest(manifest)
    if m['status']!='passed':raise RuntimeError('Stage not complete: '+m['status'])
    job=json.loads((ROOT/'work/reports'/f'stage01_{a.region}_{a.quality}.job.json').read_text())
    artifact_check(ROOT/'scenes'/f'stage01_{a.region}_{a.quality}.blend',ROOT/'work/previews'/f'stage01_{a.region}_{a.quality}.png',ROOT/'work/reports'/f'stage01_{a.region}_{a.quality}.json',job['config'],a.quality)
    print('CHECK_PASSED_HISTORICAL_STAGE01_SNAPSHOT: artifact checksums and saved dimensions verified; does not claim a rebuild with current stage02 inputs.',manifest)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('FAILED:',str(e),file=sys.stderr)
        sys.exit(1)
