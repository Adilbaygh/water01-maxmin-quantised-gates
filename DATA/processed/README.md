# Processed operating records of the Kegeyli irrigation system

The files below were transcribed by the authors from the daily operating records and the 2021 vegetation plan of the
Kegeyli irrigation system (Republic of Karakalpakstan, Uzbekistan). Discharges are in m³ s⁻¹, levels in cm at the
gauge, dates in ISO format. Empty cells are blank entries of the records. Place names are kept as written in the
records. Licence: CC BY 4.0 (`LICENSE-DATA.md`).

| File | Content |
|---|---|
| `rashod_2010_2019_daily.csv` | Daily records 2010–2019: level and discharge at the head of the Dustlik canal (`dostlik_H_cm`, `dostlik_Q`), at the Kegeyli head regulator (`kegeyli_H_cm`, `kegeyli_Q`; the supply S(t) of the model) and at the Kuanyshjarma head (`kj_H_cm`, `kj_Q`), and the discharge of the Kokozek off-take (`kok_ozek_Q`) |
| `demand_decadal.csv` | Decadal demand at the Dustlik node for the demand variants A (baseline: observed Abad-Yarmish share, the rest by irrigated area), B (all outlets by irrigated area) and C (all outlets by capacity): user index `j`, user name, share, demand volume (`D_mln_m3`, 10⁶ m³) and mean discharge (`q_mean_m3s`) |
| `plan_2021_kegeyli_decadal.csv` | Decadal plan of the Kegeyli system for the 2021 vegetation season (rows "total", "irrigation" and "other uses" of the plan): mean discharge of each decade (`plan_Q_m3s` = `irrigation_Q_m3s` + `other_Q_m3s`), the planning reference of the demand |
| `dispatcher_2020_kegeyli.csv` | Morning dispatcher sheets of 2020 (January–August): Dustlik and Kegeyli heads as above, the Abad-Yarmish regulator (`abad_yarmysh_Q`), the Kokshiel off-take (`kokshiel_Q`), the gauge immediately upstream of the Dustlik node (`pg_dustlik_Q`), the gauge below the node (`below_dostlik_Q`) and the Kokozek off-take; source of the delivery factor η and of the monthly share of the Abad-Yarmish regulator |
| `annual_volumes_2010_2019.csv` | Officially reported annual volumes, 10⁶ m³, at the heads of the Dustlik and Kegeyli canals, at the Kuanyshjarma head and at the Kokozek off-take; used only to check the transcription of the daily records |

The simulations read `rashod_2010_2019_daily.csv` and `demand_decadal.csv`; their SHA-256 checksums are stored in the
`.meta.json` file of every result. `python scripts/derive_inputs.py` recomputes, from the other three files, the
delivery factor η (median ratio of the node inflow to the head discharge on steady days of 2020), the monthly share of
the Abad-Yarmish regulator, the balance of the node, the agreement of the daily records with the annual volumes and the
checks of the daily records, and writes them to `results/inputs/derived_inputs.json`;
`python scripts/derive_inputs.py --write-demand` rewrites `demand_decadal.csv`, which is reproduced bit for bit:
D_j = η Q_plan,d s_j,m Δ_d, with Q_plan,d the planned discharge of decade d, s_j,m the share of outlet j in month m
and Δ_d the length of the decade.
