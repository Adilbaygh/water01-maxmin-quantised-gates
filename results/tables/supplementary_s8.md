## S8. Exploratory Controllers and Robustness Runs

The runs of this section were not pre-specified and are reported as exploratory (Section 2.10). The comparisons with B3V and LXB-DA and those under the reverse gate mismatch are given in Table 8 and Section 3.4. Table S7a repeats the IoT chain with three further random seeds (sensor noise and packet loss), replaces the limit forecast by a leave-one-year-out mean, and fills the blank supply entries with the nearest record of the same season; all use tuned gate coefficients. Across the four seeds, the price of LXB ranged from 5.7% to 5.8%. The decisions in Table S6 were recomputed with bootstrap blocks of 5 and 20 days, with circular blocks, and with a bootstrap over whole seasons; none of the 50 decisions changed under any of these settings. Table S7b gives the volume-weighted satisfaction *R*~vol~ of Section 2.7.

<!-- widths: 30,20,12,12,13,13 -->

**Table S7a.** Robustness of the IoT price and of the advantage of LXB (tuned gate coefficients, ten seasons). Π~1~ as a ratio of means; for the blank-supply case, the phys reference is the phys run of the same case.

| Case | Runs | *λ*~LXB~ IoT | Π~1~ LXB, % | LXB − B0 (IoT) | LXB − B3 (IoT) |
|---|---|---|---|---|---|
| Baseline seed | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.489 |
| Independent seed 1 | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.506 |
| Independent seed 2 | LXB, B0, B3; IoT | 0.765 | 5.8 | +0.319 | +0.474 |
| Independent seed 3 | LXB, B0, B3; IoT | 0.765 | 5.7 | +0.320 | +0.511 |
| Leave-one-year-out limit forecast | LXB; phys, IoT | 0.764 | 5.8 | — | — |
| Blank supply days filled with nearest record | LXB, B0, B3; phys, IoT | 0.773 | 7.2 | +0.328 | +0.483 |

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
