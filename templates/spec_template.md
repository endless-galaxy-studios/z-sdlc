# DNN: Feature Name — Specification

**Status:** Draft
**Created:** YYYY-MM-DD
**Author:** [Name]
**Depends On:** [D1, D5, etc. or "None"]

---

## Approval Brief

> For CD, who approves the spec from this section. Written last, once the rest of the spec is done, by the spec's author: the plan variant of `[sdlc-root]/templates/pr_description_template.md`, in about 450 words (`[sdlc-root]/process/writing-for-cd.md` § Approval Briefs). Every decision this spec leaves to CD appears under What you're approving. How it works covers only the approach the spec settles. Planning follows the sections below. Delete this note when you fill the section.

### The problem
### What changes for users
### What you're approving
### Scope
### Risk
### Review focus
### How it will be verified
### How it works
### Learn the change

---

## 1. Problem Statement

[What problem does this solve? Why is it needed?]

---

## 2. Requirements

### Functional
- [ ] Requirement 1
- [ ] Requirement 2

### Non-Functional
- [ ] Performance: [constraint]
- [ ] Security: [constraint]

---

## 3. Scope

### Components Affected
- [ ] [List the packages, modules, or components this touches]

### Domain Scope
- [ ] [Which areas of the domain this touches — e.g., all users, specific feature area, infrastructure-only]

### Data Model Changes
- [What data structures change, or "None"]

### Interface / Adapter Changes
- [New methods, new fields, or "None"]

---

## 4. Design

### Approach

[High-level approach to solving the problem]

### Key Components

| Component | Purpose |
|-----------|---------|
| [Name] | [What it does] |

### Data Model (if applicable)

```
[Schema, types, or structure]
```

### API (if applicable)

```
[Endpoints, function signatures]
```

---

## 5. Testing Strategy

- [ ] Build-only (no runtime tests)
- [ ] Manual QA: [describe steps]
- [ ] Unit tests: [describe coverage]
- [ ] Integration / E2E tests: [describe scenarios]

---

## 6. Success Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests pass

---

## 7. Constraints

- [Performance, security, compatibility constraints]

---

## 8. Estimation

| Dimension | Rating | Rationale |
|-----------|--------|-----------|
| **Validity** | [Low / Medium / High] | [How confident are we that the requirements are right?] |
| **Correctness** | [Low / Medium / High] | [How likely is the implementation to be correct on the first pass?] |
| **Effort** | [Light / Moderate / Heavy] | [How many human–AI coordination cycles will this need?] |

---

## 9. Out of Scope

- [What this deliverable explicitly does NOT include]

---

## 10. Open Questions / Unknowns

Each unknown is a risk the plan must address or accept.

- [ ] **Unknown**: [What you don't know]
  - **Risk**: [What could go wrong]
  - **Mitigation**: [How the plan should handle this — prototype (external), feasibility audit (own code), or accept]
  - **Plan-shaping?**: [Yes/No — does the answer change the plan's structure (split, phase count, scope, sequencing)? If yes, it MUST be resolved at planning time via the Feasibility Gate, NOT deferred to an execution spike.]
