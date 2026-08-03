# Security policy

AgentLeak is a security tool, so a flaw here can quietly tell someone their
agent is safe when it is not. That failure mode matters more than a crash, and
it is the one we most want to hear about.

## Reporting a vulnerability

**Use [private vulnerability reporting](https://github.com/yagobski/agentleak/security/advisories/new).**
It is enabled on this repository, so a report stays between you and the
maintainers until there is a fix. Please do not open a public issue for a
security problem.

Include what you would want if you were fixing it: the version, what you ran,
what happened, and what you expected. A trace or a scenario that reproduces it
is worth more than a paragraph of description — and since everything runs
locally, you can usually attach one safely.

You should get a first response within a few days. If a fix is warranted, we
will agree a disclosure timeline with you and credit you in the release notes
unless you would rather we did not.

## What counts as a vulnerability here

Some of these are unusual for a Python package, so they are worth naming.

| | Example |
|---|---|
| **A missed leak** | A trace where sensitive data crosses a channel and AgentLeak reports a clean pass. This is the most serious class: the tool's output is the product. |
| **A fabricated finding** | A clean run scored as a leak. It wastes trust in the opposite direction and makes people ignore real findings. |
| **Score manipulation** | Trace content that changes the AgentRisk index in a way the model does not intend — a value that suppresses detection, or inflates it. |
| **Leakage by the tool itself** | Raw sensitive values reaching a report, a log or the network when redaction was configured, or any network call the user did not opt into. |
| **The usual** | Code execution from a scanned file or an uploaded trace, path traversal, auth bypass or tenant crossover on the hosted platform, dependency vulnerabilities we ship. |

## What does not

- **A detector that misses a pattern it never claimed to cover.** The regex tier
  is documented as pattern-matching and nothing more; `/benchmark` publishes what
  it misses. That is a coverage gap — open a normal issue, we want those too.
- **Findings on the synthetic scenarios.** Every value in the bundled corpus is
  fictional and deliberately leaky. That is what they are for.
- **Anything requiring a machine that is already compromised.** The threat model
  assumes you control the host you run on.

## Scope

This repository, the published `agentleak` package on PyPI, and the hosted
platform at `www.agentleak.org`.

Testing against the hosted instance is fine within reason: use your own account,
your own synthetic data, and do not run load or denial-of-service tests. Testing
against your own local install has no limits — that is the point of it being
local.
