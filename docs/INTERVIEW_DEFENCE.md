# GridFlex and RAG interview practice

These exercises test understanding of the published implementation. Reading this guide does not establish independent authorship or competence. Complete the tasks yourself and keep the terminal output and your explanations. Describe the projects as AI-assisted and identify the parts you can defend or changed yourself.

## Explain the project in one minute

GridFlex forecasts Great Britain's average electricity carbon intensity and compares charging schedules under energy, power, efficiency and deadline constraints. Python handles the research pipeline; the public Cloudflare service uses the seven-day same-clock baseline. The FastAPI/Azure implementation is a separate deployment path. Original historical validation favoured the baseline. A later test showed distribution shift and poor interval coverage, so the improved candidate was not promoted.

The retrofit assistant retrieves four curated UK guidance summaries and asks a local Llama model for a relevant quote. The API validates citations and checks every returned quote against the cited source. A real-model regression suite complements mocked integration tests. This narrow assistant does not decide personal eligibility and cannot guarantee the truth, completeness or freshness of a source.

## Questions you must answer without this guide

1. **Why can a random split leak information here?** Adjacent half-hour observations and overlapping 24-hour targets are correlated. A random split can put near-identical historical context and future outcomes on both sides. Explain the purged chronological boundaries in `src/gridflex/model.py`.
2. **At a 12:00 forecast origin, which actual is latest eligible?** The 09:30–10:00 interval: its end is at least two hours old. Show how `OBSERVATION_DELAY` and the extra half hour enforce this in `features.py`.
3. **Why did the candidate improve development performance but fail later?** Development MAE was 33.59 against 35.46 for seven-day mean; later candidate MAE was 46.73, persistence 46.22, and interval coverage 82.4% against a nominal 90%. This is evidence of limited generalisation. Do not tune repeatedly on the same holdout and then describe it as unseen.
4. **Did the original model beat the strongest later baseline?** Its later MAE, 45.95, was slightly below persistence at 46.22. That small point estimate is not sufficient proof of reliable superiority, and its 78.6% interval coverage failed the nominal target. Distinguish point estimates from promotion criteria.
5. **What does 90% conformal coverage promise?** The usual guarantee depends on assumptions such as exchangeability that are unreliable under time-series drift. Report measured coverage; do not relabel an 82% interval as reliable at 90%.
6. **Why are the charging figures not measured carbon savings?** They use predicted average grid intensity and simulated energy allocation. They are not marginal emissions, physical device measurements or a causal comparison.
7. **Why use a simple baseline publicly?** It is transparent, inexpensive and consistent with the initial validation choice. Serving it does not solve the forecasting research problem or establish operational fitness. The later holdout favoured persistence among baselines; the public demo clearly reports this.
8. **Why does a citation not prove a claim?** A model can attach a valid URL to an invented sentence. The RAG implementation requires exact quoted word sequences from the cited text. That blocks new wording but does not establish relevance, source truth or current policy.
9. **What has really been deployed?** A Cloudflare Worker serving the public dashboard, baseline forecast and charging API. Azure Terraform validation is configuration evidence; there is no Azure deployment claim. Docker/API checks run separately in GitHub Actions.
10. **What did AI contribute?** State the actual assistance with coding, documentation and debugging. Point to an independently completed change and explain its failure modes. Do not claim that reading generated code proves you designed it independently.

## Practical assessment

Use a fresh checkout. No generated answers during the exercise; documentation is allowed after you first explain the idea.

| Task | Evidence to keep | Pass condition |
| --- | --- | --- |
| Trace a 12:00 forecast | Explain five rows and their eligibility | Correct 09:30 latest interval; no target actual used |
| Change an ineligible observation | Run the existing exclusion test and explain it | Predictions remain unchanged |
| Break a charging request | Request too much energy for a short window | API refuses it; no partial plan is presented as feasible |
| Recalculate one schedule by hand | Power × 0.5 h, efficiency, cost and intensity arithmetic | Totals reconcile with API output |
| Explain a failed real RAG case | Question, retrieved source and actual response | Identify retrieval, formatting, grounding or answerability failure accurately |
| Make one useful code change | Commit, test and a short explanation | Explain every changed line and the bug it prevents |

For a 30-minute mock interview, allocate 10 minutes to architecture, 10 to evidence and limitations, and 10 to a code change. Score each task 0 (cannot explain), 1 (needs substantial prompting), or 2 (independent explanation with correct evidence). Record the date and score yourself. A useful readiness target is at least 10/12 with no zero, repeated on a different day. This is a practice rubric, not an employer accreditation.

## Claims to avoid

Do not say the project is production-proven, deployed on Azure, used by customers, independently authored without assistance, or guaranteed to save carbon. Do not claim the new candidate beat every baseline. Do not state a UK degree-class equivalence or an MSc final result without documentary evidence.

## Personal facts to complete

Your stated final undergraduate CGPA is 3.39. Confirm its denominator from your transcript before adding a scale or UK equivalence. Kaspa's worked-shift period is May–September 2026 on a zero-hours arrangement; that does not establish a contractual termination date. An MSc final classification is unavailable while the course is ongoing.
