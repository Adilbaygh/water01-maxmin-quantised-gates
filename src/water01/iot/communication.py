"""Section 2.6, Equation (15): LoRaWAN packet budget and packet loss.

One packet carries the openings of all gates. The number of packets per window does not exceed M_max; if a packet is
lost or the budget is exhausted, the RTU keeps its current gate positions. Latency, collisions and airtime are not
modelled.
"""
from dataclasses import dataclass

@dataclass
class LinkState:
    window_steps: int
    budget: int
    window_start: int = 0
    sent_in_window: int = 0
    sent_total: int = 0
    dropped: int = 0             # blocked + lost
    blocked: int = 0             # not sent: the budget of the window was exhausted
    lost: int = 0                # sent but lost on the channel


def transmit(state, step, delivered=True):
    """(15): one command packet (the openings of all gates) at control step `step`.

    Returns True if the RTU receives the packet. A packet beyond the budget of the current window is not sent;
    a sent packet is lost when `delivered` is False. In both cases the RTU keeps its current gate positions."""
    if step - state.window_start >= state.window_steps:
        state.window_start = step - (step - state.window_start) % state.window_steps
        state.sent_in_window = 0
    if state.sent_in_window >= state.budget:
        state.dropped += 1; state.blocked += 1
        return False
    state.sent_in_window += 1; state.sent_total += 1
    if not delivered:
        state.dropped += 1; state.lost += 1
        return False
    return True
