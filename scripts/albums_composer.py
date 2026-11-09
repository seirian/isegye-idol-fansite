"""Permit only Composer root-project VCS labels to differ; preserve deployed bytes."""
import hashlib,json,re

def normalized_root_metadata(raw: bytes) -> str:
    if not isinstance(raw,bytes) or len(raw)>16384:raise ValueError('Invalid Composer metadata size')
    text=raw.decode('utf-8')
    for name in ('root','isegye/private-google-access'):
        pattern=re.compile(r"^([ ]*'"+re.escape(name)+r"' => array\(\n)([\s\S]*?)(^[ ]*\),\n)",re.M)
        blocks=list(pattern.finditer(text))
        if len(blocks)!=1:raise ValueError('Unexpected root metadata layout')
        block=blocks[0];body=block.group(2)
        for field in ('pretty_version','version','reference'):
            p=re.compile(r"^([ ]*'"+field+r"' => )'([A-Za-z0-9._/+:-]{1,160})'(,[ ]*)$",re.M)
            matches=list(p.finditer(body))
            if len(matches)!=1:raise ValueError('Unexpected root version field')
            if field=='reference' and not re.fullmatch('[a-f0-9]{40}',matches[0].group(2)):raise ValueError('Unexpected root reference')
            body=p.sub(lambda m:m.group(1)+"'ROOT_BUILD_LABEL'"+m.group(3),body)
        text=text[:block.start()]+block.group(1)+body+block.group(3)+text[block.end():]
    return text

def preserved_root_metadata(old:bytes,new:bytes)->bytes:
    if old==new:return old
    if normalized_root_metadata(old)!=normalized_root_metadata(new):raise ValueError('Composer dependency or executable metadata changed')
    return old

def runtime_id(files:dict[str,bytes])->str:
    manifest={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}
    return 'g'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:12]
