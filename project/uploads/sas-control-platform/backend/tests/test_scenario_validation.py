"""Unit tests for scenario validation -- pure, no database required."""
from __future__ import annotations

from app.services.scenario_validation import validate_scenario


def _n(key: str, ntype: str, **config) -> dict:
    return {"node_key": key, "type": ntype, "label": key, "config": config}


def _e(src: str, dst: str) -> dict:
    return {"source": src, "target": dst}


def test_minimal_valid_scenario():
    nodes = [_n("s", "start"), _n("e", "end")]
    edges = [_e("s", "e")]
    res = validate_scenario(nodes, edges)
    assert res.valid, res.errors


def test_full_example_scenario_is_valid():
    nodes = [
        _n("s", "start"),
        _n("cfg", "apply_profile", profile="Standard Panel A"),
        _n("on", "set_output_state", enabled=True),
        _n("w", "wait", seconds=3),
        _n("rec", "record_measurement"),
        _n("thr", "threshold_check", field="power_w", op=">=", value=10.0),
        _n("off", "set_output_state", enabled=False),
        _n("e", "end"),
    ]
    edges = [_e("s", "cfg"), _e("cfg", "on"), _e("on", "w"), _e("w", "rec"),
             _e("rec", "thr"), _e("thr", "off"), _e("off", "e")]
    res = validate_scenario(nodes, edges)
    assert res.valid, res.errors


def test_rejects_multiple_starts():
    nodes = [_n("s1", "start"), _n("s2", "start"), _n("e", "end")]
    edges = [_e("s1", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("Start" in e for e in res.errors)


def test_rejects_missing_end():
    nodes = [_n("s", "start"), _n("w", "wait", seconds=1)]
    edges = [_e("s", "w")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("End" in e for e in res.errors)


def test_rejects_unknown_node_type():
    nodes = [_n("s", "start"), _n("x", "frobnicate"), _n("e", "end")]
    edges = [_e("s", "x"), _e("x", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("unknown node type" in e for e in res.errors)


def test_rejects_unknown_command_template():
    nodes = [_n("s", "start"), _n("c", "send_command", template_id="does_not_exist"),
             _n("e", "end")]
    edges = [_e("s", "c"), _e("c", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("unknown template" in e for e in res.errors)


def test_detects_unbounded_cycle():
    nodes = [_n("s", "start"), _n("a", "wait", seconds=1),
             _n("b", "wait", seconds=1), _n("e", "end")]
    edges = [_e("s", "a"), _e("a", "b"), _e("b", "a"), _e("s", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("unbounded loop" in e for e in res.errors)


def test_repeat_node_bounds_the_loop():
    nodes = [_n("s", "start"), _n("r", "repeat", max_iterations=5),
             _n("a", "wait", seconds=1), _n("e", "end")]
    edges = [_e("s", "r"), _e("r", "a"), _e("a", "r"), _e("r", "e")]
    res = validate_scenario(nodes, edges)
    assert res.valid, res.errors


def test_repeat_requires_positive_iterations():
    nodes = [_n("s", "start"), _n("r", "repeat", max_iterations=0),
             _n("a", "wait", seconds=1), _n("e", "end")]
    edges = [_e("s", "r"), _e("r", "a"), _e("a", "r"), _e("r", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid


def test_repeat_iterations_bounded_by_ceiling():
    nodes = [_n("s", "start"), _n("r", "repeat", max_iterations=10_000_001),
             _n("a", "wait", seconds=1), _n("e", "end")]
    edges = [_e("s", "r"), _e("r", "a"), _e("a", "r"), _e("r", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid


def test_retries_bounded():
    nodes = [_n("s", "start"), _n("c", "send_command", template_id="read_measurements",
                                  retries=99), _n("e", "end")]
    edges = [_e("s", "c"), _e("c", "e")]
    res = validate_scenario(nodes, edges)
    assert not res.valid
    assert any("retries" in e for e in res.errors)


def test_empty_scenario_invalid():
    res = validate_scenario([], [])
    assert not res.valid
