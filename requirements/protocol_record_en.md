# Record of the protocol and of the experiment (English)

This record states when the hypothesis protocol was fixed, which settings were fixed with it, and how the reported
experiment relates to earlier computations. It is compiled from the decision log of the project, which is kept in the
original language and is available from the corresponding author.

## Chronology (UTC)

| Date | Event |
|---|---|
| 2026-10-03 | Daily allocation model without hydraulics (smoke computation): LXB and proportional rationing give the same worst-user satisfaction (2018, first decade of July: 0.620). The protocol records this observation and restricts H1 to the Saint–Venant plant. |
| 2026-10-03 | Tolerances fixed in the configuration: ε1 = 10⁻⁶ (checked with `scripts/check_tolerance.py` over 180 decades), ε2 = 10⁻⁴, ε_λ = 0.01; stage 1b added. |
| 2026-10-03 22:20 | First run with an earlier freeze (protocol v2.1) and earlier code; stopped after 13 runs and 4 solver failures. No result was evaluated. |
| 2026-10-04 09:22 | Freeze of protocol v2.1 for a pilot computation; the pilot results do not enter the reported experiment. |
| 2026-10-04 11:30 | Second run; stopped after a solver failure of the Oracle (2014). No result was evaluated. |
| 2026-10-04 18:44:31 | Final freeze of protocol v2.2 (`results/experiment/PREREGISTRATION.json`; SHA-256 of `requirements/hypotheses.md` fa2ab7be…). The hypotheses, metrics, families, and decision rules have not changed since. |
| 2026-10-05 | First complete main sweep (390 runs) and its evaluation. |
| 2026-10-05 to 2026-10-10 | Corrections of the simulation code and of scenario files; the main sweep was recomputed in full on 2026-10-08/09; sensitivity and exploratory runs added (descriptive). |
| 2026-10-18/19 | Code version 1.1.0: further sensitivity and exploratory cases, separate communication counters, season-level tests. |
| see `results/versions.json` | Code version 1.2.0: gate changes applied at the start of a control step in the plant and in the controller's volume reconstruction; before the production runs, the code was checked independently (numerical probes of the gate law, the command constraint, the Newton fallbacks, the volume ledgers, the result checks and the hypothesis evaluation), and the defects found were corrected; the ID model parameters were re-identified with the conveyance losses of the plant; H6 was aligned with the protocol (share of user–days). Every run reported in the article was recomputed with this version. |

## Status of the tolerances and settings

The frozen protocol lists the tolerances ε2, ε_λ, the mass-balance and convergence thresholds, the Oracle-gap
threshold, the freeboard, and the Preissmann weight under "open tolerances — awaiting confirmation". The values used in
every run are those in the configuration at the time of the freeze, whose checksum is recorded with the protocol;
none of them was changed afterwards. The confirmation referred to in the protocol was recorded in the decision log on
2026-10-03 for ε1, ε2, and ε_λ; the remaining entries kept the proposed values.

## What the pre-specification covers

The pre-specification fixes the hypotheses, the metrics, the families of the Holm correction, and the decision rules.
It does not fix the implementation of the model: the simulation code and the configuration were corrected after the
first complete sweep had been evaluated, and the main sweep was recomputed. The corrections are listed in the decision
log; none of them changed a hypothesis, a metric, or a decision rule. The analyses added after the main runs are listed
in Section S6 of the Supplementary Materials and are reported as exploratory or as robustness checks.
