import copy
import csv
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'plugins/skillset-copilot/skills/build-skillset'
spec=importlib.util.spec_from_file_location('copilot',SKILL/'scripts/copilot.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CopilotTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.work=Path(self.temp.name)
        self.sid=c.create({'context':{'job_title':'전극 공정 엔지니어','language':'ko'}},self.work)['session_id']

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self):
        return c.load_session(self.work,{'session_id':self.sid})

    def apply(self,ops):
        return c.apply({'session_id':self.sid,'expected_revision':self.snapshot()['revision'],'operations':ops},self.work)

    def entity(self,eid,name='공정 개선',parent=None):
        e={'id':eid,'name':{'ko':name,'en':'Process improvement'},
           'definition':{'ko':'공정 문제를 분석하고 개선한다.','en':'Analyze and improve process problems.'},
           'disposition':'selected','origin':'generated','review_status':'sme_review_pending',
           'field_provenance':{k:{'origin':'generated','source_ids':[],'evidence_ids':['fixture-input']} for k in ['name.ko','name.en','definition.ko','definition.en']}}
        if parent:e['parent_id']=parent
        return e

    def seed(self,with_skill=True):
        ops=[{'op':'evidence','value':{'id':'fixture-input','type':'synthetic_test','text':'Illustrative process improvement responsibilities.'}}]
        ops += [{'op':'add','level':level,'value':self.entity(eid,parent=parent)} for level,eid,parent in [('domains','d',None),('works','w','d'),('tasks','t','w')]]
        if with_skill:ops += [{'op':'add','level':'skills','value':self.entity('s')},{'op':'link','task_id':'t','skill_id':'s'}]
        return self.apply(ops)

    def test_bilingual_export_and_resume(self):
        self.seed()
        result=c.export({'session_id':self.sid},self.work)
        path=Path(result['files'][0])
        self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
        with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),1)
        for level in ['domain','work','task','skill']:
            for field in ['name','definition']:
                for lang in ['ko','en']:self.assertTrue(rows[0][f'{level}_{field}_{lang}'])
        imported=c.create({'session_path':result['files'][2]},self.work)
        self.assertNotEqual(imported['session_id'],self.sid)
        self.assertEqual(c.load_session(self.work,imported)['entities'],self.snapshot()['entities'])

    def test_partial_no_skills_and_incomplete_translation(self):
        self.seed(False)
        self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'definition':{'ko':'검사한다','en':''}}}])
        result=c.export({'session_id':self.sid},self.work)
        self.assertFalse(result['validation']['complete'])
        with open(result['files'][0],encoding='utf-8-sig') as f:row=next(csv.DictReader(f))
        self.assertEqual(row['skill_review_status'],'skills_pending')
        self.assertEqual(row['skill_id'],'')

    def test_atomic_invalid_batch_and_stale_revision(self):
        self.seed()
        before=self.snapshot()
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'parent_id':'missing'}}])
        self.assertEqual(before,self.snapshot())
        with self.assertRaises(ValueError):c.apply({'session_id':self.sid,'expected_revision':0,'operations':[]},self.work)

    def test_translation_edit_keeps_id_and_marks_related_skills(self):
        self.seed()
        self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'name':{'ko':'코팅 조건 개선','en':'Improve coating conditions'}}}])
        self.assertIn('t',self.snapshot()['entities']['tasks'])
        self.assertEqual(self.snapshot()['entities']['skills']['s']['review_status'],'needs_review')

    def test_undo_and_rejected_state(self):
        self.seed()
        self.apply([{'op':'edit','level':'skills','id':'s','changes':{'disposition':'rejected'}},
                    {'op':'decision','text':'Maintenance belongs to another team.'}])
        self.assertEqual(self.snapshot()['entities']['skills']['s']['disposition'],'rejected')
        c.apply({'session_id':self.sid,'expected_revision':2},self.work,True)
        self.assertEqual(self.snapshot()['revision'],3)
        self.assertEqual(self.snapshot()['entities']['skills']['s']['disposition'],'selected')

    def test_formula_and_csv_roundtrip(self):
        self.seed()
        value='=공정,"검토"\n다음 행'
        self.apply([{'op':'edit','level':'skills','id':'s','changes':{'name':{'ko':value,'en':'@formula'}}}])
        result=c.export({'session_id':self.sid},self.work)
        with open(result['files'][0],encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
        self.assertEqual(row['skill_name_ko'],"'"+value)
        self.assertEqual(c.read(result['files'][2])['entities']['skills']['s']['name']['ko'],value)
        result2=c.export({'session_id':self.sid},self.work)
        self.assertNotEqual(result['directory'],result2['directory'])

    def test_search_languages_and_company(self):
        for query in ['equipment procurement','장비 구매','전극 coating 공정']:
            result=c.search({'query':query})['results']
            self.assertTrue(result)
            self.assertTrue(all(r.get('kind')!='posting' for r in result))
        result=c.search({'query':'equipment procurement','limit':5})['results']
        self.assertTrue(any('equipment-procurement' in r['id'] for r in result))
        self.assertEqual(c.search({'query':'battery','company_only':True,'company_id':'unknown'})['results'],[])
        result=c.search({'query':'commissioning','company_only':True,'company_id':c.adjacent_postings()[0]['company_id'],'include_adjacent_ess':True})['results']
        self.assertTrue(result)

    def test_shared_skill_and_variant(self):
        self.seed()
        self.apply([{'op':'add','level':'tasks','value':self.entity('t2',parent='w')},{'op':'link','task_id':'t2','skill_id':'s'}])
        self.apply([{'op':'add','level':'skills','value':self.entity('s2')},{'op':'unlink','task_id':'t2','skill_id':'s'},{'op':'link','task_id':'t2','skill_id':'s2'}])
        self.assertEqual({(l['task_id'],l['skill_id']) for l in self.snapshot()['links']},{('t','s'),('t2','s2')})

    def test_lock_and_schema_errors(self):
        directory=c.session_dir(self.work,self.sid)
        with c.locked(directory):
            with self.assertRaises(ValueError):self.apply([])
        self.assertFalse((directory/'.lock').exists())
        s=self.snapshot();s['schema_version']='99';c.atomic(directory/'session.json',s)
        with self.assertRaises(ValueError):self.snapshot()

    def test_portable_installed_copy(self):
        target=self.work/'installed'
        shutil.copytree(SKILL,target)
        result=subprocess.run([sys.executable,str(target/'scripts/copilot.py'),'doctor','--workspace',str(self.work)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_source_variants_and_pack_update_isolation(self):
        records=c.catalog()
        variants=[r for r in records.values() if r.get('definition_conflict')]
        self.assertEqual(len(variants),20)
        before=self.snapshot()['pack']
        self.seed()
        self.assertEqual(before,self.snapshot()['pack'])

    def test_no_fake_approval_or_missing_evidence(self):
        self.seed()
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'skills','id':'s','changes':{'review_status':'sme_approved'}}])
        provenance={k:{'origin':'generated','evidence_ids':['missing']} for k in ['name.ko','name.en','definition.ko','definition.en']}
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'skills','id':'s','changes':{'field_provenance':provenance}}])

    def review(self, ids=None, **checks):
        values={key:'pass' for key in c.REVIEW_CHECKS}
        values.update(checks)
        return {'op':'review','value':{'entity_ids':ids or ['d','w','t','s'], 'checks':values,
                                      'note':'Korean says competency level; English says competency requirements.' if checks else ''}}

    def test_field_completeness_is_separate_from_review_and_confirmation(self):
        self.assertFalse(c.validate(self.snapshot())['field_complete'])
        self.seed()
        check=c.validate(self.snapshot())
        self.assertTrue(check['field_complete'])
        self.assertEqual(check['semantic_review_status'],'pending')
        self.assertEqual(check['review_summary']['unconfirmed_tasks'],1)
        self.apply([self.review()])
        check=c.validate(self.snapshot())
        self.assertEqual(check['semantic_review_status'],'checked')
        self.assertEqual(check['review_summary']['unconfirmed_tasks'],1)
        result=c.export({'session_id':self.sid},self.work)
        with open(result['files'][0],encoding='utf-8-sig') as f:row=next(csv.DictReader(f))
        self.assertEqual(row['completion_status'],'draft_complete')
        self.assertEqual(row['semantic_review_status'],'checked')
        self.assertEqual(row['task_confirmation_status'],'unconfirmed')
        self.assertEqual(row['skill_review_status'],'sme_review_pending')

    def test_fake_sources_and_locators_are_rejected_atomically(self):
        self.seed()
        before=self.snapshot()
        provenance=copy.deepcopy(before['entities']['skills']['s']['field_provenance'])
        provenance['definition.en']['source_ids']=['invented-record']
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'skills','id':'s','changes':{'field_provenance':provenance}}])
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'skills','id':'s','changes':{'source_refs':[{'source_id':'invented-source','row':1}]}}])
        self.assertEqual(before,self.snapshot())

    def test_missing_support_and_false_exact_reuse_are_flagged(self):
        self.seed()
        record=next(iter(c.catalog().values()))
        provenance=copy.deepcopy(self.snapshot()['entities']['skills']['s']['field_provenance'])
        provenance['name.en']={'origin':'reused','source_ids':[record['id']],'evidence_ids':[]}
        provenance['definition.ko']={'origin':'generated','source_ids':[],'evidence_ids':[]}
        result=self.apply([{'op':'edit','level':'skills','id':'s','changes':{'field_provenance':provenance}}])
        self.assertFalse(result['validation']['field_complete'])
        self.assertTrue(any('reused wording' in w for w in result['validation']['warnings']))
        self.assertTrue(any('no supporting evidence' in w for w in result['validation']['warnings']))

    def test_web_evidence_is_complete_and_ids_are_unique(self):
        self.seed()
        before=self.snapshot()
        with self.assertRaises(ValueError):self.apply([{'op':'evidence','value':{'id':'web-1','type':'web_evidence','url':'https://example.com'}}])
        with self.assertRaises(ValueError):self.apply([{'op':'evidence','value':{'id':'fixture-input','type':'user_statement','text':'duplicate'}}])
        self.assertEqual(before,self.snapshot())
        self.apply([{'op':'evidence','value':{'id':'web-1','type':'web_evidence','url':'https://example.com/spec',
                     'retrieval_date':'2026-09-28','excerpt':'An illustrative specification excerpt.',
                     'usage_boundary':'Product context, not employee authority.'}}])
        self.assertEqual(len(self.snapshot()['evidence']),2)

    def test_scope_change_resets_confirmation_and_review_but_language_does_not(self):
        self.seed()
        self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'confirmation':'user_confirmed'}},self.review()])
        self.apply([{'op':'context','value':{'language':'en'}}])
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'checked')
        self.assertEqual(self.snapshot()['entities']['tasks']['t']['confirmation'],'user_confirmed')
        self.apply([{'op':'context','value':{'excluded_activities':['equipment maintenance']}}])
        self.assertEqual(self.snapshot()['entities']['tasks']['t']['confirmation'],'unconfirmed')
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'pending')
        self.assertTrue(self.snapshot()['semantic_reviews'][0]['stale'])

    def test_skill_meaning_change_invalidates_linked_task_reviews(self):
        self.seed()
        self.apply([self.review(['d','w','t']),self.review(['s'])])
        self.apply([{'op':'edit','level':'skills','id':'s','changes':{'definition':{'ko':'변경된 능력이다.','en':'A changed ability.'}}}])
        s=self.snapshot()
        self.assertEqual(s['entities']['skills']['s']['review_status'],'needs_review')
        self.assertTrue(all(r['stale'] for r in s['semantic_reviews']))
        self.assertNotIn('definition.en',s['entities']['skills']['s']['field_provenance'])
        self.assertEqual(c.validate(s)['semantic_review_status'],'pending')

    def test_parent_meaning_change_invalidates_descendants(self):
        self.seed()
        self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'confirmation':'user_confirmed'}},self.review()])
        self.apply([{'op':'edit','level':'works','id':'w','changes':{'definition':{'ko':'다른 업무 범위.','en':'Different responsibility scope.'}}}])
        s=self.snapshot()
        self.assertEqual(s['entities']['tasks']['t']['confirmation'],'unconfirmed')
        self.assertEqual(s['entities']['skills']['s']['review_status'],'needs_review')
        self.assertEqual(c.validate(s)['semantic_review_status'],'pending')

    def test_review_findings_survive_export_import_and_undo(self):
        self.seed()
        self.apply([self.review(translation='issue',business_fit='uncertain')])
        result=c.export({'session_id':self.sid},self.work)
        check=c.read(Path(result['directory'])/'validation.json')
        self.assertTrue(check['field_complete'])
        self.assertEqual(check['semantic_review_status'],'issues_found')
        self.assertEqual(len(check['review_notes']),1)
        self.assertIn('competency level',check['review_notes'][0])
        imported=c.create({'session_path':result['files'][2]},self.work)
        self.assertEqual(c.validate(c.load_session(self.work,imported))['semantic_review_status'],'issues_found')
        self.apply([self.review()])
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'checked')
        c.apply({'session_id':self.sid,'expected_revision':3},self.work,True)
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'issues_found')

    def test_compact_preview_keeps_all_content_in_full_export(self):
        self.seed()
        ops=[{'op':'add','level':'tasks','value':self.entity(f't{i}',name=f'공정 활동 {i}',parent='w')} for i in range(2,9)]
        ops += [{'op':'link','task_id':f't{i}','skill_id':'s'} for i in range(2,9)]
        ops += [{'op':'add','level':'works','value':self.entity('w2',name='다른 업무',parent='d')},
                {'op':'add','level':'tasks','value':self.entity('other-task',name='다른 활동',parent='w2')},
                {'op':'link','task_id':'other-task','skill_id':'s'}]
        self.apply(ops)
        page=c.dispatch('preview',{'session_id':self.sid},self.work)
        self.assertEqual(page['total_tasks'],9)
        self.assertEqual(len(page['task_ids']),5)
        self.assertIn('other-task',page['task_ids'])
        next_page=c.dispatch('preview',{'session_id':self.sid,'offset':page['next_offset']},self.work)
        self.assertEqual(set(page['task_ids']) & set(next_page['task_ids']),set())
        self.assertEqual(len(set(page['task_ids']+next_page['task_ids'])),9)
        result=c.export({'session_id':self.sid},self.work)
        with open(result['files'][0],encoding='utf-8-sig') as f:self.assertEqual(len(list(csv.DictReader(f))),9)
        full=(Path(result['directory'])/'skillset-full.md').read_text()
        for i in range(2,9):self.assertIn(f'공정 활동 {i}',full)
        overview=Path(result['files'][1]).read_text()
        self.assertIn('(skillset-full.md)',overview)
        self.assertLess(len(overview),len(full))

    def test_exclusions_are_not_positive_signals_and_aliases_filter_candidates(self):
        query={'query':'equipment procurement','limit':50}
        baseline=c.search(query)
        bounded=c.search(dict(query,context={'excluded_activities':['maintenance'],'responsibility_boundaries':['Another team owns inspection maintenance.']}))
        self.assertEqual(baseline,bounded)
        results=c.search({'query':'equipment maintenance','excluded_terms':['maintenance'],'limit':50})['results']
        self.assertTrue(results)
        records=c.catalog()
        for result in results:
            ts=c.tokens(c.text(records[result['id']].get('name'))+' '+c.text(records[result['id']].get('description'))+' '+c.text(records[result['id']].get('work_name')))
            for phrase in ('maintenance','보전','유지보수'):
                self.assertFalse(c.tokens(phrase) <= ts)
        self.assertEqual(c.search({'query':'sales','context':{'business_id':'it-services'}})['results'],[])

    def test_link_provenance_is_exported_and_snapshot_survives_pack_change(self):
        self.seed()
        record=next(iter(c.catalog().values()))
        ref=record['source_refs'][0]
        self.apply([{'op':'unlink','task_id':'t','skill_id':'s'},
                    {'op':'link','task_id':'t','skill_id':'s','origin':'adapted','source_refs':[ref]},self.review()])
        result=c.export({'session_id':self.sid},self.work)
        with open(result['files'][0],encoding='utf-8-sig') as f:row=next(csv.DictReader(f))
        self.assertIn(ref,json.loads(row['source_reference_ids']))
        self.assertIn(c.locator_key(ref),self.snapshot()['reference_snapshot']['locators'])
        original_read=c.read
        def new_pack(path):
            value=original_read(path)
            if Path(path)==c.DATA/'pack.json':value['hash']='new-pack-hash'
            return value
        with patch.object(c,'read',side_effect=new_pack),patch.object(c,'reference_inventory',return_value=({},set())):
            check=c.validate(self.snapshot())
            self.assertTrue(check['valid'])
            self.assertEqual(check['semantic_review_status'],'pending')
            self.assertTrue(check['review_notes'])
            self.apply([self.review()])
            self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'checked')

    def test_old_session_without_review_metadata_remains_resumable(self):
        self.seed()
        s=self.snapshot()
        s.pop('semantic_reviews');s.pop('reference_snapshot')
        c.atomic(c.session_dir(self.work,self.sid)/'session.json',s)
        self.assertTrue(c.validate(self.snapshot())['valid'])
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'pending')
        self.apply([self.review()])
        self.assertEqual(c.validate(self.snapshot())['semantic_review_status'],'checked')

    def test_legacy_reference_ids_are_resolved_and_preserved(self):
        self.seed()
        record_id=next(iter(c.catalog()))
        self.apply([{'op':'edit','level':'works','id':'w','changes':{'source_refs':[record_id]}}])
        imported=c.create({'session_path':str(c.session_dir(self.work,self.sid)/'session.json')},self.work)
        self.assertEqual(c.load_session(self.work,imported)['entities']['works']['w']['source_refs'],[record_id])
        self.assertIn(record_id,self.snapshot()['reference_snapshot']['record_ids'])
        with self.assertRaises(ValueError):self.apply([{'op':'edit','level':'works','id':'w','changes':{'source_refs':['invented-record']}}])

    def test_invalid_reviews_do_not_save_or_clear_findings(self):
        self.seed()
        self.apply([self.review(translation='issue')])
        before=self.snapshot()
        for value in [{'entity_ids':['t'],'checks':{}},
                      {'entity_ids':['missing'],'checks':{k:'pass' for k in c.REVIEW_CHECKS}},
                      {'entity_ids':['t'],'checks':{k:'uncertain' for k in c.REVIEW_CHECKS},'note':''}]:
            with self.assertRaises(ValueError):self.apply([{'op':'review','value':value}])
            self.assertEqual(before,self.snapshot())

    def test_occupation_reference_supports_exact_english_reuse(self):
        self.seed()
        record=c.read(c.DATA/'occupations/onet-17-2141.00.json')
        provenance=copy.deepcopy(self.snapshot()['entities']['works']['w']['field_provenance'])
        provenance['name.en']={'origin':'reused','source_ids':[record['id']],'evidence_ids':[]}
        result=self.apply([{'op':'edit','level':'works','id':'w','meaning_changed':False,
                           'changes':{'name':{'ko':'기계 엔지니어 업무','en':record['name']},'field_provenance':provenance}}])
        self.assertTrue(result['validation']['valid'])
        self.assertFalse(any('name.en reused wording' in w for w in result['validation']['warnings']))

    def test_wording_edit_keeps_confirmation_and_unaffected_reviews(self):
        self.seed()
        self.apply([{'op':'edit','level':'tasks','id':'t','changes':{'confirmation':'user_confirmed'}},
                    self.review(['d','w']),self.review(['t']),self.review(['s'])])
        self.apply([{'op':'edit','level':'tasks','id':'t','meaning_changed':False,
                    'changes':{'name':{'ko':'공정개선','en':'Process Improvement'}}}])
        s=self.snapshot()
        self.assertEqual(s['entities']['tasks']['t']['confirmation'],'user_confirmed')
        self.assertEqual(s['entities']['skills']['s']['review_status'],'sme_review_pending')
        self.assertFalse(s['semantic_reviews'][0]['stale'])
        self.assertTrue(s['semantic_reviews'][1]['stale'])
        self.assertFalse(s['semantic_reviews'][2]['stale'])


if __name__=='__main__':unittest.main()
