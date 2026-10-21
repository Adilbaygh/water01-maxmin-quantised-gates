## 1. B3 + volume feedback (B3V)

| Tuned | Chain | Years | λ B3V | λ B3 | λ LXB | B3V − B3 | LXB − B3V | r R-1 (B3V) |
|---|---|---|---|---|---|---|---|---|
| tuned | phys | 10 | 0.812 | 0.812 | 0.812 | +0.000 | -0.000 | 0.812 |
| tuned | iot | 10 | 0.767 | 0.275 | 0.768 | +0.491 | +0.001 | 0.771 |
| tuned | Π1 B3V | 10 | ratio 5.6% | daily 5.4% | | | | |
| untuned | phys | 10 | 0.794 | 0.660 | 0.809 | +0.134 | +0.015 | 0.836 |
| untuned | iot | 10 | 0.701 | 0.532 | 0.750 | +0.169 | +0.049 | 0.808 |
| untuned | Π1 B3V | 10 | ratio 11.7% | daily n/a (days with λ_phys < 0.01 dominate) | | | | |

## 2. Deadband-aware execution (LXB-DA, IoT chain)

| Tuned | Years | λ LXB-DA | λ LXB | λ LXB phys | Π1 ratio DA | Π1 ratio LXB | Π1 daily DA | r R-1 DA | r R-1 LXB | 1→0 days DA | 1→0 days LXB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | 10 | 0.805 | 0.768 | 0.812 | 0.8% | 5.4% | 0.9% | 0.810 | 0.771 | 0 | 77 |
| untuned | 10 | 0.808 | 0.750 | 0.809 | 0.2% | 7.3% | 0.3% | 0.836 | 0.761 | 0 | 77 |

## 3. Independent random seeds (IoT chain, tuned)

| Seed | Years | λ LXB | λ B0 | λ B3 | Π1 ratio LXB | LXB − B0 | LXB − B3 |
|---|---|---|---|---|---|---|---|
| base | 10 | 0.768 | 0.445 | 0.275 | 5.4% | +0.322 | +0.492 |
| seed_1 | 10 | 0.768 | 0.445 | 0.214 | 5.4% | +0.322 | +0.553 |
| seed_2 | 10 | 0.767 | 0.445 | 0.302 | 5.4% | +0.322 | +0.466 |
| seed_3 | 10 | 0.768 | 0.445 | 0.219 | 5.4% | +0.322 | +0.548 |
| range | | 0.767–0.768 | 0.445–0.445 | 0.214–0.302 | 5.4%–5.4% | +0.322…+0.322 | +0.466…+0.553 |

## 4. Leave-one-year-out forecast

| Method | Years | λ phys | λ IoT | λ phys (base) | λ IoT (base) | Π1 ratio | Π1 ratio (base) |
|---|---|---|---|---|---|---|---|
| LXB | 10 | 0.812 | 0.768 | 0.812 | 0.768 | 5.4% | 5.4% |

## 5. Blank supply entries filled with the last recorded value

| Method | Years | λ phys | λ IoT | λ phys (base) | λ IoT (base) | Π1 ratio | Π1 ratio (base) |
|---|---|---|---|---|---|---|---|
| LXB | 10 | 0.833 | 0.777 | 0.812 | 0.768 | 6.8% | 5.4% |
| B0 | 10 | 0.818 | 0.445 | 0.797 | 0.445 | 45.6% | 44.1% |
| B3 | 10 | 0.833 | 0.285 | 0.812 | 0.275 | 65.8% | 66.1% |
| LXB − B0 / LXB − B3 (phys) | 10 | +0.015 | -0.000 | | | | |
| LXB − B0 / LXB − B3 (iot) | 10 | +0.332 | +0.492 | | | | |

## 6. Bootstrap settings (decisions compared with the pre-specified 10-day moving block)

- block 5: 0 of 50 decisions differ
- block 20: 0 of 50 decisions differ
- circular bootstrap: 1 of 50 decisions differ: H5 gap_LXB − gap_B3 tuned/phys rejected -> inconclusive
- season bootstrap: 1 of 50 decisions differ: H5 gap_LXB − gap_B3 tuned/phys rejected -> inconclusive
- calendar bootstrap: 0 of 50 decisions differ
- season sign-flip test: 3 of 50 decisions differ: H5 gap_LXB − gap_B3 tuned/phys rejected -> inconclusive; H1 LXB − B2 untuned/iot superior -> non-inferior; H5 gap_LXB − gap_B2 untuned/iot supported -> inconclusive

## 7. Volume-weighted satisfaction R_vol (base results, tuned)

| Method | R_vol phys | R_vol IoT | loss | λ phys | λ IoT | Π1 ratio |
|---|---|---|---|---|---|---|
| LXB | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.768 | 5.4% |
| B2 | 0.8438 | 0.8438 | 0.00% | 0.788 | 0.744 | 5.6% |
| B0 | 0.8368 | 0.8366 | 0.02% | 0.797 | 0.445 | 44.1% |
| B3 | 0.8437 | 0.8426 | 0.13% | 0.812 | 0.275 | 66.1% |
| B1 | 0.8262 | 0.8245 | 0.21% | 0.619 | 0.282 | 54.5% |
| Oracle | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.768 | 5.4% |
| B3V | 0.8437 | 0.8438 | -0.02% | 0.812 | 0.767 | 5.6% |
| LXB-DA | 0.8438 | 0.8438 | 0.00% | 0.812 | 0.805 | 0.8% |

## 8. Reverse gate mismatch (untuned_reverse)

| Chain | Years | λ LXB | λ B0 | λ B3 | λ B3V | LXB − B3V |
|---|---|---|---|---|---|---|
| phys | 10 | 0.701 | 0.767 | 0.701 | 0.701 | -0.000 |
| iot | 10 | 0.664 | 0.422 | 0.000 | 0.664 | +0.000 |

## 9. Execution on the final daily share (LXB-F) against proportional recovery of the remaining plan (LXB)

| Tuned | Chain | Years | λ LXB-F | λ LXB | LXB-F − LXB | r R-1 LXB-F | r R-1 LXB |
|---|---|---|---|---|---|---|---|
| tuned | phys | 10 | 0.8117 | 0.8117 | +0.0000 | 0.812 | 0.812 |
| tuned | iot | 10 | 0.7676 | 0.7677 | -0.0001 | 0.771 | 0.771 |
| tuned | Π1 LXB-F | 10 | ratio 5.42% | | | | |
| untuned | phys | 10 | 0.8102 | 0.8092 | +0.0011 | 0.821 | 0.826 |
| untuned | iot | 10 | 0.7681 | 0.7502 | +0.0179 | 0.781 | 0.761 |
| untuned | Π1 LXB-F | 10 | ratio 5.20% | | | | |

## 10. Pulse rule applied to B3V (B3V-DA, IoT chain)

| Tuned | Years | λ B3V-DA | λ B3V | λ LXB-DA | B3V-DA − B3V | LXB-DA − B3V-DA | r R-1 B3V-DA |
|---|---|---|---|---|---|---|---|
| tuned | 10 | 0.8032 | 0.7665 | 0.8048 | +0.0367 | +0.0016 | 0.810 |
| untuned | 10 | 0.7290 | 0.7013 | 0.8075 | +0.0278 | +0.0785 | 0.836 |

## 11. Command step of 7.5 min (dt_450, tuned)

| Method | Chain | Years | λ (7.5 min) | λ (15 min) | difference | r R-1 (7.5 min) | r R-1 (15 min) |
|---|---|---|---|---|---|---|---|
| LXB | phys | 10 | 0.8117 | 0.8117 | -0.0000 | 0.812 | 0.812 |
| LXB | iot | 10 | 0.8085 | 0.7677 | +0.0408 | 0.812 | 0.771 |
| B3 | phys | 10 | 0.8117 | 0.8117 | +0.0000 | 0.812 | 0.812 |
| B3 | iot | 10 | 0.2512 | 0.2753 | -0.0240 | 0.268 | 0.291 |
| LXB-DA | iot | 10 | 0.8067 | 0.8048 | +0.0019 | 0.811 | 0.810 |
| LXB | Π1 | 10 | ratio 0.39% | | | | |
| B3 | Π1 | 10 | ratio 69.05% | | | | |
| LXB-DA | Π1 (phys: LXB) | 10 | ratio 0.61% | | | | |

## 14. End-of-day level condition weighted 100 times less (LXB)

| Tuned | Chain | Years | λ (weak) | λ (base) | difference | mean daily h_min (weak) | mean daily h_min (base) |
|---|---|---|---|---|---|---|---|
| tuned | phys | 10 | 0.8117 | 0.8117 | +0.0000 | 2.993 | 2.996 |
| tuned | iot | 10 | 0.7678 | 0.7677 | +0.0001 | 2.985 | 2.987 |
| untuned | phys | 10 | 0.8097 | 0.8092 | +0.0005 | 2.772 | 2.945 |
| untuned | iot | 10 | 0.7674 | 0.7502 | +0.0172 | 2.750 | 2.916 |

## 13. Hydraulic step of 225 s with the 15-min command step (plant_substeps_4, tuned)

| Method | Chain | Years | λ (225 s) | λ (900 s) | difference | max daily |Δλ| | max daily |ΔV| R-1, m³ |
|---|---|---|---|---|---|---|---|
| LXB | phys | 10 | 0.8117 | 0.8117 | -0.00000 | 0.0027 | 3.56 |
| LXB | iot | 10 | 0.7677 | 0.7677 | -0.00007 | 0.0104 | 60.36 |
| B3 | phys | 10 | 0.8117 | 0.8117 | +0.00000 | 0.0003 | 0.58 |
| B3 | iot | 10 | 0.2770 | 0.2753 | +0.00176 | 0.8791 | 3531.92 |
| LXB-DA | iot | 10 | 0.8048 | 0.8048 | +0.00002 | 0.0216 | 51.28 |

## 12. Gate law near zero head (h0 = 0.1 mm instead of 1 mm, tuned)

| Method | Chain | Years | λ (h0 0.1 mm) | λ (h0 1 mm) | difference | low-head steps (1 mm) | low-head volume, m³ (1 mm) | low-head steps (0.1 mm) |
|---|---|---|---|---|---|---|---|---|
| LXB | phys | 10 | 0.8117 | 0.8117 | -0.0000 | 0 | 0 | 0 |
| LXB | iot | 10 | 0.7677 | 0.7677 | +0.0000 | 0 | 0 | 0 |
| B0 | phys | 10 | 0.7966 | 0.7966 | +0.0000 | 0 | 0 | 0 |
| B0 | iot | 10 | 0.4453 | 0.4453 | +0.0000 | 0 | 0 | 0 |
| B1 | phys | 10 | 0.6194 | 0.6194 | -0.0000 | 12221 | 330931 | 11346 |
| B1 | iot | 10 | 0.2817 | 0.2817 | -0.0000 | 11035 | 334377 | 10171 |
| B3 | phys | 10 | 0.8117 | 0.8117 | +0.0000 | 0 | 0 | 0 |
| B3 | iot | 10 | 0.2753 | 0.2753 | +0.0000 | 229 | 2780 | 222 |

