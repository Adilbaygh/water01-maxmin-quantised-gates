# water-01: max–min water delivery through quantised gates at a canal node

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23728409.svg)](https://doi.org/10.5281/zenodo.23728409)

Computation project of the article on max–min (worst-user) water delivery through gates with a finite resolution and
an actuator deadband, with the Dustlik node of the Kegeyli irrigation canal (Republic of Karakalpakstan, Uzbekistan)
as the case. The project contains the theory module of the article, the closed-loop Saint–Venant simulation core,
the execution rules, the simulation cases, the analysis scripts and the results.

## Contents

| Path | Content |
|---|---|
| `src/quantmaxmin/` | Theory module: continuous level λ\*, minimum-delivery level λ_q, price of indivisibility Π_ind and whole-step level λ_v (Theorem 2, exact algorithms with mixed-integer and enumeration checks); abstract quantised actuator and the execution rules of Theorems 1, 3 and 4 |
| `src/water01/` | Simulation core, version 1.4.0, unchanged: Saint–Venant pool (Preissmann scheme), Dustlik node with six outlets, daily three-stage lexicographic plan and 15-min execution programme (LXB), IoT layer (level sensor, quantised actuator with deadband, LoRaWAN budget, solar energy balance). File checksums: `docs/CORE_MANIFEST.sha256` |
| `scripts/rules.py` | Execution rules registered as controllers of the core: θ pulse rule (`LXB-T000`, `LXB-T025`, `LXB-T050`, `LXB-T075`), equal split with pulse fallback (`LXB-ES`), carry-over of the daily debt (`LXB-CO`) |
| `scripts/run_cases.py` | Simulation cases (seasons 2010–2019, 1 April–30 September), resumable and parallel |
| `scripts/analyse_theorems.py` | Closed-loop checks of Theorems 1–4, balance of the node, outcome of the rules and checks of the records (blank days, 2011 annual volume, outcome without the blank days) → `results/analysis/` |
| `scripts/gate_activity.py` | Gate movements and travel per day: re-runs the case `q_main` (about 4 min per season and rule) and checks that the stored volumes are reproduced → `results/analysis/gate_activity*` |
| `scripts/check_residual_cap.py` | Requests of direct execution (LXB) against the remainder of the daily plan at every step, the assumption of Theorem 1(a): re-runs the seven direct-execution cases (about 4 min per season) and checks that the stored volumes are reproduced → `results/analysis/residual_cap*` |
| `scripts/make_figures.py` | Figures → `results/figures/` |
| `scripts/verification_convergence.py`, `scripts/verification_pulse.py`, `scripts/check_swmm_benchmark.py` | Verification of the plant: grid and time-step convergence, volume of a single pulse, comparison with EPA SWMM 5 → `results/verification/` |
| `scripts/derive_inputs.py` | Delivery factor, monthly shares of the Abad-Yarmish regulator, node balance and checks of the records → `results/inputs/derived_inputs.json`; with `--write-demand`, the demand file (reproduced bit for bit) |
| `main.py`, `gui/` | Graphical interface (English and Uzbek): stored results and environment, configuration and records, gate and execution rules, runs of missing seasons, plots of the daily results, analysis scripts and tables, figures |
| `docs/EXPERIMENT.md` | Design of the computational experiment: plant, plan, actuator, rules, cases, recorded quantities and checks |
| `docs/EXPECTED_OUTCOMES_uz.md` | Expected outcomes of the rules, the device chain and the robustness cases, recorded (in Uzbek) before these results were examined |
| `tests/` | Randomised checks of Theorems 1–4 on the abstract actuator (about 29 000 instances, with a mixed-integer check of λ_q, an enumeration check of λ_v and a constructive check of the condition of Theorem 2(c) for a gate with a nonlinear discharge), short closed-loop checks of the rules, and the tests of the simulation core (`test_core_*.py`) |
| `configs/` | Reference configuration of the Kegeyli pool and the Dustlik node, and the scenario files of the cases (`sensor_udl`, `design_geometry`, `communication_loss`, `tailwater_high`, `manning_low` and `manning_high` are used only by the tests of the core) |
| `DATA/processed/` | Daily operating records 2010–2019 (supply at the Kegeyli head), the decadal demand of the node and the records it is derived from (`DATA/processed/README.md`) |
| `DATA/raw/nasa_power/` | Hourly irradiance (NASA POWER) for the solar energy balance of the full IoT chain |
| `results/runs/` | One table per (case, rule, season): daily plan, executed target, delivered and estimated volumes, openings and pulses of every outlet, with a `.meta.json` file (environment, code and input checksums, configuration) |
| `results/analysis/` | Summary tables of the theorem checks (CSV and Markdown) |
| `results/figures/` | Figures 1–5 of the article (PNG and PDF); `fig_april` and `fig_periods` are the two panels of Figure 5 as separate figures |
| `results/inputs/` | Derived inputs of the case (`derived_inputs.json`) |
| `results/verification/` | Verification of the plant (convergence, single pulse, EPA SWMM benchmark) |

## Cases

| Case | Scenario | Execution chain | Rules |
|---|---|---|---|
| `phys` | baseline | ideal execution | LXB |
| `q_main` | baseline | quantised actuator only (the setting of Theorems 1–4) | LXB, LXB-T000, LXB-T050, LXB-ES, LXB-CO |
| `q_theta` | baseline | quantised actuator only | LXB-T025, LXB-T075 |
| `iot_main` | baseline | full IoT chain (sensor, actuator, communication, energy) | LXB, LXB-T000, LXB-T050, LXB-ES, LXB-CO |
| `q_deadband_low`, `q_deadband_high` | deadband 0.25% and 1% of the travel (k = 3 and 10) | quantised actuator only | LXB |
| `q_cd_low`, `q_cd_high` | gate coefficient −20% and +20% | quantised actuator only | LXB |
| `q_leak_005mm` | regulators leak as through a 0.05 mm opening | quantised actuator only | LXB |
| `q_rating` | outlet-specific rating errors (±10%), unknown to the controller | quantised actuator only | LXB-T050, LXB-CO |

LXB is direct execution; its execution programme keeps the requested volume within the remaining plan by a penalty,
not by a constraint, which `scripts/check_residual_cap.py` checks on every step. `LXB-T050` coincides with the
deadband-aware rule LXB-DA of the simulation core (checked in `tests/test_rules_closed_loop.py`).

## Running

Python 3.13 with the packages of `requirements.txt`:

    python -m pip install -r requirements.txt
    python -m pytest -q                                   # theory and closed-loop checks
    python scripts/run_cases.py --phases A,B,C            # 200 seasonal runs, about 3 min each on one core;
                                                          # several instances may run at once
    python scripts/gate_activity.py --part 0/2 &          # gate movements: 50 re-runs of q_main, two processes
    python scripts/gate_activity.py --part 1/2
    python scripts/check_residual_cap.py --part 0/2 &     # requests of direct execution: 70 re-runs, two processes
    python scripts/check_residual_cap.py --part 1/2
    python scripts/analyse_theorems.py                    # summary tables → results/analysis/*.csv and *.md
    python scripts/make_figures.py                        # figures
    python scripts/verification_convergence.py            # verification of the plant (also with --eta 0.81),
    python scripts/verification_pulse.py                  # single pulse,
    python scripts/check_swmm_benchmark.py                # EPA SWMM 5 benchmark (needs swmm-toolkit)

A stored result is never recomputed; delete it to repeat a run. Each `.meta.json` records the checksum of the code
(`code_sha256`: `src/**/*.py`), of the unchanged core (`core_sha256`), of the rules and of the runner, the checksums of
the input files and the active configuration. The stored runs were computed with release 2.0.0; their `core_sha256`,
`rules_sha256` and `runner_sha256` match this release, whereas `code_sha256` also covers the theory module
`src/quantmaxmin`, which releases 2.1.0 and 2.2.0 extend and which the simulations do not use.
`scripts/gate_activity.py` and `scripts/check_residual_cap.py` re-run stored cases with this release and stop if a
stored daily volume is not reproduced within 10⁻⁶ m³. The numbers of the tables of the article are those of
`results/analysis/*.md`; the manuscript itself is not part of the repository.

## Graphical interface

    python main.py                # start the interface
    python main.py --lang uz      # the interface in Uzbek (the choice is remembered)
    python main.py --check        # environment, checksums of the core and state of the stored seasons, in the terminal

The interface needs Tkinter, which the Python installers for Windows and macOS include (on Linux: the package
`python3-tk`). It reads the stored results and runs the scripts of the project in separate processes, on request only;
it does not change the simulation core or a complete stored season. Its tabs show the outcome of the rules (Table 4 of
the article) and the environment; the parameters of the configuration with their status and source, and the supply,
demand and λ\* of every season; the step volumes of a regulator and the execution rules on one day and over several
days at a constant level, with the bounds of Theorems 1, 3 and 4; the state of the 200 seasons, whose missing seasons
are computed with the functions of `scripts/run_cases.py` (in parallel if requested); the daily results by case, rule,
season and outlet, with export to CSV; the analysis scripts and the tables of `results/`; and the figures of
`results/figures` (Figures 1–5 of the article and two separate panels of Figure 5). Settings are kept in
`~/.water01_gui.json`.

## Citation

Version 2.3.0 of this repository is archived at Zenodo: https://doi.org/10.5281/zenodo.23728409. The authors and the
article to cite are given in `CITATION.cff`.

## Licence

Code: MIT (`LICENSE`). Configuration, processed records and results: CC BY 4.0 (`LICENSE-DATA.md`).
