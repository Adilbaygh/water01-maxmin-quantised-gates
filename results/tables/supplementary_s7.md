## S7. Results of All Hypothesis Tests

Table S6 gives two analyses of every test. The columns from the estimate to the decision give the pre-specified daily analysis, recorded as the original analysis; the last column gives the decision with the ten seasons as the units of inference, which is the principal analysis of the article (Section 2.9). Decisions follow the pre-specified rules (Section 2.9): superiority (or a supported decrease) requires the 95% confidence interval to exclude zero on the predicted side, a Holm-adjusted *p*-value below 0.05, and the expected sign in at least 7 of 10 seasons; non-inferiority requires only a lower limit above −*ε*~λ~ (*ε*~λ~ = 0.01). An interval that excludes zero on the predicted side without the *p*-value or sign condition is reported as inconclusive. Confidence intervals come from a moving-block bootstrap with 10-day blocks within seasons (10,000 replicates; for the Shapley contrast of H7, a bootstrap over the ten seasonal values, decided by the lower confidence limit alone, without a *p*-value, shown as —); *p*-values from the paired Wilcoxon signed-rank test, Holm-corrected within the families of Section 2.9. Chain: tuned or untuned gate coefficients and the phys or IoT execution chain. H5 reproduces H1 with the opposite sign and is reported as descriptive (Section 2.9). H6 is not testable, because no step without sufficient head occurred at the small regulators. Because daily differences are serially dependent, the daily Wilcoxon *p*-values are indicative only; values below 0.001 are shown as < 0.001. The last column repeats each test with the ten seasons as the units of inference: the exact two-sided sign-flip test of the ten seasonal mean differences (1024 sign patterns, Holm-corrected within the same families; smallest attainable two-sided value 0.002), with the decision recomputed from the season bootstrap interval, this *p*-value, and the sign condition; a decision is shown only where it differs.

In the tolerance checks of H3, the pre-specified protocol evaluates *Z*~2~ as the mean satisfaction of the six users (*Z*~2~/6) and applies the margin *ε*~λ~ = 0.01 to both *λ* and *Z*~2~. An exploratory check with *Z*~2~ as the sum of satisfactions and the solver tolerances *ε*~1~ = 10^−6^ for *λ* and *ε*~2~ = 10^−4^ for *Z*~2~ gave: *λ*: −4.1 × 10^−7^ [−4.7 × 10^−7^, −3.6 × 10^−7^], non-inferior; *Z*~2~: −2.1 × 10^−6^ [−2.5 × 10^−6^, −1.9 × 10^−6^], non-inferior.

<!-- widths: 5,16,12,9,21,9,6,11,11 -->

**Table S6.** All hypothesis tests of the main runs.

| Hyp. | Comparison | Chain | Role | Estimate [95% CI] | p (Holm) | Sign | Decision | Seasons as units: p (Holm) |
|---|---|---|---|---|---|---|---|---|
| H1 | LXB − B0 | tuned/phys | primary | +0.015 [+0.013, +0.018] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B1 | tuned/phys | primary | +0.192 [+0.174, +0.212] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B2 | tuned/phys | primary | +0.024 [+0.019, +0.029] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B3 | tuned/phys | primary | −2.1 × 10^−5^ [−4.8 × 10^−5^, −5.8 × 10^−7^] | < 0.001 | 4/10 | Non-inferior | 0.135 |
| H5 | gap~LXB~ − gap~B0~ | tuned/phys | descriptive | −0.015 [−0.018, −0.013] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B1~ | tuned/phys | descriptive | −0.192 [−0.212, −0.174] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B2~ | tuned/phys | descriptive | −0.024 [−0.029, −0.019] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B3~ | tuned/phys | descriptive | +2.1 × 10^−5^ [+5.8 × 10^−7^, +4.8 × 10^−5^] | < 0.001 | 4/10 | Descriptive | 0.135 (inconclusive) |
| H6 | LXB − B0 | tuned/phys | primary | +0.000 | — | — | Not testable | — |
| H6 | LXB − B3 | tuned/phys | primary | +0.000 | — | — | Not testable | — |
| H1 | LXB − B0 | tuned/IoT | primary | +0.322 [+0.281, +0.383] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B1 | tuned/IoT | primary | +0.486 [+0.452, +0.552] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B2 | tuned/IoT | primary | +0.024 [+0.019, +0.029] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B3 | tuned/IoT | primary | +0.492 [+0.460, +0.560] | < 0.001 | 10/10 | Superior | 0.008 |
| H5 | gap~LXB~ − gap~B0~ | tuned/IoT | descriptive | −0.322 [−0.383, −0.281] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B1~ | tuned/IoT | descriptive | −0.486 [−0.552, −0.452] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B2~ | tuned/IoT | descriptive | −0.024 [−0.029, −0.019] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B3~ | tuned/IoT | descriptive | −0.492 [−0.560, −0.460] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H6 | LXB − B0 | tuned/IoT | primary | +0.000 | — | — | Not testable | — |
| H6 | LXB − B3 | tuned/IoT | primary | +0.000 | — | — | Not testable | — |
| H1 | LXB − B0 | untuned/phys | primary | +0.022 [+0.018, +0.026] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B1 | untuned/phys | primary | +0.115 [+0.096, +0.133] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B2 | untuned/phys | primary | +0.029 [+0.024, +0.035] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B3 | untuned/phys | primary | +0.149 [+0.120, +0.175] | < 0.001 | 10/10 | Superior | 0.008 |
| H5 | gap~LXB~ − gap~B0~ | untuned/phys | descriptive | −0.022 [−0.026, −0.018] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B1~ | untuned/phys | descriptive | −0.115 [−0.133, −0.096] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B2~ | untuned/phys | descriptive | −0.029 [−0.035, −0.024] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B3~ | untuned/phys | descriptive | −0.149 [−0.175, −0.120] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H6 | LXB − B0 | untuned/phys | primary | +0.000 | — | — | Not testable | — |
| H6 | LXB − B3 | untuned/phys | primary | +0.000 | — | — | Not testable | — |
| H1 | LXB − B0 | untuned/IoT | primary | +0.281 [+0.243, +0.341] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B1 | untuned/IoT | primary | +0.393 [+0.350, +0.459] | < 0.001 | 10/10 | Superior | 0.008 |
| H1 | LXB − B2 | untuned/IoT | primary | +0.012 [+0.008, +0.019] | < 0.001 | 7/10 | Superior | 0.084 (non-inferior) |
| H1 | LXB − B3 | untuned/IoT | primary | +0.218 [+0.182, +0.264] | < 0.001 | 10/10 | Superior | 0.008 |
| H5 | gap~LXB~ − gap~B0~ | untuned/IoT | descriptive | −0.281 [−0.341, −0.243] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B1~ | untuned/IoT | descriptive | −0.393 [−0.459, −0.350] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H5 | gap~LXB~ − gap~B2~ | untuned/IoT | descriptive | −0.012 [−0.019, −0.008] | < 0.001 | 7/10 | Descriptive | 0.084 (inconclusive) |
| H5 | gap~LXB~ − gap~B3~ | untuned/IoT | descriptive | −0.218 [−0.264, −0.182] | < 0.001 | 10/10 | Descriptive | 0.008 |
| H6 | LXB − B0 | untuned/IoT | primary | +0.000 | — | — | Not testable | — |
| H6 | LXB − B3 | untuned/IoT | primary | +0.000 | — | — | Not testable | — |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → untuned/IoT | primary | −0.201 [−0.261, −0.161] | < 0.001 | 10/10 | Supported | 0.002 |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → untuned/phys | secondary | +0.078 [+0.070, +0.088] | < 0.001 | 0/10 | Rejected | 0.002 |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → tuned/IoT | secondary | −0.294 [−0.357, −0.261] | < 0.001 | 10/10 | Supported | 0.002 |
| H3 | *Z*~3~: LXB − LXB-noS3 | tuned/phys | primary | +9.8 × 10^−8^ [−1.7 × 10^−7^, +4.1 × 10^−7^] | < 0.001 | 5/10 | Inconclusive | 0.754 |
| H3 | *λ*: LXB − LXB-noS3 | tuned/phys | tolerance | −4.1 × 10^−7^ [−4.7 × 10^−7^, −3.6 × 10^−7^] | < 0.001 | 0/10 | Non-inferior | 0.002 |
| H3 | *Z*~2~/6: LXB − LXB-noS3 | tuned/phys | tolerance | −3.6 × 10^−7^ [−4.2 × 10^−7^, −3.2 × 10^−7^] | < 0.001 | 0/10 | Non-inferior | 0.002 |
| H4 | Π~1~ (LXB) − 0 | tuned phys → IoT | primary | +0.047 [+0.011, +0.048] | < 0.001 | 10/10 | Supported | 0.002 |
| H4 | Π~1~ (LXB) − 0 | untuned phys → IoT | secondary | +0.095 [+0.049, +0.098] | < 0.001 | 10/10 | Supported | 0.002 |
| H7a | Π~1,LXB~ − Π~1,B1~ (IoT-open) | tuned phys → IoT | primary | −0.551 [−0.628, −0.489] | < 0.001 | 10/10 | Supported | 0.002 |
| H7b | *φ*~Q~ + *φ*~C~ − *φ*~S~ | tuned | primary | +0.047 [+0.033, +0.058] | — | 10/10 | Supported | — |
