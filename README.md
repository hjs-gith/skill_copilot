# Bilingual Skill-Set Copilot

An installable Codex plugin for drafting Korean–English domain–work–task–skill sets through conversation. It builds abilities around the employee's product, customers, business conditions and responsibilities. The bundled examples cover battery manufacturing and staff work; they are candidates, not a definitive requirements catalog. Codex reasons, researches material gaps on the public web, and translates; Python handles local retrieval, session revisions and exports. No separate API key or local server is required.

## Use

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

The repository includes the ready-to-use reference pack under the skill's `data/` directory. It bundles selected evidence excerpts and attribution, not the entire raw dataset. The pack retains conflicting definitions for review. Its source registry and validation report are included alongside the runtime data.

Raw `example_data/`, reference-preparation files (`references/` and root `scripts/`), demo outputs, employee sessions, temporary request JSON, and caches remain local and are ignored by Git. They are not needed to run the plugin or its tests. Rebuilding the pack from those local preparation files is a separate maintenance workflow; a checkout runs with the bundled pack as-is.

Local installation uses the personal Codex marketplace. Keep company references private; this repository does not publish or synchronize them. Saved user statements are stored locally and processed in the Codex conversation under the user's existing Codex setup. Codex may research public sources using generic business/activity terms; researched evidence is saved in the session, without changing the shared pack. The helper runtime sends no network requests and collects no external telemetry.
