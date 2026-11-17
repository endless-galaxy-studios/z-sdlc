"""The project's host module for the checks-only production broker (factory_op.py, z-sdlc's factory-broker bundle).

This file is the project's: write it for the host production runs on. The broker loads it only inside a sandboxed
step, as the operator user, with no IP network and only the egress hosts the catalog's `broker` block declares, and
never as root. It is in the operations digest, so a change here means re-running setup on the host.

Until it's written, every primitive below fails its step closed, so no gate can pass on a host nobody described.
The contract, each primitive's arguments, what it returns and what the broker checks on each return, is in
z-sdlc's process/factory-broker.md, § The host module (installed at [sdlc-root]/process/factory-broker.md).

Import only what the broker's HOST_API names:
    from factory_op import StepFailed, Unavailable, HostError, Deployment, STATUSES, Deadline, NETWORK_ERRORS, SHA, safe, parse_ts, canonical
"""

from factory_op import StepFailed


def _unwritten(name):
    raise StepFailed(f"the host module isn't written yet: {name} (process/factory-broker.md, § The host module)")


def client(ctx):
    """The host API client, built from the step's credential (ctx.secret(label)), read-only."""
    _unwritten("client")


def preflight(ctx):
    """config.json's host block is valid and names exactly the declared services; the credential is this project's."""
    _unwritten("preflight")


def latest(ctx):
    """{service: newest deployment status or None}, for every declared service, in one read."""
    _unwritten("latest")


def deployments(ctx, svc):
    """The service's recent deployments, at least the newest 20, as Deployment(id, commit, status, created, branch)."""
    _unwritten("deployments")


def serving(ctx, svc):
    """The newest successful deployment, or None."""
    _unwritten("serving")


def reports(ctx, svc, deployment_id):
    """Whether the running service says it is this deployment, and ready. Raise Unavailable for no usable answer."""
    _unwritten("reports")


def heartbeat(ctx, svc, deployment_id, patient):
    """(started, written) for this deployment, or None for not yet; StepFailed when definitive."""
    _unwritten("heartbeat")


def capture(ctx):
    """capture-state's outputs: <svc>_commit and <svc>_settled per checked service, every recorded and invariant one."""
    _unwritten("capture")


# The host's own catalog operations, {name: fn(ctx) -> {output: value}}: exactly the broker block's host_ops.
OPS = {}

# Checks CD runs by hand (`diagnose <name>`), {name: fn(ctx)}; each fails its own step when something is wrong.
DIAGNOSTICS = {}
