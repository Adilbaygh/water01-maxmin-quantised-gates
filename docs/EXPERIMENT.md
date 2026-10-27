# Design of the computational experiment

## Purpose

The experiment checks Theorems 1–4 of the article in closed loop with the Saint–Venant model of the Kegeyli pool and
measures, at the Dustlik node, how much of the daily max–min plan the quantised gates execute under each execution
rule over the vegetation seasons 2010–2019.

## Plant, plan and actuator

- **Plant** (`src/water01/hydraulics`): the Kegeyli pool upstream of the Dustlik node, Saint–Venant equations solved by
  the four-point Preissmann scheme; recorded head discharge S(t) of the Kegeyli canal times the delivery factor
  η = 0.81 as inflow; six outlets at the node: five gated regulators (Abad-Yarmish, R-1, Khalkabad-2, Kanly-Yab, K-2)
  and the check structure (barrier) towards the lower Kegeyli canal, which holds the level and is not operated by
  the rules; all six gates are positioned by the actuator.
- **Plan** (`src/water01/control/lxb.py`, `src/water01/optimization/lexlp.py`): every day the three-stage
  lexicographic programme LXB fixes the daily volumes x_j of the six outlets over a receding window of 10 days (first
  stage: the max–min level of satisfaction λ\*, with a second max–min level for the current day; second stage: the
  weighted sum of the satisfactions; third stage: the day-to-day variation of the satisfactions, each stage retaining
  the optimum of the previous one within a tolerance); a fifteen-minute execution programme (Δt = 900 s, N = 96 steps a
  day) turns the remaining plan into discharge commands.
- **Actuator** (`src/water01/iot/devices.py`): the opening of a regulator is an integer number n of resolution steps
  ρ = 0.001 of the travel (nearest rounding of the command); a change of the opening is executed only when it is at
  least the deadband δ = 0.005 of the travel, compared in whole steps, except the full closure n = 0, which is always
  executed. A gate that is closed therefore opens at least k = ⌈δ/ρ⌉ = 5 steps.
- **Step volumes** (Equation (4) of the article, `scripts/analysis_common.py`, class `Quanta`): v_j(h) — volume of one
  resolution step during one step Δt at the level h upstream of the node; quantum q_j(h) = k v_j(h); pulse
  p_j(h) = (k + 1) v_j(h), the volume of the pulse opening δ + ρ of the simulation core. At h = 3.0 m the R-1 regulator
  has v ≈ 8.6 m³, q ≈ 43.1 m³, p ≈ 51.7 m³; the Abad-Yarmish regulator has q ≈ 605 m³.

## Execution rules (`scripts/rules.py`)

Every rule keeps the daily plan and the execution programme of LXB and changes only the commands of the five
regulators.

| Rule | Execution of the regulators | Theorem |
|---|---|---|
| LXB | direct execution: commands of the execution programme as they are (the programme keeps the requested volume within the remaining plan by a penalty, not by a constraint; `scripts/check_residual_cap.py` lists the steps at which it does not); a command inside the deadband of a closed gate is not executed | 1(a) |
| LXB-T000, LXB-T025, LXB-T050, LXB-T075 | θ pulse rule, θ = 0, 0.25, 0.5, 0.75: a command inside the deadband becomes one pulse when the remaining plan R_j is positive and R_j ≥ θ min{p_j, x_j}, and a closure otherwise; LXB-T050 coincides with the deadband-aware rule LXB-DA of the simulation core | 3 |
| LXB-ES | equal split with pulse fallback: a plan between one quantum at the upper operating level and the pulse-regime limit is delivered in m_j open steps separated by closed steps, m_j = min(⌈N/2⌉, max(1, ⌊x_j/(q_j^hi + v_j^hi)⌋)); the other plans are executed as under the θ rule with θ = 0.5 | 1(b) |
| LXB-CO | carry-over: the θ rule (θ = 0.5) applied to the plan plus the estimated debt of the previous day, x̃_j(s) = x_j(s) + e_j(s−1), e_j(s) = x̃_j(s) − V̂_j(s); the regulator is closed for the day when x̃_j(s) ≤ 0 | 4 |

## Cases and seeds (`scripts/run_cases.py`)

Ten cases (table in `README.md`), each run for the ten seasons 2010–2019 (1 April–30 September, 183 days) with the
seed 20261003 + season; 200 seasonal runs in three phases: A (`phys`, `q_main`), B (`q_theta`, `iot_main`) and C (the
robustness cases). The execution chain Q (quantised actuator, exact level, no message or energy constraint) is the
setting of Theorems 1–4; the chain iot adds the level sensor, the LoRaWAN communication and the solar energy balance;
the chain phys executes the commands exactly.

## Recorded quantities (`results/runs/<case>/<rule>_<season>.csv`)

One row per day: the worst-case satisfaction λ of the day, the minimum and maximum level upstream of the node (true and
estimated) and, for every outlet j, the demand D_j, the base plan x_j, the executed target x̃_j, the volume of the
plant V_j, the volume V̂_j reconstructed by the controller from the measured level and the executed openings, the
satisfaction r_j = min{V_j/D_j, 1} and the number of steps with the gate open; for the regulators, also the numbers of
pulses and of equal-split open steps, the number m_j of the equal split and the mode of the day (LP, PULSE or ES).

## Checks (`scripts/analyse_theorems.py` → `results/analysis/`)

| Part | Check | Quantities |
|---|---|---|
| t1 | Theorem 1(a): under LXB a regulator-day with 0 < x_j < (1 − 1/(2k)) q_j^min is excluded | predicted exclusions against regulator-days with the gate never open and against days without water, for the deadband, gate-coefficient and leakage cases (q_j^min at the minimum level of the day); the assumption 0 ≤ u_i ≤ R_i⁺ of every request is checked by `scripts/check_residual_cap.py` (re-runs of the seven direct-execution cases) |
| t1 | Theorem 1(b): under LXB-ES, \|V_j − x_j\| ≤ v_j^max/2 | share of equal-split regulator-days within the bound, with V̂ and with V |
| t2 | Theorem 2: 0 ≤ Π_ind ≤ Σq_j/ΣD_j, Π_ind = 0 ⇔ λ\* D_j ≥ q_j for every outlet; τ ≤ λ_v ≤ λ_q with the lower bound τ of part (c); V < Σq_j^min forces a dry outlet | daily λ\*, minimum-delivery level λ_q and Π_ind = λ\* − λ_q of the node from the operating records (exact breakpoint algorithm of `quantmaxmin.allocation.quantised_level`, checked against a mixed-integer programme in `tests/`), with the quantum of the barrier from the closed position; at the levels of the operating range in steps of 1 cm, the lower bound τ of part (c) (`whole_step_lower_bound`), which holds for every gate that delivers a volume in each interval of one step above its quantum (the barrier at a constant level with its quantum and largest one-step volume, if one fully open step passes at least twice the quantum and N − 3 such steps cover its demand; both are checked), and λ_v with all six gates on grids (`whole_step_level`, checked by enumeration); on the days without deficit, the margin of the supply over max{D_j, q_j} plus one step of every gate |
| node | balance of the six outlets | surplus of the regulators over their plans, satisfaction of the barrier against its plan on the deficit days, storage change of the pool, seasonal delivery over the plan of every outlet |
| t3 | Theorem 3: in the pulse regime the θ rule gives x̃_j − θ min{p_j^max, x̃_j} ≤ V_j < x̃_j + p_j^max | bounds on the regulator-days with pulses only, with V̂ and with V |
| t4 | Theorem 4: −p_j^max < e_j(s) ≤ θ p_j^max for the carry-over debt; period error \|ΣV_j − Σx_j\|/ΣD_j for T = 1, 10, 30 days and the season | debt recursion reconstructed from x_j and V̂_j; period errors of LXB-CO against LXB-T050 |
| rules | outcome of every rule | mean and minimum daily λ, days with λ = 0, regulator-days with r_j = 0, shortfall and over-delivery of the regulators, seasonal satisfaction of R-1, error of R-1 over the calendar dekads (mean, median, 95th percentile, largest) with V and with V̂, days of R-1 by execution mode, gate movements (from `scripts/gate_activity.py`) |
| device | device chain against the quantised actuator alone | pulse days on which the executed open steps differ from the commanded pulses by one or two (a lost command packet), the error of V̂ against V, equal-split days outside half a resolution step |
| data | operating records | blank Kegeyli entries classified by the balance of the Dustlik head; the 2011 annual volume against the daily records, month by month; outcome of the rules with the blank days and the day after each run of them left out |

Tolerances: 10⁻⁶ m³ for volumes, 10⁻¹² for levels of satisfaction.

The bounds for V̂ use the step volumes at the levels estimated by the controller (equal to the plant levels in the
chain Q), those for V the step volumes at the plant levels.

## Verification of the plant (`results/verification/`)

`scripts/verification_convergence.py` (grid and time step, with and without the distributed loss),
`scripts/verification_pulse.py` (volume of a single pulse against the hydraulic step) and
`scripts/check_swmm_benchmark.py` (three transients replayed in EPA SWMM 5 through `swmm-toolkit`).

## Reproducibility

Every result has a `.meta.json` file with the command, the Python and package versions, the SHA-256 checksums of the
code (`code_sha256`), of the unchanged simulation core (`core_sha256`, listed file by file in `CORE_MANIFEST.sha256`),
of `scripts/rules.py` (`rules_sha256`) and of `scripts/run_cases.py` (`runner_sha256`), the checksums of the input
files and the active configuration. The theory module is checked independently of the simulation by
`tests/test_theorems.py` (randomised instances of the abstract actuator).
