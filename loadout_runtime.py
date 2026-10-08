"""Child-process pipeline; runs outside the Qt UI thread."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def elevated_launch(config,target,args,hidden=False):
    """Wait for the actual elevated payload and stream its combined output."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='pylerium-elevated-') as folder:
        root=Path(folder);launcher=root/'launch.py';log=root/'output.log'
        log.touch()
        environment=dict(os.environ);environment['PYLERIUM_EXECUTION_LOADOUT']=json.dumps(config)
        command=[sys.executable,'-u',str(Path(__file__).resolve()),target,*args]
        launcher.write_text(
            'import ctypes,os,subprocess,threading,time\n'
            'os.environ.update('+repr(environment)+')\n'
            'kernel=ctypes.windll.kernel32\n'
            'kernel.OpenProcess.restype=ctypes.c_void_p\n'
            'kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]\n'
            'kernel.CloseHandle.argtypes=[ctypes.c_void_p]\n'
            'parent=kernel.OpenProcess(0x100000,False,'+str(os.getpid())+')\n'
            'done=threading.Event()\n'
            'with open('+repr(str(log))+',"ab",buffering=0) as output:\n'
            ' child=subprocess.Popen('+repr(command)+',stdout=output,stderr=subprocess.STDOUT,cwd='+repr(os.getcwd())+')\n'
            ' def monitor():\n'
            '  while not done.wait(.2):\n'
            '   if not parent or kernel.WaitForSingleObject(parent,0)==0:\n'
            '    subprocess.run(["taskkill","/PID",str(child.pid),"/T","/F"],stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)\n'
            '    return\n'
            ' threading.Thread(target=monitor,daemon=True).start()\n'
            ' code=child.wait();done.set()\n'
            ' if parent:kernel.CloseHandle(parent)\n'
            'raise SystemExit(code)\n',encoding='utf-8')
        def quote(value): return "'"+str(value).replace("'","''")+"'"
        script=("$ErrorActionPreference='Stop'; try { $child=Start-Process -FilePath "+quote(sys.executable)+
            " -ArgumentList "+quote(subprocess.list2cmdline(['-u',str(launcher)]))+
            " -WorkingDirectory "+quote(os.getcwd())+" -Verb RunAs -WindowStyle "+('Hidden' if hidden else 'Normal')+
            " -Wait -PassThru; exit $child.ExitCode } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }")
        print('Requesting administrator access; waiting for the project to finish…',flush=True)
        process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],creationflags=subprocess.CREATE_NO_WINDOW)
        with log.open('rb') as stream:
            def forward():
                data=stream.read()
                if data:sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
            while process.poll() is None:forward();time.sleep(.05)
            forward()
        return process.returncode


def main():
    config=json.loads(os.environ['PYLERIUM_EXECUTION_LOADOUT'])
    target=sys.argv[1]; args=sys.argv[2:]
    policies=set(config.get('perks',[])) | {p for group in config.get('policy_slots',{}).values() for p in group}
    if 'juggernaut' in policies and os.name=='nt':
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            config['perks']=[p for p in config.get('perks',[]) if p!='juggernaut']
            config['policy_slots']={k:[p for p in v if p!='juggernaut'] for k,v in config.get('policy_slots',{}).items()}
            return elevated_launch(config,target,args,'ninja' in policies)
    executable=sys.executable
    hidden={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' and 'ninja' in policies else {}
    setup_output={'stdout':sys.stdout.buffer,'stderr':subprocess.STDOUT,**hidden}
    if 'ghost' in policies:
        environment=Path('.venv').resolve(); executable=str(environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))
        if not Path(executable).is_file(): subprocess.run([sys.executable,'-m','venv','--system-site-packages',str(environment)],check=True,**setup_output)
    if 'ghost' in policies:
        print('Ghost: using project virtual environment (shared SDK dependencies available).',flush=True)
        settings=environment/'pyvenv.cfg'
        if settings.is_file():
            text=settings.read_text(encoding='utf-8')
            updated=text.replace('include-system-site-packages = false','include-system-site-packages = true')
            if updated!=text:settings.write_text(updated,encoding='utf-8')
        os.environ['VIRTUAL_ENV']=str(environment)
        os.environ['PATH']=str(Path(executable).parent)+os.pathsep+os.environ.get('PATH','')
    if 'scavenger' in policies:
        if Path('requirements.txt').is_file():
            subprocess.run([executable,'-m','pip','install','-r','requirements.txt'],check=True,**setup_output)
        else:
            print('Scavenger: no requirements.txt; using available dependencies.',flush=True)
    if 'sleight_of_hand' in policies: subprocess.run([executable,'-m','ruff','format',target],check=True,**setup_output)
    if config.get('wildcard')=='overkill':
        os.environ['OMP_NUM_THREADS']=str(os.cpu_count() or 1); os.environ['PYLERIUM_WORKERS']=str(os.cpu_count() or 1)
    if config.get('wildcard')=='danger_close': os.environ['CUDA_VISIBLE_DEVICES']='0'
    tactical=config.get('tactical_hook')
    if tactical=='debug': os.environ['PYLERIUM_LOG_LEVEL']='DEBUG'
    prefix=[executable,'-u']
    if tactical=='warnings': prefix+=['-W','error']
    if tactical=='profiler': prefix+=['-m','cProfile','-o','loadout.prof']
    if tactical=='debug':
        prefix+=['-c',"import logging,runpy,sys; logging.basicConfig(level=logging.DEBUG); p=sys.argv.pop(1); sys.argv[0]=p; runpy.run_path(p,run_name='__main__')"]
    hidden={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' and 'ninja' in policies else {}
    companions=[]; started=time.time(); code=0; output=[]
    def run_command(command,collect=False):
        # Explicit pipes preserve output with CREATE_NO_WINDOW and GUI interpreters.
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**hidden)
        try:
            for line in iter(process.stdout.readline,b''):
                sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
                if collect:output.append(line.decode('utf-8','replace'))
            return process.wait()
        finally:
            process.stdout.close()
    def hook(command):
        result=run_command(command)
        if result and 'hardline' not in policies:raise subprocess.CalledProcessError(result,command)
    try:
        for task in config.get('secondary_target',[]):
            command=[executable,'-u',task['script'],*task.get('args',[])]
            if task.get('run_mode','pre_execution')=='companion': companions.append(subprocess.Popen(command,stdout=sys.stdout.buffer,stderr=subprocess.STDOUT,**hidden))
            else: hook(command)
        print('Executing project: '+target,flush=True)
        for _ in range(config.get('passes',1) if config.get('wildcard')=='repeat' else 1):
            code=run_command([*prefix,target,*args],collect=config.get('lethal_hook')=='json')
            if code: break
        lethal=config.get('lethal_hook')
        if lethal=='json': Path('loadout-result.json').write_text(json.dumps({'script':target,'args':args,'exit_code':code,'duration':time.time()-started,'output':''.join(output)},indent=2),encoding='utf-8')
        if code==0:
            if lethal=='script':
                if not config.get('post_script'): raise ValueError('Set post_script before using a custom output hook')
                hook([executable,config['post_script']])
    finally:
        for process in companions:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
    return code

if __name__=='__main__':
    sys.exit(main())
