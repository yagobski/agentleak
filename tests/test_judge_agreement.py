# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The judge-agreement harness, checked against a fake local judge.

No model is called: a small HTTP server on 127.0.0.1 answers like an
OpenAI-compatible endpoint, with a rule the test knows, so the confusion
table and kappa the harness reports can be recomputed here independently.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "judge_agreement.py"


def _load():
    spec = importlib.util.spec_from_file_location("judge_agreement", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["judge_agreement"] = module
    spec.loader.exec_module(module)
    return module


ja = _load()


def _flags(text: str) -> bool:
    """The fake judge's rule: a statement is sensitive when its hash is even."""
    return hashlib.sha256(text.encode()).digest()[0] % 2 == 0


class _FakeJudge(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeJudge.seen.append({"body": body, "auth": self.headers.get("Authorization", "")})
        text = body["messages"][1]["content"]
        if "FAIL" in text:
            self.send_response(500)
            self.end_headers()
            return
        hits = [{"data_type": "other_pii", "evidence": text[:10], "confidence": 0.9}] if _flags(text) else []
        payload = {"model": "fake-judge-1", "choices": [{"message": {"content": json.dumps(hits)}}]}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="module")
def endpoint():
    server = HTTPServer(("127.0.0.1", 0), _FakeJudge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def _independent_kappa(pairs: list[tuple[int, int]]) -> float:
    """Kappa from the 2x2 matrix, written differently from the harness."""
    m = [[0, 0], [0, 0]]
    for judged, label in pairs:
        m[judged][label] += 1
    n = sum(map(sum, m))
    po = (m[0][0] + m[1][1]) / n
    rows = [sum(r) / n for r in m]
    cols = [(m[0][j] + m[1][j]) / n for j in range(2)]
    pe = sum(r * c for r, c in zip(rows, cols, strict=True))
    return (po - pe) / (1 - pe)


def test_kappa_on_a_textbook_table() -> None:
    # 50 items: po = 0.7, pe = 0.5, kappa = 0.4.
    assert ja.cohen_kappa({"tp": 20, "fn": 5, "fp": 10, "tn": 15}) == pytest.approx(0.4)
    assert ja.cohen_kappa({"tp": 10, "fn": 0, "fp": 0, "tn": 10}) == pytest.approx(1.0)
    assert ja.cohen_kappa({"tp": 0, "fn": 10, "fp": 10, "tn": 0}) == pytest.approx(-1.0)


def test_items_have_both_classes_and_come_from_the_pack() -> None:
    items = ja.load_items()
    positives = [i for i in items if i["label"] == 1]
    negatives = [i for i in items if i["label"] == 0]
    assert len(positives) > 300 and len(negatives) > 100
    assert len({i["scenario"] for i in items}) > 100
    assert ja.load_items() == items, "the negative sample must be seeded"


def test_a_perfect_judge_agrees_fully() -> None:
    items = ja.load_items()[:120]
    truth = {i["text"] for i in items if i["label"]}
    judge = lambda text: [{"confidence": 1.0}] if text in truth else []  # noqa: E731
    result = ja.evaluate(items, judge, resamples=200)
    assert result["kappa"] == 1.0
    assert result["kappa_ci95"] == [1.0, 1.0]
    assert result["confusion"]["fp"] == result["confusion"]["fn"] == 0


def test_the_harness_against_a_fake_endpoint(endpoint, monkeypatch) -> None:
    items = ja.load_items()[:150]
    items.append({"scenario": "broken", "text": "FAIL this one", "label": 1})
    monkeypatch.setenv("FAKE_JUDGE_KEY", "test-key-value")
    judge, seen = ja.endpoint_judge(endpoint, "fake-judge", "test-key-value")
    _FakeJudge.seen.clear()
    result = ja.evaluate(items, judge, model=seen, resamples=300)

    pairs = [(int(_flags(i["text"])), i["label"]) for i in items if "FAIL" not in i["text"]]
    expected = {
        "tp": sum(1 for j, lab in pairs if j and lab), "fp": sum(1 for j, lab in pairs if j and not lab),
        "fn": sum(1 for j, lab in pairs if not j and lab), "tn": sum(1 for j, lab in pairs if not j and not lab),
    }
    assert result["confusion"] == expected
    assert result["kappa"] == pytest.approx(round(_independent_kappa(pairs), 4))
    low, high = result["kappa_ci95"]
    assert low <= result["kappa"] <= high
    # A failed call is counted and left out, never scored as "not sensitive".
    assert result["errors"] == 1 and result["scored"] == len(items) - 1
    # Provenance: the model the endpoint reported and the prompt actually sent.
    assert result["judge_model"] == {"model_requested": "fake-judge", "model_reported": "fake-judge-1"}
    sent = _FakeJudge.seen[0]
    assert sent["body"]["messages"][0]["content"] == ja._SYSTEM_PROMPT
    assert result["prompt_sha256"] == hashlib.sha256(ja._SYSTEM_PROMPT.encode()).hexdigest()
    assert sent["auth"] == "Bearer test-key-value"
    assert sent["body"]["temperature"] == 0.0


def test_nothing_is_sent_without_an_endpoint(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["judge_agreement.py"])
    assert ja.main() == 2
    assert "nothing was sent" in capsys.readouterr().out
