## S8. Exploratory Controllers, Added Cases, and Robustness Runs

The runs of this section were not pre-specified and are reported as exploratory (Section 2.10). The comparisons with B3V, LXB-DA, LXB-F, and B3V-DA, those with the 7.5 min step, and those under the reverse gate mismatch are given in Table 8 and Section 3.4. Table S7a repeats the IoT chain with three further random seeds (sensor noise and packet loss), replaces the limit forecast by a leave-one-year-out mean, and fills the blank supply entries with the last recorded value of the same season; all use tuned gate coefficients. Across the four seeds, the price of LXB ranged from 5.41% to 5.45%. The decisions of the pre-specified daily analysis were recomputed with bootstrap blocks of 5 and 20 days, with circular blocks, with a bootstrap over whole seasons, and with moving blocks on the full season calendar; 0, 0, 1, 1, 0 of the 50 decisions changed, respectively (with circular blocks, H5 (tuned/phys) became inconclusive instead of rejected; with the season bootstrap, H5 (tuned/phys) became inconclusive instead of rejected). The season-level analysis of Table 6 differs from the daily analysis in 3 decisions (H5 gap~LXB~ − gap~B3~ tuned/phys: rejected → inconclusive; H1 LXB − B2 untuned/IoT: superior → non-inferior; H5 gap~LXB~ − gap~B2~ untuned/IoT: supported → inconclusive). Table S7b gives the volume-weighted satisfaction *R*~vol~ of Section 2.7, Table S7c the sensitivity cases added after the main runs, Table S7d the execution variants, and Table S7e the attribution of the price as a ratio of means and the coalition prices of the day with the largest daily price of the sensor-only constraint set.

<!-- widths: 30,20,12,12,13,13 -->

**Table S7a.** Robustness of the IoT price and of the advantage of LXB (tuned gate coefficients, ten seasons). Π~1~ as a ratio of means; for the blank-supply case, the phys reference is the phys run of the same case.

| Case | Runs | *λ*~LXB~ IoT | Π~1~ LXB, % | LXB − B0 (IoT) | LXB − B3 (IoT) |
|---|---|---|---|---|---|
| Baseline seed | LXB, B0, B3; IoT | 0.768 | 5.4 | +0.322 | +0.492 |
| Independent seed 1 | LXB, B0, B3; IoT | 0.768 | 5.4 | +0.322 | +0.553 |
| Independent seed 2 | LXB, B0, B3; IoT | 0.767 | 5.4 | +0.322 | +0.466 |
| Independent seed 3 | LXB, B0, B3; IoT | 0.768 | 5.4 | +0.322 | +0.548 |
| Leave-one-year-out limit forecast | LXB; phys, IoT | 0.768 | 5.4 | — | — |
| Blank supply days filled with the last recorded value | LXB, B0, B3; phys, IoT | 0.777 | 6.8 | +0.332 | +0.492 |

<!-- widths: 16,14,14,12,12,12,12 -->

**Table S7b.** Volume-weighted satisfaction *R*~vol~ = Σ min(*V*, *D*)/Σ *D* and worst-user satisfaction *λ* (tuned gate coefficients, 1830 days). Loss: relative change of *R*~vol~ from phys to IoT. For LXB-DA, the phys reference is LXB, with which it coincides under ideal execution.

| Method | *R*~vol~ phys | *R*~vol~ IoT | Loss, % | *λ* phys | *λ* IoT | Π~1~, % |
|---|---|---|---|---|---|---|
| Oracle | 0.844 | 0.844 | 0.00 | 0.812 | 0.768 | 5.4 |
| LXB | 0.844 | 0.844 | 0.00 | 0.812 | 0.768 | 5.4 |
| B2 | 0.844 | 0.844 | 0.00 | 0.788 | 0.744 | 5.6 |
| B3 | 0.844 | 0.843 | 0.13 | 0.812 | 0.275 | 66.1 |
| B0 | 0.837 | 0.837 | 0.02 | 0.797 | 0.445 | 44.1 |
| B1 | 0.826 | 0.825 | 0.21 | 0.619 | 0.282 | 54.5 |
| B3V | 0.844 | 0.844 | −0.02 | 0.812 | 0.767 | 5.6 |
| LXB-DA | 0.844 | 0.844 | 0.00 | 0.812 | 0.805 | 0.8 |

<!-- widths: 34,13,13,13,13,14 -->

**Table S7c.** Sensitivity cases added after the main runs (tuned gate coefficients, ten seasons; descriptive). For the sensor offsets, the phys reference is the baseline run.

| Case | *λ* LXB phys | *λ* LXB IoT | Π~1~ LXB, % | *λ* B0 IoT | *λ* B3 IoT |
|---|---|---|---|---|---|
| Baseline | 0.812 | 0.768 | 5.4 | 0.445 | 0.275 |
| *η* = 0.75, demand at the node fixed | 0.796 | 0.752 | 5.6 | 0.424 | 0.283 |
| Plant *η* = 0.75, controller 0.82 | 0.795 | 0.731 | 8.2 | 0.441 | 0.373 |
| Regulator ratings 1.05/0.90/1.10/0.95/1.05 | 0.730 | 0.694 | 5.0 | 0.443 | 0.436 |
| Tail water of the regulators +0.3 m | 0.812 | 0.768 | 5.4 | 0.459 | 0.419 |
| Sensor offset +0.025 m | 0.812 | 0.763 | 6.0 | 0.445 | 0.046 |
| Sensor offset −0.025 m | 0.812 | 0.769 | 5.3 | 0.445 | 0.463 |

<!-- widths: 26,15,14,14,14,17 -->

**Table S7d.** Execution variants (ten seasons). LXB-F: final-share execution program; B3V-DA: B3V with the pulse rule; 7.5 min: control, command, and plant step of 7.5 min. ^a^ Price against the phys run of LXB with the same step.

| Controller and step | Coefficients | *λ* phys | *λ* IoT | Π~1~, % | *r* R-1 IoT |
|---|---|---|---|---|---|
| LXB, 15 min | tuned | 0.812 | 0.768 | 5.4 | 0.771 |
| LXB-F, 15 min | tuned | 0.812 | 0.768 | 5.4 | 0.771 |
| LXB, 15 min | untuned | 0.809 | 0.750 | 7.3 | 0.761 |
| LXB-F, 15 min | untuned | 0.810 | 0.768 | 5.2 | 0.781 |
| B3V-DA, 15 min | tuned | — | 0.803 | — | 0.810 |
| B3V-DA, 15 min | untuned | — | 0.729 | — | 0.836 |
| LXB, 7.5 min | tuned | 0.812 | 0.809 | 0.39 | 0.812 |
| B3, 7.5 min | tuned | 0.812 | 0.251 | 69.0 | 0.268 |
| LXB-DA, 7.5 min ^a^ | tuned | — | 0.807 | 0.61 | 0.811 |

<!-- widths: 16,20,16,16,16,16 -->

**Table S7e.** Shapley attribution of the price of LXB as a ratio of means (tuned gate coefficients; descriptive). The pre-specified attribution of the mean daily price (H7b) is given in Table S6.

| Season | Π~1~ (ratio of means), % | *φ*~S~, pp | *φ*~Q~, pp | *φ*~C~, pp | *φ*~E~, pp |
|---|---|---|---|---|---|
| 2010–2019 | 5.41 | −0.007 | +5.42 | −0.001 | 0 |
| 2010 | 5.95 | −0.091 | +6.02 | +0.023 | 0 |
| 2011 | 9.38 | +0.020 | +9.33 | +0.036 | 0 |
| 2012 | 5.79 | −0.004 | +5.79 | +0.003 | 0 |
| 2013 | 3.14 | +0.001 | +3.18 | −0.041 | 0 |
| 2014 | 7.25 | −0.002 | +7.25 | +0.009 | 0 |
| 2015 | 6.07 | +0.012 | +6.07 | −0.002 | 0 |
| 2016 | 6.64 | −0.006 | +6.66 | −0.010 | 0 |
| 2017 | 6.64 | +0.018 | +6.63 | −0.003 | 0 |
| 2018 | 3.02 | −0.026 | +3.07 | −0.022 | 0 |
| 2019 | 0.33 | +0.016 | +0.32 | −0.008 | 0 |

The largest daily price of the sensor-only constraint set occurred on 20 May 2018 (*λ*^phys^ = 0.619); this day carries 11% of the summed magnitudes of the daily sensor prices of 2018. The daily prices of the 15 constraint sets on that day were: S −0.58%; Q 0.99%; C 0.00%; E 0.00%; SQ −0.51%; SC −0.58%; SE −0.58%; QC 0.86%; QE 0.99%; CE 0.00%; SQC −0.63%; SQE −0.51%; SCE −0.58%; QCE 0.86%; SQCE −0.63%.
