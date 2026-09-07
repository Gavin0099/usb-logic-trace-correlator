<!-- AI Governance Framework: copilot-instructions BEGIN -->
# Copilot Workspace Instructions
<!-- AI Governance Framework: copilot-instructions v1.1 -->
<!-- Source: ai-governance-framework/governance/copilot-instructions-template.md -->
<!-- Deploy via: bash scripts/install-hooks.sh --target /path/to/repo -->
<!-- Response envelope contract: v0.7 -->
<!-- Everything between the BEGIN and END markers is framework-managed and is
     replaced on every install. Repository-specific Copilot instructions belong
     outside this block; the installer preserves them. -->

## DONE Boundary Rules (MANDATORY)

### Rule 1: Hard Stop After DONE

When the defined DONE condition is met, stop immediately.

Do NOT automatically continue into:
- full regression or broad smoke validation
- governance artifact chains (triage → decision → contract → gate → acceptance → freeze)
- commit, push, closeout, or status rollup
- inspection of unrelated dirty or untracked files

Report next options only. Wait for explicit instruction.

### Rule 2: Scope-Matched Validation

Run targeted validation first (the test file for the changed module only).

Do NOT upgrade to full regression or broader smoke unless:
- the DONE definition explicitly requires it, OR
- the user explicitly requests it

When broader validation fails: report the failure and classification in ONE message, then stop.
Do not build triage/decision/contract chains from a broader validation failure.

### Rule 3: Dirty Tree Allowlist

When the working tree is dirty, produce a concise `git status` summary only.

Stage only files explicitly listed by the user or required by the DONE scope.
Do not read, explain, stage, or modify unrelated dirty or untracked files.

### Rule 4: Result-First Rendering

When reporting task completion, follow `governance/RESPONSE_ENVELOPE_CONTRACT.md`.
The complete machine envelope remains the canonical record. Keep
`mode_source`, `task_authority`, `scope`, `done`, `claim_ceiling`,
`not_claimed`, `evidence_refs`, `risk`, and `next_action` separate and
traceable; compact human text is only a projection and never replaces that
record.

### Compact by default

For a complete task with supporting evidence, use the first three lines in the
session language. Add one `注意：` line when dirty state, high-risk scope, or a
decision-relevant limitation needs to be visible but can still be stated
without changing the claim boundary:

```text
Result: <what is complete>
Reason: <the supporting evidence and claim boundary>
Next step: <one concrete action, or a complete sentence saying none is needed>
注意：<one decision-relevant limitation, when applicable>
```

In Chinese, use `完成：`, `原因：`, and `下一步：`. Bind these lines to
`done`, a directly linked `evidence_refs` entry, and `next_action`; do not
invent a rationale or upgrade structural `PASS` into semantic trust. A
non-decision-relevant `not_claimed` item may remain machine-side without a
visible Cannot claim section. Keep the event/session traceability path,
`task_authority`, and `claim_ceiling` available even when they remain in the
machine record.

### Expanded by trigger

Use expanded reporting only when one of these three conditions applies:

- `full_evidence_request`（要求完整證據）：使用者明確要求完整證據；
- `owner_decision_required`（需要負責人決定）：目前需要負責人回覆或授權；
- `failed_or_partial`（失敗或只完成一部分）：工作失敗、只完成一部分，或必要驗證無法取得、互相矛盾、無法保留宣稱界線。

F-7 terminal results remain an expanded-report exception and must relay the
complete adoption summary required by `governance/F7_FULL_UPDATE.md`, including
the unavailable-summary fallback when applicable.

Expanded output keeps all decision-relevant `not_claimed` items, risks, claim
boundaries, evidence references, and the exact or traceable machine
`next_action`. Emit the primary expansion reason first, then other matching
reasons once in contract priority order. Preserve the machine envelope even
when the human report is expanded.

### Language and progress

Use the current session language for prose and labels. In a Chinese session,
translate conceptual terms such as ordinary expansion policy（一般展開規則）、
dirty state（工作樹未乾淨）、authority surface（治理或權限面）、limitation
（限制）、compact（精簡版）、progress update（進度更新）、adoption summary
（導入摘要）、fallback（退路）、scoped diff（本次範圍差異）與 diagnostics
（靜態檢查）. Keep English only for exact paths, commands, commits, APIs,
schema fields, fixed machine tokens, and trigger IDs. When an exact token is
shown, add its plain-language meaning once.

Keep `注意：` for one decision-relevant limitation. Do not put test commands,
test counts, `git diff --check`, diagnostics, or general worktree status in it;
put those under `驗證：` or the machine `evidence_refs`. Report commands with
complete repository-root paths such as `tests/test_response_envelope_validator.py`,
and use actual workspace-relative file links and verified line numbers.

Progress updates must contain at least one new discovery, root-cause convergence,
or plan change. Omit updates that only narrate routine commands, searches, or
repeated validation; there is no hard maximum number of updates.

Fixed vocabulary remains exact where it is part of machine evidence:
`NOT PRESENT`, `NOT CLAIMED`, `PASS`, `FAIL`, and `NOT RUN`. `PASS` must include
a command, artifact, or source; bare `PASS` is invalid. Do not replace claim
ceiling, risk, authority, or evidence maturity with confidence scores or broad
impact prose.

## Governance Contract Output (MANDATORY)

The rules in the region below are projected verbatim from the canonical source
named in the projection header, which also carries the projection version and
the content digest of that canonical section. Do not edit them here. Edit the
canonical section, then regenerate:

```bash
python -m governance_tools.copilot_instructions_projection --framework-root . --write
```

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

### Surface adaptation: incomplete governance context

This subsection is authored by the framework for Copilot surfaces. It does not
override the canonical rules above; it states what to do when they cannot be
satisfied honestly.

`LOADED` must name governance documents actually loaded into this context, and
the canonical rules require `SYSTEM_PROMPT` among them. This instructions file
is a projection of one canonical section — it is not `SYSTEM_PROMPT.md`, and its
presence is not evidence that `SYSTEM_PROMPT.md` was read. When
`governance/SYSTEM_PROMPT.md` has not actually been loaded into the current
context, no compliant `[Governance Contract]` block can be produced.

In that case emit this notice at the same checkpoints, and never emit a
`[Governance Contract]` block whose `LOADED` names documents that were not read:

```text
[Governance Contract: UNAVAILABLE]
REASON  = governance context incomplete
MISSING = SYSTEM_PROMPT
SOURCE  = .github/copilot-instructions.md (checkpoint projection)
NEXT    = load governance/SYSTEM_PROMPT.md, or ask the human to provide it
```

Reading `governance/SYSTEM_PROMPT.md` during the session clears the notice; from
that point the canonical block applies. Resolve the canonical path against this
repository's governance root — it may sit under a submodule or a contract
directory rather than `governance/` at the repository root.

Filling in field values by inference, or reusing a `[Governance Contract]` block
from an earlier session, is a governance failure. The block is evidence of what
was loaded, not a formatting ritual.
<!-- AI Governance Framework: copilot-instructions END -->
