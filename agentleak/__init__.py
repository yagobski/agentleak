"""AgentLeak OSS — open-source privacy-leakage testing for AI agents.

Quick start::

    from agentleak import Trace, AgentLeakRunner

    trace = Trace(run_id="demo")
    trace.add_event(
        channel="tool_call", source="agent", target="crm",
        content={"customer_email": "test@example.com", "account_id": "ACC-12345"},
    )
    trace.add_event(channel="final_output", content="All set!")

    result = AgentLeakRunner().analyze(trace)
    print(result.privacy_score, result.verdict)
"""

from __future__ import annotations

__version__ = "0.11.4"

from .client import AgentLeakClient, AgentSelfClient, connect
from .core.agentcard import AgentCard, fetch_agent_card, parse_agent_card
from .core.agentrisk import AgentRiskReport, compute_agentrisk, dominates, level_for
from .core.codescan import (
    CodeScanner,
    CodeScanResult,
    scan_dir,
    scan_file,
    scan_files,
    scan_github_repo,
    scan_path,
)
from .core.config import Config
from .core.detector import Finding, RawMatch, Severity, redact
from .core.report import AnalysisResult
from .core.runner import AgentLeakRunner, analyze
from .core.scenario import Scenario
from .core.scoring import Score, score_findings, verdict_for
from .core.store import Store
from .core.trace import CHANNELS, Channel, Event, Trace
from .monitor import Alert, Monitor
from .sdk import Capture, capture, monitor, record
from .track import Run, watch

__all__ = [
    "__version__",
    # core data model
    "Trace",
    "Event",
    "Channel",
    "CHANNELS",
    # detection / scoring
    "AgentLeakRunner",
    "analyze",
    "AnalysisResult",
    "Finding",
    "RawMatch",
    "Severity",
    "Score",
    "score_findings",
    "verdict_for",
    "redact",
    # agentrisk
    "AgentRiskReport",
    "compute_agentrisk",
    "dominates",
    "level_for",
    # config / scenarios
    "Config",
    "Scenario",
    # sdk
    "capture",
    "Capture",
    "monitor",
    "record",
    # unified one-line API
    "watch",
    "Monitor",
    "Alert",
    "Run",
    # platform
    "AgentLeakClient",
    "AgentSelfClient",
    "connect",
    "Store",
    # agent-first layer
    "AgentCard",
    "parse_agent_card",
    "fetch_agent_card",
    "CodeScanResult",
    "CodeScanner",
    "scan_files",
    "scan_dir",
    "scan_file",
    "scan_path",
    "scan_github_repo",
]
