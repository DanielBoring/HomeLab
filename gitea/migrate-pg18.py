#!/usr/bin/env python3
"""Operator-run Gitea PG17->18 helper. Default stage mode never stops live services."""
import argparse, datetime, hashlib, json, os, pathlib, socket, stat, subprocess, sys, time, uuid, signal

APP = 'docker.gitea.com/gitea@sha256:87a67ee09d3ae0d1df5fda5dcda3e2a1f9236a45b0a59025d6e00e46adc43bef'
PG17 = 'postgres:17.11@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3'
PG18 = 'postgres:18.6@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4'
BASE = 'cd62a229eb96ac768fffecd10cb99c8aaf586340'
HEAD = '62b9a17b5eca5c11d075da21c85f31c1759b1510'
D = ['docker', '--host', 'unix:///var/run/docker.sock']
ROOT = pathlib.Path('/mnt/SSD/Containers/gitea')
COMPOSE_ENV = None
NULL_ENV = '/dev/null'
MAPPING = {'PUID':'USER_UID', 'PGID':'USER_GID', 'TZ':'TZ',
 'GITEA_DB_PASSWORD':'GITEA__database__PASSWD', 'GITEA_SECRET_KEY':'GITEA__security__SECRET_KEY',
 'GITEA_INTERNAL_TOKEN':'GITEA__security__INTERNAL_TOKEN', 'GITEA_DOMAIN':'GITEA__server__DOMAIN',
 'GITEA_SSH_PORT':'GITEA__server__SSH_PORT', 'GITEA_DISABLE_REGISTRATION':'GITEA__service__DISABLE_REGISTRATION'}

def need(ok, msg):
    if not ok: raise RuntimeError(msg)
def run(args, *, inp=None, output=None, log=None):
    p = subprocess.run(args, input=inp, stdout=output or subprocess.PIPE,
                       stderr=log or subprocess.PIPE,
                       env=COMPOSE_ENV if args[:len(D)+1]==D+['compose'] else None)
    if p.returncode: raise RuntimeError('Command failed: '+args[0]+' '+args[1]+' (details kept private)')
    return p.stdout if output is None else b''
def dj(*args): return json.loads(run(D+list(args)))
def dt(*args): return run(D+list(args)).decode().strip()
def private(path):
    fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, 'wb')
def save(path, data):
    with private(path) as f: f.write(data)
    need(stat.S_IMODE(path.stat().st_mode)==0o600, 'Private artifact mode is not 0600')
def env(c):
    entries=c['Config']['Env']; pairs=[x.split('=',1) for x in entries]
    need(len(pairs)==len({x[0] for x in pairs}), 'Duplicate runtime environment keys')
    return dict(pairs)
def compose(stage, version, *args):
    return D+['compose','-p','gitea','--env-file',NULL_ENV,'-f',str(stage/f'compose.pg{version}.yaml'),*args]
def inspect_named(): return {c['Name'].lstrip('/'):c for c in dj('inspect','gitea','gitea-db')}
def host_guard(stage):
    need(os.geteuid()==0 and socket.gethostname()=='TrueNAS', 'Expected root on TrueNAS')
    need(stage.parent==pathlib.Path('/root') and stage.name.startswith('gitea-pg18-upgrade.'), 'Unexpected staging directory')
    need(stage.is_dir() and stage.resolve()==stage, 'Staging directory missing or aliased')
    need(stage.stat().st_uid==0 and stat.S_IMODE(stage.stat().st_mode)==0o700, 'Staging directory must be root-owned 0700')
    need(not os.environ.get('DOCKER_HOST') and os.environ.get('DOCKER_CONTEXT','default')=='default', 'Unexpected Docker override')
    need(subprocess.check_output(['docker','context','show'],text=True).strip()=='default', 'Expected default Docker context')
    need(dt('info','--format','{{.OSType}}')=='linux', 'Expected local Linux Docker')
    for p in [ROOT,ROOT/'data',ROOT/'db']:
        need(p.is_dir() and p.resolve()==p and not p.is_symlink(), 'Source path missing or aliased')
        record=subprocess.check_output(['findmnt','-T',str(p),'-n','-o','TARGET,SOURCE,FSTYPE'],text=True).split()
        need(record==['/mnt/SSD/Containers','SSD/Containers','zfs'], 'Unexpected source mount/dataset')
    nested=subprocess.check_output(['findmnt','-rn','-o','TARGET'],text=True).splitlines()
    need(not any(p==str(ROOT) or p.startswith(str(ROOT)+'/') for p in nested), 'Nested mount requires separate review')
    need((ROOT/'db'/'PG_VERSION').read_text().strip()=='17', 'Source is not PG17')
def runtime_guard(cs, captured, vols):
    for name, ref in [('gitea',APP),('gitea-db',PG17)]:
        c=cs[name]; old=captured[name]
        need(c['Id']==old['Id'] and c['Image']==old['Image'], 'Source container/image identity changed: '+name)
        need(c['State']['Running'] and not c['State']['Paused'], 'Expected source running: '+name)
        need(c['Config']['Image']==ref, 'Unexpected source image reference: '+name)
        need(c['Config']['Labels'].get('com.docker.compose.project')=='gitea', 'Wrong Compose project')
        need(env(c)==env(old), 'Runtime environment changed since capture')
        need(len(c['Mounts'])==1, 'Additional source mounts require review')
        m=c['Mounts'][0]; suffix='data' if name=='gitea' else 'db'
        target='/data' if name=='gitea' else '/var/lib/postgresql/data'
        vn='gitea_gitea-'+suffix
        need(m['Type']=='volume' and m['Name']==vn and m['Destination']==target and m['RW'], 'Unexpected source mount')
        v=vols[vn]
        need(v['Driver']=='local' and v['Options']=={'type':'none','device':str(ROOT/suffix),'o':'bind'}, 'Unexpected source bind volume')
        need(dj('volume','inspect',vn)[0]['Options']==v['Options'], 'Volume definition changed')
    a,b=env(cs['gitea']),env(cs['gitea-db'])
    need(all(a.get(k) for k in MAPPING.values()), 'Required effective app setting is absent')
    need(a['GITEA__database__PASSWD']==b.get('POSTGRES_PASSWORD'), 'App/DB password settings differ')
    need(a['GITEA__database__NAME']==b.get('POSTGRES_DB')=='gitea' and a['GITEA__database__USER']==b.get('POSTGRES_USER')=='gitea', 'Unexpected DB name/role')

def model(stage, version): return json.loads(run(compose(stage,version,'config','--format','json')))
def probe_environment(stage, service, rendered, expected):
    # A create-only disposable container proves Compose quoting by actual Config.Env.
    token='gitea-pg18-probe-'+uuid.uuid4().hex[:12]
    probe_file=stage/(token+'.json')
    probe={'services':{'probe':{'image':rendered['image'],'container_name':token,
      'network_mode':'none','entrypoint':['/bin/true'],'environment':rendered['environment'],
      'labels':{'gitea.upgrade.probe':token},'restart':'no'}}}
    save(probe_file,json.dumps(probe).encode())
    try:
        run(D+['compose','-p',token,'--env-file',NULL_ENV,'-f',str(probe_file),'create','--pull','never'])
        c=dj('inspect',token)[0]
        need(c['HostConfig']['NetworkMode']=='none' and not c['HostConfig'].get('PortBindings'), 'Probe isolation failed')
        need(all(m['Type']=='volume' for m in c['Mounts']), 'Unexpected probe bind mount')
        need(env(c)==expected, 'Resolved Compose environment differs from actual runtime: '+service)
    finally:
        p=subprocess.run(D+['inspect',token],capture_output=True)
        if p.returncode==0:
            c=json.loads(p.stdout)[0]
            need(c['Config']['Labels'].get('gitea.upgrade.probe')==token, 'Refusing unknown probe cleanup')
            run(D+['rm','--volumes',c['Id']])

def validate_model(stage, old, new, captured):
    need(old['services']['gitea']==new['services']['gitea'], 'Unexpected app change in proposed Compose')
    need(old['volumes']==new['volumes'] and old['networks']==new['networks'], 'Unexpected storage/network definition change')
    od,nd=old['services']['gitea-db'],new['services']['gitea-db']
    need(od['image']==PG17 and nd['image']==PG18, 'Unexpected database image pins')
    need({k:v for k,v in od.items() if k not in ['image','volumes']}=={k:v for k,v in nd.items() if k not in ['image','volumes']}, 'Unexpected DB configuration change')
    need(od['volumes'][0]['target']=='/var/lib/postgresql/data' and nd['volumes'][0]['target']=='/var/lib/postgresql', 'Wrong DB mount transition')
    for name in ['gitea','gitea-db']:
        s=old['services'][name]; c=captured[name]; im=dj('image','inspect',c['Image'])[0]
        need(s['container_name']==name and s['restart']==c['HostConfig']['RestartPolicy']['Name'], 'Runtime restart/container settings differ')
        normalize=lambda xs:{x if ':' in x else x+':true' for x in (xs or [])}
        need(normalize(s.get('security_opt'))==normalize(c['HostConfig'].get('SecurityOpt')), 'Runtime security options differ')
        logging=s.get('logging',{})
        need(c['HostConfig'].get('LogConfig')=={'Type':logging.get('driver'),'Config':logging.get('options',{})}, 'Runtime logging options differ')
        expected_labels={**(im['Config'].get('Labels') or {}),**s.get('labels',{})}
        actual_labels={k:v for k,v in c['Config']['Labels'].items() if not k.startswith('com.docker.compose.')}
        need(expected_labels==actual_labels, 'Additional or differing runtime labels require review: '+name)
        expected_networks={old['networks'][n]['name'] for n in s['networks']}
        need(expected_networks==set(c['NetworkSettings']['Networks']), 'Runtime networks differ')
        expected_ports={str(p['target'])+'/'+p.get('protocol','tcp'):[{'HostIp':p.get('host_ip',''),'HostPort':str(p['published'])}] for p in s.get('ports',[])}
        need(expected_ports==(c['HostConfig'].get('PortBindings') or {}), 'Runtime published ports differ')
        probe_environment(stage,name,s,env(c))

def stage_only(stage, captured):
    need(not (stage/'ready.private.json').exists(), 'Stage already prepared; use migrate mode or a fresh capture directory')
    for version,ref in [(17,BASE),(18,HEAD)]:
        target=stage/f'compose.pg{version}.yaml'
        need(not target.exists(), 'Refusing to overwrite a staged Compose file')
        content=run(['curl','--fail','--silent','--show-error','--location',f'https://raw.githubusercontent.com/DanielBoring/HomeLab/{ref}/gitea/compose.yaml'])
        save(target,content)
    a=env(captured['gitea'])
    save(stage/'environment.private.json',json.dumps({k:a[v] for k,v in MAPPING.items()},ensure_ascii=False).encode('utf-8'))
    old,new=model(stage,17),model(stage,18)
    validate_model(stage,old,new,captured)
    # Save exact local rollback image identities; no moving tag is used for rollback.
    override={'services':{n:{'image':captured[n]['Image']} for n in ['gitea','gitea-db']}}
    save(stage/'images.pg17.json',json.dumps(override).encode())
    files=['compose.pg17.yaml','compose.pg18.yaml','environment.private.json','images.pg17.json','containers.private.json','volumes.private.json']
    ready={'head':HEAD,'base':BASE,'files':{n:hashlib.sha256((stage/n).read_bytes()).hexdigest() for n in files},'app_id':captured['gitea']['Id'],'db_id':captured['gitea-db']['Id']}
    save(stage/'ready.private.json',json.dumps(ready).encode())
    print('STAGED: exact PG17/PG18 Compose; actual settings and create-only environment probes match. No live service stopped.')

def counts(db):
    sql='SELECT (SELECT count(*) FROM public."user"),(SELECT count(*) FROM public.repository),(SELECT count(*) FROM public.issue);'
    return dt('exec',db,'psql','-X','-w','-At','-v','ON_ERROR_STOP=1','-U','gitea','-d','gitea','-c',sql)
def wait_db(db):
    for _ in range(90):
        p=subprocess.run(D+['exec',db,'pg_isready','-h','127.0.0.1','-p','5432','-U','gitea','-d','postgres'],capture_output=True)
        if p.returncode==0:
            # Official-image initialization's temporary server has no TCP listener.
            finalized=dt('exec',db,'sh','-ec','test "$(cat /proc/1/comm)" = postgres && printf ready')
            if finalized=='ready':return
        time.sleep(2)
    raise RuntimeError('Database readiness timeout')
def wait_app(app):
    for _ in range(90):
        p=subprocess.run(D+['exec',app,'curl','-fsS','http://localhost:3000/api/healthz'],capture_output=True)
        if p.returncode==0:return
        time.sleep(2)
    raise RuntimeError('Gitea readiness timeout')

def resume_old(captured):
    db,app=captured['gitea-db']['Id'],captured['gitea']['Id']
    for name,c in captured.items(): need(dj('inspect',c['Id'])[0]['Image']==c['Image'], 'Original identity unavailable: '+name)
    if not dj('inspect',db)[0]['State']['Running']:dt('start',db)
    wait_db(db)
    if not dj('inspect',app)[0]['State']['Running']:dt('start',app)
    wait_app(app)
    print('Original source containers resumed after pre-switch failure.')

def migrate(stage,captured):
    ready=json.loads((stage/'ready.private.json').read_bytes())
    need(ready['head']==HEAD, 'Stage head mismatch')
    for n,h in ready['files'].items(): need(hashlib.sha256((stage/n).read_bytes()).hexdigest()==h, 'Staged artifact changed: '+n)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    cut=stage/('cutover-'+stamp);cut.mkdir(mode=0o700);os.chmod(cut,0o700)
    log=private(cut/'commands.private.log')
    app,db=captured['gitea']['Id'],captured['gitea-db']['Id'];old_dir=ROOT/('db.pg17-'+stamp)
    need(not old_dir.exists(), 'Old DB retention path already exists')
    save(cut/'old-db-path.txt',(str(old_dir)+'\n').encode())
    phase='before-stop'
    try:
        print('Stopping Gitea for the approved migration; GitOps/writers must remain paused.')
        phase='source-stopping';run(D+['stop','--time','120',app],log=log)
        need(not dj('inspect',app)[0]['State']['Running'], 'Source app did not stop')
        clients=dt('exec',db,'psql','-X','-w','-At','-U','gitea','-d','gitea','-c',"SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid();")
        need(clients=='0', 'Other DB clients remain; aborting before switch')
        baseline=counts(db);save(cut/'source-counts.txt',baseline.encode())
        with private(cut/'gitea.pg17.dump') as f:run(D+['exec',db,'pg_dump','--format=custom','--create','-U','gitea','-d','gitea'],output=f,log=log)
        with private(cut/'globals.private.sql') as f:run(D+['exec',db,'pg_dumpall','--globals-only','-U','gitea'],output=f,log=log)
        need((cut/'gitea.pg17.dump').stat().st_size>0 and (cut/'globals.private.sql').stat().st_size>0, 'Empty fresh backup')
        with (cut/'gitea.pg17.dump').open('rb') as f, private(cut/'dump-list.private.txt') as listing:
            q=subprocess.run(D+['exec','-i',db,'pg_restore','--list'],stdin=f,stdout=listing,stderr=log)
            need(q.returncode==0, 'Fresh dump archive listing failed')
        save(cut/'backup-sha256.json',json.dumps({n:hashlib.sha256((cut/n).read_bytes()).hexdigest() for n in ['gitea.pg17.dump','globals.private.sql']}).encode())
        run(D+['stop','--time','120',db],log=log)
        state=dj('inspect',db)[0]['State'];need(not state['Running'] and state['ExitCode']==0 and not state['OOMKilled'], 'PG17 shutdown not clean')
        # After down begins, container identities may disappear: fail closed, never auto-rename/rollback data.
        phase='removing-source-containers';run(compose(stage,17,'down'),log=log)
        phase='retaining-pg17-data';os.rename(ROOT/'db',old_dir)
        (ROOT/'db').mkdir(mode=0o700);os.chown(ROOT/'db',999,999);os.chmod(ROOT/'db',0o700)
        phase='initializing-pg18';run(compose(stage,18,'up','-d','gitea-db'),log=log)
        newdb=dj('inspect','gitea-db')[0];need(newdb['Config']['Image']==PG18, 'Unexpected new DB image')
        need(len(newdb['Mounts'])==1 and newdb['Mounts'][0]['Type']=='volume' and newdb['Mounts'][0]['Name']=='gitea_gitea-db' and newdb['Mounts'][0]['Destination']=='/var/lib/postgresql' and newdb['Mounts'][0]['RW'], 'Unexpected PG18 data mount')
        image18=dj('image','inspect',PG18)[0]
        expected18=dict(x.split('=',1) for x in image18['Config']['Env'])
        expected18.update({'POSTGRES_DB':'gitea','POSTGRES_USER':'gitea','POSTGRES_PASSWORD':env(captured['gitea-db'])['POSTGRES_PASSWORD']})
        need(env(newdb)==expected18, 'PG18 effective environment differs from image defaults plus captured DB settings')
        wait_db(newdb['Id'])
        phase='restoring-pg18'
        with (cut/'gitea.pg17.dump').open('rb') as f:
            p=subprocess.run(D+['exec','-i',newdb['Id'],'pg_restore','--exit-on-error','--clean','--if-exists','--create','-U','gitea','-d','postgres'],stdin=f,stdout=log,stderr=log)
            need(p.returncode==0, 'PG18 restore failed; app remains stopped')
        datadir=dt('exec',newdb['Id'],'psql','-X','-w','-At','-U','gitea','-d','gitea','-c','SHOW data_directory;')
        version=dt('exec',newdb['Id'],'psql','-X','-w','-At','-U','gitea','-d','gitea','-c','SHOW server_version;')
        need(datadir=='/var/lib/postgresql/18/docker' and version.startswith('18.6 '), 'Wrong restored engine/data path')
        need(counts(newdb['Id'])==baseline, 'Restored user/repository/issue counts differ')
        collation=dt('exec',newdb['Id'],'psql','-X','-w','-At','-U','gitea','-d','gitea','-c',"SELECT count(*) FROM pg_database WHERE datname='gitea' AND datcollversion IS DISTINCT FROM pg_database_collation_actual_version(oid);")
        need(collation=='0', 'Database collation version differs; app remains stopped for review')
        run(D+['exec',newdb['Id'],'psql','-X','-w','-v','ON_ERROR_STOP=1','-U','gitea','-d','gitea','-c','ANALYZE;'],output=log,log=log)
        phase='starting-gitea';run(compose(stage,18,'up','-d','gitea'),log=log)
        newapp=dj('inspect','gitea')[0];need(newapp['Image']==captured['gitea']['Image'], 'Gitea app image bytes changed')
        wait_app(newapp['Id'])
        need(counts(newdb['Id'])==baseline, 'Counts changed during acceptance')
        accepted=dj('inspect','gitea-db')[0]
        need(accepted['Id']==newdb['Id'] and accepted['Mounts']==newdb['Mounts'], 'PG18 identity/mount changed while starting app')
        phase='healthy-pending-user-checks'
        save(cut/'result.json',json.dumps({'phase':phase,'head':HEAD,'server_version':version,'counts':baseline,'old_pg17_dir':str(old_dir)}).encode())
        print('PG18 restore and Gitea health passed. Retained original PG17 data: '+str(old_dir))
        print('Keep GitOps paused. Verify login, repositories and SSH/HTTPS clones before merge/adoption; no PR merge performed.')
    except BaseException:
        print('FAILED at phase '+phase+'. Private evidence: '+str(cut),file=sys.stderr)
        if phase in ['before-stop','source-stopping']:
            try:resume_old(captured)
            except Exception:print('Original container restart failed; manual recovery required.',file=sys.stderr)
        else:
            if phase=='starting-gitea':
                try:
                    candidate=dj('inspect','gitea')[0]
                    if candidate['Id']!=app and candidate['Image']==captured['gitea']['Image'] and candidate['Config']['Labels'].get('com.docker.compose.project')=='gitea':
                        run(D+['stop','--time','120',candidate['Id']],log=log)
                except Exception:pass
            print('No automatic data rollback. Keep GitOps paused and preserve both database trees.',file=sys.stderr)
        raise
    finally:log.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['stage','migrate']);p.add_argument('directory');a=p.parse_args()
    stage=pathlib.Path(a.directory);host_guard(stage)
    captured={c['Name'].lstrip('/'):c for c in json.loads((stage/'containers.private.json').read_bytes())}
    vols={v['Name']:v for v in json.loads((stage/'volumes.private.json').read_bytes())}
    runtime_guard(inspect_named(),captured,vols)
    global COMPOSE_ENV
    COMPOSE_ENV={k:v for k,v in os.environ.items() if not k.startswith('COMPOSE_')}
    COMPOSE_ENV.update({k:env(captured['gitea'])[v] for k,v in MAPPING.items()})
    COMPOSE_ENV['COMPOSE_DISABLE_ENV_FILE']='1'
    if a.mode=='migrate':
        need(json.loads((stage/'environment.private.json').read_bytes())=={k:env(captured['gitea'])[v] for k,v in MAPPING.items()}, 'Captured settings mapping changed')
    if a.mode=='stage':stage_only(stage,captured)
    else:migrate(stage,captured)
if __name__=='__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Operator signal '+str(signum))
    for sig in [signal.SIGTERM,signal.SIGHUP]: signal.signal(sig,interrupted)
    try:main()
    except Exception as e:
        print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
