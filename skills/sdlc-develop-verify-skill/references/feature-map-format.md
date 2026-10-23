# Feature Map Format

The feature map is `.claude/skills/verify/features/`: an index, `README.md`, and one file per user-facing feature. CREATE seeds it with the 3 to 5 most-used features (step 4); MAINTAIN keeps it true (steps 1 to 5). It describes what a user does and sees, never how the code does it; the only code it names is each feature's `Source:` in the index.

## The Index: `features/README.md`

Five sections, in this order:

1. **Baseline preconditions:** the state every recipe starts from: the URL or command, the disposable data folder, the seed data, the health check that must pass, and "never drive an instance this run didn't start."
2. **Driving conventions:** which harness runs what, which handles to prefer (accessible names over CSS selectors or position), that commands are literal, and that a recipe restores seed data after it changes something.
3. **Proof and reporting:** what each proof captures (the action and the resulting state; for UI a snapshot and a screenshot; for a CLI the command, output and exit code; for a change, a second read-only view of the stored value), that each artifact names its feature and entry point, and that an unreachable path is reported with the route tried and the missing prerequisite. A path that was skipped is never reported as proven through another one.
4. **Feature file contract:** the shape below.
5. **Features:** one line per feature file: a link, what it covers, its status if it isn't proven (`unproven` or `unreachable`, with the reason), and `Source:` with the paths or folders that implement it. MAINTAIN picks each feature's readers from those paths; nothing else in the map names code.

## A Feature File

An H1 with the feature's name, one paragraph on what a user can do with it, then exactly four H2 sections in this order:

1. **`Sub-features`:** a short ID and one line for each behavior.
2. **`How a user reaches it`:** every entry point: buttons, shortcuts, routes, commands.
3. **`Driving it with {harness}`:** starts with `Preconditions:`, then one bullet per step. Each bullet pairs the user's action with the exact command and the result a user would see.
4. **`Gotchas`:** traps that waste a run or make its proof wrong, including any precondition the seed data lacks.

The map lists every entry point. A proof that drives only the most convenient one is incomplete.

## Example

A feature file for Tally, the fictional expense tracker in `generated-skill-template.md`:

```markdown
# Record an Expense

A signed-in user records an expense with an amount, a category and a date, from the dashboard or the
CLI, and sees it in the month's list and total.

## Sub-features

- `expense-add`: saves an expense from the dashboard form.
- `expense-validate`: rejects a missing amount or a future date with a message.
- `expense-cli`: records the same expense from `tally add`.

## How a user reaches it

- The "Add expense" button on the dashboard.
- The `a` key on the dashboard, when no text field has focus.
- `tally add --amount <n> --category <name> --date <yyyy-mm-dd>` in a terminal.

## Driving it with Playwright MCP

Preconditions:

- Tally is healthy at `http://127.0.0.1:5180`, signed in as `TALLY_TEST_EMAIL`.
- The seed month has no expense in category "Travel".

- **Open the form.** Choose "Add expense": click the button named "Add expense". A dialog named
  "New expense" opens with focus in "Amount".
- **Save.** Fill "Amount" with `42.50`, choose "Travel" in "Category", keep today's date, and click
  "Save". The dialog closes and the list shows "Travel, 42.50".
- **Check it stuck.** Reload the page. The month total has risen by 42.50, and the row is still there.
- **Reject bad input.** Open the form, leave "Amount" empty and click "Save". The message "Enter an
  amount" appears and nothing is saved.
- **From the CLI.** Run `tally add --amount 12 --category Travel --date <today> --json`. Exit code 0,
  and the output has the new expense's ID.
- **Proof.** Save an accessibility snapshot and a screenshot of the list to
  `.evidence/<run>/expense-add/`, and the CLI output to `.evidence/<run>/expense-cli/`.

## Gotchas

- The `a` key types into a focused field instead of opening the form.
- Amounts are rounded to cents on save. Check the list, not the field you typed into.
- A "Saved" toast is not proof. Reload and read the list.
- Delete both test expenses during cleanup; keep their evidence.
```
