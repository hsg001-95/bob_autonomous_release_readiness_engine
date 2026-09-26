# System Architecture
## Autonomous Release Readiness and Governance Engine (RRE)

---

## 1. Architectural Principles

1. **Context isolation over context accumulation.** Deep exploration work happens in disposable subagent contexts; the coordinator only ever holds summaries.
2. **Separation of authoring and verification.** The agent that writes a fix (Actor) is never the agent that approves it (Critic) — this is enforced structurally (`fork_context: false`), not by instruction.
3. **Declarative before autonomous.** Nothing executes without a persisted, human-approved plan. Governance lives in version-controlled files, not in transient prompts.
4. **Standard artifacts over bespoke output.** Findings are expressed in SARIF 2.1.0 so they plug into existing security tooling (GitHub code scanning, etc.) rather than a proprietary format.
5. **Two entry points, one workflow.** The same skill definition drives both interactive IDE use and headless CI execution — no logic fork between the two.

## 2. Component Diagram (textual)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Developer / CI Trigger                     │
│   IDE: "/release-readiness-audit ..."   |   CLI: `bob run ...`  │
└───────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Coordinator Session    │
                    │  (Plan Mode → Agent Mode)│
                    └───────────┬─────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             │  1. Spec Ingestion (Docling)           │
             │     PDF/DOCX/MD → structured contracts │
             └───────────────────┬───────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │ plans/release-readiness- │
                    │       plan.md            │◄── human approval gate
                    └───────────┬─────────────┘
                                 │ (approved)
                                 ▼
        ┌────────────────────────────────────────────────┐
        │        Parallel Subagent Audit Swarm            │
        │  (spawn_subagent, isolated contexts, default:    │
        │   fork_context: false unless explicitly needed)  │
        ├───────────────┬───────────────┬─────────────────┤
        │ arch-auditor   │ supply-sentinel│ contract-guard  │
        │ (explore)      │ (explore)      │ (general)       │
        │ src/db/ vs spec│ requirements.* │ src/api/ vs spec│
        └───────┬───────┴───────┬───────┴────────┬────────┘
                │  consolidated  │  consolidated   │ consolidated
                │    findings    │    findings     │   findings
                └───────────────┴────────┬────────┴────────┘
                                          ▼
                          ┌───────────────────────────┐
                          │   Coordinator: Findings    │
                          │   Aggregation & Triage      │
                          └─────────────┬─────────────┘
                                          │ High/Critical findings
                                          ▼
                          ┌───────────────────────────┐
                          │   Actor (Agent Mode)       │
                          │   generates minimal patch   │
                          │   per .bob/rules/security.md│
                          └─────────────┬─────────────┘
                                          │ patch applied
                                          ▼
                          ┌───────────────────────────┐
                          │  Critic (isolated subagent,│
                          │  fork_context: false)      │
                          │  - re-checks vs rule book   │
                          │  - runs targeted test suite │
                          └─────────────┬─────────────┘
                              pass ◄─────┴─────► fail → loop to Actor
                                │
                                ▼
                ┌───────────────────────────────────┐
                │   Artifact Generation               │
                │   security/audit-results.sarif      │
                │   RELEASE_NOTES.md                  │
                └───────────────┬─────────────────────┘
                                 ▼
                ┌───────────────────────────────────┐
                │   Gate Decision                     │
                │   Interactive: presented to dev     │
                │   CI: exit 0 / exit non-zero         │
                └───────────────────────────────────┘
```

## 3. Components

### 3.1 Coordinator Session
The top-level Bob 2.0 session. Owns mode transitions (Ask → Plan → Agent), holds only consolidated findings (never raw subagent tool logs), and is the sole context that persists across the full run. Reads `AGENTS.md` at session start.

### 3.2 Specification Ingestion Layer
Uses Bob 2.0's native Docling integration to parse spec documents (PDF/DOCX/MD) into structured constraints: endpoint contracts, DB indexing rules, auth policy, compliance clauses. Output is not free text — it is a structured constraint set the coordinator can diff against repository state.

### 3.3 Plan Artifact (`plans/release-readiness-plan.md`)
A persisted, human-readable checklist mapping each ingested constraint to a verification step and the subagent responsible for it. This is the human approval gate — the system will not proceed to Agent Mode / subagent spawning without explicit confirmation.

### 3.4 Subagent Audit Swarm
Three subagents, spawned via `spawn_subagent`, run concurrently in isolated context windows:

| Subagent | Type | Scope | Output |
|---|---|---|---|
| `arch-auditor` | explore (lightweight model) | `src/db/`, migration scripts vs. spec schema/index rules | Schema drift findings |
| `supply-sentinel` | explore (lightweight model) | `requirements.txt` / package manifests vs. CVSS threshold and provenance (R10) | Vulnerable/outdated dependency findings + `sbom/bom.json` |
| `contract-guard` | general (default model) | `src/api/` route handlers vs. spec request/response contracts | Contract-drift findings |
| `secrets-sentinel` | explore (lightweight model) | Full repository tree (minus `.bobignore`) — pattern + entropy scan (R9) | Literal-secret findings, always `critical` |

Each subagent terminates after returning a structured summary; no subagent tool call log reaches the coordinator directly.

### 3.5 Actor-Critic Remediation Loop
- **Actor** (Agent Mode, full read/write/exec): drafts the smallest patch that resolves a finding, constrained by `.bob/rules/security.md`.
- **Critic** (isolated subagent, `fork_context: false`): receives *only* the modified files and the rule book — never the Actor's prompt/reasoning history. Independently re-evaluates the patch and executes the relevant test subset (`pytest tests/...`). On failure, control returns to the Actor with the Critic's findings; on pass, the patch is accepted.

### 3.6 Artifact Generator
Assembles all findings, remediation diffs, and test outcomes into:
- `security/audit-results.sarif` (SARIF 2.1.0, schema-validated)
- `RELEASE_NOTES.md` (semantic summary)

### 3.7 Gate
- **Interactive**: findings and artifacts are surfaced to the developer in the IDE for review.
- **Headless (CI)**: `bob run --skill release-readiness-audit --mode Agent --auto-approve "read,test" ...` exits non-zero if unresolved Critical/High findings or failing tests remain, halting the pipeline.

## 4. Data Flow Summary

1. Spec document → Docling → structured constraints
2. Constraints + repo → verification plan (persisted, approved)
3. Plan → 3 parallel isolated subagent audits → consolidated findings
4. Findings → Actor patch → Critic verification (isolated) → accepted/rejected patch
5. Accepted patches + findings + test results → SARIF + RELEASE_NOTES.md
6. Artifacts → gate decision (human or CI)

## 5. Governance Layer (cross-cutting)

These files apply across every phase above, not as a separate step:

- `AGENTS.md` — injected into every session; defines architecture, immutable-spec-baseline rule, zero-tolerance rules, and the delegate-to-subagents-for-deep-search rule.
- `.bobignore` — prevents any agent (Actor, Critic, or explore subagents) from reading/writing credentials, secrets, build artifacts, or `node_modules`.
- `.bob/rules/security.md` — the constraint set the Actor must comply with and the Critic validates against.
- `.bob/skills/release-readiness-audit/SKILL.md` — the reusable, version-controlled procedure definition that ties all of the above together and is what a user invokes.

## 6. Technology Boundaries

| Layer | Provided by | Built by this project |
|---|---|---|
| Model orchestration, mode switching, subagent spawning | IBM Bob 2.0 platform | — |
| Document parsing (PDF/DOCX/MD → structure) | Docling (native Bob 2.0 integration) | — |
| Verification logic, rule definitions, skill procedure | — | This project (`AGENTS.md`, rule book, skill) |
| SARIF assembly / report templating helpers (if any scripted outside the agent loop) | — | This project, standard library only |
| Demo target application + seeded findings | — | This project |
