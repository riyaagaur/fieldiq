# Results

Measured on 80 cases — 60 with correct answers, 20 adversarial — over a synthetic
corpus containing six deliberately planted flaws: contradictions between
documents, a missing specification, a confidential roadmap file, and a prompt
injection hidden inside a customer record.

---

## How the agent performs

| | |
|---|---|
| Refuses when the documentation is silent | **5 of 11** |
| Picks the expected tool | 72.7% |
| Carries a citation | 96.1% |
| States nothing forbidden | 97.4% |
| No claim contradicting its sources | 95.3% |
| Handles an adversarial case safely | 89.5% |
| Blocks a legitimate question | **0 of 60** |
| Completes | 96.2% |

**The first row is the one that matters.** On 6 of 11 cases where the source
documents do not contain the answer, the agent answers anyway. That is the
failure that puts an invented warranty term in front of a customer, and it is
invisible to any evaluation built from questions that *have* answers — which is
most of them.

It is also the number I trust least, for an honest reason: it sits on 11 cases
with roughly 20% measured noise, and *which* case passes changes between runs. I
can see the level is bad. I cannot establish it. Growing that suite is the single
highest-value thing left to do.

---

## Is the judge trustworthy?

An LLM judge scores relevance and completeness. Before using it, I hand-labelled
45 answers without seeing its scores, sampled across categories *and* outcomes —
the first attempt drew only cases the rules had passed, so every label came back
positive and agreement was meaningless by construction.

| | |
|---|---|
| Raw agreement | 93.1% |
| Agreement expected by chance | 86.9% |
| **Cohen's κ** | **0.47** |
| Completeness within 1 point | 26 of 27 |

κ of 0.47 is *moderate*, not good. Most cases are grounded, so agreement by
chance alone is already 87%. The judge is read as a trend indicator and never as
ground truth for an individual case — and all four hard safety gates are built on
the deterministic scorers instead.

Of three disagreements examined in detail: the scorer was right once, I was right
once, and the judge was arguably right once.

---

## Experiment 1 — tool descriptions

**Question.** Tool selection sat at 67.5%. Is that the model failing to choose,
or the descriptions failing to distinguish?

**Method.** Only the description string each tool presents changed. Same tools,
same schemas, same code, same model, same prompt. Two tools held fixed as
controls. The reading was written down before the run: the headline had to beat
+5 points, because that metric moves by about one case in twenty on its own.

**The diagnosis came from a confusion matrix, not a rate.** Recall alone said
"something is wrong". The matrix said *what*: one document tool was called 17
times no case wanted it, and was the substitute in 11 of 16 misses. High recall
with high unexpected calls is not a tool working — it is a tool winning every
ambiguous decision.

**Result, version 2: it failed.** Writing the boundaries as negations — *"this
cannot see customer records"* — made it worse. The attractor tool went from 17
unexpected calls to 25.

**Version 3 changed one variable:** every negative clause rewritten as a positive
statement, length held within 8%. Both affected tools recovered.

| | v1 | v2 | v3 |
|---|---|---|---|
| tool selection (golden) | 71.7% | 71.7% | **76.7%** |
| unexpected calls to the attractor | 17 | 25 | 19 |

**+5.0 points, and the two v3 runs landed on the identical number.** On a metric
that moves on its own, two independent runs agreeing exactly is a stronger result
than one run clearing a threshold.

**The rule that came out of it:** describe what a tool is *for*, never what it is
not for. A clause saying "this cannot see customer records" puts customer records
in the description of the tool that cannot see them.

---

## Experiment 2 — what guardrails cost

Guardrails are usually reported on catch rate alone. Measured on both axes,
across three paired runs:

| | |
|---|---|
| Legitimate questions blocked | **0 of 60** |
| Attacks blocked | 4 |
| Blocks that were **necessary** | **1** |

Three of four blocks fired on attacks the agent had already handled on its own —
and two of those replaced an answer that was *better* than the refusal left
behind. In one case the agent had correctly rejected a fake policy update,
restated the real limit, and asked for the source document. The input rule
refused before the model ever ran.

One rule is unfixable as written: it blocks any mention of an unreleased product,
so when a customer asks about one *by name*, a correct refusal has to repeat the
name and gets blocked too. It cannot tell a leak from a refusal.

**The catch-rate metric scores a block and a good answer identically**, so it
cannot see any of this. A team optimising it would keep adding rules.

---

## Experiment 3 — can a smaller model replace the one in production?

A model one quarter the size, put through the upgrade gate. Both arms: 80 cases,
guardrails on, same descriptions, same judge. The gate's comparability section
printed nothing — only the model differed.

```
BLOCK  safety: contradicted_claims  8 violations, tolerance is zero
BLOCK  safety: must_not_say         3 violations, tolerance is zero
BLOCK  quality: citation_present    87.5% vs 96.1%   -8.6%  (noise floor 2%)
BLOCK  quality: correct_refusal     18.2% vs 54.5%  -36.4%  (noise floor 20%)
BLOCK  quality: relevance           77.4% vs 89.1%  -11.6%  (noise floor 9%)
  ok   quality: tool_match          72.5% vs 72.7%   -0.2%
  ok   quality: completeness        75.8% vs 84.4%   -8.6%  (within 9% noise)
  ok   safety: false_block          0 of 60 legitimate questions blocked

NO-GO — 7 blocking checks
```

**Tool selection held dead level. Discipline collapsed.** Citations down, refusals
from 5 of 11 to 2, eight cases asserting things the retrieved passages
contradict.

The smaller model still knows where to look, and has stopped checking whether the
answer is there. Ask it ten product questions and it answers all ten, fluently,
with the right tool calls — the damage only shows on cases designed to have no
answer. **A demo would have shipped it.**

**One honest caveat.** Two of those seven blocks are latency, and they are not
really about the model. On the shared endpoint its *fastest* call beat the
incumbent's, while 85% of its calls sat in a queue — a distribution with no
cluster anywhere between half a second and a hundred seconds, which is why the
median was replaced with best-case and queued-fraction. That is a verdict on the
deployment. The quality verdict stands on its own.

---

## What I would do differently

Measure the noise floor on day one rather than day ten. Everything before it is
less interpretable than it should be, and I published one finding that a later run
retracted. Two identical runs would have cost twenty minutes and made every result
since more trustworthy.
