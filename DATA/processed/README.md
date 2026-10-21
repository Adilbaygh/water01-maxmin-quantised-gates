# Processed operating records of the Kegeyli irrigation system

The files below were transcribed by the authors from the daily operating records of the Kegeyli irrigation system
(Republic of Karakalpakstan, Uzbekistan) and are the inputs of every reported run; their SHA-256 checksums are stored in
the `.meta.json` file of every result. Discharges are in m³ s⁻¹, levels in cm at the gauge, dates in ISO format. Empty
cells are blank entries of the records (Section 2.1 of the article). Place names are kept as written in the records.
Licence: CC BY 4.0 (`LICENSE-DATA.md`).

| File | Content |
|---|---|
| `rashod_2010_2019_daily.csv` | Daily records 2010–2019: level and discharge at the head of the Dustlik canal (`dostlik_H_cm`, `dostlik_Q`), at the Kegeyli head regulator (`kegeyli_H_cm`, `kegeyli_Q`; the supply S(t) of the model) and at the Kuanyshjarma head (`kj_H_cm`, `kj_Q`), and the discharge of the Kokozek off-take (`kok_ozek_Q`) |
| `dispatcher_2020_kegeyli.csv` | Morning dispatcher sheets of 2020 (January–August): Dustlik and Kegeyli heads as above, the Abad-Yarmish regulator (`abad_yarmysh_Q`), the Kokshiel off-take (`kokshiel_Q`), the gauge immediately upstream of the Dustlik node (`pg_dustlik_Q`), the gauge below the node (`below_dostlik_Q`) and the Kokozek off-take; used for the delivery factor and the node balance |
| `limit_2021_kegeyli_decadal.csv` | Official decadal limit of the Kegeyli canal for the 2021 vegetation season (`limit_Q_m3s`, `limit_W_mln_m3`); sensitivity case `limit_2021` |
| `demand_decadal.csv` | Decadal demand at the Dustlik node derived from the 2021 vegetation plan by Equation (1) of the article, for the demand variants A (baseline), B, and C: user index `j`, user name, share, demand volume (`D_mln_m3`, 10⁶ m³) and mean discharge (`q_mean_m3s`) |
