# Business Analysis Knowledge Store — Cross-Project

Requirements elicitation patterns, acceptance criteria feedback loops, and domain modeling principles that apply across all projects using the SDLC framework. Focuses on how requirements flow between BA and other disciplines.

## Structure

```
knowledge/business-analysis/
├── README.md                              ← This file
├── data-storytelling-rules.yaml           ← Data presentations as narratives: insight-first headlines, progressive reveal, uncertainty
├── gdpr-patterns.yaml                     ← GDPR legal basis, consent, data subject rights, retention, breach notification
└── requirements-feedback-loops.yaml       ← Bidirectional acceptance criteria, test data as domain modeling, domain validation
```

## How This Gets Used

1. **BA practitioners** consult feedback loop patterns when writing specs (checklist of commonly missing criteria)
2. **Testers** reference the reverse flow pattern when test execution reveals unstated assumptions
3. **Architects** use the domain validation pattern when proposing expected values for computed fields
4. **Planning agents** check for bidirectional criteria completeness during spec review

## Relationship to Other Knowledge Stores

- **`[sdlc-root]/knowledge/testing/testing-paradigm.yaml`** — the testing-side view of boundary case discovery (test data design surfaces domain questions)
- **`[sdlc-root]/knowledge/coding/code-quality-principles.yaml`** — the cross-discipline flow pattern (testability gaps flowing back from testing to coding)
- **`[sdlc-root]/knowledge/architecture/knowledge-management-methodology.yaml`** — the generalized cross-discipline remediation flow

## Maintenance

- Updated when spec reviews or test sessions reveal new patterns of missing requirements
- Entries promoted from `[sdlc-root]/disciplines/business-analysis.md` parking lot after validation through real use
