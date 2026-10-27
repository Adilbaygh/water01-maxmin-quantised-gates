"""§2.6, (14)–(15): quantisation, deadband, message budget, fail-safe; §2.4: delay."""
from water01.iot.communication import LinkState, transmit
from water01.iot.devices import quantize
from water01.optimization.constraints import delay_steps


def test_deadband_holds_small_moves():
    assert quantize(0.502, 0.001, previous=0.500, deadband=0.005) == 0.500
    assert quantize(0.520, 0.001, previous=0.500, deadband=0.005) == 0.52


def test_quantize_is_bounded():
    assert quantize(1.3, 0.01) == 1.0 and quantize(-0.2, 0.01) == 0.0


def test_message_budget_resets_each_window():
    s = LinkState(window_steps=4, budget=2)
    out = [transmit(s, k) for k in range(8)]
    assert out == [True, True, False, False, True, True, False, False]
    assert s.sent_total == 4 and s.dropped == 4


def test_lost_packet_is_counted_and_not_received():
    s = LinkState(window_steps=4, budget=4)
    assert transmit(s, 0) and not transmit(s, 1, delivered=False)
    assert s.sent_total == 2 and s.dropped == 1


def test_delay_ceiling():
    assert delay_steps(1800.5, 900) == 3 and delay_steps(1800, 900) == 2


def test_change_of_exactly_the_deadband_is_executed_at_every_position():
    res, db = 0.001, 0.005
    for n in range(0, 990):
        prev = n * res
        assert quantize(prev + db, res, previous=prev, deadband=db) != prev
        if n >= 5:
            assert quantize(prev + db - res, res, previous=prev, deadband=db) == prev


def test_command_that_rounds_to_closed_is_a_full_closure():
    assert quantize(1e-12, 0.001, previous=0.003, deadband=0.005) == 0.0
