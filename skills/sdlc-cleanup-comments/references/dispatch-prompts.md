# Dispatch Prompts

The three prompts `sdlc-cleanup-comments` sends: the trimmer prompt (step 4), one per slice, to the slice's domain agent; the check prompt (step 5), to a fresh `code-reviewer`; and the fix prompt (step 6), to the agent that owns a file a new verify failure names. All three follow the full dispatch template in `[sdlc-root]/knowledge/architecture/agent-orchestration-patterns.yaml` § dispatch_prompt_templates. Fill in the braces, and drop a line in braces that doesn't apply. Don't restate the comment rule in a prompt: the knowledge file is the rule.

## Trimmer Prompt

```markdown
**Objective:** Cut the comments in your slice that repeat or narrate the code, keep the ones that carry what the code can't show, and report what needs CD's eye.

**Owned files:** {the slice's file list}. You may edit comments in these files and nothing else.

**Constraints:**
- Read [sdlc-root]/knowledge/coding/comment-discipline.yaml. It is the rule. Follow all of it, including its trimming rules for unclear comments, contradictions, constraints and vague TODOs.
- Read .claude/skills/sdlc-cleanup-comments/references/machine-read-comments.md. Never cut or edit a comment it describes.
- Read {the agent's mapped knowledge files} for this codebase's patterns.
- {Commit-range scope only: trim only comments that {range} added or changed. Leave every other comment alone.}
- {Headless run only: this run is headless. Ask nothing; put questions in your report. Cause no side effect outside the working tree: no push, post, comment or external send.}
- You may do three things: delete a comment; shorten one by cutting the part that repeats the code, keeping the reason's original wording; and delete the one blank line a cut leaves redundant (two blank lines in a row, or a blank line against a brace). When you cut a trailing comment, the padding before it goes too. Nothing else: no code edits, no other reformatting, no new comments, no rewording. Don't stage or commit.
- `suppressions` is this skill's own list, not one of the rule's kinds. List a lint or type suppression whose rule guards correctness or security, such as `# nosec`, an `@ts-ignore` over a type error, or an `eslint-disable` of a rule that catches bugs. Never edit it.
- While reading, note up to 10 spots in your slice where non-obvious code has no explanation. For each, read the commits that wrote it and their pull request. Record the reason and its source (commit SHA or PR number) if one is stated, or "no source found". Don't write the comment.

**Acceptance criteria:**
- In your files, `git diff HEAD` shows only deleted comment lines, shortened comment lines, blank lines a cut left redundant, and code lines whose trailing comment and its padding were removed with the code unchanged token for token. No other code, no other whitespace, and no line order changed.
- `lines_modified` counts every line changed in place: shortened comment lines plus code lines that lost a trailing comment.
- You return the report below. Every entry has a `location` (`path:line` in your file now) and an `anchor`: the first words of the comment, or for gaps and reshape candidates, the code token at that line. The orchestrator uses the anchor to find the line again after other lines move.

**Out of scope:**
- Changing code so a comment becomes unnecessary. List it under `reshape`.
- Fixing a contradiction, a constraint or a suppressed rule. List it.
- Writing a new comment or rewording a kept one.
- Files outside your slice.

**Report:**
    slice: {slice name}
    files_changed: [{path}, ...]
    lines_cut: {N}
    comments_shortened: {N}
    lines_modified: {N}
    kept_for_cd:        # unclear whether it carries a reason; vague TODOs
      - {location: "path:line", anchor: "...", comment: "...", why_unclear: "..."}
    contradicts_code:   # the comment says something the code doesn't do
      - {location: "path:line", anchor: "...", comment_says: "...", code_does: "..."}
    gaps:               # non-obvious code with no explanation, at most 10
      - {location: "path:line", anchor: "...", unclear: "...", reason: "... or no source found", source: "SHA or PR#"}
    reshape:            # a comment explaining a surprise in our own code
      - {location: "path:line", anchor: "...", symbol: "...", comment: "...", suggestion: "rename / extract / type / split"}
    constraints:        # a rule the code relies on, stated only in a comment
      - {location: "path:line", anchor: "...", constraint: "...", possible_check: "type / test / lint"}
    suppressions:       # a lint or type suppression whose rule protects correctness or safety
      - {location: "path:line", anchor: "...", suppression: "...", rule_protects: "..."}
```

## Check Prompt

```markdown
**Objective:** Check every cut and every shortened comment in this diff against the comment rule. Report problems. Change nothing.

**Owned files:** Read-only. Do not modify files.

**Constraints:**
- Read [sdlc-root]/knowledge/coding/comment-discipline.yaml. It is the rule.
- Read .claude/skills/sdlc-cleanup-comments/references/machine-read-comments.md.
- {Headless run only: this run is headless. Ask nothing; put questions in your report.}
- {Commit-range scope only: the trim covers only comments that {range} added or changed.}
- The diff: `git diff -U0 HEAD -- {slice files}`. Each `@@` header starts one hunk; get the count with `git diff -U0 HEAD -- {slice files} | grep -c '^@@'`. Read each removed comment with the code around it as it was before the trim (`git show HEAD:{path}`).
- A clean report is an expected, acceptable outcome. It still states how many hunks you reviewed, and that count must match the diff's.

**Acceptance criteria:** Start with `hunks_reviewed: {N}` and `problems: {M}`. Then one row per problem hunk, with the `HEAD` line number, the original text, and one of these kinds:
- `keep-cut`: cut a comment of a kind the rule's keep list names.
- `machine-read`: cut or changed a comment a tool reads.
- `code-changed`: changed code other than removing a trailing comment and its padding, changed whitespace other than deleting a blank line a cut left redundant, or changed line order.
- `out-of-range`: for a commit-range scope, cut or changed a comment the range didn't add or change.
- `reason-lost`: shortened a comment and dropped its reason.
- `text-added`: a shortened comment has words the original didn't.
- `listed-item-cut`: cut a comment of a kind the rule says to keep and list. Name the list it belongs on (`kept_for_cd`, `contradicts_code`, `reshape` or `constraints`), and fill in that list's fields in the trimmer report's shape, with the `HEAD` location and an anchor.

**Out of scope:** Comments the trimmer kept, suggestions for further cuts, and fixes.
```

## Fix Prompt

```markdown
**Objective:** A check that passed before the comment trim fails now. Find the cut in your slice that caused it, and undo only what the failure needs.

**Owned files:** {the slice's file list}. Change only the lines this fix needs, in the one file it needs.

**Constraints:**
- The failure: {the verify command and the output of the new failure}.
- Read .claude/skills/sdlc-cleanup-comments/references/machine-read-comments.md.
- {Headless run only: this run is headless. Ask nothing; put questions in your report. Cause no side effect outside the working tree: no push, post, comment or external send.}
- Your slice's trims are in `git diff HEAD -- {slice files}`, and the original text is in `git show HEAD:{path}`.
- A cut breaks a tool in one of two ways, and you may make only the matching fix:
  - The tool needed the comment: a suppression, a directive, a doc tag, a docstring a framework reads, or the only content of a block. Put back that hunk's exact `HEAD` text.
  - The cut left a blank line the tool rejects: two blank lines in a row, or a blank line against a brace. Delete that one blank line, and the cut stands.
- Don't stage or commit.

**Acceptance criteria:** Only the file you name has changed since the trim. A put-back matches `HEAD` byte for byte, and its hunk is gone from `git diff -U0 HEAD -- {path}`. A deleted blank line is the only other change.

**Out of scope:** Fixing code, a failure the trim didn't cause, and any other cut.

**Report:**
    cause_found: yes | no
    file: {path}
    fix: put-back | blank-line
    location: "path:line"
    the_cut: "{the comment that was cut, or the blank line}"
    what_failed: "{the check and its message}"
```
