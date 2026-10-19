## 1. B3 + volume feedback (B3V)

| Tuned | Chain | Years | λ B3V | λ B3 | λ LXB | B3V − B3 | LXB − B3V | r R-1 (B3V) |
|---|---|---|---|---|---|---|---|---|
| tuned | phys | 10 | 0.812 | 0.812 | 0.812 | +0.000 | -0.000 | 0.812 |
| tuned | iot | 10 | 0.763 | 0.276 | 0.765 | +0.488 | +0.001 | 0.766 |
| tuned | Π1 B3V | 10 | ratio 5.9% | daily 6.6% | | | | |
| untuned | phys | 10 | 0.795 | 0.660 | 0.809 | +0.135 | +0.014 | 0.836 |
| untuned | iot | 10 | 0.663 | 0.533 | 0.750 | +0.130 | +0.087 | 0.802 |
| untuned | Π1 B3V | 10 | ratio 16.6% | daily n/a (days with λ_phys < 0.01 dominate) | | | | |

## 2. Deadband-aware execution (LXB-DA, IoT chain)

| Tuned | Years | λ LXB-DA | λ LXB | λ LXB phys | Π1 ratio DA | Π1 ratio LXB | Π1 daily DA | r R-1 DA | r R-1 LXB | 1→0 days DA | 1→0 days LXB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | 10 | 0.811 | 0.765 | 0.812 | 0.1% | 5.8% | 0.5% | 0.815 | 0.766 | 0 | 77 |
| untuned | 10 | 0.809 | 0.750 | 0.809 | 0.0% | 7.4% | 0.5% | 0.841 | 0.760 | 0 | 77 |

## 3. Independent random seeds (IoT chain, tuned)

| Seed | Years | λ LXB | λ B0 | λ B3 | Π1 ratio LXB | LXB − B0 | LXB − B3 |
|---|---|---|---|---|---|---|---|
| base | 10 | 0.765 | 0.445 | 0.276 | 5.8% | +0.319 | +0.489 |
| seed_1 | 10 | 0.765 | 0.445 | 0.259 | 5.8% | +0.319 | +0.506 |
| seed_2 | 10 | 0.765 | 0.445 | 0.291 | 5.8% | +0.319 | +0.474 |
| seed_3 | 10 | 0.765 | 0.445 | 0.254 | 5.7% | +0.320 | +0.511 |
| range | | 0.765–0.765 | 0.445–0.445 | 0.254–0.291 | 5.7%–5.8% | +0.319…+0.320 | +0.474…+0.511 |

## 4. Leave-one-year-out forecast

| Method | Years | λ phys | λ IoT | λ phys (base) | λ IoT (base) | Π1 ratio | Π1 ratio (base) |
|---|---|---|---|---|---|---|---|
| LXB | 10 | 0.812 | 0.764 | 0.812 | 0.765 | 5.8% | 5.8% |

## 5. Blank supply entries filled with the nearest record

| Method | Years | λ phys | λ IoT | λ phys (base) | λ IoT (base) | Π1 ratio | Π1 ratio (base) |
|---|---|---|---|---|---|---|---|
| LXB | 10 | 0.833 | 0.773 | 0.812 | 0.765 | 7.2% | 5.8% |
| B0 | 10 | 0.818 | 0.445 | 0.797 | 0.445 | 45.5% | 44.1% |
| B3 | 10 | 0.833 | 0.290 | 0.812 | 0.276 | 65.2% | 66.0% |
| LXB − B0 / LXB − B3 (phys) | 10 | +0.015 | +0.000 | | | | |
| LXB − B0 / LXB − B3 (iot) | 10 | +0.328 | +0.483 | | | | |

## 6. Bootstrap settings (decisions compared with the pre-specified 10-day moving block)

- block 5: 0 of 50 decisions differ
- block 20: 0 of 50 decisions differ
- circular bootstrap: 0 of 50 decisions differ
- season bootstrap: 0 of 50 decisions differ
- calendar bootstrap: not computed (python scripts/evaluate_hypotheses.py --bootstrap calendar)
- season sign-flip test: not computed (python scripts/evaluate_hypotheses.py --bootstrap season --inference season)

## 7. Volume-weighted satisfaction R_vol (base results, tuned)

| Method | R_vol phys | R_vol IoT | loss | λ phys | λ IoT | Π1 ratio |
|---|---|---|---|---|---|---|
| LXB | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.765 | 5.8% |
| B2 | 0.8438 | 0.8438 | 0.01% | 0.788 | 0.743 | 5.7% |
| B0 | 0.8368 | 0.8366 | 0.02% | 0.797 | 0.445 | 44.1% |
| B3 | 0.8437 | 0.8426 | 0.13% | 0.812 | 0.276 | 66.0% |
| B1 | 0.8264 | 0.8250 | 0.18% | 0.619 | 0.283 | 54.4% |
| Oracle | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.765 | 5.8% |
| B3V | 0.8437 | 0.8437 | -0.01% | 0.812 | 0.763 | 5.9% |
| LXB-DA | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.811 | 0.1% |

## 8. Reverse gate mismatch (untuned_reverse)

| Chain | Years | λ LXB | λ B0 | λ B3 | λ B3V | LXB − B3V |
|---|---|---|---|---|---|---|
| phys | 10 | 0.701 | 0.767 | 0.701 | 0.701 | +0.000 |
| iot | 10 | 0.661 | 0.422 | 0.000 | 0.661 | +0.000 |

## 9. Execution on the final daily share (LXB-F) against proportional recovery of the remaining plan (LXB)

| Tuned | Chain | Years | λ LXB-F | λ LXB | LXB-F − LXB | r R-1 LXB-F | r R-1 LXB |
|---|---|---|---|---|---|---|---|
| tuned | phys | 10 | 0.8117 | 0.8117 | -0.0000 | 0.812 | 0.812 |
| tuned | iot | 10 | 0.7645 | 0.7645 | +0.0000 | 0.766 | 0.766 |
| tuned | Π1 LXB-F | 10 | ratio 5.80% | | | | |
| untuned | phys | 10 | 0.8102 | 0.8091 | +0.0011 | 0.821 | 0.826 |
| untuned | iot | 10 | 0.7675 | 0.7496 | +0.0179 | 0.779 | 0.760 |
| untuned | Π1 LXB-F | 10 | ratio 5.27% | | | | |

## 10. Pulse rule applied to B3V (B3V-DA, IoT chain)

| Tuned | Years | λ B3V-DA | λ B3V | λ LXB-DA | B3V-DA − B3V | LXB-DA − B3V-DA | r R-1 B3V-DA |
|---|---|---|---|---|---|---|---|
| tuned | 10 | 0.8079 | 0.7635 | 0.8107 | +0.0444 | +0.0028 | 0.815 |
| untuned | 10 | 0.6939 | 0.6626 | 0.8088 | +0.0313 | +0.1150 | 0.838 |

## 11. Command step of 7.5 min (dt_450, tuned)

| Method | Chain | Years | λ (7.5 min) | λ (15 min) | difference | r R-1 (7.5 min) | r R-1 (15 min) |
|---|---|---|---|---|---|---|---|
| LXB | phys | 10 | 0.8116 | 0.8117 | -0.0000 | 0.812 | 0.812 |
| LXB | iot | 10 | 0.8003 | 0.7645 | +0.0358 | 0.803 | 0.766 |
| B3 | phys | 10 | 0.8117 | 0.8117 | +0.0000 | 0.812 | 0.812 |
| B3 | iot | 10 | 0.2081 | 0.2757 | -0.0676 | 0.223 | 0.292 |
| LXB-DA | iot | 10 | 0.8111 | 0.8107 | +0.0004 | 0.814 | 0.815 |
| LXB | Π1 | 10 | ratio 1.40% | | | | |
| B3 | Π1 | 10 | ratio 74.36% | | | | |
| LXB-DA | Π1 (phys: LXB) | 10 | ratio 0.06% | | | | |

