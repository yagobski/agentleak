"""Leak provenance and agent topology — the debugging views.

Two graphs are derived from a run's events and findings:

- **Leak paths** (`build_leak_paths`): for each leaked secret, the ordered chain
  of events that carried it — from where it *entered* the system (a source
  channel like ``tool_response``) through each agent/component that handled it, to
  where it was *disclosed*. This is what lets you trace, in a multi-agent system,
  *where a leak originated and how it propagated*.

- **Topology** (`build_topology`): the agent/component graph — nodes are the
  participants (agents, tools, memory, logs, the user…), edges are the channels
  between them, and edges that carried a leak are flagged with their severity.
  It's a behavioral model of the agent, built from what it actually did.

Both are pure functions over lightweight event dicts (``event_id`` / ``channel``
/ ``source`` / ``target``) and :class:`~agentleak.core.detector.Finding`s, so
they add no dependency and can be recomputed or rendered anywhere.
"""

from __future__ import annotations

from typing import Any

from .agentrisk import BASELINE_CHANNELS, LEVEL_LABELS
from .detector import Finding

# Each channel implies a role for its source (who emitted) and target (who
# received). Used to classify nodes into lanes for the diagram.
_CHANNEL_ROLES: dict[str, tuple[str, str]] = {
    "user_input": ("user", "agent"),
    "tool_call": ("agent", "external"),   # outbound: the call target is a sink
    "tool_response": ("tool", "agent"),   # inbound: the responder is a source
    "inter_agent_message": ("agent", "agent"),
    "shared_memory": ("agent", "memory"),
    "log": ("agent", "log"),
    "generated_file": ("agent", "file"),
    "final_output": ("agent", "output"),
}

# Priority when a node plays several roles (an actor always wins).
_KIND_PRIORITY = ("agent", "user", "tool", "memory", "external", "file", "log", "output")

# Lane (column) per kind: inputs left, agents middle, sinks right.
_KIND_LANE = {
    "user": 0, "tool": 0,
    "agent": 1,
    "memory": 2, "log": 2, "file": 2, "external": 2, "output": 2,
}

# Synthetic participant labels used only when a framework did not attach
# explicit ``source`` / ``target`` metadata to an event.  The channel still
# tells us the direction of travel, so preserving that structure is more useful
# (and more truthful) than collapsing every endpoint into one ``unknown`` node.
_IMPLIED_NODE_ID = {
    "user": "user",
    "tool": "tool / data",
    "agent": "agent",
    "memory": "shared memory",
    "log": "logs",
    "file": "generated file",
    "external": "external tool",
    "output": "final output",
}


def _roles_for(channel: str) -> tuple[str, str]:
    return _CHANNEL_ROLES.get(channel, ("agent", "external"))


def _pick_kind(tags: set[str]) -> str:
    for kind in _KIND_PRIORITY:
        if kind in tags:
            return kind
    return "agent"


def _event_endpoints(event: dict[str, Any]) -> tuple[str, str]:
    """Return explicit endpoints, or infer them from channel semantics.

    Real framework adapters normally provide participant names.  Scripted
    scenarios and minimal SDK traces may not; in that case the channel roles
    still define a reliable source → agent → sink flow.  ``agent`` is carried
    as display-only metadata by the runner and falls back to a generic label.
    """
    source_role, target_role = _roles_for(str(event["channel"]))
    agent = str(event.get("agent") or "agent")

    def implied(role: str) -> str:
        return agent if role == "agent" else _IMPLIED_NODE_ID.get(role, role)

    def explicit(value: Any) -> str | None:
        text = str(value or "").strip()
        return None if text.lower() in {"", "unknown", "?"} else text

    return (
        explicit(event.get("source")) or implied(source_role),
        explicit(event.get("target")) or implied(target_role),
    )


def build_topology(events: list[dict[str, Any]], findings: list[Finding]) -> dict[str, Any]:
    """Build the participant graph with leak-carrying edges highlighted."""
    role_tags: dict[str, set[str]] = {}
    for ev in events:
        src_role, tgt_role = _roles_for(ev["channel"])
        source, target = _event_endpoints(ev)
        role_tags.setdefault(source, set()).add(src_role)
        role_tags.setdefault(target, set()).add(tgt_role)

    nodes = [
        {"id": node, "kind": (kind := _pick_kind(tags)), "lane": _KIND_LANE.get(kind, 1)}
        for node, tags in role_tags.items()
    ]
    nodes.sort(key=lambda n: (n["lane"], n["id"]))

    # Highest leaked level per (source, target, channel).
    events_by_id = {str(ev["event_id"]): ev for ev in events}
    leak_level: dict[tuple[str, str, str], int] = {}
    for f in findings:
        if f.channel in BASELINE_CHANNELS:
            continue
        event = events_by_id.get(f.event_id, {
            "channel": f.channel,
            "source": f.source,
            "target": f.target,
        })
        source, target = _event_endpoints(event)
        key = (source, target, f.channel)
        leak_level[key] = max(leak_level.get(key, 0), f.level)

    edges_acc: dict[tuple[str, str, str], int] = {}
    for ev in events:
        source, target = _event_endpoints(ev)
        key = (source, target, ev["channel"])
        edges_acc[key] = edges_acc.get(key, 0) + 1

    edges: list[dict[str, Any]] = []
    for (source, target, channel), count in edges_acc.items():
        level = leak_level.get((source, target, channel), 0)
        edges.append({
            "source": source,
            "target": target,
            "channel": channel,
            "count": count,
            "leaked": level > 0,
            "level": level,
            "level_label": LEVEL_LABELS.get(level, ""),
        })
    edges.sort(key=lambda e: (-int(e["level"]), str(e["source"]), str(e["target"])))
    return {"nodes": nodes, "edges": edges}


def build_leak_paths(
    events: list[dict[str, Any]], findings: list[Finding], *, redact: bool = True
) -> list[dict[str, Any]]:
    """Trace each leaked secret from its origin through every hop to disclosure.

    Secrets are correlated on their raw value internally; the output only ever
    carries the redacted form. A secret is included only if it was disclosed on
    at least one non-baseline channel.
    """
    order = {ev["event_id"]: i for i, ev in enumerate(events)}
    events_by_id = {str(ev["event_id"]): ev for ev in events}

    # Group all occurrences (sources + disclosures) of each distinct secret.
    groups: dict[tuple[str, str], list[Finding]] = {}
    for f in findings:
        groups.setdefault((f.data_type, f.matched_value), []).append(f)

    paths: list[dict[str, Any]] = []
    for (data_type, value), occ in groups.items():
        occ.sort(key=lambda f: order.get(f.event_id, 1_000_000))
        steps = []
        for f in occ:
            event = events_by_id.get(f.event_id, {
                "channel": f.channel,
                "source": f.source,
                "target": f.target,
            })
            source, target = _event_endpoints(event)
            steps.append({
                "event_id": f.event_id,
                "channel": f.channel,
                "source": source,
                "target": target,
                "kind": "source" if f.channel in BASELINE_CHANNELS else "leak",
                "level": f.level,
                "level_label": LEVEL_LABELS.get(f.level, ""),
            })
        leak_findings = [f for f in occ if f.channel not in BASELINE_CHANNELS]
        if not leak_findings:
            continue  # entered but never disclosed — not a leak path

        max_level = max(f.level for f in leak_findings)
        origin = steps[0]
        paths.append({
            "data_type": data_type,
            "value": occ[0].redacted_value if redact else value,
            "level": max_level,
            "level_label": LEVEL_LABELS.get(max_level, ""),
            "entered_via": origin["channel"] if origin["kind"] == "source" else None,
            "origin": origin,
            "leak_count": len(leak_findings),
            "channels": sorted({f.channel for f in leak_findings}),
            "agents": sorted({
                step["source"]
                for step in steps
                if step["kind"] == "leak"
                and _roles_for(str(step["channel"]))[0] == "agent"
            }),
            "steps": steps,
        })

    paths.sort(key=lambda p: (-int(p["level"]), -int(p["leak_count"]), str(p["data_type"])))
    return paths
