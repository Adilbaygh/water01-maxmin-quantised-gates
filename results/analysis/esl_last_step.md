# Last open step of LXB-ESL on its equal-split regulator-days (q_variants, ten seasons)

Error of the day V − T = rounding error at the controller's level (U^ − r) + change of the step volume with the level within the step (η = U − U^); v_est: one resolution step at the controller's level, v_max_day: at the highest level of the day (half-step bound of Theorem 1(b) in Table S8f). Re-runs reproduce the stored daily volumes within 10⁻⁶ m³; the identity residual and the ledger error are in m³.

| season | regulator_days | days_over_daily_half_step | days_within_half_step_plus_eta | max_rounding_minus_half_step_m3 | max_abs_eta_m3 | max_eta_minus_bound_m3 | max_ledger_error_m3 | max_identity_residual_m3 | max_after_step_minus_day_m3 |
|---|---|---|---|---|---|---|---|---|---|
| 2010 | 263 | 0 | 263 | -0.05963 | 2.88 | 2.046e-12 | 0 | 7.622e-15 | 0 |
| 2011 | 286 | 1 | 286 | -0.01698 | 1.356 | 2.842e-12 | 0 | 7.55e-15 | 0 |
| 2012 | 245 | 0 | 245 | -0.005607 | 1.376 | 4.547e-13 | 0 | 7.647e-15 | 0 |
| 2013 | 225 | 0 | 225 | -0.02712 | 1.364 | 3.411e-13 | 0 | 7.561e-15 | 0 |
| 2014 | 336 | 0 | 336 | -0.002599 | 1.424 | 2.501e-12 | 0 | 7.639e-15 | 0 |
| 2015 | 274 | 1 | 274 | -0.001959 | 2.871 | 3.411e-12 | 0 | 8.082e-15 | 0 |
| 2016 | 293 | 0 | 293 | -0.03234 | 2.644 | 2.729e-12 | 0 | 1.421e-14 | 0 |
| 2017 | 271 | 1 | 271 | -0.002097 | 1.24 | 1.251e-12 | 0 | 7.543e-15 | 0 |
| 2018 | 314 | 0 | 314 | -0.00505 | 3.21 | 3.524e-12 | 0 | 8.526e-15 | 0 |
| 2019 | 217 | 0 | 217 | -0.0198 | 1.744 | 1.705e-12 | 0 | 7.51e-15 | 0 |
| all | 2724 | 3 | 2724 | -0.001959 | 3.21 | 3.524e-12 | 0 | 1.421e-14 | 0 |


## Regulator-days above half the daily largest resolution step

| date | user | T | error_day | rounding_error | eta | h_min_step | h_max_step | half_v_est | half_v_max_day |
|---|---|---|---|---|---|---|---|---|---|
| 2011-04-28 | Khalkabad-2 | 1776 | 4.413 | 4.268 | 0.1459 | 2.984 | 2.996 | 4.293 | 4.348 |
| 2015-08-20 | R-1 | 3664 | 4.344 | 4.3 | 0.04377 | 2.994 | 2.997 | 4.302 | 4.318 |
| 2017-08-12 | R-1 | 3664 | -4.365 | -4.308 | -0.05667 | 2.998 | 3.003 | 4.31 | 4.315 |
