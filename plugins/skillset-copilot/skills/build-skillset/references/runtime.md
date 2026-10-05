# Local runtime interface

Run `python3 <skill-directory>/scripts/copilot.py COMMAND --workspace <absolute-workspace> --input <request.json>`. Input is a UTF-8 JSON object. `doctor` and `session-list` need no input. Responses are JSON; failures exit nonzero with an `error` on stderr. No model/network calls occur in the runtime. Use Python 3.9 or later.

## Read commands

- `doctor`: validates pack hashes and workspace access.
- `search`: `{ "query": "전극 공정 코팅 불량", "context": {"job_title":"공정 엔지니어"}, "excluded_terms":["maintenance"], "company_id":"example-company", "limit":15 }`. Optional `company_only:true`, `kinds:["work","task","skill"]`, `include_adjacent_ess:true`, `excluded_ids:["reference-id"]`. Only job title, product, customers and work area from context contribute positive terms. Boundaries and exclusions never contribute positive terms. Exclusions match supplied phrases and exact glossary aliases; they do not infer negation or responsibility from natural language. Compose a positive query and explicit excluded activity terms. Absence of company does not exclude company examples; results label them accordingly. A different `business_id` in arguments or context returns no local candidates; draft from user evidence and relevant public research instead.
- `get`: `{ "ids":["reference-id"] }`. Returns full work/task/skill records; work records include tasks. Optional `collection:"business"` or `"company"`; `collection:"company"` accepts `company_id` and otherwise requires exactly one local company context. Adjacent providers are discovered from the local pack. `collection:"occupation"` uses O*NET IDs from the business context. `collection:"evidence"` uses source IDs and returns bundled original excerpts.
- `session-list`: returns local session summaries.
- `session-read` / `validate`: `{ "session_id":"uuid" }` or `{ "session_path":"/absolute/session.json" }`.
- `preview`: `{ "session_id":"uuid", "language":"ko", "offset":0, "limit":5 }`. Returns a compact Markdown page, displayed task IDs, total task count and next offset. Pages cover different work areas before showing additional tasks in the same area; the limit is capped at 10. No session change occurs.

## Create and edit

`session-create`: `{ "context": { "job_title":"공정 엔지니어", "business_id":"secondary-battery-manufacturing", "language":"ko", "product":"battery electrodes", "customers":"internal cell production", "responsibility_boundaries":[], "excluded_activities":["equipment maintenance"], "assumptions":[] } }`. Company is optional. Other useful context fields are `value_chain_role`, `constraints`, and `work_area`. Keep inferred context in `assumptions`, separate from user evidence. Returns session ID, revision and saved path. Supplying `session_path` imports a saved draft into a new local session while preserving entity IDs, evidence, reviews and original pack version.

`session-apply` requires:

```json
{
  "session_id": "existing-session-uuid",
  "expected_revision": 0,
  "operations": [
    {"op":"evidence","value":{"id":"user-context-1","type":"user_statement","text":"전극 코팅 공정의 불량 원인을 분석합니다."}},
    {"op":"decision","text":"Exclude equipment maintenance; another team owns it."}
  ]
}
```

Supported operations:

- `add`: `level` is domains/works/tasks/skills; `value` contains the entity. Generate UUIDs before composing multi-entity batches so later operations can refer to them. The runtime generates an ID when omitted.
- `edit`: `level`, `id`, `changes`; IDs are immutable. Names/definitions are full `{ko,en}` objects, not one-language patches. Text or parent changes invalidate reviews of affected entities and mark them `needs_review`; domain/work meaning changes propagate to descendants and their skills. Meaning changes reset affected confirmation. Skill meaning changes also invalidate semantic reviews covering linked tasks. `meaning_changed:false` retains confirmation and limits invalidation to the edited entity for wording-only changes; its translation review is still invalidated. Reparenting always changes scope. Supply updated `field_provenance` when rewriting text, or attribution for rewritten fields is cleared.
- `context`: merge `value`; substantive semantic context changes reset confirmations and invalidate reviews. Changes only to `language` or `presentation` do not change meaning. Use `meaning_changed:false` for other formatting-only changes.
- `link`: `task_id`, `skill_id`, `origin`, `source_refs`.
- `unlink`: `task_id`, `skill_id`.
- `evidence`: append original user statements or researched web evidence. IDs must be unique. For `type:"web_evidence"` include HTTP(S) URL, `retrieval_date` (`YYYY-MM-DD`), excerpt and usage boundary. Other evidence requires original `text`.
- `decision`: append a concise accepted choice or rejected responsibility.
- `review`: `value` contains `entity_ids`, all six `checks` and an optional `note`. Checks are `business_fit`, `scope`, `granularity`, `translation`, `evidence`, and `links`, each `pass`/`issue`/`uncertain`. Issues or uncertainty require a concrete note. The runtime adds ID, revision, time and staleness; never manufacture a human approval. An all-pass review returns affected `needs_review` states to `sme_review_pending`, without confirming tasks. Make reviews the last operations after the content they inspect.

Example semantic review operation:

```json
{"op":"review","value":{"entity_ids":["task-uuid","skill-uuid"],"checks":{"business_fit":"pass","scope":"pass","granularity":"pass","translation":"uncertain","evidence":"pass","links":"pass"},"note":"Confirm whether the Korean term means competency level or competency requirements."}}
```

Record separate reviews for small related groups. Overall semantic status is `pending` until all selected entities have current checks, `issues_found` for an active issue, and `checked` when current checks pass and no selected entity needs recheck. These are Codex review records, not SME approval. The latest non-stale review covering an entity is used. Changes to a task–skill link invalidate both endpoints' reviews without resetting user task confirmation.

Entity shape:

```json
{
  "id":"generated-uuid",
  "name":{"ko":"전극 공정 개선","en":"Electrode Process Improvement"},
  "definition":{"ko":"전극 제조 공정의 문제를 분석하고 공정 조건을 개선하는 업무.","en":"Investigate electrode manufacturing problems and improve process conditions."},
  "parent_id":"domain-uuid-for-work-or-work-uuid-for-task",
  "disposition":"selected",
  "confirmation":"unconfirmed",
  "review_status":"sme_review_pending",
  "origin":"generated",
  "source_refs":[],
  "field_provenance":{
    "name.ko":{"origin":"generated","source_ids":[],"evidence_ids":["user-context-1"]},
    "name.en":{"origin":"generated","source_ids":[],"evidence_ids":["user-context-1"],"note":"Translation of Korean wording"},
    "definition.ko":{"origin":"generated","source_ids":[],"evidence_ids":["user-context-1"]},
    "definition.en":{"origin":"generated","source_ids":[],"evidence_ids":["user-context-1"],"note":"Translation of Korean wording"}
  }
}
```

Domains and skills have no parent. Works belong to domains; tasks belong to works. Skills connect to tasks through explicit link operations, not a parent field. Disposition is suggested/selected/rejected. Confirmation is unconfirmed/user_confirmed. Review status is draft/needs_review/sme_review_pending; no approved state exists.

Suggested items remain outside exports. A selected skill candidate may be unconfirmed and SME-review-pending. Selected tasks require selected parents; selected skills require a selected task link. To reject a parent, update its selected children and any orphaned skills in the same batch. The batch is validated atomically.

`session-undo`: `{ "session_id":"uuid", "expected_revision":3 }` restores the preceding saved content as revision 4. History remains intact. Read the new revision before the next change.

`export`: `{ "session_id":"uuid" }`. Requires at least one selected task. Returns versioned CSV, compact Markdown (`skillset.md`), full bilingual Markdown (`skillset-full.md`), canonical JSON and `validation.json` paths. The compact view shows five tasks and up to three core skill names per task; all selected content remains in the full draft and CSV. Partial exports retain tasks without skills. Structural errors block export; unresolved semantic issues do not block an explicitly requested draft.

Validation reports `field_complete`, `semantic_review_status`, a `review_summary`, field/provenance `warnings` and semantic `review_notes` separately. `complete` remains a compatibility alias for `field_complete`, never semantic validation. CSV `completion_status` is `draft_complete` or `partial`, with a separate `semantic_review_status`; task confirmation and skill review also remain separate. Source IDs must resolve to reference records (including bundled O*NET occupations), source locators to bundled excerpts, and evidence IDs to the session. `source_refs` also accepts known reference record IDs used by older sessions. Exact `reused` text is checked against cited bilingual records. Empty support is a warning; traceability does not prove relevance. CSV includes link references as well as entity references. Formula-like text is escaped only in CSV; JSON preserves original text.

## Persistence and recovery

Workspace-local `skillset_sessions/<uuid>/session.json` is authoritative; `history/` holds earlier versions. `draft.md` is the compact view and `draft-full.md` contains all bilingual definitions. Exports are immutable revision bundles. Rejected suggestions, decisions, source versions, semantic reviews and user evidence survive resumption and undo. Older schema-1.0 sessions without review records can be read and are reported as review-pending.

Only referenced record IDs and locators are captured in `reference_snapshot` after validation. When the bundled pack changes, that retained lineage remains resolvable, and old semantic checks no longer count toward coverage. New reviews record the current pack hash; the original session pack version is retained. New references must resolve to the current pack; snapshots are lineage records, not independent content verification. Use the index in the bundled pack; never scan stale unindexed work files as current references.

On stale revision errors, reread and rebase the intended operation; do not overwrite the new state. On lock errors, retry after the active writer finishes. Inspect stale locks before removing one. On unsupported schema, preserve the file and explain the compatibility issue. Do not copy a session into the plugin cache.
