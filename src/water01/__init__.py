"""Water-01: three-stage lexicographic water allocation executed via IoT for the Kegeyli canal
(PK 0+00 to 114+40) and the Dustlik hydraulic node (MDPI Water, simulation study).

Package structure (layers from bottom to top; each layer imports only the layers below it):
    domain        -- passport parameters, cross-section geometry, state objects;
    hydraulics    -- Saint-Venant equations, Preissmann solver, Dustlik node and gates;
    optimization  -- lexicographic LP, its constraints and objective functions, ID model;
    iot           -- devices and actuation (quantisation), telemetry, communication, energy;
    control       -- B0-B3, LXB and Oracle controllers;
    simulation    -- scenarios and data, plant loop, runner;
    evaluation    -- metrics and IoT price, statistics, hypothesis decisions.
"""
__version__ = "1.4.0"
