> English translation of requirements/hypotheses.md (the frozen protocol, SHA-256 recorded in results/experiment/PREREGISTRATION.json). The Uzbek original is authoritative; this translation is provided for readers.

# Hypotheses for Kegeyli water allocation v2.2

**Project:** Water-01, Python Desktop, Kegeyli PK 0+00–114+40.  
**Status:** v2.2 — frozen before the final experiment (`run_experiment.py --freeze`; SHA-256 in `results/experiment/PREREGISTRATION.json`). The previous freeze (v2.1, 2026-10-04 09:22) was for a pilot experiment; its results do not enter the final computation (`decisions.md`).  
**Primary source:** `paper/src/methods.md`, Section 2.9, and `paper/manuscript.docx`, Section 2.9.

In this version the old H1–H10 list was not used as a basis. The main hypotheses are H1–H7; they are designed to compare the LXB, B0–B3 and Oracle methods on the same Saint–Venant plant, with the same supply, demand, seed and initial state. Each parameter is stored in the configuration with the status `observed`, `derived` or `assumed`.

## 1. General testing protocol

- Primary data: years 2010–2019, April–September.
- The statistical unit is the day. For hypotheses concerning λ, the paired unit is the **daily worst-case satisfaction** $\lambda[p]=\min_j r_j[p]$ (over pairs with $D_j[p]>0$). The seasonal $\lambda=\min_p\lambda[p]$ yields a single number per year. It is therefore reported only in a descriptive table, not in a test. User–day pairs are used only in H6 (share of command loss).
- Strata: all years; drought years 2011 and 2018; wet years 2010, 2012, 2017; `S < Q_c`; tuned and untuned.
- Paired methods: LXB–B0, LXB–B1, LXB–B2, LXB–B3; where needed, LXB–Oracle and LXB–IoT-open.
- Main test: paired Wilcoxon signed-rank.
- Confidence interval: **daily moving-block bootstrap** with 10 000 replicates, block length 10 days, within year. This preserves the autocorrelation between days. A bootstrap built only from blocks of the 10 years would be too coarse for a 95 % CI and is therefore not used.
- Sign stability across years is a separate criterion: the correct sign in at least 7/10 years.
- Multiple comparisons: Holm correction. Families: H1 — 4 pairs (B0–B3); H5 — 4 pairs; H6 — 2 pairs; the others — a single comparison.
- Directional acceptance rule: the difference is written as "LXB − baseline".
  - Superiority — the **lower** bound of the CI of the difference > 0.
  - Non-inferiority — the lower bound > −ε_λ.
  - For metrics expected to decrease — the **upper** bound of the CI < 0.
- Rejection: if the CI lies on the opposite sign or the sign-stability criterion is not met. If the CI covers zero, the decision is "not confirmed (inconclusive)" and is reported as such.
- The results are interpreted as simulation results, not as a field trial.

## 2. Main hypotheses

### H1 — LXB improves the worst daily satisfaction

**Statement.** The worst daily satisfaction of LXB is higher than, or practically not lower than, that of the B0–B3 baseline methods.

**Metric.** Daily $\lambda[p]=\min_j r_j[p]$ ((10)–(13)). Paired difference $\Delta\lambda[p]=\lambda_{\mathrm{LXB}}[p]-\lambda_b[p]$.

**Observation prior to the computation (smoke, 2026-10-03).** In a daily model without hydraulics, if the capacity constraints are not active, the proportional allocation of B3 is itself max–min optimal. Therefore the λ values of LXB and B3 come out equal (2018, July, decade I: 0.620 and 0.620). Hence a superiority of LXB over B3 can appear only on the reference hydraulic plant: through command loss at the small regulators, delay and gate constraints. H1 is tested only on the Saint–Venant plant.

**Scenario.** All years, 2011/2018 drought, `S < Q_c`, tuned/untuned.

**Acceptance.** A decision is made separately for each baseline (Holm, 4 pairs).
- **Superiority:** the lower CI bound of $\Delta\lambda$ > 0 and the sign is positive in at least 7/10 years.
- **Non-inferiority:** the lower CI bound > −ε_λ.
- H1 is considered fully confirmed if non-inferiority holds for all four baselines and superiority holds for at least one baseline.

**Rejection.** If for any baseline the upper CI bound < −ε_λ, i.e., LXB is practically worse.

### H2 — Feedback mitigates model error

**Statement.** Under sensor and plant errors, supply variation and untuned conditions, the satisfaction loss of feedback LXB is smaller than that of the B1 open-loop method.

**Metric.** `Delta_lambda = lambda_nominal - lambda_perturbed`.

**Pair.** LXB–B1, same perturbation and seed.

**Acceptance.** If the upper bound of the 95 % CI for $\Delta\lambda_{\mathrm{LXB}}-\Delta\lambda_{\mathrm{B1}}$ < 0 and the sign is negative in at least 7/10 years.

**Rejection.** If the CI covers zero or the loss of LXB is larger than that of B1.

### H3 — The third stage increases stability

**Statement.** Stage 3 reduces day-to-day variation and keeps the Stage 1 and Stage 2 optima within the specified `epsilon_1`, `epsilon_2`.

**Metric.** `Z3 = sum(abs(r_j[p] - r_j[p-1]))`, `lambda`, `Z2`.

**Pair.** Full LXB–LXB-without-stage3.

**Acceptance.** The CI for `Z3_full < Z3_no_stage3` is below zero; the losses in `lambda` and `Z2` are within the corresponding tolerance.

**Rejection.** If `Z3` does not decrease or the Stage 1/2 tolerance is violated.

### H4 — The IoT cost is positive

**Statement.** IoT constraints make `Pi_1` positive relative to the physical reference.

**Metric.** `Pi_1 = (lambda_phys - lambda_IoT) / lambda_phys`; the absolute difference if `lambda_phys = 0`.

**Pair.** phys–IoT, same plant and seed.

**Acceptance.** The lower bound of the CI for the daily $\Pi_1[p]$ > 0. Days with $\lambda^{\mathrm{phys}}[p]=0$ are reported separately as an absolute difference.

**Rejection.** If the CI covers zero or `Pi_1` is practically equal to zero or negative.

### H5 — LXB is closer to the Oracle

**Statement.** The Oracle gap of LXB is smaller than the gaps of B0–B3.

**Metric.** `G_oracle = lambda_Oracle - lambda_method` and, where needed, `Z2`.

**Pair.** `G_oracle_LXB - G_oracle_baseline`.

**Acceptance.** In accordance with the statement in `methods.md` §2.9, the LXB gap must be smaller than the gap of **all four** baselines. For each pair the upper bound of the CI is < 0 (Holm, 4 pairs).

**Rejection.** If LXB is not superior in terms of the Oracle gap.

### H6 — Under low supply, command-aware control is superior

**Statement.** On days with `S < Q_c`, command-aware LXB reduces the command loss at the small regulators relative to B0 and B3.

**Metric.** Share of user–day pairs with command loss, violations of `q_j <= f_j(h_L)`, and `lambda`.

**Pair.** LXB–B0, LXB–B3; only days with `S < Q_c`.

**Acceptance.** If the command-loss share of LXB is lower than that of both baselines, the CI is below zero, and the sign holds in 7/10 years.

**Rejection.** If the difference covers zero or the loss of LXB is higher.

### H7 — Feedback reduces the IoT cost relative to open loop

**Statement.** For feedback LXB, $\Pi_1$ is smaller than for IoT-open. The main contribution comes not from sensor error but from quantisation and delay. Delay is included in the "communication" (C) component of the Shapley factors.

**Metric.** $\Pi_1^{\mathrm{fb}}-\Pi_1^{\mathrm{open}}$. Factor contributions: Shapley $\phi_S,\phi_Q,\phi_C,\phi_E$ ((18)).

**Pair.** IoT–IoT-open; 16 subset runs for the factors.

**Acceptance.** Both conditions must hold:
- the upper CI bound of the feedback difference < 0;
- $\phi_Q+\phi_C>\phi_S$, and the lower CI bound of this difference > 0.

**Rejection.** If the CI covers zero or sensor error makes the dominant contribution.

## 3. Open tolerances — awaiting confirmation

The following values are given in `configs/kegeyli_reference.yaml` (sections `fairness`, `hypotheses`) and are currently regarded as `assumed/proposed`:

| Parameter | Proposed initial value | Status |
|---|---:|---|
| epsilon_1 | 1e-6 satisfaction units (ε_λ = 1e-2 = 10⁴·ε1). With stage 1b, λ_LXB − λ_B3 ≥ −1e-6 over 180 decades (scripts/check_tolerance.py) | confirmed 2026-10-03 |
| epsilon_2 | 1e-4 weighted-satisfaction units | proposed, awaiting confirmation |
| epsilon_lambda | 0.01 | proposed, awaiting confirmation |
| Mass balance | relative residual <= 1e-3 | proposed, awaiting confirmation |
| Grid convergence | metric change <= 0.5% | proposed, awaiting confirmation |
| Oracle gap practical threshold | 0.01 lambda units | proposed, awaiting confirmation |
| H_min^op | 2.40 m | passport-based baseline |
| freeboard f_b | 0.20 m | proposed assumption |
| Preissmann theta | 0.6. Reason: θ = 0.5 is neutrally stable and produces oscillations. Cunge et al. (1980) recommend 0.55–0.67 | proposed |

These values must be confirmed in `requirements/decisions.md` before the hypotheses are frozen.

## 3a. Operational definitions (v2.2, `scripts/evaluate_hypotheses.py`)

- **Pairing:** (year, date); variant — the `tuned`, `iot` columns in the CSV. CI — 10-day block bootstrap (within year); p — daily Wilcoxon (days are mutually dependent, so the main evidence is the CI and the sign across years); Holm — within a family.
- **H1, H5, H6:** each variant (tuned/untuned × phys/iot). In the paired difference of H5 the Oracle cancels: gap_LXB − gap_b = λ_b − λ_LXB — a sign-reversed copy of H1; descriptive.
- **H2:** nominal — tuned/phys; main perturbation — untuned/iot (C_d error + all IoT factors); secondary — untuned/phys and tuned/iot. Metric: (λ_nom − λ_pert)_LXB − (λ_nom − λ_pert)_B1, "decrease".
- **H3:** LXB and LXB-noS3 (no stage 3 in the daily plan), tuned/phys. Z3[p] = Σ_j |r_j[p] − r_j[p−1]| (plant satisfaction) "decrease"; tolerance — "increase" for λ and Z2 = mean r (non-inferiority, ε_λ). At the LP level, ε1 and ε2 hold by construction in every solve.
- **H4:** LXB, Π1[p] = (λ_phys[p] − λ_IoT[p])/λ_phys[p], days with λ_phys[p] > 0; the number of days with λ_phys = 0 separately. tuned — main, untuned — secondary.
- **H7:** (a) Π1_LXB[p] − Π1_B1[p] (IoT-open — B1 with the IoT chain), tuned; (b) for each year v(F) = mean daily Π1 (LXB, tuned), 16 subsets, Shapley (18); d_y = φ_Q + φ_C − φ_S, CI — bootstrap across years.
- **IoT:** "iot" = {S, Q, C, E}. E — (16): NASA POWER, RTU + gateway load; the radio is switched off when the charge falls below the reserve.

## 4. Results table

| H | Metric | Result | 95% CI | Decision |
|---|---|---|---|---|
Final values — `results/hypotheses_summary_normal.md` (single source); this table is filled in from it after the final experiment.

| H1 | lambda difference | TBD | TBD | TBD |
| H2 | Delta_lambda difference | TBD | TBD | TBD |
| H3 | Z3 difference | TBD | TBD | TBD |
| H4 | Pi_1 | TBD | TBD | TBD |
| H5 | Oracle gap difference | TBD | TBD | TBD |
| H6 | command-loss difference | TBD | TBD | TBD |
| H7 | feedback/open-loop Pi_1; Shapley | TBD | TBD | TBD |

## 5. Freeze log

Status: **v2.2 — ready for freezing.** Relative to v2.1 (2026-10-03): operational definitions (§3a), the energy factor, H3/H7 runs (`decisions.md`, 2026-10-04).  
SHA-256: `results/experiment/PREREGISTRATION.json` (written at the final `--freeze`).  
Changes after freezing are introduced as a new version with the reason recorded in `decisions.md`.
