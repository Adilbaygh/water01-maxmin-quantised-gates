"""Tabs of the main window, in the order shown."""
from .analysis import AnalysisTab
from .data import DataTab
from .figures import FiguresTab
from .overview import OverviewTab
from .paper import PaperTab
from .results import ResultsTab
from .simulation import SimulationTab
from .theory import TheoryTab

TABS = (
    ("overview", "Overview", OverviewTab),
    ("data", "Data", DataTab),
    ("theory", "Gate and rules", TheoryTab),
    ("simulation", "Simulation", SimulationTab),
    ("results", "Results", ResultsTab),
    ("analysis", "Analysis", AnalysisTab),
    ("figures", "Figures", FiguresTab),
    ("paper", "Article", PaperTab),
)
