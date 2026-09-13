"""Fresh fictional ad demonstrations, checked against their own resume evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from difflib import SequenceMatcher
from collections import Counter

from .config import KNOWLEDGE, ROOT, load_json


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9]+', str(text).lower()))


def resembles(text, previous):
    a, b = normalized(text), normalized(previous)
    return bool(a and b) and (a == b or SequenceMatcher(None, a, b).ratio() >= .82)


def validate_scenario(s, history):
    from .campaign import BAD_CLAIMS, authored_script, script_problems
    issues=[]
    for key,low,high in [('question',5,13),('answer',20,36),('profile',25,100),
                         ('bridge',12,19),('benefit',3,7),('name',1,3),('audience',4,20)]:
        value=s.get(key)
        if not isinstance(value,str) or not low<=len(value.split())<=high:
            issues.append(f'{key} needs {low}-{high} words')
    for key,low,high,count in [('hooks',4,12,3),('evidence',2,9,2)]:
        values=s.get(key)
        if not isinstance(values,list) or len(values)!=count or any(not isinstance(v,str) or not low<=len(v.split())<=high for v in values):
            issues.append(f'invalid {key}')
    if issues:
        return issues
    if BAD_CLAIMS.search(json.dumps(s)) or re.search(r'\d',s['profile']+' '+s['answer']):
        issues.append('unsupported claims or invented numerical results')
    if any(resembles(s['question'],p.get('topic')) for p in history.recent(90)):
        issues.append('question too similar to a recent ad')
    for variant in ('short','standard'):
        issues += script_problems(authored_script(s,variant,0),variant)
    if not issues:
        try:
            from .render.motion import MotionScene
            from .render.poster import build_poster
            for index in range(3):
                build_poster(s, authored_script(s, 'short', index), None)
            script=authored_script(s,'standard',0)
            # Prove text fits without decoding footage or calling any provider.
            for kind in ('hook','answer','evidence','product','cta'):
                MotionScene({**s,'_layout_check':True},script,kind).frame(3.0,8)
        except ValueError:
            issues.append('creative does not fit readable layout')
    return list(dict.fromkeys(issues))


def fresh_scenario(llm, seed, history):
    from .campaign import FACTS
    fallback=copy.deepcopy(seed)
    receipt={'source':'authored','issues':[]}
    if llm is None:
        return fallback,receipt
    strings=['name','audience','profile','question','answer','bridge','benefit']
    schema={'type':'object','required':strings+['hooks','evidence'],
            'properties':{k:{'type':'string'} for k in strings}}
    schema['properties'].update({k:{'type':'array','items':{'type':'string'},'minItems':n,'maxItems':n}
                                 for k,n in [('hooks',3),('evidence',2)]})
    prompt=('Create one NEW fictional candidate and a specific interview follow-up, for an advertisement. '
            'Use the seed only for audience category and language; change the project, responsibility, '
            'question and answer. This is an illustrative resume, never a customer testimonial. '
            'No real company claims, numerical improvements, invented customer counts or outcomes. '
            'Write the resume profile in English and make every fact in the answer supported by it. '
            'Use English narration and hook; use Roman Hinglish for question/answer only if seed language is hinglish. '
            'Question 5-13 words; answer 20-36; profile 25-100; name 1-3; audience 4-20; bridge 12-19; benefit 3-7. '
            'Three distinct hooks, each 4-12 words. Two evidence phrases, each 2-9 words, copied from profile facts. '
            'The bridge points out a concrete resume detail in the answer. The benefit describes resume context or language support. '
            'Return only the schema. Local checks reject recently used ideas.\n'+json.dumps({'fictional_seed':seed}))
    for _ in range(2):
        try:
            print('[creative] generating a fresh fictional demonstration',flush=True)
            draft=llm.json(FACTS,prompt,schema=schema,max_tokens=4000,temperature=.85)
            if not isinstance(draft,dict):
                receipt['issues'].append('invalid scenario object'); continue
            s={**copy.deepcopy(seed),**{k:draft[k] for k in schema['required'] if k in draft}}
            issues=validate_scenario(s,history)
            if not issues:
                review=llm.json(FACTS,'Check that this fictional answer is supported by the provided fictional resume; '
                    'the hooks advertise live interview help accurately. Return approved and supported booleans '
                    'and issues array.\n'+json.dumps({'fictional_scenario':s}),
                    schema={'type':'object','required':['approved','supported','issues'],'properties':{
                        'approved':{'type':'boolean'},'supported':{'type':'boolean'},
                        'issues':{'type':'array','items':{'type':'string'}}}},max_tokens=1800,temperature=.1)
                if isinstance(review,dict) and review.get('approved') is True and review.get('supported') is True and not review.get('issues'):
                    s['id']='fresh-'+hashlib.sha256(normalized(s['profile']+' '+s['question']).encode()).hexdigest()[:16]
                    return s,{'source':'model','review':review,'model':llm.last_model}
                issues=['scenario evidence review failed']
            receipt['issues']+=issues
            prompt+='\nCorrect these problems: '+'; '.join(issues)
        except Exception as exc:
            receipt['issues'].append(type(exc).__name__); break
    return fallback,receipt


def select_visual(history):
    catalog=load_json(KNOWLEDGE/'visuals.json')
    clips=[c for c in catalog['clips'] if (ROOT/c['path']).is_file()]
    if not clips:
        raise RuntimeError('No verified motion footage available')
    recent=history.recent(2)
    counts=Counter(p.get('visual_clip') for p in history.posts)
    clip=min(clips,key=lambda c:(c['id'] in [p.get('visual_clip') for p in recent],counts[c['id']],clips.index(c)))
    themes=catalog['themes']
    last=history.posts[-1].get('visual_theme') if history.posts else None
    theme=next(x for x in themes if x!=last)
    # Fair theme rotation, independently from footage and narrative category.
    theme=min(themes,key=lambda x:(x==last,sum(p.get('visual_theme')==x for p in history.posts),themes.index(x)))
    return {'clip':clip['path'],'clip_id':clip['id'],'theme':theme}
