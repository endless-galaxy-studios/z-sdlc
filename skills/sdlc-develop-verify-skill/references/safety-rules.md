# Safety Rules

The rules that bind every drive of the app, in `sdlc-develop-verify-skill`'s two modes and in every later run of the verify skill it writes. CREATE copies the list below word for word into the generated skill's Safety Rules section; MAINTAIN step 1 replaces that section when it differs; the step 6 reviewer checks the copy against this file.

## The Rules

- **Drive only an instance started for this verification run,** on disposable local data. Never production, a shared environment, or a session someone is using. If two instances can't run side by side, Launch says so, and a run refuses to drive one it didn't start.
- **Point every target at this run's own copy.** Each database, queue, cache, storage bucket and service URL the app reads is overridden to a local or disposable one. Before the first write of any kind (create, migrate, seed or reset), the run confirms each one by something observed, such as the app's own log or a config command naming the host and database it resolved, and the health check confirms them again. A target the run can't see resolving locally counts as not overridden. A default from `.env` that points at a shared service is never used.
- **No effect outside the machine.** Every outbound integration (mail, payments, messages, webhooks, third-party writes) is sandboxed or stubbed, and the health check confirms it with something observed, such as a local mail catcher receiving the message or a sandbox host in the logs. A feature that needs a live integration is `unreachable`, with that reason.
- **Stop only what this run started,** by the process ID, container or session name the run recorded under its run ID. Never by process name or by whatever holds a port.
- **Secrets by name only.** The skill and the map name the variables that hold secrets, never their values. Evidence strips auth headers, cookies and tokens, and before a run reports its result it searches the evidence for those variables' values.
- **Evidence survives cleanup.** It goes to `.claude/skills/verify/.evidence/<run ID>/`, which the skill's own `.gitignore` excludes. Cleanup never touches it, and it is never committed.
- **Prove the real user path:** the route a user takes, not internal setters or test-only endpoints. Capture the action and the resulting state, and check side effects (rows written, files saved) alongside what's visible. Mock only where a production boundary already isolates the outside system.
