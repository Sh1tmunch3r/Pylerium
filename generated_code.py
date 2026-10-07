"""Remove response wrappers without stripping backticks inside Python strings."""
import ast
import re
import textwrap


def clean_python_response(text):
    if not isinstance(text,str):
        raise ValueError('The model response must be text')
    lines = text.splitlines()
    if lines and lines[0].strip().lower() in ('python','python3','py'):
        text = '\n'.join(lines[1:])
    # Already valid Python must be preserved, including Markdown examples in strings.
    try:
        ast.parse(text)
        if text.strip():
            return text.rstrip('\n')+'\n'
    except SyntaxError:
        pass
    text = text.replace('\r\n', '\n').replace('\ufeff', '')
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S | re.I).strip()
    lines = text.splitlines()
    blocks, current, language = [], None, ''
    fence = re.compile(r'^\s*((?:`\s*){3,}|~{3,})\s*([\w+-]*)\s*$')
    for line in lines:
        match = fence.match(line)
        if match:
            if current is None:
                current, language = [], match.group(2).lower()
            else:
                blocks.append((language, '\n'.join(current)))
                current = None
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        blocks.append((language, '\n'.join(current)))
    selected = [body for lang, body in blocks if lang in ('python','py','python3','')]
    if selected:
        text = '\n\n'.join(selected)
    elif blocks:
        raise ValueError('The response contains no Python code block')
    else:
        # A standalone language tag is a common malformed response wrapper.
        if lines and lines[0].strip().lower() in ('python','python3','py'):
            text = '\n'.join(lines[1:])
    text = textwrap.dedent(text).strip('\n')
    if not text.strip():
        raise ValueError('The model returned an empty draft')
    return text + '\n'


def validate_python(text):
    ast.parse(text)
    return text
