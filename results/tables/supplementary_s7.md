## S7. Results of All Hypothesis Tests

Decisions follow the pre-specified rules (Section 2.9): superiority (or a supported decrease) requires the 95% confidence interval to exclude zero on the predicted side, a Holm-adjusted *p*-value below 0.05, and the expected sign in at least 7 of 10 seasons; non-inferiority requires only a lower limit above −*ε*~λ~ (*ε*~λ~ = 0.01). An interval that excludes zero on the predicted side without the *p*-value or sign condition is reported as inconclusive. Confidence intervals come from a moving-block bootstrap with 10-day blocks within seasons (10,000 replicates; for the Shapley contrast of H7, a bootstrap over the ten seasonal values, decided by the lower confidence limit alone, without a *p*-value, shown as —); *p*-values from the paired Wilcoxon signed-rank test, Holm-corrected within the families of Section 2.9. Chain: tuned or untuned gate coefficients and the phys or IoT execution chain. H5 reproduces H1 with the opposite sign and is reported as descriptive (Section 2.9). H6 is not testable, because no step without sufficient head occurred at the small regulators. Because daily differences are serially dependent, the Wilcoxon *p*-values are indicative only; values below 0.001 are shown as < 0.001, and the decisions rest on the bootstrap intervals and the sign stability.

In the tolerance checks of H3, the pre-specified protocol evaluates *Z*~2~ as the mean satisfaction of the six users (*Z*~2~/6) and applies the margin *ε*~λ~ = 0.01 to both *λ* and *Z*~2~. An exploratory check with *Z*~2~ as the sum of satisfactions and the solver tolerances *ε*~1~ = 10^−6^ for *λ* and *ε*~2~ = 10^−4^ for *Z*~2~ gave: *λ*: −5.5 × 10^−7^ [−6.2 × 10^−7^, −5.1 × 10^−7^], non-inferior; *Z*~2~: −2.8 × 10^−6^ [−3.2 × 10^−6^, −2.6 × 10^−6^], non-inferior.

<!-- widths: 6,18,14,11,23,12,7,13 -->

**Table S6.** All hypothesis tests of the main runs.

| Hyp. | Comparison | Chain | Role | Estimate [95% CI] | p (Holm) | Sign | Decision |
|---|---|---|---|---|---|---|---|
| H1 | LXB − B0 | tuned/phys | primary | +0.015 [+0.012, +0.018] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B1 | tuned/phys | primary | +0.193 [+0.174, +0.212] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B2 | tuned/phys | primary | +0.024 [+0.019, +0.029] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B3 | tuned/phys | primary | +6.1 × 10^−6^ [−3.1 × 10^−5^, +4.2 × 10^−5^] | < 0.001 | 6/10 | Non-inferior |
| H5 | gap~LXB~ − gap~B0~ | tuned/phys | descriptive | −0.015 [−0.018, −0.012] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B1~ | tuned/phys | descriptive | −0.193 [−0.212, −0.174] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B2~ | tuned/phys | descriptive | −0.024 [−0.029, −0.019] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B3~ | tuned/phys | descriptive | −6.1 × 10^−6^ [−4.2 × 10^−5^, +3.1 × 10^−5^] | < 0.001 | 6/10 | Descriptive |
| H6 | LXB − B0 | tuned/phys | primary | +0.000 | — | — | Not testable |
| H6 | LXB − B3 | tuned/phys | primary | +0.000 | — | — | Not testable |
| H1 | LXB − B0 | tuned/IoT | primary | +0.319 [+0.278, +0.380] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B1 | tuned/IoT | primary | +0.482 [+0.448, +0.548] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B2 | tuned/IoT | primary | +0.021 [+0.017, +0.026] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B3 | tuned/IoT | primary | +0.489 [+0.456, +0.557] | < 0.001 | 10/10 | Superior |
| H5 | gap~LXB~ − gap~B0~ | tuned/IoT | descriptive | −0.319 [−0.380, −0.278] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B1~ | tuned/IoT | descriptive | −0.482 [−0.548, −0.448] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B2~ | tuned/IoT | descriptive | −0.021 [−0.026, −0.017] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B3~ | tuned/IoT | descriptive | −0.489 [−0.557, −0.456] | < 0.001 | 10/10 | Descriptive |
| H6 | LXB − B0 | tuned/IoT | primary | +0.000 | — | — | Not testable |
| H6 | LXB − B3 | tuned/IoT | primary | +0.000 | — | — | Not testable |
| H1 | LXB − B0 | untuned/phys | primary | +0.022 [+0.018, +0.026] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B1 | untuned/phys | primary | +0.115 [+0.096, +0.133] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B2 | untuned/phys | primary | +0.029 [+0.024, +0.035] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B3 | untuned/phys | primary | +0.149 [+0.119, +0.175] | < 0.001 | 10/10 | Superior |
| H5 | gap~LXB~ − gap~B0~ | untuned/phys | descriptive | −0.022 [−0.026, −0.018] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B1~ | untuned/phys | descriptive | −0.115 [−0.133, −0.096] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B2~ | untuned/phys | descriptive | −0.029 [−0.035, −0.024] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B3~ | untuned/phys | descriptive | −0.149 [−0.175, −0.119] | < 0.001 | 10/10 | Descriptive |
| H6 | LXB − B0 | untuned/phys | primary | +0.000 | — | — | Not testable |
| H6 | LXB − B3 | untuned/phys | primary | +0.000 | — | — | Not testable |
| H1 | LXB − B0 | untuned/IoT | primary | +0.280 [+0.242, +0.341] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B1 | untuned/IoT | primary | +0.392 [+0.349, +0.458] | < 0.001 | 10/10 | Superior |
| H1 | LXB − B2 | untuned/IoT | primary | +0.012 [+0.008, +0.018] | < 0.001 | 7/10 | Superior |
| H1 | LXB − B3 | untuned/IoT | primary | +0.217 [+0.181, +0.263] | < 0.001 | 10/10 | Superior |
| H5 | gap~LXB~ − gap~B0~ | untuned/IoT | descriptive | −0.280 [−0.341, −0.242] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B1~ | untuned/IoT | descriptive | −0.392 [−0.458, −0.349] | < 0.001 | 10/10 | Descriptive |
| H5 | gap~LXB~ − gap~B2~ | untuned/IoT | descriptive | −0.012 [−0.018, −0.008] | < 0.001 | 7/10 | Descriptive |
| H5 | gap~LXB~ − gap~B3~ | untuned/IoT | descriptive | −0.217 [−0.263, −0.181] | < 0.001 | 10/10 | Descriptive |
| H6 | LXB − B0 | untuned/IoT | primary | +0.000 | — | — | Not testable |
| H6 | LXB − B3 | untuned/IoT | primary | +0.000 | — | — | Not testable |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → untuned/IoT | primary | −0.199 [−0.260, −0.160] | < 0.001 | 10/10 | Supported |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → untuned/phys | secondary | +0.078 [+0.070, +0.089] | < 0.001 | 0/10 | Rejected |
| H2 | Δ*λ*~LXB~ − Δ*λ*~B1~ | tuned/phys → tuned/IoT | secondary | −0.289 [−0.352, −0.257] | < 0.001 | 10/10 | Supported |
| H3 | *Z*~3~: LXB − LXB-noS3 | tuned/phys | primary | −4.8 × 10^−8^ [−1.9 × 10^−7^, +1.9 × 10^−7^] | < 0.001 | 8/10 | Inconclusive |
| H3 | *λ*: LXB − LXB-noS3 | tuned/phys | tolerance | −5.5 × 10^−7^ [−6.2 × 10^−7^, −5.1 × 10^−7^] | < 0.001 | 0/10 | Non-inferior |
| H3 | *Z*~2~/6: LXB − LXB-noS3 | tuned/phys | tolerance | −4.6 × 10^−7^ [−5.3 × 10^−7^, −4.3 × 10^−7^] | < 0.001 | 0/10 | Non-inferior |
| H4 | Π~1~ (LXB) − 0 | tuned phys → IoT | primary | +0.060 [+0.021, +0.059] | < 0.001 | 10/10 | Supported |
| H4 | Π~1~ (LXB) − 0 | untuned phys → IoT | secondary | +0.097 [+0.050, +0.099] | < 0.001 | 10/10 | Supported |
| H7a | Π~1,LXB~ − Π~1,B1~ (IoT-open) | tuned phys → IoT | primary | −0.544 [−0.622, −0.484] | < 0.001 | 10/10 | Supported |
| H7b | *φ*~Q~ + *φ*~C~ − *φ*~S~ | tuned | primary | +0.079 [+0.044, +0.131] | — | 10/10 | Supported |
