<!-- governance:memory_authority -->
memory_root: memory/
external_memory_allowed: false
operational_records_must_stay_under_memory_root: true

# AGENTS.md
<!-- governance-baseline: overridable -->
<!-- baseline_version: 1.0.0 -->
<!-- This file is repo-specific. Edit freely. -->
<!-- DO NOT edit AGENTS.base.md — it is a protected framework file. -->

This file extends `AGENTS.base.md`.
All rules in `AGENTS.base.md` are non-negotiable and apply to this repo unconditionally.

Add repo-specific rules below.
Fill in each section below, or write `N/A` if the section is not applicable to this repo.

Quick start:

1. Start with the top 1-3 risky paths in this repo, not a full policy rewrite.
2. If you already have a checklist / runbook / test convention, copy that wording here instead of inventing new terms.
3. If a section truly does not apply, keep `N/A` and move on.

---

## Repo-Specific Risk Levels
<!-- governance:key=risk_levels -->

<!-- Define what makes a change HIGH / MEDIUM / LOW risk in this repo.
Example:
- HIGH: any change to auth, payment, or data migration paths
- MEDIUM: adding a new API endpoint or external dependency
- LOW: documentation, config comments, test-only changes

Prompt yourself:
- What changes in this repo can corrupt state, break compatibility, or cause production downtime?
- What changes are review-heavy but still reversible?
- What changes are safe enough to keep in a fast path?
-->

- HIGH: changes to `src/usb_logic_trace_correlator/bushound.py`, `saleae.py`,
  `compare.py`, `app.py`, `qt_desktop.py`, or PyInstaller specs that alter
  parsing, correlation, upload/readiness, or packaged startup behavior.
- MEDIUM: dependency, entrypoint, UI page, or governance hook/contract changes
  that can alter runtime behavior or enforcement.
- LOW: documentation, test-only, or presentation-only changes with no parser,
  correlation, or packaging behavior change.

## Must-Test Paths
<!-- governance:key=must_test_paths -->

<!-- List modules or code paths that require tests before merge.
Example:
- src/auth/       any change here needs integration tests
- src/migrations/ schema changes need a rollback test

Prompt yourself:
- Which files or directories would you never want changed without a test?
- Which paths are easy to break with static changes alone?
- Which user-visible or hardware-facing flows need explicit coverage?
-->

- `src/usb_logic_trace_correlator/bushound.py`, `saleae.py`, and `compare.py`:
  parser or correlation changes require fixture or smoke checks covering valid,
  invalid, boundary, and failure-path inputs.
- `app.py` and `src/usb_logic_trace_correlator/ui/`: source classification,
  readiness, or correlation changes require targeted behavior checks plus
  Python compile/import validation.
- `qt_desktop.py` and `*.spec`: packaging or startup changes require the
  canonical PyInstaller build or an explicitly recorded environment blocker,
  followed by the Streamlit health endpoint check.

## L1 → L2 Escalation Triggers
<!-- governance:key=escalation_triggers -->

<!-- When does this repo's work need the full L2 evidence checklist?
Example:
- Changing shared database schema
- Modifying public API contracts
- Any change touching >3 modules simultaneously

Prompt yourself:
- What kinds of changes cross system boundaries?
- What changes would require a reviewer to ask for stronger evidence than normal?
- What changes become risky mainly because they are broad, not because they touch one file?
-->

- Changing the v1 input boundary to support raw `.sal` files or bypassing the
  Saleae CSV classification gate.
- Changing normalized event, USB transaction, match-result schemas, or
  correlation-window semantics.
- Changing the Qt/Streamlit process boundary, PyInstaller data collection,
  external dependencies, or commit/push governance hooks.
- Any change spanning more than three runtime modules or overlapping existing
  dirty application edits so the scope cannot be isolated cleanly.

## Repo-Specific Forbidden Behaviors
<!-- governance:key=forbidden_behaviors -->

<!-- Add restrictions beyond the framework baseline.
Example:
- Do not write directly to the production database from tests
- Do not commit .env files even if .gitignored

Prompt yourself:
- What are the easy-to-make mistakes that are specific to this repo?
- Are there tool, environment, hardware, or deployment actions that should never happen casually?
- What "cleanup" or "shortcut" behaviors have already caused pain here?
-->

- Do not claim raw `.sal` parsing as a v1 feature; the supported Saleae input is
  an exported analyzer CSV/TXT unless `Plan.md` is updated first.
- Do not treat a digital-export CSV as I2C input; preserve the classification
  gate before parsing correlation events.
- Do not commit generated `build/`, `dist/`, `dist-rebuild/`, or runtime
  artifacts as part of source changes.
- Do not skip targeted parser, correlation, or packaging verification when the
  corresponding surface is changed.

<!-- AI Governance Framework: agent-contract BEGIN -->
<!-- AI Governance Framework: agent-contract v1.0 -->
<!-- Source: ai-governance-framework/governance/agent-contract-template.md -->
<!-- Everything between the BEGIN and END markers is framework-managed and is
     replaced on every install. Repository-specific rules belong outside this
     block; the installer preserves them. -->

## Governance Contract Output (MANDATORY)

The rules below are projected verbatim from the canonical source named in the
projection header, which carries the projection version and the content digest
of that canonical section. Do not edit them here; they are replaced on install.

<!-- ai-governance:checkpoint-projection BEGIN version=1.1 source=governance/SYSTEM_PROMPT.md#2.8 sha256=0829946513494089ed95b333733572a03666060dfabd10eca36c4ab662b4888f -->
### 2.8 Governance Contract Output

在以下時點輸出此 block：
- task 開始
- milestone 完成
- scope 改變
- stop / escalation 事件
- 任何 contract 欄位發生實質變化時

若只是 routine progress commentary 且 state 未變，可省略。

```text
[Governance Contract]
LANG     = <value>
LEVEL    = <value>
SCOPE    = <value>
PLAN     = <current phase> / <sprint> / <task>
LOADED   = <comma-separated list of loaded governance docs>
CONTEXT  = <context name> -> <responsible for X>; NOT: <not responsible for Y>
PRESSURE = <SAFE|WARNING|CRITICAL|EMERGENCY> (<line count>/200)
         # 或 <LEVEL> (<line count>/200 lines; <char count> chars)
AGENT_ID = <agent-id>       # optional; required in multi-agent sessions
SESSION  = <YYYY-MM-DD-NN>  # optional; required when AGENT_ID is present
```

欄位規則：
- `LANG`: 取自 `C | C++ | C# | ObjC | Swift | JS | Python | Verilog | SystemVerilog`。
  單一語言直接填該值；跨語言任務以逗號分隔，每個元素都必須是上列值之一（例：`C, C++`）。
  不得把多個語言寫成單一 token（例：`C/C++`）：`/` 已是 `SCOPE` 的 `I/O` 值的一部分，
  在同一個 block 內不能再兼作清單分隔符。分隔符與 `LOADED` 一致。
- `LEVEL`: 單值，取自 `L0 | L1 | L2`
- `SCOPE`: **單值**，取自 `feature | refactor | bugfix | I/O | tooling | review | governance | kernel-driver`。
  `SCOPE` 會決定 review、testing 與 governance routing；多值會引入未定義的優先序與衝突語義，
  因此不接受清單。任務橫跨多個 scope 時，拆成多個 task 或選擇主導的那一個。
- `PLAN`: 取自 `PLAN.md`；若人類明確授權 governance analysis，可標 `Out-of-scope`
- `LOADED`: must name governance docs actually loaded into the agent context. It must include `SYSTEM_PROMPT`; `HUMAN-OVERSIGHT.md` is human-only authority and must not be listed as loaded unless a human explicitly provides it.
  每個項目以逗號分隔。文件識別採**最後一段路徑、可省略 `.md`**，因此下列四種寫法識別為同一份文件：
  `SYSTEM_PROMPT`、`SYSTEM_PROMPT.md`、`governance/SYSTEM_PROMPT.md`、
  `ai-governance-framework\governance\SYSTEM_PROMPT.md`。
  正規化規則：`\` 一律視為 `/`；取最後一段；**只有 `.md` 可省略**，其他副檔名不得省略；
  比對**區分大小寫**。因此 `SYSTEM_PROMPT.txt`、`MY_SYSTEM_PROMPT.md`、`system_prompt`
  都不是 `SYSTEM_PROMPT`。寫出完整路徑比裸 token 攜帶更多可稽核資訊，兩者同等合法。
- `CONTEXT`: 必須同時包含 `->` 與 `NOT:`
- `PRESSURE`: 必須含 label 與**實際的** line count，兩種形式擇一：
  - `<LEVEL> (<line count>/200)`
  - `<LEVEL> (<line count>/200 lines; <char count> chars)`
  第二種形式存在的理由：§7.4 的判級依據是「行數**或**字元數任一達標」，只寫 line count
  時，因字元數達標而升級的判定在 contract 裡無法被檢視。需要說明判級理由時用第二種。
  兩個數字都必須是實際整數；分母固定 200。`(<line count>/200)` 這種未替換的樣板、
  `(pending exact line count/200)` 這類佔位字串、非數字與負數都屬格式錯誤。
- `SESSION`: 當 `AGENT_ID` 存在時必填

格式錯誤的 contract block 屬於 governance failure。
<!-- ai-governance:checkpoint-projection END -->

### When SYSTEM_PROMPT.md is not loaded

`LOADED` must name governance documents actually loaded into this context, and
the canonical rules require `SYSTEM_PROMPT` among them. This block is a
projection of one canonical section — it is not `SYSTEM_PROMPT.md`, and its
presence is not evidence that `SYSTEM_PROMPT.md` was read.

When the canonical `SYSTEM_PROMPT.md` has not actually been loaded, no compliant
`[Governance Contract]` block can be produced. Emit this notice at the same
checkpoints instead, and never emit a block whose `LOADED` names documents that
were not read:

```text
[Governance Contract: UNAVAILABLE]
REASON  = governance context incomplete
MISSING = SYSTEM_PROMPT
SOURCE  = agent instructions (checkpoint projection)
NEXT    = load the canonical SYSTEM_PROMPT.md, or ask the human to provide it
```

Reading `SYSTEM_PROMPT.md` during the session clears the notice, and that change
to `LOADED` is itself a material contract change — emit the full block at that
point. Resolve the canonical path against this repository's governance root; it
may sit under a submodule or contract directory rather than `governance/` at the
repository root.
<!-- AI Governance Framework: agent-contract END -->

<!-- governance:key=f7_update_boundary -->
- F-7 updates must preserve existing repo-specific AGENTS.md rules.
- Validate F-7 state with `python -X utf8 -m governance_tools.f7_full_update --repo . --format human` from the framework environment.
- Final AI Governance update reports must relay `[human_readable_adoption_summary]` table rows as a table, not a prose summary, and include the user-facing adoption status; reporting only machine-readable fields or `F-7 completed` is incomplete.
- F-7 terminal results are an expanded-report exception to the compact three-line default: relay the complete adoption table and preserve its machine status, claim boundary, evidence references, and next action.
- Response envelope contract version: v0.7. Compact human responses are the default.
- Ordinary expanded reporting has exactly three triggers: `full_evidence_request`, `owner_decision_required`, and `failed_or_partial`.
- Keep validation commands, counts, and diagnostics under `驗證` or `evidence_refs`; use `注意` only for one decision-relevant limitation.
- If the adoption table is unavailable or cannot be relayed, report `human_readable_adoption_summary: NOT REPORTED`, `update_report_complete=false`, and `completion_claim_allowed=false` with the reason; do not fabricate rows or claim a complete update report.
- When a `mode` is used, keep `mode` event-derived with its `mode_source`; the human projection must not create trust claims or replace the canonical machine envelope.
- Non-trivial feature or bugfix work must not be reported with happy-path-only tests: reproducible bugs need regression tests when feasible, expected values must come from a spec/invariant/fixture rather than copied production logic, mock-only assertions are weak evidence unless observable behavior is asserted, and domain validators need pass/fail fixtures plus an execution harness before fixture evidence is treated as strong.
- `test_signal_quality_audit` output is report-only reviewer evidence; it helps surface weak signals but does not prove industry-grade tests, domain correctness, or enforcement.
- Required external contract surfaces: contract.yaml, governance/framework.lock.json, .git/hooks/pre-commit, .git/hooks/pre-push, .github/copilot-instructions.md.

<!-- governance:key=memory_workflow -->
- Before claiming completion for any change touching `memory/**`, run `python -m governance_tools.memory_workflow --check --repo .`.
- For memory completion claims, run `python -m governance_tools.memory_workflow --check --repo . --run-guard` and report blockers before claiming DONE.
- Use the canonical memory writer for session-derived memory; do not edit memory records as ordinary markdown.
