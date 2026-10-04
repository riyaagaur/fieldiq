# FieldIQ

An evaluation and release-gating system for a tool-using AI agent.

## The goal

AI agents are easy to demo and hard to trust. Ask one ten questions and it
answers all ten, fluently. That tells you almost nothing about whether it is safe
to put in front of a customer.

I wanted to build the thing that answers the harder question: **how do you decide
whether an agent is good enough to ship, and how do you know your measurements
are telling you the truth?**

## What it had to do

- Score an agent's answers automatically, across correctness, grounding,
  tool use, and safety
- Catch the failures a demo hides — in particular, what the agent does when the
  documentation does not contain the answer
- Measure guardrails on both what they catch *and* what they wrongly block
- Decide go / no-go on a model change, with evidence rather than impressions
- Block a release when quality regresses, automatically

The agent itself is deliberately ordinary. Everything it reads is synthetic data
written for the project — no real customer information is involved.

## What was built

A 14-day build, run end to end:

- **An evaluation suite** of 80 cases, half of them adversarial, over a corpus
  with deliberately planted flaws — contradictions, missing facts, confidential
  material, and a prompt injection hidden in a data record
- **A scoring stack** combining deterministic rules, a grounding verifier, and an
  LLM judge — with the judge calibrated against hand-labelled answers
- **Guardrails**, measured on catch rate and false-block rate together
- **A release gate** that compares every run against a recorded baseline and
  exits non-zero when anything regresses
- **A model-upgrade gate** for deciding whether to switch models
- **Reports** — a scorecard and a per-case trace viewer

## What it found

**The agent's worst behaviour:** on roughly half the cases where the source
documents do not contain the answer, it answers anyway instead of saying so. That
failure is invisible to any evaluation built from questions that have answers.

**The experiment that worked:** rewriting how the agent's tools describe
themselves improved tool selection by 5 points, replicated across two runs. The
first attempt made it *worse*, which is how the mechanism was found.

**The model decision:** a model a quarter the size matched the original on tool
selection while losing citation discipline, grounding, and refusals. Correctly
rejected.

**The result I did not expect, and the one I'd lead with:** more than half of
everything found in two weeks was *the measurement* being wrong, not the agent.
Metrics that scored perfectly on runs where nothing was generated. A threshold
that was arithmetically impossible to pass. A scorer that counted careful
refusals as leaks. Each one produced a confident, plausible, completely wrong
number — and each was caught by an independent check with an answer already
known.

Building the evaluation taught me more about evaluation than about the agent.

---

*Built as a portfolio project. Source, methodology, measurement write-ups and the
full failure catalogue are kept privately and are available on request.*
