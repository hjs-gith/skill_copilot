# Codex conversation pilot

These scenarios require a live Codex conversation and human semantic review. The deterministic test suite does not claim to verify model behavior or the five-to-ten-minute usability target.

Run each scenario in a fresh task with the installed plugin and a writable workspace. Do not supply expected draft wording to the person evaluating the conversation.

| Scenario | Starting prompt | Follow-up | Inspect |
|---|---|---|---|
| Korean process engineer | `$build-skillset 저는 전극 코팅 공정 엔지니어입니다.` | `불량 원인 조사와 조건 개선은 합니다. 설비 보전은 다른 팀 업무예요.` | Concrete process examples; maintenance exclusion survives revisions |
| English researcher | `$build-skillset I develop battery cells and evaluate trial cells.` | `Generate a bilingual draft.` | Names and definitions at all four levels; English/Korean scope equivalence |
| Procurement | `$build-skillset Help with my battery equipment procurement skill set.` | `I compare proposals, but final budget approval belongs to management.` | No invented approval authority; proposal comparison skills |
| Mixed-language SCM | `$build-skillset SCM기획 담당입니다. Demand와 capacity gap을 분석해요.` | `물류 실행은 담당하지 않습니다.` | Bilingual retrieval, SCM boundaries and consistent acronyms |
| Adjacent ESS | `$build-skillset I support ESS commissioning; public examples from other ESS companies would help.` | `Use suitable local adjacent-provider examples.` | Adjacent source explicitly identified, no cell-production assumptions |
| Novel task | `$build-skillset I design an internal review workflow for a new battery reuse pilot.` | `The supplied examples don't fit; use the activities I describe.` | Generated origin and supporting user evidence, no fake sources |
| Resume and edit | `Resume this session JSON with $build-skillset.` | `Change this English task definition and export now, even if some skills are pending.` | Stable IDs, paired Korean update, partial export and retained decisions |
| Business context contrast | Run separately: `$build-skillset I handle customer proposals in battery manufacturing sales.` and `$build-skillset I handle customer proposals in an IT services company.` | `Draft skills for proposal preparation. Technical approval belongs to specialists.` | Different product-specific judgments and constraints; no battery examples imposed on IT sales; generic abilities retained only where useful |
| Insufficient references | `$build-skillset I sell battery manufacturing equipment and interpret customer acceptance-test requirements. Local sales examples may not fit.` | `Explain the missing evidence and research what would change the skills.` | Targeted public primary sources, saved excerpt/URL/date/usage boundary, explicit separation of source facts and generated abilities |
| No browsing | `$build-skillset Draft skills for an internal battery-reuse pilot. Do not browse.` | `Use only the activities I describe and mark assumptions.` | No public lookup; generated lineage and unresolved evidence gaps, without forced unrelated reference matches |
| Compact broad catalog | `$build-skillset Draft an HR department catalog for battery manufacturing covering HRM, HRD, recruiting, organization development and employee relations.` | `Show the next page, then export all of it.` | At most five tasks per default page, breadth across work areas, no padded skill quota; next page has new tasks; complete content survives in full export |
| Template and translation review | `Review an existing HR session with $build-skillset.` | `Check whether the skills are distinct, and whether 역량 수준 and competency requirements mean the same thing here.` | Concrete granularity and translation findings saved against affected IDs; clear corrections in both languages; unresolved findings remain visible |

Record time to first useful examples, time to export, number of substantive task corrections, whether examples were relevant, and SME comments on bilingual accuracy and skill granularity. Do not store employee identity or send pilot logs to external telemetry. A failed scenario should lead to a narrow fix to retrieval or authoring guidance, followed by rerunning that scenario.

For each run, keep the starting prompt, substantive follow-ups, exported session and validation notes. Reviewers should inspect the compact page first, then the full definitions and evidence for disputed items. Assess the output against these observable criteria:

- Business-specific abilities change meaningfully between the sales contexts; changing only the industry noun is a failure.
- Every inspected task states an activity and output. Every linked skill is a distinct enabling ability whose connection can be explained.
- Reference examples and public sources do not invent employee scope or authority. Explicit exclusions survive resume, edits and export.
- Korean and English preserve the same inputs, actions, outputs and limits; a semantic mismatch is a failure even with all fields filled.
- Material source gaps trigger targeted research when available and permitted. A failed or unavailable lookup is reported as uncertainty, never fabricated support.
- The default page is compact, and pagination/detail reveal all selected content. The overview never implies that hidden tasks were removed.
- Field completeness, task confirmation and Codex semantic checks remain distinguishable; pending checks or issues cannot be described as SME validation.

Record pass/issue/uncertain per criterion with the affected entity IDs and a short reason. This evaluates the draft and interaction, not employee performance. Run the same prompt after a fix and compare semantic outcomes; do not require exact wording or a fixed number of skills. Automated tests cover persistence and validation, not these model judgments. Do not claim the live pilot passed unless its conversations and review results were actually collected.
