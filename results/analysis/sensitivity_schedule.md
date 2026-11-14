# Recorded daily pulse counts of the four small regulators on one shared pulse per step: earliest-deadline schedule of the days with at most N = 96 pulses (counts of the day known at its start and spread uniformly over the day); largest deviation of the cumulative pulses of a regulator from its uniform share, against the bound 1 − 1/(2k − 2) with k = 5 (four regulators and the idle state)

| case | rule | days | N | days_within_N | days_above_N | max_pulses_per_day | distinct_count_vectors | max_deviation_pulses | bound_pulses |
|---|---|---|---|---|---|---|---|---|---|
| q_main | LXB-T000 | 1830 | 96 | 1649 | 181 | 160 | 133 | 0.875 | 0.875 |
| q_main | LXB-T050 | 1830 | 96 | 1665 | 165 | 160 | 144 | 0.875 | 0.875 |
| q_main | LXB-CO | 1830 | 96 | 1665 | 165 | 158 | 214 | 0.875 | 0.875 |
| q_theta | LXB-T075 | 1830 | 96 | 1666 | 164 | 157 | 146 | 0.875 | 0.875 |
