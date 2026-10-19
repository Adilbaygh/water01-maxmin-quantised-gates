## S8. Exploratory Controllers, Added Cases, and Robustness Runs

The runs of this section were not pre-specified and are reported as exploratory (Section 2.10). The comparisons with B3V, LXB-DA, LXB-F, and B3V-DA, those with the 7.5 min step, and those under the reverse gate mismatch are given in Table 8 and Section 3.4. Table S7a repeats the IoT chain with three further random seeds (sensor noise and packet loss), replaces the limit forecast by a leave-one-year-out mean, and fills the blank supply entries with the last recorded value of the same season; all use tuned gate coefficients. Across the four seeds, the price of LXB ranged from 5.7% to 5.8%. The decisions in Table S6 were recomputed with bootstrap blocks of 5 and 20 days, with circular blocks, with a bootstrap over whole seasons, and with moving blocks on the full season calendar; none of the 50 decisions changed under any of these settings. With the ten seasons as the units of inference, 2 decisions changed (H1 LXB − B2 untuned/IoT: superior → non-inferior; H5 gap~LXB~ − gap~B2~ untuned/IoT: supported → inconclusive). Table S7b gives the volume-weighted satisfaction *R*~vol~ of Section 2.7, Table S7c the sensitivity cases added after the main runs, Table S7d the execution variants, and Table S7e the attribution of the price as a ratio of means and the coalition prices of the day that dominates the 2014 attribution.

<!-- widths: 30,20,12,12,13,13 -->

**Table S7a.** Robustness of the IoT price and of the advantage of LXB (tuned gate coefficients, ten seasons). Π~1~ as a ratio of means; for the blank-supply case, the phys reference is the phys run of the same case.

| Case | Runs | *λ*~LXB~ IoT | Π~1~ LXB, % | LXB − B0 (IoT) | LXB − B3 (IoT) |
|---|---|---|---|---|---|
| Baseline seed | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.489 |
| Independent seed 1 | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.506 |
| Independent seed 2 | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.474 |
| Independent seed 3 | LXB, B0, B3; IoT | 0.765 | 5.7 | +0.320 | +0.511 |
| Leave-one-year-out limit forecast | LXB; phys, IoT | 0.764 | 5.8 | — | — |
| Blank supply days filled with the last recorded value | LXB, B0, B3; phys, IoT | 0.773 | 7.2 | +0.328 | +0.483 |

<!-- widths: 16,14,14,12,12,12,12 -->

**Table S7b.** Volume-weighted satisfaction *R*~vol~ = Σ min(*V*, *D*)/Σ *D* and worst-user satisfaction *λ* (tuned gate coefficients, 1830 days). Loss: relative change of *R*~vol~ from phys to IoT. For LXB-DA, the phys reference is LXB, with which it coincides under ideal execution.

| Method | *R*~vol~ phys | *R*~vol~ IoT | Loss, % | *λ* phys | *λ* IoT | Π~1~, % |
|---|---|---|---|---|---|---|
| Oracle | 0.844 | 0.844 | 0.00 | 0.812 | 0.765 | 5.8 |
| LXB | 0.844 | 0.844 | 0.00 | 0.812 | 0.765 | 5.8 |
| B2 | 0.844 | 0.844 | 0.01 | 0.788 | 0.743 | 5.7 |
| B3 | 0.844 | 0.843 | 0.13 | 0.812 | 0.276 | 66.0 |
| B0 | 0.837 | 0.837 | 0.02 | 0.797 | 0.445 | 44.1 |
| B1 | 0.826 | 0.825 | 0.18 | 0.619 | 0.283 | 54.4 |
| B3V | 0.844 | 0.844 | −0.01 | 0.812 | 0.763 | 5.9 |
| LXB-DA | 0.844 | 0.844 | 0.00 | 0.812 | 0.811 | 0.1 |

<!-- widths: 34,13,13,13,13,14 -->

**Table S7c.** Sensitivity cases added after the main runs (tuned gate coefficients, ten seasons; descriptive). For the sensor offsets, the phys reference is the baseline run.

| Case | *λ* LXB phys | *λ* LXB IoT | Π~1~ LXB, % | *λ* B0 IoT | *λ* B3 IoT |
|---|---|---|---|---|---|
| Baseline | 0.812 | 0.765 | 5.8 | 0.445 | 0.276 |
| *η* = 0.75, demand at the node fixed | 0.796 | 0.749 | 5.9 | 0.425 | 0.293 |
| Plant *η* = 0.75, controller 0.82 | 0.795 | 0.730 | 8.2 | 0.442 | 0.373 |
| Regulator ratings 1.05/0.90/1.10/0.95/1.05 | 0.730 | 0.690 | 5.6 | 0.443 | 0.437 |
| Tail water of the regulators +0.3 m | 0.812 | 0.765 | 5.7 | 0.459 | 0.412 |
| Sensor offset +0.025 m | 0.812 | 0.761 | 6.3 | 0.445 | 0.030 |
| Sensor offset −0.025 m | 0.812 | 0.766 | 5.6 | 0.445 | 0.465 |

<!-- widths: 26,15,14,14,14,17 -->

**Table S7d.** Execution variants (ten seasons). LXB-F: final-share execution program; B3V-DA: B3V with the pulse rule; 7.5 min: control, command, and plant step of 7.5 min. ^a^ Price against the phys run of LXB with the same step.

| Controller and step | Coefficients | *λ* phys | *λ* IoT | Π~1~, % | *r* R-1 IoT |
|---|---|---|---|---|---|
| LXB, 15 min | tuned | 0.812 | 0.765 | 5.8 | 0.766 |
| LXB-F, 15 min | tuned | 0.812 | 0.765 | 5.8 | 0.766 |
| LXB, 15 min | untuned | 0.809 | 0.750 | 7.4 | 0.760 |
| LXB-F, 15 min | untuned | 0.810 | 0.768 | 5.3 | 0.779 |
| B3V-DA, 15 min | tuned | — | 0.808 | — | 0.815 |
| B3V-DA, 15 min | untuned | — | 0.694 | — | 0.838 |
| LXB, 7.5 min | tuned | 0.812 | 0.800 | 1.4 | 0.803 |
| B3, 7.5 min | tuned | 0.812 | 0.208 | 74.4 | 0.223 |
| LXB-DA, 7.5 min ^a^ | tuned | — | 0.811 | 0.06 | 0.814 |

<!-- widths: 16,20,16,16,16,16 -->

**Table S7e.** Shapley attribution of the price of LXB as a ratio of means (tuned gate coefficients; descriptive). The pre-specified attribution of the mean daily price (H7b) is given in Table S6.

| Season | Π~1~ (ratio of means), % | *φ*~S~, pp | *φ*~Q~, pp | *φ*~C~, pp | *φ*~E~, pp |
|---|---|---|---|---|---|
| 2010–2019 | 5.81 | +0.012 | +5.80 | −0.001 | 0 |
| 2010 | 6.46 | +0.013 | +6.39 | +0.056 | 0 |
| 2011 | 9.77 | +0.031 | +9.73 | +0.016 | 0 |
| 2012 | 6.06 | +0.001 | +6.09 | −0.024 | 0 |
| 2013 | 3.39 | −0.025 | +3.42 | −0.004 | 0 |
| 2014 | 7.41 | +0.020 | +7.39 | +0.005 | 0 |
| 2015 | 6.78 | +0.021 | +6.74 | +0.015 | 0 |
| 2016 | 7.33 | +0.014 | +7.32 | −0.012 | 0 |
| 2017 | 7.06 | +0.010 | +7.01 | +0.032 | 0 |
| 2018 | 3.56 | +0.023 | +3.51 | +0.019 | 0 |
| 2019 | 0.39 | +0.023 | +0.47 | −0.104 | 0 |

On 6 June 2014, the phys run released only a residual (*λ*^phys^ = 8.1 × 10^−6^). The daily prices of the 15 constraint sets were: S −3491.54%; Q 100.00%; C −819.27%; E 0.00%; SQ −1004.93%; SC −3492.95%; SE −3491.54%; QC 100.00%; QE 100.00%; CE −819.27%; SQC 100.00%; SQE −1004.93%; SCE −3492.95%; QCE 100.00%; SQCE 100.00%. Each value is the relative change of a satisfaction close to zero, so this single day decides the sign and size of the mean-daily *φ*~S~ of 2014.
