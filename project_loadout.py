"""Dynamic project execution loadouts and extensible registries."""
from pathlib import Path
import copy

POLICIES = {
    'ghost': 'Ghost / isolated virtual environment',
    'scavenger': 'Scavenger / install requirements',
    'juggernaut': 'Juggernaut / request administrator launch',
    'ninja': 'Ninja / hidden console',
    'sleight_of_hand': 'Sleight of Hand / Ruff format',
    'hardline': 'Hardline / continue after optional hook failure',
}
TACTICALS = {'none': 'None', 'profiler': 'Stim / cProfile', 'debug': 'Snapshot / debug logging', 'warnings': 'Strict warnings'}
LETHALS = {'none': 'None', 'json': 'Semtex / JSON execution report', 'script': 'Custom post-run script'}
WILDCARDS = {'none': 'None', 'overkill': 'Overkill / CPU worker hint', 'danger_close': 'Danger Close / CUDA device hint', 'repeat': 'Multiple execution passes'}

def default_loadout(project):
    return {'schema_version': 1, 'loadout_id': project['id'],
        'primary_target': {'script': project['script'], 'attachments_flags': project.get('args', []), 'attachments': {}},
        'secondary_target': [], 'context': {'env_file': '', 'env': {}},
        'perks': [], 'policy_slots': {k: [] for k in ('perk1','perk2','perk3','specialty')},
        'tactical_hook': 'none', 'lethal_hook': 'none', 'post_script': '',
        'wildcard': 'none', 'passes': 1}

def validate_loadout(value):
    value = copy.deepcopy(value)
    if not isinstance(value, dict): raise ValueError('Loadout must be a JSON object')
    # Older saved loadouts must never trigger packaging during Run.
    if value.get('lethal_hook') in ('pyinstaller','build_compiler'):
        value['lethal_hook']='none'
    primary = value['primary_target']
    if not isinstance(primary['script'], str) or not primary['script']: raise ValueError('Choose an entry point')
    flags = primary.get('attachments_flags', [])
    attachments = primary.get('attachments', {})
    if not isinstance(attachments, dict): raise ValueError('Attachments must be a key / flag-array object')
    for group in [flags, *attachments.values()]:
        if not isinstance(group, list) or not all(isinstance(x,str) for x in group): raise ValueError('Arguments must be JSON arrays of strings')
    secondary = value.get('secondary_target', [])
    if isinstance(secondary, dict): secondary = [secondary] if secondary.get('script') else []
    if not isinstance(secondary, list): raise ValueError('Secondary pipeline must be an array')
    for task in secondary:
        if not isinstance(task,dict) or not isinstance(task.get('script'),str) or task.get('run_mode','pre_execution') not in ('pre_execution','companion'): raise ValueError('Invalid auxiliary script or run mode')
        args=task.get('args',[])
        if not isinstance(args,list) or not all(isinstance(x,str) for x in args): raise ValueError('Auxiliary arguments must be strings')
    value['secondary_target'] = secondary
    context = value.get('context', {})
    if not isinstance(context,dict) or not isinstance(context.get('env',{}),dict): raise ValueError('Context needs env_file and an environment object')
    policies = value.get('perks', []) + [p for group in value.get('policy_slots',{}).values() for p in group]
    if any(p not in POLICIES for p in policies): raise ValueError('Unknown policy ID')
    for key,registry in [('tactical_hook',TACTICALS),('lethal_hook',LETHALS),('wildcard',WILDCARDS)]:
        if value.get(key,'none') not in registry: raise ValueError('Unknown '+key)
    if not isinstance(value.get('passes',1),int) or not 1 <= value.get('passes',1) <= 100: raise ValueError('Passes must be 1–100')
    return value

def prepare_launch(project, profile, loadout):
    value = validate_loadout(loadout)
    project, profile = copy.deepcopy(project), copy.deepcopy(profile)
    cwd = Path(project['cwd'])
    script = Path(value['primary_target']['script'])
    project['script'] = str(script if script.is_absolute() else cwd/script)
    project['args'] = value['primary_target'].get('attachments_flags',[]) + [a for group in value['primary_target'].get('attachments',{}).values() for a in group]
    env = dict(profile.get('env',{}))
    context = value.get('context',{})
    if context.get('env_file'):
        path = Path(context['env_file']); path = path if path.is_absolute() else cwd/path
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('export '): line=line[7:]
            key,sep,val=line.partition('=')
            if not sep or not key.strip(): raise ValueError('Invalid environment file line')
            env[key.strip()] = val.strip().strip('\"\'')
    env.update(context.get('env',{}))
    profile['env'] = env
    project['_execution_loadout'] = value
    return project, profile
