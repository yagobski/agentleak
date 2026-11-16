# Interop fixtures

Each file here is the real output of the named tool, at the exact version
given, produced offline on 2026-11-15 and then trimmed by
[`generators/trim_fixtures.py`](generators/trim_fixtures.py) (bulk and local
absolute paths removed; every key an importer reads kept as the tool wrote it).
No model API was called: each run used the tool's own offline mechanism and a
stub that returns canned text. All personal data in them is synthetic
(`Jane Roe`, `123-45-6789`, `example.com`/`example.net` addresses).

| File | Tool and version | How it was produced |
| --- | --- | --- |
| `promptfoo_0.125.1_plain.json` | promptfoo 0.125.1 (npm, Node 24.22.1) | `promptfoo eval -o results.json` with two providers: the built-in `echo` provider and a local JavaScript stub provider. No tracing. |
| `promptfoo_0.125.1_traced.json` | promptfoo 0.125.1 | Same, with `tracing: {enabled: true}` and the OTLP HTTP receiver on 127.0.0.1:4318; the stub provider ([`generators/promptfoo_provider.js`](generators/promptfoo_provider.js), config [`generators/promptfooconfig.yaml`](generators/promptfooconfig.yaml)) posts OpenInference spans (AGENT, TOOL, LLM) for its own work under the `traceparent` promptfoo passes it. The export's top-level `traces` holds them next to promptfoo's own `test_case`, `target` and `grader` spans. |
| `inspect_0.3.290.eval` | Inspect AI 0.3.290 (Python 3.12) | [`generators/inspect_task.py`](generators/inspect_task.py): `mockllm/model` with scripted outputs (two tool calls, then a reply with a reasoning part), `log_format="eval"`. Untouched: its members are zstd-compressed, as Inspect 0.3.290 writes them. |
| `inspect_0.3.290_deflate.eval` | Inspect AI 0.3.290 | The same archive members, recompressed with deflate so the stdlib path can be tested on Python < 3.14. |
| `inspect_0.3.290.json` | Inspect AI 0.3.290 | Same task, `log_format="json"`; `events`, `model_usage` and `model_args` removed. |
| `garak_0.17.1.report.jsonl` | garak 0.17.1 (PyPI, installed without its torch/transformers dependencies) | `garak --target_type function --target_name stubagent#respond --probes test.Test,dan.Dan_11_0 --generations 1` with [`generators/garak_stubagent.py`](generators/garak_stubagent.py). The configuration dump, digest and long DAN prompt bodies were trimmed. |
| `pyrit_1.2.0_scenario_conversations.json` | PyRIT 1.2.0 | [`generators/pyrit_run.py`](generators/pyrit_run.py): `PromptSendingAttack` against a stub `PromptTarget`, in-memory database, a prepended system message and tool exchange; serialized by PyRIT's `JsonConversationMemoryPrinter` and `build_scenario_conversations_document` (the functions behind `output_scenario_conversations_async` and `scenario-results --view conversations --format json`). The `pyrit_scan` CLI was not run: it reads results from a PyRIT server. |
| `pyrit_1.2.0_conversation.json` | PyRIT 1.2.0 | The first conversation alone, from `JsonConversationMemoryPrinter.render_async` (`output_conversation_async(format="json")`). |

The `dan.Dan_11_0` prompt in the garak fixture is garak's own probe text
(Apache-2.0), cut to its first 300 characters.

The tools are not dependencies of AgentLeak. They were installed in throwaway
virtual environments outside the package and are not needed to run the tests.
