"""Persistent storage inventory and reversible, bounded workspace removal."""
import json,shutil,time,uuid
from pathlib import Path
from file_saving import write_text_atomic


class WorkspaceInventory:
    def __init__(self,window):self.window=window;self.store=window.store

    def items(self):
        from asset_helper import ASSETS
        result=[]
        for kind,ident,body in self.store.db.execute("SELECT kind,id,body FROM documents WHERE kind!='settings' ORDER BY kind,id"):
            doc=json.loads(body)
            result.append({'kind':kind,'id':ident,'name':str(doc.get('name',ident)) if isinstance(doc,dict) else ident})
        result.extend({'kind':'shared','id':key,'name':key} for key in self.store.shared())
        result.extend({'kind':'run','id':row[0],'name':row[1]+' // '+row[2]} for row in self.store.db.execute('SELECT id,name,status FROM runs ORDER BY started DESC'))
        for folder in ('models','textures','icons','backgrounds'):
            root=ASSETS.root/folder
            if root.is_dir():
                for path in root.iterdir():
                    if path.is_symlink():continue
                    result.append({'kind':'asset','id':path.relative_to(ASSETS.root).as_posix(),'name':folder+' / '+path.name})
        for descriptor in self.window.plugin_host.descriptors():
            result.append({'kind':'plugin','id':descriptor['id'],'name':descriptor['name'],'folder':descriptor.get('folder')})
        import os
        for folder,directories,filenames in os.walk(self.store.root,followlinks=False):
            directories[:]=[name for name in directories if name not in ('projects','trash','__pycache__')]
            for name in filenames:
                path=Path(folder)/name;relative=path.relative_to(self.store.root)
                if path.is_symlink() or name in ('shared.sqlite3','shared.sqlite3-wal','shared.sqlite3-shm') or name.endswith(('-wal','-shm')):continue
                result.append({'kind':'stored file','id':relative.as_posix(),'name':relative.as_posix()})
        return result

    def plan(self,item):
        from asset_helper import ASSETS
        kind,ident=item['kind'],item['id'];documents=[];references=[];files=[]
        if kind not in ('asset','plugin','shared','run','stored file'):
            documents.append((kind,ident))
            # Removing a dependency also removes the saved configurations that require it.
            pending=True
            while pending:
                pending=False
                for other in ('operator','workflow','schedule'):
                    for doc in self.store.list(other):
                        if (other,doc['id']) in documents:continue
                        refs=[doc]+doc.get('nodes',[])
                        if any(ref.get(k)==i for ref in refs for k,i in documents if k in ('project','profile','operator','workflow')):
                            documents.append((other,doc['id']));pending=True
            if kind=='project':
                doc=self.store.get(kind,ident);path=Path(doc['script']).resolve().parent
                managed=(self.store.root/'projects').resolve()
                if path!=managed and path.is_relative_to(managed) and path.is_dir():files.append(path)
            elif kind=='build':
                doc=self.store.get(kind,ident);path=Path(doc['path']).resolve()
                if path.is_relative_to(self.store.root/'projects') and path.is_file():files.append(path)
        elif kind=='asset':
            path=(ASSETS.root/ident).resolve()
            if path==ASSETS.root or not path.is_relative_to(ASSETS.root):raise ValueError('Asset path escapes the library')
            if path.exists():files.append(path)
            for name,entry in ASSETS.manifest.get('items',{}).items():
                for key,value in entry.items():
                    if isinstance(value,str) and (value==ident or value.startswith(ident+'/')):references.append((name,key))
            value=ASSETS.manifest.get('background','')
            if value==ident or value.startswith(ident+'/'):references.append(('', 'background'))
            value=ASSETS.manifest.get('logo','')
            if value==ident or value.startswith(ident+'/'):references.append(('', 'logo'))
        elif kind=='plugin':
            path=Path(item.get('folder') or self.window.plugin_host.root/ident).resolve()
            root=self.window.plugin_host.root.resolve()
            if path==root or not path.is_relative_to(root):raise ValueError('Plugin path escapes its managed directory')
            if path.exists():files.append(path)
        elif kind=='stored file':
            path=(self.store.root/ident).resolve()
            if path==self.store.db_path or not path.is_relative_to(self.store.root):raise ValueError('Cannot remove the active workspace database')
            if path.exists():files.append(path)
            for suffix in ('-wal','-shm'):
                sidecar=Path(str(path)+suffix)
                if sidecar.exists():files.append(sidecar)
        return {'documents':documents,'references':references,'files':files}

    def remove(self,item):
        from asset_helper import ASSETS
        if self.window.runner.jobs or self.window.runner.workflow:raise ValueError('Stop active operations before removing stored data')
        plan=self.plan(item);kind,ident=item['kind'],item['id']
        if kind=='profile' and ident=='default':raise ValueError('The default execution loadout is required; edit it instead')
        if kind=='stored file' and ident.split('/')[0] in self.window.plugin_host.enabled():
            raise ValueError('Disable the owning plugin before removing its stored files')
        if kind=='plugin' and ident in self.window.plugin_host.enabled():
            self.window.plugin_host.disable(ident)
        trash=self.store.root/'trash'/(str(int(time.time()))+'-'+uuid.uuid4().hex[:8]);trash.mkdir(parents=True)
        receipt={'item':item,'documents':[],'shared':None,'run':None,'manifest':ASSETS.manifest,'files':[],
            'references':plan['references']}
        for k,i in plan['documents']:receipt['documents'].append([k,i,self.store.get(k,i)])
        if kind=='shared':receipt['shared']=[ident,self.store.shared()[ident]]
        if kind=='run':receipt['run']=self.store.db.execute('SELECT * FROM runs WHERE id=?',(ident,)).fetchone()
        write_text_atomic(trash/'receipt.json',json.dumps(receipt,indent=2))
        moved=[]
        try:
            for index,path in enumerate(plan['files']):
                target=trash/('file-'+str(index));shutil.move(str(path),str(target));moved.append((path,target))
                receipt['files'].append([str(path),str(target)])
                write_text_atomic(trash/'receipt.json',json.dumps(receipt,indent=2))
            manifest=json.loads(json.dumps(ASSETS.manifest))
            for name,key in plan['references']:
                if name:manifest['items'][name].pop(key,None)
                else:manifest.pop(key,None)
            if kind=='project':manifest.get('items',{}).pop('project:'+ident,None)
            ASSETS.save_manifest(manifest)
            with self.store.db:
                for k,i in plan['documents']:self.store.db.execute('DELETE FROM documents WHERE kind=? AND id=?',(k,i))
                if kind=='shared':self.store.db.execute('DELETE FROM shared WHERE key=?',(ident,))
                if kind=='run':self.store.db.execute('DELETE FROM runs WHERE id=?',(ident,))
                if kind=='plugin':
                    enabled=[i for i in self.store.get('settings','plugins',[]) if i!=ident]
                    self.store.db.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?)',('settings','plugins',json.dumps(enabled)))
                    tombstones=self.window.plugin_host.root/'.removed.json'
                    removed=json.loads(tombstones.read_text(encoding='utf-8')) if tombstones.exists() else []
                    write_text_atomic(tombstones,json.dumps(sorted(set(removed+[ident]))))
            self.store.put('settings','seeded',True)
        except Exception:
            for path,target in reversed(moved):shutil.move(str(target),str(path))
            ASSETS.save_manifest(receipt['manifest'])
            receipt['restored']=True;receipt['failed']=True;write_text_atomic(trash/'receipt.json',json.dumps(receipt,indent=2));raise
        return trash

    def restore_latest(self):
        from asset_helper import ASSETS
        receipts=sorted((self.store.root/'trash').glob('*/receipt.json'),key=lambda path:path.stat().st_mtime,reverse=True)
        path=next((p for p in receipts if not json.loads(p.read_text(encoding='utf-8')).get('restored')),None)
        if path is None:raise ValueError('No removal to restore')
        data=json.loads(path.read_text(encoding='utf-8'))
        for k,i,doc in data['documents']:
            if self.store.get(k,i) is not None:raise ValueError('A stored record already uses this ID; restore would overwrite it')
        for original,target in data['files']:
            original=Path(original).resolve();target=Path(target).resolve()
            allowed=(self.store.root.resolve(),ASSETS.root.resolve(),self.window.plugin_host.root.resolve())
            if not any(original!=root and original.is_relative_to(root) for root in allowed) or not target.is_relative_to(path.parent.resolve()):raise ValueError('Invalid restoration path')
            if original.exists():raise ValueError('A file already occupies the original path')
            if not target.exists():raise ValueError('The removed file is no longer in trash')
        if data['shared'] and data['shared'][0] in self.store.shared():raise ValueError('Shared key already exists')
        # Restore only removed assignments, preserving assignments made since removal.
        manifest=json.loads(json.dumps(ASSETS.manifest))
        for name,key in data.get('references',[]):
            if name:
                current=manifest.setdefault('items',{}).setdefault(name,{})
                if key not in current:current[key]=data['manifest']['items'][name][key]
            elif key not in manifest:manifest[key]=data['manifest'][key]
        if data['item']['kind']=='project':
            key='project:'+data['item']['id']
            if key not in manifest.get('items',{}) and key in data['manifest'].get('items',{}):
                manifest.setdefault('items',{})[key]=data['manifest']['items'][key]
        moved=[];previous=json.loads(json.dumps(ASSETS.manifest))
        try:
            for original,target in data['files']:
                Path(original).parent.mkdir(parents=True,exist_ok=True);shutil.move(target,original);moved.append((original,target))
            with self.store.db:
                for k,i,doc in data['documents']:
                    self.store.db.execute('INSERT INTO documents VALUES (?,?,?)',(k,i,json.dumps(doc)))
                if data['shared']:
                    key,value=data['shared'];self.store.db.execute('INSERT INTO shared VALUES (?,?)',(key,json.dumps(value)))
                if data['run']:self.store.db.execute('INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,?,?)',data['run'])
                ASSETS.save_manifest(manifest)
        except Exception:
            for original,target in reversed(moved):shutil.move(original,target)
            ASSETS.save_manifest(previous);raise
        data['restored']=True;write_text_atomic(path,json.dumps(data,indent=2))
        if data['item']['kind']=='plugin':
            tombstones=self.window.plugin_host.root/'.removed.json'
            if tombstones.exists():write_text_atomic(tombstones,json.dumps([i for i in json.loads(tombstones.read_text(encoding='utf-8')) if i!=data['item']['id']]))
        return data['item']['name']
