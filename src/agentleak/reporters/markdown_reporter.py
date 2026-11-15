# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Markdown report — readable in any editor, PR, or terminal."""

from __future__ import annotations

from typing import Any

_BADGE_ORDER = ["critical", "high", "medium", "low"]
_LEVEL_LABEL = {
    "critical": "L4 critical",
    "high": "L3 high",
    "medium": "L2 medium",
    "low": "L1 low",
    "none": "none",
}


def _t(value: Any) -> str:
    """Trace-controlled text for Markdown: no raw HTML, no table breaks, no links.

    Agent names, run ids, data types, sources and channels come from the
    trace. Unescaped, ``<img src=x onerror=...>`` reaches any viewer that
    renders raw HTML, a ``|`` breaks a table row and a newline starts a new
    block.
    """
    text = str(value).replace("\r", " ").replace("\n", " ")
    for ch, rep in (("<", "&lt;"), (">", "&gt;"), ("|", "\\|"), ("[", "\\["), ("]", "\\]")):
        text = text.replace(ch, rep)
    return text


def _c(value: Any) -> str:
    """Text inside an inline code span: a backtick or newline would end it."""
    return str(value).replace("`", "'").replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def render(data: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append

    a("# AgentLeak Privacy Report")
    a("")
    a(f"- **Project:** {_t(data.get('project', 'n/a'))}")
    a(f"- **Agent:** {_t(data.get('agent_name', 'n/a'))}")
    if data.get("scenario_id"):
        a(f"- **Scenario:** {_t(data['scenario_id'])}")
    a(f"- **Run:** {_t(data.get('run_id', 'n/a'))}")
    a(f"- **Generated:** {data.get('generated_at', 'n/a')}")
    a("- **Scoring:** AgentRisk (severity-weighted Risk Index)")
    a("")

    ri = data.get("risk_index", 0.0)
    a(f"## Risk Index: {ri:.3f}  ·  Privacy score {data['privacy_score']}/100 — {data['verdict']}")
    a("")
    summary = data.get("summary", {})
    lp = summary.get("level_profile", {})
    a(f"- WSL (weighted severity leakage): **{data.get('wsl', 0)}**  /  ρ_S (vault density): **{data.get('rho_s', 0)}**")
    a(f"- Total findings: **{summary.get('total_findings', 0)}**")
    a(
        f"- Leaked by level — L4: {lp.get('L4', 0)} · L3: {lp.get('L3', 0)} · "
        f"L2: {lp.get('L2', 0)} · L1: {lp.get('L1', 0)}"
    )
    if data.get("scope_def"):
        a(f"- Scope (ρ_S denominator): {_t(data['scope_def'])}")
    if data.get("blocked"):
        a("- ⛔ **Blocked:** this run would fail a CI gate.")
    a("")

    policy = data.get("privacy_policy", {})
    if policy.get("enabled"):
        status = "✅ passed" if policy.get("passed") else "⛔ failed"
        a(f"## Privacy policy — {status}")
        a("")
        checked = ", ".join(policy.get("assertions_checked", [])) or "none"
        a(f"- Assertions checked: `{_c(checked)}`")
        for violation in policy.get("violations", []):
            ids = ", ".join(violation.get("finding_ids", []))
            evidence = f" Evidence: `{_c(ids)}`." if ids else ""
            a(f"- **{_t(violation['rule'])}** — {_t(violation['message'])}{evidence}")
        flow_violations = policy.get("flows", {}).get("violations", [])
        if flow_violations:
            a("")
            a("| Data | From | To | Purpose | Why |")
            a("|---|---|---|---|---|")
            for decision in flow_violations:
                a(
                    f"| `{_c(decision['data_type'])}` | {_t(decision.get('sender') or '—')} "
                    f"| {_t(decision.get('recipient') or '—')} "
                    f"| {_t(decision.get('purpose')) if decision.get('purpose') else '_none declared_'} "
                    f"| {_t(decision['reason'])} |"
                )
        a("")

    a("## Risk by channel")
    a("")
    obs = data.get("observation") or {}
    if obs.get("unobserved_channels"):
        a(f"> Imported from {obs.get('source')}: only {', '.join(obs.get('observable_channels', []))} "
          f"could be observed. Not observed, so not audited: {', '.join(obs['unobserved_channels'])}.")
        a("")
    channel_risks = data.get("channel_risks", [])
    if channel_risks:
        a("| Channel | Level | Findings | Channel RI |")
        a("| --- | --- | ---: | ---: |")
        for cr in channel_risks:
            level = cr.get("level_label", _LEVEL_LABEL.get(cr.get("level", "none"), cr.get("level")))
            a(f"| {_t(cr['channel'])} | {level} | {cr['finding_count']} | {cr.get('ri', 0):.3f} |")
    else:
        a("_No leaks detected in any channel._")
    a("")

    a("## Findings")
    a("")
    findings = data.get("findings", [])
    if not findings:
        a("_No findings._")
    else:
        ordered = sorted(
            findings,
            key=lambda f: (_BADGE_ORDER.index(f["badge"]) if f.get("badge") in _BADGE_ORDER else 99),
        )
        for i, f in enumerate(ordered, start=1):
            value = f.get("redacted_value", f.get("matched_value", ""))
            a(f"### Finding {i} — {f.get('level_label', '')} ({_t(f.get('data_type'))})")
            a("")
            a(f"- **Channel:** {_t(f['channel'])}")
            a(f"- **Severity level:** {f.get('level_label', '')} (detector severity: {f['severity']})")
            a(f"- **Detector:** {_t(f['detector'])}")
            a(f"- **Value:** `{_c(value)}`")
            if f.get("recommendation"):
                a(f"- **Recommendation:** {_t(f['recommendation'])}")
            a("")

    leak_paths = data.get("leak_paths", [])
    if leak_paths:
        a("## Leak paths")
        a("")
        a("_Where each disclosed secret entered the system and how it propagated across agents._")
        a("")
        for p in leak_paths:
            chain = " → ".join(f"{_t(s['source'] or '?')}:{_t(s['channel'])}" for s in p["steps"])
            agents = f" · agents: {', '.join(_t(x) for x in p['agents'])}" if p.get("agents") else ""
            a(
                f"- **{p['level_label']} {_t(p['data_type'])}** (`{_c(p['value'])}`) — entered via "
                f"`{_c(p.get('entered_via') or 'unknown')}`, {p['leak_count']} disclosure(s){agents}\n"
                f"  - path: {chain}"
            )
        a("")

    recs = data.get("recommendations", [])
    if recs:
        a("## Recommendations")
        a("")
        for r in recs:
            a(f"- {_t(r)}")
        a("")

    compliance = data.get("compliance", {})
    frameworks = compliance.get("frameworks", [])
    if frameworks:
        cs = compliance.get("summary", {})
        a("## Compliance")
        a("")
        a(f"_{cs.get('compliant', 0)}/{cs.get('total', 0)} frameworks clear · "
          f"{cs.get('controls_at_risk', 0)} control(s) at risk · "
          f"{cs.get('controls_not_assessed', 0)} not assessed_")
        a("")
        for fw in frameworks:
            status = "✅ clear" if fw["status"] == "compliant" else f"⚠️ {fw['at_risk']} at risk"
            a(f"### {fw['name']} — {status}")
            a("")
            for ctrl in fw["controls"]:
                mark = {"at_risk": "✗", "ok": "✓", "info": "ℹ", "not_assessed": "○"}.get(ctrl["status"], "·")
                ev = f" ({', '.join(_t(e) for e in ctrl['evidence'])})" if ctrl["evidence"] else ""
                a(f"- {mark} **{ctrl['name']}**{ev}")
                finding_ids = ctrl.get("evidence_details", {}).get("finding_ids", [])
                if finding_ids:
                    a(f"  - findings: `{_c(', '.join(finding_ids))}`")
            a("")

        integrity = compliance.get("integrity", {})
        if integrity.get("digest"):
            a(f"_Evidence manifest: `{integrity.get('algorithm', 'sha256')}:{integrity['digest']}` "
              "(integrity check, not a digital signature)_")
            a("")

    a("---")
    a("_Scored with AgentRisk: RI = WSL / ρ_S, a density-normalized, "
      "severity-weighted Risk Index grounded in GDPR Article 9 and Québec Law 25._")

    return "\n".join(lines)
