"""Quantised max-min delivery at a canal node (article, Sections 2-3).

allocation -- continuous level lambda*, minimum-delivery level lambda_q, price of indivisibility and whole-step level
              lambda_v (Theorem 2);
execution  -- an abstract quantised actuator and the execution rules of Theorems 1, 3 and 4 (direct execution, equal
              split, theta pulse rule, carry-over), used to check the theorems on random instances.
The package depends only on NumPy and SciPy; the closed-loop simulation core is the package water01.
"""
__version__ = "1.2.0"
