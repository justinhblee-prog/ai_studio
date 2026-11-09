#!/usr/bin/env python3
"""Static audit of literal JSON request bodies in Viewer fetch() calls vs runtime OpenAPI."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OPENAPI = PROJECT / "docs/api/openapi.runtime.v1.json"
SRC = ROOT / "src"


def matching(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0; quote = None; escaped = False; i = start
    while i < len(text):
        c = text[i]
        if quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote: quote = None
        else:
            if c in "'\"`": quote = c
            elif c == opening: depth += 1
            elif c == closing:
                depth -= 1
                if depth == 0: return i
        i += 1
    raise ValueError(f"unclosed {opening} at {start}")


def top_level_keys(obj: str) -> list[str]:
    keys=[]; depth=0; quote=None; escaped=False; segment=1
    def add(part: str):
        part=part.strip()
        m=re.match(r"([A-Za-z_$][\w$]*)(?:\s*:|$)", part)
        if m: keys.append(m.group(1))
    for i,c in enumerate(obj):
        if quote:
            if escaped: escaped=False
            elif c == "\\": escaped=True
            elif c == quote: quote=None
            continue
        if c in "'\"`": quote=c
        elif c in "{[(": depth += 1
        elif c in "}])":
            if depth == 1: add(obj[segment:i])
            depth -= 1
        elif c == ',' and depth == 1:
            add(obj[segment:i]); segment=i+1
    return list(dict.fromkeys(keys))


def extract_calls(path: Path):
    text=path.read_text(encoding='utf-8')
    for m in re.finditer(r"fetch\s*\(", text):
        op_start=m.end(); op_end=matching(text, m.start(), '(', ')')
        call=text[m.start():op_end+1]
        urlm=re.search(r"fetch\s*\(\s*`([^`]+)`", call, re.S)
        if not urlm: continue
        url=urlm.group(1).split('?',1)[0]
        url=re.sub(r'^\$\{base\}', '', url)
        # only requests with a JSON.stringify literal body
        bm=re.search(r"body\s*:\s*JSON\.stringify\s*\(\s*\{", call, re.S)
        if not bm: continue
        brace=call.find('{', bm.start())
        end=matching(call, brace, '{','}')
        obj=call[brace:end+1]
        methodm=re.search(r"method\s*:\s*['\"](POST|PUT|PATCH)['\"]", call, re.I)
        method=(methodm.group(1) if methodm else 'GET').lower()
        # Convert template interpolations to OpenAPI path parameters.
        normalized=re.sub(r"\$\{encodeURIComponent\([^}]+\)\}", "{param}", url)
        normalized=re.sub(r"\$\{[A-Za-z_$][\w$]*\}", "{dynamic}", normalized)
        yield {"file":path.name,"line":text.count('\n',0,m.start())+1,"method":method,"path":normalized,"keys":top_level_keys(obj)}


def schema_for(op, spec):
    schema=op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema')
    if not schema: return None
    if '$ref' in schema:
        return spec.get('components',{}).get('schemas',{}).get(schema['$ref'].rsplit('/',1)[-1])
    return schema


def main():
    spec=json.loads(OPENAPI.read_text(encoding='utf-8'))
    operations=spec.get('paths',{})
    findings=[]; checked=[]; skipped=[]
    for file in sorted(SRC.glob('*.tsx')):
        for call in extract_calls(file):
            # Resolve static route, or dynamic action segment against known paths.
            candidates=[]
            call_segments=call['path'].strip('/').split('/')
            for p, methods in operations.items():
                if call['method'] not in methods: continue
                route_segments=p.strip('/').split('/')
                if len(route_segments) != len(call_segments): continue
                matched=True
                for actual, declared in zip(call_segments, route_segments):
                    if (actual.startswith('{') and actual.endswith('}') or
                        declared.startswith('{') and declared.endswith('}')):
                        continue
                    if actual != declared:
                        matched=False; break
                if matched: candidates.append((p,methods[call['method']]))
            if not candidates:
                skipped.append({**call,"reason":"no matching runtime operation (dynamic route or route gap)"}); continue
            sent=set(call['keys'])
            candidates_with_schema=[(p,op,schema_for(op,spec)) for p,op in candidates]
            candidates_with_schema=[item for item in candidates_with_schema if item[2] is not None]
            compatible=[]
            for p,op,schema in candidates_with_schema:
                props=set(schema.get('properties',{})); required=set(schema.get('required',[]))
                if sent <= props and required <= sent:
                    compatible.append((p,op,schema))
            if len(compatible) == 1:
                candidates_with_schema=compatible
            elif len(compatible) > 1:
                # Multiple action values may intentionally share the same request model.
                signatures={(tuple(sorted(s.get('properties',{}))),tuple(sorted(s.get('required',[])))) for _,_,s in compatible}
                if len(signatures) == 1:
                    candidates_with_schema=compatible[:1]
                else:
                    findings.append({**call,"error":"ambiguous compatible route schemas","candidates":[p for p,_,_ in compatible]}); continue
            elif len(candidates_with_schema) > 1:
                findings.append({**call,"error":"ambiguous route schemas; no candidate matches body keys","candidates":[p for p,_,_ in candidates_with_schema]}); continue
            if not candidates_with_schema:
                findings.append({**call,"error":"Viewer sends JSON body but no matching runtime operation has an application/json request schema","candidates":[p for p,_ in candidates]}); continue
            operation_candidates=[item[0] for item in candidates_with_schema]
            operation=operation_candidates[0]
            _, _, schema=candidates_with_schema[0]
            props=set(schema.get('properties',{})); required=set(schema.get('required',[]))
            unknown=sorted(sent-props); missing=sorted(required-sent)
            item={**call,"operation":operation,"operation_candidates":operation_candidates,"schema":schema.get('title'),"unknown":unknown,"missing_required":missing}
            checked.append(item)
            if unknown or missing:
                findings.append({**item,"error":"request body key mismatch"})
    enum_checks=[]
    enum_bindings=[
        ("PhotoDraftWorkspace.tsx", "operation", "PhotoOperation", "PhotoDraftInput"),
        ("PhotoDraftWorkspace.tsx", "output_format", "OutputFormat", "PhotoDraftInput"),
    ]
    for filename, field, alias, model in enum_bindings:
        source=(SRC/filename).read_text(encoding="utf-8")
        match=re.search(rf"type\s+{re.escape(alias)}\s*=\s*([^;]+);",source)
        prop=spec.get("components",{}).get("schemas",{}).get(model,{}).get("properties",{}).get(field,{})
        viewer_values=set(re.findall(r"['\"]([^'\"]+)['\"]",match.group(1))) if match else set()
        api_values=set(prop.get("enum",[]))
        enum_item={"file":filename,"field":field,"type":alias,"viewer_values":sorted(viewer_values),"api_values":sorted(api_values)}
        enum_checks.append(enum_item)
        if not match or viewer_values != api_values:
            findings.append({**enum_item,"error":"Viewer union type differs from runtime OpenAPI enum"})
    report={"source_files":len(list(SRC.glob('*.tsx'))),"json_body_calls_checked":len(checked),"enum_checks":enum_checks,"skipped":skipped,"findings":findings,"checked":checked}
    out=ROOT/'docs'/'viewer_request_contract_audit.v1.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ('source_files','json_body_calls_checked','skipped','findings')},indent=2,ensure_ascii=False))
    return 1 if findings else 0

if __name__=='__main__': sys.exit(main())
