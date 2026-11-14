# Process Documentation

Workflow rules, behavioral protocols, and process definitions. Skills reference these files instead of duplicating shared logic.

## Files

### Workflow
| File | Purpose |
|------|---------|
| `overview.md` | The full SDLC flow: Idea → Spec → Plan → Execute → Validate → Deploy → Result → Chronicle |
| `deliverable_lifecycle.md` | State machine for deliverables (Draft → In Progress → Validated → Deployed → Complete → Archived) |
| `collaboration_model.md` | How CD (human) and CC (agent system) interact — roles, responsibilities, communication patterns |
| `chronicle_organization.md` | How and when to archive completed work from `current_work/` to `chronicle/` |
| `ad_hoc_reconciliation.md` | Sweeping untracked ad hoc commits back into the deliverable catalog |
| `compliance_audit.md` | What the compliance audit checks and how to run one |

### Shared Behavioral Protocols
| File | Referenced By | Purpose |
|------|-------------|---------|
| `manager-rule.md` | 5+ skills | The orchestrator dispatches domain agents by default. It applies a change itself only under the Delegation Economics Exception, every change is reviewed before commit, and there is no complexity exception. |
| `review-fix-loop.md` | 7 skills | The loop for every review context (code, plan, reference doc): roster rule → verify → dedup/calibrate/classify → fix critical+major → mechanical re-review → exit when no critical/major remain, 3-round cap. Owns the two mirrored critical-steps blocks |
| `finding-classification.md` | 7 skills | FIX / PLAN / INVESTIGATE / DECIDE / PRE-EXISTING taxonomy with per-skill subsets; owns the one severity scale (impact × likelihood) and calibration, the deduplication table, the planning scope-change marker, and Open Minor Findings |
| `headless-mode.md` | Every skill, `CLAUDE-SDLC.md` | Running a skill with no person present (CI, an agent factory, `claude -p`): how a run knows it is headless, why every question, approval or escalation stops the run instead of being guessed past, outward actions handed to the caller, the result format, and restart-not-resume. Owns the mirrored stop-rule block every skill carries |
| `production-gates.md` | `sdlc-plan`, `sdlc-lite-plan`, `sdlc-execute`, `sdlc-lite-execute`, the plan and result templates | Work that touches production happens only in gates between phases, never in a phase: the gate section, review and commit before a gate, interactive and headless behavior at a gate, and the optional operations catalog a production runner uses |
| `discipline_capture.md` | 6 skills | Lightweight protocol for capturing cross-discipline insights during active work |

### Meta
| File | Purpose |
|------|---------|
| `sdlc_changelog.md` | Living record of process changes — what changed, why, and where the change originated |
| `changelog-archive/` | Older changelog entries, one file per quarter (`YYYY-Qn.md`), moved there unedited once the changelog passes about 150 KB (`sdlc-archive`) |
