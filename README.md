# Water-01: IoT executability price of lexicographic water allocation

[![tests](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)

Code, configuration, inputs and results of the article

> Kudaybergenov, A.; Kabulov, A.; Kazimbetova, M.; Ametova, G.; Ispanova, J.; Shikhiyev, R. Quantifying the IoT Executability Price of Lexicographic Water Allocation: A Saint–Venant
> Simulation Study of the Kegeyli Irrigation Canal, Uzbekistan. *Water* (MDPI), 2026 (submitted).

The model simulates one pool of the Kegeyli canal (PK 0+00–114+40) with the Saint–Venant equations (Preissmann
scheme) and the six outlets of the Dustlik node over the vegetation seasons 2010–2019. A daily lexicographic plan
(max–min-first: satisfaction of the worst user, then total satisfaction, then day-to-day variation) is executed every
15 min by a receding-horizon controller (LXB), which recovers the remaining daily plan in equal proportion for all
users, and compared with an area-based, PI-controlled surrogate for current practice (B0), an open-loop fair plan (B1),
a weighted-sum controller (B2), proportional rationing (B3) and an Oracle. Every controller runs with ideal execution
(*phys*) and through a simulated IoT chain (*IoT*): level-sensor error, actuator quantisation and deadband, a LoRaWAN
packet budget with packet loss, and a solar energy balance of the node. The **IoT executability price**

Π₁ = (λ^phys − λ^IoT) / λ^phys

is the relative loss of λ, the daily delivered-to-demanded volume of the worst-served user, and Shapley values
attribute it to the four device constraints.

| Controller (tuned gate coefficients) | mean daily λ, phys | mean daily λ, IoT | Π₁ (ratio of means) |
|---|---|---|---|
| LXB (proposed) | 0.812 | 0.765 | 5.8% |
| B0 current practice | 0.797 | 0.445 | 44.1% |
| B3 proportional rationing | 0.812 | 0.276 | 66.0% |
| LXB-DA, deadband-aware execution (exploratory) | 0.812 | 0.811 | 0.1% |

The tables and numbers of the article are regenerated from the stored results by `scripts/make_results_tables.py`
(`results/tables/`); the quantities that need the demand records (see *Data*) are skipped without them.

## Quick start: the graphical interface

```bash
git clone <repository URL>
cd <repository folder>
python -m pip install -r requirements.txt -r requirements-gui.txt     # Python 3.13
streamlit run app/water01_app.py
```

The interface opens in the browser and has six pages:

| Page | Content |
|---|---|
| Overview | the study in brief, the main numbers and the figures of the article |
| Results explorer | daily worst-user satisfaction, satisfaction of each user and node level of every stored run |
| IoT price | price of every controller, daily price of LXB, Shapley attribution by season |
| Hypothesis tests | pre-specified tests H1–H7 with the bootstrap variants, exploratory comparisons, sensitivity cases, verification |
| Run the model | closed-loop simulation of a chosen period, controller, scenario and set of IoT constraints |
| Reproducibility | code checksum of the copy and of the stored results, software environment, commands |

Without the operating records (see *Data*), *Run the model* uses the synthetic inputs of `DATA/synthetic/`.

## Data

| Folder | Content | In this repository |
|---|---|---|
| `DATA/raw/nasa_power/` | hourly NASA POWER irradiance at the node, used by the energy model | yes (open data) |
| `DATA/synthetic/` | generated supply and demand with the structure of the records (`scripts/make_synthetic_inputs.py`) | yes |
| `DATA/processed/` | daily head discharge 2010–2019, decadal demand at the node, official 2021 limit profile, and the 2020 dispatcher sheets of the Kegeyli canal, transcribed from the operating records of the irrigation system (`DATA/processed/README.md`) | yes |

The processed operating records are those used by every reported run; their SHA-256 checksums are stored in the
`.meta.json` file of every result and are checked by `scripts/check_results.py`. The original record sheets are not
included.

## Installation and tests

```bash
python -m pip install -r requirements.txt          # pinned numpy, scipy, pandas, PyYAML, pytest; matplotlib
python -m pytest -q
```

The tests use the operating records in `DATA/processed/`; without them (for example in a copy without the data
folder), they use the synthetic inputs, and the test of the official 2021 limit profile is skipped. The tests cover the hydraulic plant (mass balance, steady profiles,
grid convergence), the lexicographic linear programs, the controllers, the IoT layer, the statistics and decision
rules, provenance and determinism (Table S2 of the Supplementary Materials).

## Reproducing the results

Every run writes one CSV per controller × season × chain with a `.meta.json` file that records the software
environment, the active configuration, and the SHA-256 checksums of the source code and of the inputs.

Three levels of reproduction are possible. (1) Integrity: `check_results.py --all` checks that every stored result is
complete, numerically valid (finite satisfactions in [0, 1], non-negative volumes, mass error, retained optima,
packet counters) and was computed with the current code and inputs. (2) Evaluation: the hypothesis tests, the
exploratory comparisons, the tables and the figures are recomputed from the stored daily results. (3) Simulation:
every season is rerun from the operating records in `DATA/processed/`.

From the stored results:

```bash
python scripts/make_results_tables.py          # Tables 6-8, S6, S7 and the numbers of the text -> results/tables/
python scripts/fig_results.py                  # Figures 4-6 -> results/figures/
python scripts/fig_methods.py                  # Figures 1-3 -> results/figures/
```

Without `DATA/processed/`, `make_results_tables.py` skips the quantities that need the demand file (the
demand-floor checks, the demand of the outlet R-1 and the delivered volume relative to the demand). The hypothesis
tests (`evaluate_hypotheses.py`) also run from the stored results; H6 needs the supply records and is reported as not
available without them.

With the operating records in `DATA/processed/`:

```bash
python scripts/run_experiment.py --verify --years 2018 --methods LXB --tuned tuned --iot iot
                                               # reruns one stored season and compares it with the stored file
python scripts/run_experiment.py --all --jobs 4            # main runs: 240 + 140 Shapley + 10 ablation
python scripts/run_experiment.py --sensitivity --jobs 4    # sensitivity runs -> results/sensitivity/
python scripts/run_experiment.py --exploratory --jobs 4    # exploratory runs -> results/exploratory/
python scripts/check_results.py --all --write              # completeness, identical code and inputs, manifest
python scripts/evaluate_hypotheses.py                      # H1-H7 -> results/hypotheses_summary_normal.csv
python scripts/evaluate_hypotheses.py --bootstrap circular # bootstrap variants (also: season, calendar)
python scripts/evaluate_hypotheses.py --bootstrap season --inference season   # seasons as the units of inference
python scripts/evaluate_hypotheses.py --scenario block_5 --data normal
python scripts/evaluate_hypotheses.py --scenario block_20 --data normal
python scripts/summarize_sensitivity.py                    # -> results/sensitivity_summary.csv
python scripts/summarize_exploratory.py                    # -> results/exploratory_summary.csv
python scripts/compare_exploratory.py                      # -> results/exploratory_tests.csv (same options)
python scripts/verification_convergence.py                 # grid and time-step convergence (Table S2a)
python scripts/verification_pulse.py                       # gate pulse vs hydraulic step (Table S2b)
```

A season takes about 2 min for B0, B1 and B3 and about 8 min for B2, LXB and the Oracle on one core; an existing result
is kept only if its metadata show the current code and inputs and its table is complete (a table appears only after
its metadata), so an interrupted sweep resumes where it stopped and results of other versions are recomputed. Linear-program solutions can differ at the level
of the solver tolerance between platforms and solver versions; in the environment of `requirements.txt`, a stored season
computed under Windows was reproduced under Linux to 4 × 10⁻¹⁶ in λ and 2 × 10⁻⁹ m³ in the delivered volumes
(`results/verification/rerun/comparison.csv`).

Every result records the checksum of the code that computed it. `check_results.py` requires every run to come from
the current code and the current version of every recorded input; with `--accept-listed`, runs of earlier versions
are accepted if each version is listed in `results/versions.json`, together with the evidence that the later version
reproduces the earlier results. Evaluation outputs record the checksum of the whole code base and of the daily results
they were computed from (`.meta.json`, `results/tables/PROVENANCE.json`). The bootstrap schemes are: `block` (pre-specified; 10-day moving blocks
within each season), `circular`, `season` (whole seasons) and `calendar` (moving blocks on the full calendar of each
season; excluded days stay in place and are left out of the replicate means).

The hypotheses, metrics and decision rules were fixed before the simulation runs. The protocol is
`requirements/hypotheses.md` (original language; its SHA-256 is recorded in `results/experiment/PREREGISTRATION.json`
and checked before every run), with an English translation in `requirements/hypotheses_en.md`.

## Repository layout

```
src/water01/
    domain/        configuration (reference + scenario), parameter registry with status and source, geometry, state
    hydraulics/    Saint-Venant equations, Preissmann solver, gate equations and the Dustlik node
    optimization/  daily lexicographic LP (stages 1, 1b, 2, 3) and the 15-min execution LP
    iot/           devices, quantisation and deadband, measurement model, packet budget, energy balance
    control/       controllers B0, B1, B2, B3, B3V, B3V-DA, LXB, LXB-F, LXB-DA, LXB-noS3, Oracle
    simulation/    closed loop, scenarios, runner, provenance (.meta.json)
    evaluation/    metrics, price, Shapley values, statistics, decision rules
configs/           kegeyli_reference.yaml (every parameter: value, status observed/derived/assumed/setting, source)
                   scenarios/*.yaml (sensitivity, stress and exploratory cases)
requirements/      hypothesis protocol and its English translation
scripts/           experiment, evaluation, summaries, tables, figures, verification, synthetic inputs
tests/             automated tests (pytest)
app/               graphical interface (Streamlit)
results/           daily result files with .meta.json, summaries, manifest, tables and figures
DATA/              open NASA POWER irradiance and synthetic inputs
```

## Citation and licence

Please cite the article and this repository (`CITATION.cff`). The code is released under the MIT License (`LICENSE`);
the results, configuration and synthetic inputs under CC BY 4.0 (`LICENSE-DATA.md`).

Contact: Adilbay Kudaybergenov, Karakalpak State University named after Berdakh, Nukus, Uzbekistan
(q_adilbay@karsu.uz).
