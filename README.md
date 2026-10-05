# Bilingual Skill-Set Copilot

An installable Codex plugin for drafting Korean–English domain–work–task–skill sets through conversation. It builds abilities around the employee's product, customers, business conditions and responsibilities. Locally supplied reference examples are candidates, not a definitive requirements catalog. Codex reasons, researches material gaps on the public web, and translates; Python handles local retrieval, session revisions and exports. No separate API key or local server is required.

## Use

Before running a fresh checkout, supply an authorized reference pack in `plugins/skillset-copilot/skills/build-skillset/data/`. This directory is intentionally excluded from Git because it may contain private reference information. The repository alone does not include the data required for reference retrieval or the full test suite.

To test directly in this project without installation, ask Codex to read `plugins/skillset-copilot/skills/build-skillset/SKILL.md` and follow it. This runs the project copy, including local changes.

Install the `skillset-copilot` plugin in Codex and start a new task in a writable workspace. Invoke `$build-skillset`, for example:

> Use $build-skillset. 저는 배터리 전극 공정 엔지니어입니다. 코팅 불량 조사와 공정 개선 업무의 스킬셋을 만들고 싶어요.

Or:

> Use $build-skillset to draft a Korean–English skill set for battery equipment procurement. Maintenance belongs to another team.

Select useful examples, correct the tasks, then ask to generate skills or export a draft. Saved sessions live in `skillset_sessions/` in the active workspace. Resume by giving Codex the session JSON file or asking it to list saved sessions. The plugin works in another workspace without this repository's raw data.

The default review page shows up to five tasks and three core skill names per task in the conversation language. It covers different work areas before expanding each area. Ask for another page or the full definitions to inspect more detail. Every export retains all selected content in a BOM-encoded bilingual CSV for Excel, full bilingual Markdown and canonical JSON, alongside the compact overview and validation notes. Partial drafts are supported.

Validation separates field completeness, user task confirmation and semantic review. Source and evidence references must resolve. Codex records business fit, scope, skill granularity, translation, evidence relevance and task–skill relevance; edits invalidate affected reviews. A field-complete draft or a recorded Codex check does not establish employee capability or SME approval. See `tests/PILOT.md` for live conversation evaluation scenarios.

## Development

Python 3.9+ is required; no third-party runtime packages are needed. The implementation also supports the Python version already available on this Mac.

```bash
python3 -m unittest discover -s tests -v
python3 plugins/skillset-copilot/skills/build-skillset/scripts/copilot.py doctor
```

Reference packs are maintained locally under the skill's `data/` directory. A compatible pack includes `pack.json`, the business/work indexes, skill and occupation records, source registry and excerpts, and validation information. Preserve the pack's directory structure and hashes when provisioning it through an approved private channel. Run `doctor` after provisioning. Do not commit private reference packs or include them in a publicly shared plugin archive.

Raw `example_data/`, reference-preparation files (`references/` and root `scripts/`), demo outputs, employee sessions, temporary request JSON, and caches also remain local and are ignored by Git. Raw preparation files are not needed at runtime once an authorized pack is provisioned. Rebuilding a pack is a separate maintenance workflow. The current tests require the original development reference pack; they are not data-independent tests for arbitrary packs.

## Design considerations

- **Employees first:** Engineers, researchers and staff should recognize and correct familiar examples instead of completing an HR-style interview. Start with minimal context and a small set of suggestions.
- **Business-specific abilities:** Use products, processes, customers and responsibility boundaries to identify useful skills. Avoid generic lists or mechanically turning every task into similarly named skills.
- **A consistent hierarchy:** Keep business context separate from domain → work → task → skill. Tasks describe activities and outputs; skills describe learnable abilities that can support several tasks.
- **Bilingual meaning:** Every level has Korean and English names and definitions. Edits should preserve equivalent scope in both languages, using the user's authoring language as the starting point.
- **Traceable drafts:** Distinguish reused, adapted and generated content. Retain sources and user context, and keep user-confirmed tasks separate from semantic review and SME approval.
- **Low-friction review:** Show compact task/skill summaries, retain the full detail in saved drafts, and allow partial export. Completeness checks do not prove capability or translation quality.
- **Private data stays local:** Separate reusable code from company reference packs, employee sessions and exports. Git ignores reduce accidental future uploads; they do not remove data from earlier commits or prevent a plugin archive from containing local data.
- **Simple execution:** Use Codex for conversation and reasoning, with deterministic local Python tools for retrieval, revision control, validation and export. No separate model API key, server or external telemetry is required.

Local installation uses the personal Codex marketplace. Keep company references private; this repository does not publish or synchronize them. Saved user statements are stored locally and processed in the Codex conversation under the user's existing Codex setup. Codex may research public sources using generic business/activity terms; researched evidence is saved in the session, without changing the shared pack. The helper runtime sends no network requests and collects no external telemetry.
