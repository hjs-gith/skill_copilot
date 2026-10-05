"""Local deterministic tools for Codex. No network or model calls; Python 3.9+."""
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
DATA = HOME / 'data'
BUSINESS = 'secondary-battery-manufacturing'
LEVELS = ('domains', 'works', 'tasks', 'skills')
ORIGINS = {'reused', 'adapted', 'generated'}
STATES = {'suggested', 'selected', 'rejected'}
REVIEW_CHECKS = {'business_fit', 'scope', 'granularity', 'translation', 'evidence', 'links'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(directory):
    path = directory / '.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Session is locked. Retry after the other command finishes; inspect a stale lock before removing it.')
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def session_dir(workspace, session_id):
    if str(uuid.UUID(session_id)) != session_id:
        raise ValueError('Invalid session ID')
    return workspace / 'skillset_sessions' / session_id


def load_session(workspace, args):
    if args.get('session_path'):
        s = read(args['session_path'])
    else:
        s = read(session_dir(workspace, args['session_id']) / 'session.json')
    if s.get('schema_version') != '1.0':
        raise ValueError('Unsupported session schema')
    return s


def persist(directory, s):
    atomic(directory / 'session.json', s)


def tokens(text):
    text = unicodedata.normalize('NFKC', str(text)).lower()
    result = set(re.findall(r'[a-z0-9]+', text))
    for term in re.findall(r'[가-힣]+', text):
        result.add(term)
        for n in (2, 3):
            result.update(term[i:i+n] for i in range(len(term)-n+1))
    return result


def text(value):
    if isinstance(value, dict):
        return ' '.join(text(v) for v in value.values())
    if isinstance(value, list):
        return ' '.join(text(v) for v in value)
    return str(value or '')


def catalog():
    index = read(DATA / f'businesses/{BUSINESS}/index.json')
    records = {}
    for w in index['works']:
        obj = read(DATA / w['path'])
        records[obj['id']] = dict(obj, kind='work')
        for task in obj['tasks']:
            records[task['id']] = dict(task, kind='task', work_id=obj['id'], work_name=obj['name'],
                                        company_id=obj['company_id'], domain=obj['domain'])
    for skill in read(DATA / 'skills/catalog.json')['records']:
        records[skill['id']] = dict(skill, kind='skill')
    return records


def adjacent_postings():
    records = []
    for path in sorted((DATA / f'businesses/{BUSINESS}/adjacent').glob('*/job-postings.json')):
        records.extend(read(path)['records'])
    return records


def company_context(args):
    contexts = [read(path) for path in sorted((DATA / f'businesses/{BUSINESS}/companies').glob('*/context.json'))]
    requested = args.get('company_id')
    if requested:
        contexts = [context for context in contexts if context.get('id') == requested]
    if len(contexts) != 1:
        raise ValueError('Specify a company_id matching one local company context')
    return contexts[0]


def search(args):
    context = args.get('context', {})
    if args.get('business_id', context.get('business_id', BUSINESS)) != BUSINESS:
        return {'results': [], 'notice': 'This pack covers secondary battery manufacturing only.'}
    records = catalog()
    # Boundaries and decisions are not positive retrieval signals.
    positive_context = {k: context[k] for k in ('job_title', 'product', 'customers', 'work_area') if k in context}
    query = args.get('query', '') + ' ' + text(positive_context)
    glossary = read(HOME / 'references/glossary.json')
    expanded = tokens(query)
    for group in glossary['aliases']:
        if any(tokens(alias) <= expanded for alias in group):
            expanded.update(tokens(' '.join(group)))
    kinds = args.get('kinds', ['work', 'task'])
    candidates = [r for r in records.values() if r['kind'] in kinds]
    if args.get('include_adjacent_ess'):
        postings = adjacent_postings()
        candidates.extend(dict(p, kind='posting', name={'en': p['source_record']['title']},
                               description=p['source_record']['sections']) for p in postings)
    document_tokens = [tokens(text(r.get('name'))+' '+text(r.get('description'))+' '+text(r.get('work_name'))) for r in candidates]
    frequencies = Counter(token for ts in document_tokens for token in ts)
    exclusions = []
    for term in args.get('excluded_terms', []):
        alternatives = [tokens(term)]
        for group in glossary['aliases']:
            if any(tokens(alias) == tokens(term) for alias in group):
                alternatives.extend(tokens(alias) for alias in group)
        exclusions.append([ts for ts in alternatives if ts])
    results = []
    for record, ts in zip(candidates, document_tokens):
        if record['id'] in args.get('excluded_ids', []) or any(v <= ts for group in exclusions for v in group):
            continue
        if args.get('company_only') and record.get('company_id') != args.get('company_id'):
            continue
        matched = expanded & ts
        if not matched:
            continue
        names = tokens(text(record.get('name')))
        score = sum((6 if token in names else 1) * (1+math.log((len(candidates)+1)/(frequencies[token]+1))) for token in matched)
        if args.get('company_id') == record.get('company_id'):
            score *= 1.15
        results.append({'id': record['id'], 'kind': record['kind'], 'name': record.get('name'),
                        'work_name': record.get('work_name'), 'company_id': record.get('company_id'),
                        'score': round(score, 3), 'matched_terms': sorted(matched),
                        'company_example': record.get('company_id') != args.get('company_id')})
    return {'results': sorted(results, key=lambda r: (-r['score'], r['id']))[:min(int(args.get('limit', 15)), 50)]}


def locator_key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def reference_text(record, field, language):
    value = record.get(field)
    if isinstance(value, dict):
        return value.get(language)
    if isinstance(value, str) and language == 'en':
        return value
    return None


@lru_cache(maxsize=2)
def cached_reference_inventory(data_path, pack_hash):
    records = catalog()
    records.update({r['id']: r for r in adjacent_postings()})
    for path in (DATA / 'occupations').glob('onet-*.json'):
        record = read(path)
        if 'id' in record:
            records[record['id']] = record
    locators = {locator_key(e['locator']) for e in read(DATA / 'sources/excerpts.json')}
    return records, locators


def reference_inventory():
    return cached_reference_inventory(str(DATA), read(DATA / 'pack.json')['hash'])


def used_references(s):
    record_ids, locators = set(), set()
    def collect(refs):
        for ref in refs:
            if isinstance(ref, str):
                record_ids.add(ref)
            else:
                locators.add(locator_key(ref))
    for group in s['entities'].values():
        for e in group.values():
            collect(e.get('source_refs', []))
            for entry in e.get('field_provenance', {}).values():
                record_ids.update(entry.get('source_ids', []))
    for link in s.get('links', []):
        collect(link.get('source_refs', []))
    return record_ids, locators


def capture_references(s):
    """Retain only used, resolved lineage so a later pack update can be reviewed."""
    records, locators = reference_inventory()
    used_ids, used_locators = used_references(s)
    snapshot = s.setdefault('reference_snapshot', {'record_ids': [], 'locators': []})
    snapshot['record_ids'] = sorted(set(snapshot['record_ids']) | (used_ids & records.keys()))
    snapshot['locators'] = sorted(set(snapshot['locators']) | (used_locators & locators))


def invalidate(s, entity_ids, reset_confirmation=True):
    entity_ids = set(entity_ids)
    for group in s['entities'].values():
        for eid, e in group.items():
            if eid in entity_ids:
                e['review_status'] = 'needs_review'
                if reset_confirmation:
                    e['confirmation'] = 'unconfirmed'
    for review in s.get('semantic_reviews', []):
        if entity_ids.intersection(review['entity_ids']):
            review['stale'] = True


def affected_entities(s, level, eid):
    affected = {eid}
    if level == 'domains':
        affected.update(k for k, e in s['entities']['works'].items() if e['parent_id'] == eid)
    if level in ('domains', 'works'):
        affected.update(k for k, e in s['entities']['tasks'].items() if e['parent_id'] in affected)
    affected.update(l['skill_id'] for l in s['links'] if l['task_id'] in affected)
    return affected


def validate(s):
    errors, warnings = [], []
    entities = s.get('entities', {})
    records, locators = reference_inventory()
    current_pack_hash = read(DATA / 'pack.json')['hash']
    pack_changed = s.get('pack', {}).get('hash') != current_pack_hash
    snapshot = s.get('reference_snapshot', {}) if pack_changed else {}
    known_records = set(records) | set(snapshot.get('record_ids', []))
    known_locators = locators | set(snapshot.get('locators', []))
    evidence_ids = set()
    for evidence in s.get('evidence', []):
        eid = evidence.get('id')
        if not isinstance(eid, str) or not eid or eid in evidence_ids:
            errors.append('Evidence IDs must be nonempty and unique')
            continue
        evidence_ids.add(eid)
        if evidence.get('type') == 'web_evidence':
            if not all(isinstance(evidence.get(k), str) and evidence[k].strip() for k in ('url', 'retrieval_date', 'excerpt', 'usage_boundary')):
                errors.append(f'{eid}: web evidence needs URL, retrieval date, excerpt and usage boundary')
            else:
                try:
                    datetime.strptime(evidence['retrieval_date'], '%Y-%m-%d')
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', evidence['retrieval_date']) or not re.match(r'^https?://[^/\s]+', evidence['url']):
                        raise ValueError('Invalid web evidence URL or date')
                except ValueError:
                    errors.append(f'{eid}: invalid web evidence URL or date')
        elif not isinstance(evidence.get('text'), str) or not evidence['text'].strip():
            errors.append(f'{eid}: evidence needs original text')

    def check_refs(refs, owner):
        if not isinstance(refs, list) or any(not isinstance(v, (dict, str)) for v in refs):
            errors.append(f'{owner}: source_refs must be a list of locators or reference record IDs')
            return
        for ref in refs:
            if isinstance(ref, str):
                if ref not in known_records:
                    errors.append(f'{owner}: unknown reference record {ref}')
            elif locator_key(ref) not in known_locators:
                errors.append(f'{owner}: unknown source locator {locator_key(ref)}')

    ids = set()
    for level in LEVELS:
        for key, e in entities.get(level, {}).items():
            if key != e.get('id') or key in ids:
                errors.append(f'Invalid or duplicate ID: {key}')
            ids.add(key)
            if e.get('disposition') not in STATES:
                errors.append(f'{key}: invalid disposition')
            if e.get('origin') not in ORIGINS:
                errors.append(f'{key}: invalid origin')
            check_refs(e.get('source_refs', []), key)
            for field in ('name', 'definition'):
                if not isinstance(e.get(field), dict) or any(not isinstance(e[field].get(lang), str) for lang in ('ko','en')):
                    errors.append(f'{key}: {field} must contain ko/en strings')
                elif e['disposition'] == 'selected' and any(not e[field][lang].strip() for lang in ('ko','en')):
                    warnings.append(f'{key}: incomplete bilingual {field}')
            provenance=e.get('field_provenance', {})
            for field in ('name.ko','name.en','definition.ko','definition.en'):
                entry=provenance.get(field, {})
                if e.get('disposition') == 'selected' and entry.get('origin') not in ORIGINS:
                    warnings.append(f'{key}: {field} provenance missing')
                source_ids = entry.get('source_ids', [])
                supporting_ids = entry.get('evidence_ids', [])
                if any(not isinstance(v, list) or any(not isinstance(i, str) for i in v) for v in (source_ids, supporting_ids)):
                    errors.append(f'{key}: {field} provenance IDs must be string lists')
                    continue
                for source_id in source_ids:
                    if source_id not in known_records:
                        errors.append(f'{key}: unknown reference record {source_id}')
                for evidence_id in supporting_ids:
                    if evidence_id not in evidence_ids:
                        errors.append(f'{key}: unknown evidence {evidence_id}')
                if e.get('disposition') == 'selected' and not (source_ids or supporting_ids):
                    warnings.append(f'{key}: {field} has no supporting evidence')
                if e.get('disposition') == 'selected' and entry.get('origin') == 'reused':
                    name, lang = field.split('.')
                    source_field = 'description' if name == 'definition' else name
                    if not source_ids or (all(i in records for i in source_ids) and not any(
                        reference_text(records[i], source_field, lang) == e.get(name, {}).get(lang) for i in source_ids)):
                        warnings.append(f'{key}: {field} reused wording does not match a cited record')
            if e.get('confirmation') not in {'unconfirmed', 'user_confirmed'}:
                errors.append(f'{key}: invalid confirmation')
            if e.get('review_status') not in {'draft', 'needs_review', 'sme_review_pending'}:
                errors.append(f'{key}: unsupported review status; this tool does not confer SME approval')
            if level in ('works', 'tasks'):
                parent_level = 'domains' if level == 'works' else 'works'
                parent = entities.get(parent_level, {}).get(e.get('parent_id'))
                if not parent:
                    errors.append(f'{key}: missing parent')
                elif e['disposition'] == 'selected' and parent['disposition'] != 'selected':
                    errors.append(f'{key}: selected child requires selected parent')
    seen = set()
    for link in s.get('links', []):
        pair = (link.get('task_id'), link.get('skill_id'))
        if pair in seen or pair[0] not in entities.get('tasks', {}) or pair[1] not in entities.get('skills', {}):
            errors.append(f'Invalid task–skill link: {pair}')
        seen.add(pair)
        if link.get('origin') not in ORIGINS:
            errors.append(f'Invalid link origin: {pair}')
        check_refs(link.get('source_refs', []), str(pair))
    for e in entities.get('skills', {}).values():
        if e['disposition'] == 'selected' and not any(t in entities['tasks'] and entities['tasks'][t]['disposition']=='selected' and k==e['id'] for t,k in seen):
            errors.append(f'{e["id"]}: selected skill has no selected task')
    for e in entities.get('tasks', {}).values():
        if e['disposition'] == 'selected' and not any(t==e['id'] and entities['skills'][k]['disposition']=='selected' for t,k in seen if k in entities['skills']):
            warnings.append(f'{e["id"]}: skills pending')
    selected = {key: e for group in entities.values() for key, e in group.items() if e.get('disposition') == 'selected'}
    coverage = {}
    review_ids = set()
    for review in s.get('semantic_reviews', []):
        checks = review.get('checks', {})
        targets = review.get('entity_ids', [])
        if not isinstance(review.get('id'), str) or not review['id'] or review['id'] in review_ids:
            errors.append('Semantic review IDs must be nonempty and unique')
            continue
        review_ids.add(review.get('id'))
        if (not isinstance(targets, list) or not targets or any(not isinstance(eid, str) or eid not in ids for eid in targets)
                or not isinstance(checks, dict) or set(checks) != REVIEW_CHECKS
                or any(v not in {'pass', 'issue', 'uncertain'} for v in checks.values())):
            errors.append('Invalid semantic review: identify entities and supply all six checks')
            continue
        if not isinstance(review.get('note', ''), str) or (any(v != 'pass' for v in checks.values()) and not review.get('note', '').strip()):
            errors.append('Semantic review issues and uncertainties need a note')
            continue
        if not review.get('stale', False) and review.get('pack_hash', s.get('pack', {}).get('hash')) == current_pack_hash:
            coverage.update({eid: review for eid in targets})
    active_reviews = {r['id']: r for eid, r in coverage.items() if eid in selected}
    issues = [r for r in active_reviews.values() if 'issue' in r['checks'].values()]
    uncertain = [r for r in active_reviews.values() if 'uncertain' in r['checks'].values() and 'issue' not in r['checks'].values()]
    missing = sum(eid not in coverage for eid in selected)
    needs_review = sum(e.get('review_status') == 'needs_review' for e in selected.values())
    semantic_status = 'issues_found' if issues else ('pending' if missing or uncertain or needs_review or not selected else 'checked')
    review_notes = list(dict.fromkeys(r['note'] for r in issues + uncertain))
    if pack_changed:
        review_notes.append('Reference pack differs from the saved version; original lineage is retained. ' +
                            ('Current checks cover the changed pack.' if semantic_status == 'checked' else 'Recheck lineage and content against the current pack.'))
    field_complete = not errors and not warnings and any(e.get('disposition') == 'selected' for e in entities.get('tasks', {}).values())
    return {'valid': not errors, 'complete': field_complete, 'field_complete': field_complete,
            'semantic_review_status': semantic_status, 'errors': errors, 'warnings': warnings,
            'review_summary': {'unconfirmed_tasks': sum(e.get('confirmation') != 'user_confirmed' for e in entities.get('tasks', {}).values() if e.get('disposition') == 'selected'),
                               'entities_needing_review': needs_review, 'entities_without_semantic_review': missing,
                               'issue_reviews': len(issues), 'uncertain_reviews': len(uncertain)},
            'review_notes': review_notes,
            'semantic_review': 'Field completeness and Codex checks do not confer SME approval or establish employee proficiency.'}


def create(args, workspace):
    sid = uid()
    s = {'schema_version':'1.0', 'id':sid, 'revision':0, 'created_at':now(), 'updated_at':now(),
         'context':args.get('context', {}), 'pack':read(DATA/'pack.json') | {'files':None},
         'entities':{level:{} for level in LEVELS}, 'links':[], 'evidence':[], 'decisions':[], 'events':[],
         'semantic_reviews':[], 'reference_snapshot':{'record_ids':[], 'locators':[]}}
    directory = session_dir(workspace, sid)
    directory.mkdir(parents=True)
    if args.get('session_path'):
        imported = load_session(workspace,args)
        check = validate(imported)
        if not check['valid']:
            raise ValueError(check['errors'])
        s.update({k:copy.deepcopy(imported[k]) for k in ['context','entities','links','evidence','decisions','pack']})
        for key in ('semantic_reviews', 'reference_snapshot'):
            if key in imported:
                s[key] = copy.deepcopy(imported[key])
        s['imported_from'] = imported['id']
    capture_references(s)
    persist(directory, s)
    render_draft(directory, s)
    return {'session_id':sid, 'revision':0, 'path':str(directory/'session.json')}


def apply(args, workspace, undo=False):
    directory = session_dir(workspace, args['session_id'])
    with locked(directory):
        old = read(directory/'session.json')
        if old.get('schema_version') != '1.0':
            raise ValueError('Unsupported session schema')
        if args.get('expected_revision') != old['revision']:
            raise ValueError(f'Stale revision; current revision is {old["revision"]}')
        s = copy.deepcopy(old)
        if undo:
            if old['revision'] == 0:
                raise ValueError('No previous revision')
            prior = read(directory/'history'/f'{old["revision"]-1:06}.json')
            for key in ['entities','links','context','evidence','decisions']:
                s[key] = prior[key]
            for key, default in [('semantic_reviews', []), ('reference_snapshot', {'record_ids':[], 'locators':[]})]:
                s[key] = prior.get(key, default)
        else:
            for operation in args.get('operations', []):
                op = operation['op']
                if op == 'context':
                    changed = any(s['context'].get(k) != v for k, v in operation['value'].items() if k not in {'language', 'presentation'})
                    s['context'].update(operation['value'])
                    if changed and operation.get('meaning_changed', True):
                        invalidate(s, [eid for group in s['entities'].values() for eid in group])
                elif op == 'evidence':
                    s['evidence'].append({'id':uid(), **operation['value']})
                elif op == 'decision':
                    s['decisions'].append({'at':now(), 'text':operation['text']})
                elif op in ('add','edit'):
                    level = operation['level']
                    if level not in LEVELS:
                        raise ValueError('Unknown entity level')
                    if op == 'add':
                        value = operation['value']
                        eid = value.get('id', uid())
                        if any(eid in g for g in s['entities'].values()):
                            raise ValueError('Entity already exists')
                        s['entities'][level][eid] = {'id':eid,'disposition':'suggested','confirmation':'unconfirmed',
                            'review_status':'draft','origin':'generated','source_refs':[], 'field_provenance':{}, **value}
                    else:
                        e = s['entities'][level][operation['id']]
                        changes = operation['changes']
                        if 'id' in changes:
                            raise ValueError('IDs cannot be edited')
                        content_changed = any(k in changes and changes[k] != e.get(k) for k in ('name','definition','parent_id'))
                        parent_changed = 'parent_id' in changes and changes['parent_id'] != e.get('parent_id')
                        lineage_changed = any(k in changes and changes[k] != e.get(k) for k in ('field_provenance','source_refs','origin','disposition'))
                        edited_fields = [k for k in ('name', 'definition') if k in changes and changes[k] != e.get(k)]
                        e.update(changes)
                        # Old attribution cannot silently support newly written text.
                        if edited_fields and 'field_provenance' not in changes:
                            e['field_provenance'] = {k:v for k,v in e.get('field_provenance', {}).items() if k.split('.')[0] not in edited_fields}
                        if content_changed:
                            meaning_changed = operation.get('meaning_changed', True) or parent_changed
                            invalidate(s, affected_entities(s, level, e['id']) if meaning_changed else {e['id']}, meaning_changed)
                            if level == 'skills' and meaning_changed:
                                for review in s.get('semantic_reviews', []):
                                    if any(l['task_id'] in review['entity_ids'] for l in s['links'] if l['skill_id'] == e['id']):
                                        review['stale'] = True
                        elif lineage_changed:
                            for review in s.get('semantic_reviews', []):
                                if e['id'] in review['entity_ids']:
                                    review['stale'] = True
                elif op == 'link':
                    s['links'].append({'task_id':operation['task_id'],'skill_id':operation['skill_id'],
                                       'origin':operation.get('origin','generated'), 'source_refs':operation.get('source_refs',[])})
                    invalidate(s, [operation['task_id'], operation['skill_id']], False)
                elif op == 'unlink':
                    s['links']=[l for l in s['links'] if (l['task_id'],l['skill_id']) != (operation['task_id'],operation['skill_id'])]
                    invalidate(s, [operation['task_id'], operation['skill_id']], False)
                elif op == 'review':
                    review = copy.deepcopy(operation['value'])
                    review.update(id=uid(), revision=old['revision']+1, at=now(), stale=False,
                                  pack_hash=read(DATA / 'pack.json')['hash'])
                    s.setdefault('semantic_reviews', []).append(review)
                    if isinstance(review.get('checks'), dict) and set(review['checks']) == REVIEW_CHECKS and all(v == 'pass' for v in review['checks'].values()):
                        for group in s['entities'].values():
                            for eid in review.get('entity_ids', []):
                                if eid in group and group[eid]['review_status'] == 'needs_review':
                                    group[eid]['review_status'] = 'sme_review_pending'
                else:
                    raise ValueError('Unknown operation: '+op)
        result = validate(s)
        if not result['valid']:
            raise ValueError(result['errors'])
        capture_references(s)
        s['revision']=old['revision']+1
        s['updated_at']=now()
        s['events'].append({'at':now(),'type':'undo' if undo else 'apply','revision':s['revision'],
                            'operation_count':len(args.get('operations',[])), 'warning_count':len(result['warnings'])})
        atomic(directory/'history'/f'{old["revision"]:06}.json',old)
        persist(directory,s)
        render_draft(directory,s)
    return {'session_id':s['id'],'revision':s['revision'],'validation':result,'draft_path':str(directory/'draft.md'),
            'full_draft_path':str(directory/'draft-full.md')}


def full_markdown(s):
    lines=['# Skill-set draft / 스킬셋 초안','',f'Revision / 버전: {s["revision"]}', '', 'Draft for SME review / SME 검토용 초안','']
    def label(e):
        return e['name']['ko']+' / '+e['name']['en']
    for domain in s['entities']['domains'].values():
        if domain['disposition']!='selected': continue
        lines.extend(['## '+label(domain),'',domain['definition']['ko'],'',domain['definition']['en'],''])
        for work in s['entities']['works'].values():
            if work['disposition']!='selected' or work['parent_id']!=domain['id']: continue
            lines.extend(['### '+label(work),'',work['definition']['ko'],'',work['definition']['en'],''])
            for task in s['entities']['tasks'].values():
                if task['disposition']!='selected' or task['parent_id']!=work['id']: continue
                lines.extend(['#### '+label(task),'',task['definition']['ko'],'',task['definition']['en'],'',f'Task: {task["confirmation"]}',''])
                for link in s['links']:
                    if link['task_id']!=task['id']: continue
                    skill=s['entities']['skills'][link['skill_id']]
                    if skill['disposition']!='selected': continue
                    lines.extend(['- **'+label(skill)+'** — '+skill['definition']['ko']+' '+skill['definition']['en'],
                                  '  '+skill['origin']+'; '+skill['review_status'],''])
    check=validate(s)
    lines.extend(['## Draft status / 초안 상태', '',
                  f'Fields complete: {check["field_complete"]}; semantic checks: {check["semantic_review_status"]}. No SME approval.', ''])
    lines.extend(['## Review notes / 검토 사항','']+['- '+v for v in check['warnings']])
    lines.extend(['- '+v for v in check['review_notes']])
    lines.extend(['','## Decisions / 결정 사항','']+['- '+d['text'] for d in s['decisions']])
    return '\n'.join(lines)+'\n'


def preview_tasks(s):
    # Show breadth across work areas before further tasks from the same area.
    groups = [[t for t in s['entities']['tasks'].values() if t['disposition'] == 'selected' and t['parent_id'] == w['id']]
              for w in s['entities']['works'].values() if w['disposition'] == 'selected']
    return [g[i] for i in range(max((len(g) for g in groups), default=0)) for g in groups if i < len(g)]


def markdown(s, language=None, offset=0, limit=5, detailed_file='draft-full.md'):
    lang = language or s['context'].get('language', 'ko')
    lang = 'en' if lang == 'en' else 'ko'
    korean = lang == 'ko'
    tasks = preview_tasks(s)
    shown = tasks[offset:offset+limit]
    check = validate(s)
    counts = {level:sum(e['disposition'] == 'selected' for e in s['entities'][level].values()) for level in LEVELS}

    def cell(value, cap=180):
        value = str(value).replace('\n', ' ').replace('|', '\\|')
        return value if len(value) <= cap else value[:cap-1] + '…'

    lines = ['# 스킬셋 검토용 초안' if korean else '# Skill-set review draft', '',
             cell(s['context'].get('job_title', '')), '',
             (f'업무 {counts["works"]}개 · Task {counts["tasks"]}개 · Skill {counts["skills"]}개' if korean else
              f'{counts["works"]} work areas · {counts["tasks"]} tasks · {counts["skills"]} skills'), '']
    for key in ('product', 'customers', 'value_chain_role', 'constraints', 'responsibility_boundaries', 'excluded_activities', 'assumptions'):
        if s['context'].get(key):
            labels = {'product':'제품', 'customers':'고객', 'value_chain_role':'사업 역할', 'constraints':'업무 조건',
                      'responsibility_boundaries':'담당 범위', 'excluded_activities':'제외 업무', 'assumptions':'확인할 가정'}
            lines.append(f'- {labels[key] if korean else key.replace("_", " ").capitalize()}: {cell(text(s["context"][key]))}')
    lines.extend(['', '| 업무 | Task 및 산출물 | 핵심 Skill |' if korean else '| Work | Task and output | Core skills |',
                  '|---|---|---|'])
    for task in shown:
        work = s['entities']['works'][task['parent_id']]
        skills = [s['entities']['skills'][l['skill_id']] for l in s['links'] if l['task_id'] == task['id']
                  and s['entities']['skills'][l['skill_id']]['disposition'] == 'selected']
        names = '; '.join(cell(e['name'][lang], 70) for e in skills[:3])
        if len(skills) > 3:
            names += f' (+{len(skills)-3})'
        if not skills:
            names = '작성 예정' if korean else 'Pending'
        lines.append(f'| {cell(work["name"][lang], 70)} | **{cell(task["name"][lang], 90)}**: {cell(task["definition"][lang])} | {names} |')
    if shown:
        lines.extend(['', f'{offset+1}–{offset+len(shown)} / {len(tasks)} tasks.'])
    else:
        lines.extend(['', '선택된 Task가 없습니다.' if korean else 'No tasks in this page.'])
    summary = check['review_summary']
    status_labels = {'pending':'검토 대기', 'issues_found':'수정 사항 있음', 'checked':'Codex 검토 기록 있음'}
    lines.extend(['', ('필드 작성: '+('완료' if check['field_complete'] else '보완 필요') if korean else
                      'Fields: '+('complete' if check['field_complete'] else 'incomplete')),
                  (f'검토: {status_labels[check["semantic_review_status"]]} · 미확인 Task {summary["unconfirmed_tasks"]}개 · 재검토 항목 {summary["entities_needing_review"]}개' if korean else
                      f'Review: {check["semantic_review_status"].replace("_", " ")} · {summary["unconfirmed_tasks"]} unconfirmed tasks · {summary["entities_needing_review"]} items need recheck'),
                  'SME 승인 전 초안입니다.' if korean else 'Draft pending SME review.'])
    if check['warnings']:
        lines.append(f'{len(check["warnings"])} field/provenance warnings; see validation notes.')
    if check['errors']:
        lines.append(f'{len(check["errors"])} structural errors; see validation notes before export.')
    lines.extend('- '+cell(v, 240) for v in check['review_notes'][:3])
    lines.extend(['', f'[전체 한영 정의 보기]({detailed_file})' if korean else f'[Full bilingual definitions]({detailed_file})', ''])
    return '\n'.join(lines)


def render_draft(directory,s):
    (directory/'draft.md').write_text(markdown(s),encoding='utf-8')
    (directory/'draft-full.md').write_text(full_markdown(s),encoding='utf-8')


def export(args,workspace):
    directory=session_dir(workspace,args['session_id'])
    with locked(directory):
        s=read(directory/'session.json')
        check=validate(s)
        if not check['valid']: raise ValueError(check['errors'])
        if not any(t['disposition']=='selected' for t in s['entities']['tasks'].values()):
            raise ValueError('Select at least one task before exporting')
        dest=directory/'exports'/f'r{s["revision"]:06}-{uid()[:8]}'
        staging=directory/('.export-'+uid())
        staging.mkdir()
        fields=[]
        for level in ('domain','work','task','skill'):
            fields += [level+'_id']+[f'{level}_{field}_{lang}' for field in ('name','definition') for lang in ('ko','en')]
        fields+=['task_confirmation_status','skill_review_status','skill_origin','source_reference_ids','completion_status','semantic_review_status']
        rows=[]
        for task in s['entities']['tasks'].values():
            if task['disposition']!='selected': continue
            work=s['entities']['works'][task['parent_id']]
            domain=s['entities']['domains'][work['parent_id']]
            linked=[s['entities']['skills'][l['skill_id']] for l in s['links'] if l['task_id']==task['id'] and s['entities']['skills'][l['skill_id']]['disposition']=='selected']
            for skill in linked or [None]:
                row={}
                refs=[]
                for level,e in [('domain',domain),('work',work),('task',task),('skill',skill)]:
                    row[level+'_id']=e['id'] if e else ''
                    for field in ('name','definition'):
                        for lang in ('ko','en'): row[f'{level}_{field}_{lang}']=e[field][lang] if e else ''
                    if e: refs.extend(e.get('source_refs',[]))
                refs.extend(ref for link in s['links'] if skill and link['task_id'] == task['id'] and link['skill_id'] == skill['id'] for ref in link.get('source_refs', []))
                refs = list({locator_key(ref):ref for ref in refs}.values())
                row.update(task_confirmation_status=task['confirmation'],skill_review_status=skill['review_status'] if skill else 'skills_pending',
                           skill_origin=skill['origin'] if skill else '',source_reference_ids=json.dumps(refs,ensure_ascii=False),
                           completion_status='draft_complete' if check['field_complete'] else 'partial',
                           semantic_review_status=check['semantic_review_status'])
                rows.append(row)
        try:
            with (staging/'skillset.csv').open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    writer.writerow({k:("'"+str(v) if str(v).lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
            (staging/'skillset.md').write_text(markdown(s, detailed_file='skillset-full.md'),encoding='utf-8')
            (staging/'skillset-full.md').write_text(full_markdown(s),encoding='utf-8')
            atomic(staging/'session.json',s)
            atomic(staging/'validation.json',check)
            dest.parent.mkdir(exist_ok=True)
            os.replace(staging,dest)
        except Exception:
            import shutil
            shutil.rmtree(staging)
            raise
    return {'directory':str(dest),'rows':len(rows),'validation':check,'files':[str(dest/name) for name in ['skillset.csv','skillset.md','session.json','skillset-full.md','validation.json']]}


def dispatch(command,args,workspace):
    if command=='doctor':
        pack=read(DATA/'pack.json')
        bad=[name for name,h in pack['files'].items() if not (DATA/name).is_file() or hashlib.sha256((DATA/name).read_bytes()).hexdigest()!=h]
        return {'ok':not bad and sys.version_info >= (3,9) and os.access(workspace,os.W_OK),'python':sys.version.split()[0], 'invalid_pack_files':bad,'workspace_writable':os.access(workspace,os.W_OK)}
    if command=='search': return search(args)
    if command=='get':
        records=catalog()
        records.update({r['id']:r for r in adjacent_postings()})
        if args.get('collection')=='business': return read(DATA/f'businesses/{BUSINESS}/context.json')
        if args.get('collection')=='company': return company_context(args)
        if args.get('collection')=='occupation':
            return [read(DATA/'occupations'/f'{i}.json') for i in args['ids'] if re.fullmatch(r'onet-[0-9.-]+',i)]
        if args.get('collection')=='sources': return read(DATA/'sources/registry.json')
        if args.get('collection')=='evidence':
            excerpts=[e for e in read(DATA/'sources/excerpts.json')
                      if e['locator']['source_id'] in args.get('ids',[]) or e['locator'] in args.get('source_refs',[])]
            offset=max(0,int(args.get('offset',0)))
            limit=max(1,min(20,int(args.get('limit',5))))
            return {'records':excerpts[offset:offset+limit], 'total':len(excerpts),
                    'next_offset':offset+limit if offset+limit<len(excerpts) else None}
        return {'records':[records[i] for i in args.get('ids',[]) if i in records], 'missing_ids':[i for i in args.get('ids',[]) if i not in records]}
    if command=='session-create': return create(args,workspace)
    if command=='session-list':
        return [{'id':s['id'],'revision':s['revision'],'context':s['context'],'updated_at':s['updated_at']} for p in sorted((workspace/'skillset_sessions').glob('*/session.json')) for s in [read(p)]]
    if command=='session-read': return load_session(workspace,args)
    if command=='preview':
        s=load_session(workspace,args)
        offset=max(0,int(args.get('offset',0)))
        limit=max(1,min(10,int(args.get('limit',5))))
        tasks=preview_tasks(s)
        return {'markdown':markdown(s,args.get('language'),offset,limit), 'total_tasks':len(tasks),
                'task_ids':[t['id'] for t in tasks[offset:offset+limit]],
                'next_offset':offset+limit if offset+limit<len(tasks) else None}
    if command=='session-apply': return apply(args,workspace)
    if command=='session-undo': return apply(args,workspace,True)
    if command=='validate': return validate(load_session(workspace,args))
    if command=='export': return export(args,workspace)
    raise ValueError('Unknown command')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['doctor','search','get','session-create','session-list','session-read','preview','session-apply','session-undo','validate','export'])
    parser.add_argument('--input',type=Path,help='JSON request file; defaults to empty object')
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    args=parser.parse_args()
    try:
        result=dispatch(args.command,read(args.input) if args.input else {},args.workspace.resolve())
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
