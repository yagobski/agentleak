# Publishing a score, and watching it over time

Two features that answer the same question from different sides: *is this agent
still safe?* One makes the answer public. The other keeps asking.

---

## The public trust page

A badge an agent awards itself is worth nothing. What makes this worth putting
in a README is that AgentLeak measured the number and that anyone can follow the
link to see what it was measured on.

```bash
# From the workspace, or over the API:
curl -X POST https://www.agentleak.org/api/projects/<id>/publish \
     -H 'Cookie: …' -d '{"slug": "support-bot"}'
```

You get back two URLs:

| | |
|---|---|
| Page | `https://www.agentleak.org/a/support-bot` |
| Badge | `https://www.agentleak.org/a/support-bot/badge.svg` |

```markdown
[![privacy](https://www.agentleak.org/a/support-bot/badge.svg)](https://www.agentleak.org/a/support-bot)
```

Publishing is opt-in and reversible: post an empty slug to take it down. A run
never publishes anything as a side effect of being recorded.

### What the badge refuses to do

The whole design weight sits on one rule: **the badge must never flatter the run
behind it.** There are three ways it could, and each is closed.

**A stale score reading as current.** A green badge from six months ago says
nothing about the code someone is looking at today. Past 30 days the colour goes
grey and the message becomes `stale (47d)` — the age, not the score, because the
score is about code that may no longer exist.

**A weak check reading as a strong one.** A pass from the pattern tier alone is a
narrower claim than a pass from the full pipeline — [the benchmark](https://www.agentleak.org/benchmark)
measures how much narrower. The page names the tiers that ran, and a degraded run
can never show the passing colour.

**A cherry-picked run reading as the state of things.** The badge always shows
the *latest* run. Not the best one, not an average.

### What a stranger can see

The verdict, the score, the date, the tiers that ran, and a 20-point trend line.
Never the findings — those name real values from someone's private data. The
point of the page is that a score was measured and by what, not what it found.

The SVG is self-contained: no scripts, no external fonts, no remote images.
GitHub's image proxy would silently render any of those as a broken badge.

---

## Continuous watch

A one-shot audit tells you about the code you had the day you ran it. Agents
drift — a prompt changes, a tool is added, a model is swapped — and the next leak
arrives without a release to blame.

```python
from agentleak import Monitor, watch

monitor = Monitor(sample=0.05, drop=10, on_alert=notify_the_team)

def handle(request):
    if monitor.should_sample():
        with watch(project="support-bot") as run:
            answer = agent(request)
        monitor.record(run.report.to_dict())
    else:
        answer = agent(request)
    return answer
```

### The settings, and why they default where they do

| | Default | Why |
|---|---|---|
| `sample` | `0.05` | Scoring every run costs latency in a hot path. At a thousand runs an hour, 5% still gives fifty measurements — enough for a trend, cheap enough that nobody switches it off. |
| `drop` | `10` | Points below the baseline before it says something. Smaller than this is drift, not regression. |
| `floor` | none | An absolute line. Catches a slow slide that never trips `drop` in one step. |
| `window` | `20` | Runs in the rolling average. One unlucky sample cannot move it far; a real regression still surfaces in minutes. |

### The two ways a monitor makes itself useless

**Alerting on every wobble.** People mute it, and then it may as well not be
running. So: no alert before five samples, no alert on a single bad run, and no
alert on a flat line — a service that has always scored 70 does not need telling
hourly.

**Staying quiet through a real regression.** So: a severity the deployment has
never produced before is reported on the first occurrence rather than waiting for
a trend, and the baseline tracks improvement but never decays toward a
regression. A baseline that follows a slow slide downward is what makes the slide
invisible.

### Nothing in this path can break your agent

The monitor runs in-process with no thread and no timer. `on_alert` is called
outside the lock, and an exception inside it is swallowed — your pager being down
is not a reason for the agent to stop answering users.

Nothing leaves the machine unless the surrounding `watch()` was already
configured to submit.
