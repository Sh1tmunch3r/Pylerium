"""Reusable, bounded local tool operations. No Qt, global state or file mutation."""
import ast
import base64
import csv
import difflib
import hashlib
import io
import json
import os
import re
import sqlite3
from pathlib import Path

TOOLS = {
    'json_lab':('JSON Lab','Validate, format, flatten and inspect JSON.','Paste JSON',''),
    'csv_profiler':('CSV Profiler','Column types, missing values, distinct counts and numeric summaries.','Paste CSV with a header',''),
    'regex_lab':('Regex Lab','Search text with capture groups and match locations.','Text to search','Regular expression'),
    'text_diff':('Text Diff','Unified line diff between two versions.','Original text','Replacement text'),
    'file_integrity':('File Integrity','Stream SHA-256 fingerprints and compare expected checksums.','File path','Optional expected SHA-256'),
    'duplicate_finder':('Duplicate Finder','Find identical files by size and streaming SHA-256; report only.','Folder path',''),
    'file_catalog':('File Catalog','Search a folder and inventory file sizes and extensions.','Folder path','Optional filename search'),
    'sqlite_explorer':('SQLite Explorer','Read-only queries, table schemas and bounded result previews.','SQLite database path','SELECT query, or blank for schema'),
    'log_analyzer':('Log Analyzer','Count severity levels and find repeated messages.','Paste log text','Optional search text'),
    'python_inspector':('Python Inspector','Inspect syntax, imports, functions, classes and complexity indicators.','Paste Python source',''),
    'codec_lab':('Codec Lab','UTF-8 Base64, URL encoding and text fingerprints.','Input text','encode or decode'),
    'markdown_report':('Report Builder','Create a portable Markdown report from structured records.','Paste JSON records','Report title'),
}


def fingerprint(path,cancel=None):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            if cancel and cancel.is_set(): raise RuntimeError('Cancelled')
            digest.update(chunk)
    return digest.hexdigest()


def files(root,cancel=None):
    root=Path(root).expanduser().resolve()
    if not root.is_dir(): raise ValueError('Choose an existing directory')
    count=0
    for directory,folders,names in os.walk(root):
        folders[:]=[name for name in folders if name not in ('.git','__pycache__','node_modules') and not Path(directory,name).is_symlink()]
        for name in names:
            if cancel and cancel.is_set(): raise RuntimeError('Cancelled')
            path=Path(directory,name)
            if path.is_symlink(): continue
            count+=1
            if count>20000: raise ValueError('Folder exceeds 20,000 files; choose a smaller folder')
            yield path


def execute(kind,text,option='',cancel=None):
    if kind not in TOOLS: raise ValueError('Unknown tool')
    if len(text)>4_000_000 or len(option)>4_000_000: raise ValueError('Input exceeds 4 MB')
    result=None
    if kind=='json_lab':
        data=json.loads(text)
        def flatten(value,prefix=''):
            if isinstance(value,dict):
                for key,item in value.items(): yield from flatten(item,prefix+'/'+str(key).replace('~','~0').replace('/','~1'))
            elif isinstance(value,list):
                for i,item in enumerate(value): yield from flatten(item,prefix+'/'+str(i))
            else: yield prefix,value
        result={'formatted':data,'leaf_paths':dict(flatten(data))}
    elif kind=='csv_profiler':
        reader=csv.DictReader(io.StringIO(text));rows=[]
        for row in reader:
            if len(rows)>=100000: raise ValueError('CSV preview limit: 100,000 rows')
            rows.append(row)
        columns={}
        for key in reader.fieldnames or []:
            values=[row.get(key) for row in rows];present=[v for v in values if v not in ('',None)]
            entry={'missing':len(values)-len(present),'distinct':len(set(present))}
            try:
                numbers=[float(v) for v in present]
                if numbers: entry.update(min=min(numbers),max=max(numbers),mean=sum(numbers)/len(numbers))
            except ValueError: entry['type']='text'
            columns[key]=entry
        result={'rows':len(rows),'columns':columns,'preview':rows[:20]}
    elif kind=='regex_lab':
        # Runs in the standalone Workshop interpreter, not a GUI worker: pathological
        # regexes can monopolize CPython's GIL. The app runner enforces its timeout.
        matches=[]
        for match in re.finditer(option,text):
            matches.append({'span':match.span(),'text':match.group(),'groups':match.groups(),'named':match.groupdict()})
            if len(matches)>=1000: break
        result={'matches':matches,'limit':1000}
    elif kind=='text_diff':
        return ''.join(difflib.unified_diff(text.splitlines(True),option.splitlines(True),fromfile='before',tofile='after')) or 'No differences'
    elif kind=='file_integrity':
        digest=fingerprint(text.strip(),cancel)
        result={'path':text.strip(),'sha256':digest,'expected_matches':digest.lower()==option.strip().lower() if option.strip() else None}
    elif kind in ('duplicate_finder','file_catalog'):
        paths=list(files(text.strip(),cancel)); errors=[]; records=[]; sizes={}
        for path in paths:
            try:
                size=path.stat().st_size
                if kind=='file_catalog' and option.casefold() in path.name.casefold(): records.append({'path':str(path),'bytes':size,'extension':path.suffix.lower()})
                sizes.setdefault(size,[]).append(path)
            except OSError as exc: errors.append(str(exc))
        if kind=='duplicate_finder':
            groups={}
            for size,items in sizes.items():
                if len(items)<2: continue
                for path in items:
                    try: groups.setdefault((size,fingerprint(path,cancel)),[]).append(str(path))
                    except OSError as exc: errors.append(str(exc))
            records=[{'bytes':size,'sha256':digest,'paths':items,'recoverable_bytes':size*(len(items)-1)} for (size,digest),items in groups.items() if len(items)>1]
        result={'scanned':len(paths),'records':records,'errors':errors}
    elif kind=='sqlite_explorer':
        path=Path(text.strip()).resolve()
        if not path.is_file(): raise ValueError('Choose an existing SQLite database')
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)
        try:
            db.execute('PRAGMA query_only=ON')
            ticks=[0]
            def stop():
                ticks[0]+=1
                return int(ticks[0]>10000 or bool(cancel and cancel.is_set()))
            db.set_progress_handler(stop,1000)
            cursor=db.execute(option.strip() or "SELECT name,type,sql FROM sqlite_master ORDER BY name")
            rows=cursor.fetchmany(501)
            result={'columns':[column[0] for column in cursor.description or []],'rows':rows[:500],'truncated':len(rows)>500}
        finally: db.close()
    elif kind=='log_analyzer':
        from collections import Counter
        lines=text.splitlines();counts=Counter()
        for line in lines:
            severity=re.search(r'\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b',line,re.I)
            counts[(severity.group().upper() if severity else 'OTHER')]+=1
        result={'lines':len(lines),'severity':dict(counts),'repeated':Counter(lines).most_common(20),'search':[line for line in lines if option and option.casefold() in line.casefold()][:500]}
    elif kind=='python_inspector':
        tree=ast.parse(text)
        result={'imports':[],'functions':[],'classes':[],'branches':0}
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)): result['imports'].append(ast.unparse(node))
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): result['functions'].append({'name':node.name,'line':node.lineno,'arguments':ast.unparse(node.args)})
            if isinstance(node,ast.ClassDef): result['classes'].append({'name':node.name,'line':node.lineno})
            if isinstance(node,(ast.If,ast.For,ast.While,ast.Try,ast.Match)): result['branches']+=1
    elif kind=='codec_lab':
        from urllib.parse import quote,unquote
        result=({'base64_decoded':base64.b64decode(text,validate=True).decode('utf-8'),'url_decoded':unquote(text)} if option.strip().lower()=='decode' else {'base64':base64.b64encode(text.encode()).decode(),'url_encoded':quote(text,safe=''),'sha256':hashlib.sha256(text.encode()).hexdigest()})
    elif kind=='markdown_report':
        records=json.loads(text)
        if not isinstance(records,list) or not all(isinstance(row,dict) for row in records): raise ValueError('Expected a JSON array of objects')
        columns=list(dict.fromkeys(key for row in records for key in row))
        def escape(value): return str(value).replace('|','\\|').replace('\n','<br>')
        return '# '+(option or 'Workspace report')+'\n\n'+' | '.join(map(escape,columns))+'\n'+' | '.join('---' for _ in columns)+'\n'+'\n'.join(' | '.join(escape(row.get(key,'')) for key in columns) for row in records)
    return json.dumps(result,indent=2,ensure_ascii=False,default=str)
