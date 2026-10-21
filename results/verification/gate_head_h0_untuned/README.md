# Gate relation smoothed over 0.1 mm: untuned B3 and B3V

Check of the gate relation near zero head for the two controllers that draw the pool down with untuned gate
coefficients (Section 3.4 of the article). Command:

    python scripts/run_experiment.py --scenario gate_head_h0 --methods B3,B3V --tuned untuned --iot phys,iot

The runs that completed are stored here with their metadata; `run_log.txt` lists the completed runs and the runs in
which Newton's method did not converge even with 64 hydraulic steps per control step. The comparison references are
results/experiment/normal (B3) and results/exploratory/b3_feedback (B3V).
