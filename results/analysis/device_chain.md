# Device chain against the quantised actuator alone: lost commands on pulse days, estimated against plant volumes, equal-split days outside half a resolution step

| case | rule | seasons | pulse_regime_days | days_with_pulses | pulse_days_one_or_two_steps_differ | of_which_step_missing | of_which_step_added | lost_days_err_min_over_p | lost_days_err_max_over_p | pure_days_mean_abs_V_minus_Vhat_over_p | pure_days_max_abs_V_minus_Vhat_over_p | es_days | es_days_outside_half_step_est | es_outside_median_err_over_open_step | es_outside_max_err_over_open_step |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q_main | LXB-T000 | 10 | 2784 | 3119 | 6 | 0 | 6 | 0.1584 | 1.261 | 0 | 0 | 0 | 0 |  |  |
| q_main | LXB-T050 | 10 | 2784 | 3130 | 8 | 0 | 8 | -0.1954 | 0.5987 | 0 | 0 | 0 | 0 |  |  |
| q_main | LXB-ES | 10 | 77 | 373 | 1 | 0 | 1 | 0.08585 | 0.08585 | 0 | 0 | 2719 | 2 | 0.07865 | 0.07923 |
| q_main | LXB-CO | 10 | 2764 | 3078 | 5 | 0 | 5 | -0.4782 | 0.8187 | 0 | 0 | 0 | 0 |  |  |
| iot_main | LXB-T000 | 10 | 2666 | 3098 | 122 | 59 | 63 | 0.02678 | 1.968 | 0.0137 | 0.07245 | 0 | 0 |  |  |
| iot_main | LXB-T050 | 10 | 2663 | 3063 | 125 | 60 | 65 | -0.4469 | 1.437 | 0.01355 | 0.08571 | 0 | 0 |  |  |
| iot_main | LXB-ES | 10 | 74 | 336 | 4 | 3 | 1 | 0.549 | 0.5853 | 0.001659 | 0.005233 | 2725 | 170 | 0.9539 | 2.283 |
| iot_main | LXB-CO | 10 | 2655 | 3083 | 117 | 55 | 62 | -0.4743 | 1.483 | 0.01359 | 0.1027 | 0 | 0 |  |  |
