# Authoring and bilingual review

Every domain, work, task and skill needs `name.ko`, `name.en`, `definition.ko` and `definition.en`. Use concise names and one or two sentences per definition. A domain describes related responsibilities; work describes a coherent responsibility and its business contribution; a task describes an activity and its output; a skill describes a learnable ability enabling that activity.

## Business context and skill selection

Before choosing skills, connect the prompt to the product/service, customers, value-chain role, operating constraints and outputs the employee owns. Store known details in session context (`product`, `customers`, `value_chain_role`, `constraints`, `responsibility_boundaries`, `excluded_activities`). Put tentative inferences in `assumptions`; never save them as original user statements. A broad department catalog may be appropriate when requested; it does not establish one employee's remit.

For each task, identify the information or materials used, the judgments made, the methods used and the resulting deliverable. Choose the few abilities that actually enable these. Explain each task–skill association to yourself; if the relationship only follows from a broad work-area label, omit or reconsider it. Shared skills are useful when the same ability enables several tasks, but do not attach every work-area skill to every task.

Use a context-swap test: if the company moved from battery manufacturing to IT services, which proposed skills would change, and why? Do not force all skills to be industry-specific. Make the product-specific judgments explicit where they matter; adding “battery” to a generic skill name is insufficient.

Illustrative generated contrast, not a verified job requirement:

| Task | Battery manufacturing sales | IT services sales |
|---|---|---|
| Prepare a customer proposal | Translate customer battery performance and volume requirements into a proposal with product capability, validation and production-ramp assumptions, working with technical and manufacturing teams. | Translate customer workflow, integration and service requirements into a proposal with solution scope, implementation and support assumptions. |
| Distinct enabling ability | Battery RFQ feasibility interpretation: connect customer specifications and delivery demand to product and manufacturing constraints, escalating technical commitments to their owners. | Solution integration scoping: identify dependencies between the proposed service and the customer's systems and implementation responsibilities. |

Do not turn a fixed skill count into a generation target. “Task X requirement analysis,” “Task X execution design,” and “Task X performance/risk management” are not sufficient merely because they are differently named. Prefer concrete methods or judgments, such as workforce demand modeling or RFQ requirement interpretation. If a real skill is broad, define its enabling action clearly. Exclude approval authority, operational work or specialist judgments the user assigned to another team.

## Research when evidence is insufficient

First identify the missing question: a product constraint, customer process, technical method, industry-specific judgment, or current requirement. Local examples may be wrong, too broad, unrelated or missing; they do not overrule the prompt. Research the public web for material gaps and uncertain facts, rather than forcing the nearest reference to fit. An unfamiliar internal task may be adequately described by the user; research only the public aspects that need evidence.

Use primary sources suited to the question: official technical documentation, industry research, standards publishers, or employer role descriptions. A job posting illustrates one employer's scope; it does not establish the user's responsibilities. Regulations and standards need applicability checks before being included as requirements. Search with generic business/activity terms; keep private user statements and internal plans out of search queries. If browsing is unavailable or the user prohibited it, continue with clearly generated candidates and an uncertainty note.

Save only the evidence that influences the draft: URL, retrieval date, relevant excerpt, and a usage boundary. Cite its evidence ID in affected fields and explain what the excerpt supports. Separate the source fact from the inferred skill. Stop researching once the concrete gap is resolved; avoid accumulating background material that does not change the skill set. Session research must not mutate the shared reference pack.

## Compact review and semantic checks

The first useful output should fit on a short review page in the conversation language. Default to up to five tasks with short output descriptions and two or three core skills per task. When more skills are requested, order task–skill links by importance to that task, placing distinctive enabling abilities first; the overview shows the first three linked skills and the remaining count. Use `preview` for another page. When a full catalog is requested, retain all selected content in the full bilingual draft and exports; the overview is a window, not a truncated canonical output. Definitions, source IDs and repeated shared skills belong in detail unless necessary to distinguish candidates.

Before recording a semantic review, inspect all six categories:

- `business_fit`: distinctive abilities follow from product, customer and business conditions; important assumptions remain visible.
- `scope`: the prompt and exclusions match task outputs and authority.
- `granularity`: tasks are activities; skills are distinct learnable abilities, without redundant templates or compound padding.
- `translation`: both languages preserve inputs, actions, outputs, exclusions and uncertainty. For example, competency **level** and competency **requirements** are different concepts.
- `evidence`: cited material supports the field or the stated inference, without treating examples as truth.
- `links`: each linked ability enables that particular task; generic relevance to the work area is insufficient.

Use `pass`, `issue` or `uncertain`, with a concrete note for anything unresolved. Review small related groups so a later task edit does not invalidate unrelated findings. Checks apply to the exact content reviewed and become stale after relevant edits. A model check records what was inspected; it is not an independent SME judgment. Resolve clear issues, record another review, and leave substantive uncertainties visible. Partial export remains available.

Example (illustrative generated wording, not a quoted requirement):

| Level | Korean name and definition | English name and definition |
|---|---|---|
| Domain | 제조: 제품을 요구 품질과 생산 조건에 맞춰 안정적으로 생산하는 업무 영역. | Manufacturing: The function responsible for producing products reliably within required quality and operating conditions. |
| Work | 전극 공정 개선: 전극 제조 공정의 문제를 분석하고 조건 및 작업 방법을 개선하는 업무. | Electrode Process Improvement: Investigate electrode manufacturing problems and improve process conditions and operating methods. |
| Task | 코팅 불량 원인 조사: 검사 결과와 공정 데이터를 비교하여 코팅 불량의 원인 후보와 후속 검증 항목을 도출한다. | Investigate Coating Defects: Compare inspection findings with process data to identify potential causes of coating defects and define follow-up checks. |
| Skill | 공정 데이터 원인 분석: 공정 조건과 품질 결과의 관계를 분석하고 증거에 기반한 원인 가설을 수립하는 능력. | Process Data Root-Cause Analysis: Analyze relationships between process conditions and quality outcomes to develop evidence-based causal hypotheses. |

Source job labels can mix work, roles, departments and generic competencies. Preserve their source IDs, but do not copy an unsuitable label into the generated taxonomy. In particular, do not turn every generic AI or communication source entry into an employee task.

Use the user's current authoring language as the source of meaning. Translate the paired field and compare scope, action, exclusions, technical nouns and uncertainty. An English conversation does not require the employee to review Korean wording before continuing. Do not mark a translation as user-confirmed just because the underlying task was selected. Preserve existing glossary choices; propose a clarification when two technical interpretations materially differ.

Meaning changes reset affected confirmation and review states. A shared skill edit also invalidates reviews of linked tasks; create a variant when only one association changes. Pure wording corrections may use `meaning_changed: false` to retain confirmation, but still update both languages and provenance and recheck translation. A user can separately confirm the updated text in a later edit operation.

Field provenance format is keyed by `name.ko`, `name.en`, `definition.ko`, `definition.en`. Each entry contains `origin` (reused/adapted/generated), `source_ids` (reference record IDs), `evidence_ids` (session evidence IDs), and a short optional `note`. Reuse exact text only where it fits; do not claim source support for newly generated details. Record references at the task–skill link as well when the association is adapted or generated.

After rewriting a name or definition, supply updated provenance. The runtime clears attribution for rewritten fields if the edit omits it. A valid source locator establishes traceability, not that the source supports a generated detail. Use supporting user evidence for generated scope, and a note to distinguish inference from exact reuse.

Avoid broad compound skills that combine independently assessable abilities. Preserve distinct source variants until their meanings are understood. Reuse one session skill across tasks only when the definition is genuinely the same. A task-specific change should create a new UUID, then unlink/relink the affected task.

Do not generate proficiency levels, employee scores, assessment rubrics or training catalogs in this workflow. Existing reference assessment text may help understand a skill, but the requested output is concise names and definitions.
