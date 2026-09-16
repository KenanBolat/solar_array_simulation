"""Scenario graph validation.

Enforces the safety rules from the spec:
  * exactly one Start and at least one End
  * no unbounded loops (every cycle must pass through a Repeat node with a
    finite max_iterations)
  * Repeat max_iterations and retry counts are bounded
  * only known node types / known command templates
  * no dangling nodes (everything reachable from Start; non-terminal nodes
    must have an outgoing edge)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.drivers.templates import TEMPLATES_BY_ID

NODE_TYPES = {
    "start", "end", "set_output_state", "configure_parameters", "apply_profile",
    "wait", "read_measurement", "record_measurement", "condition", "threshold_check",
    "branch", "repeat", "send_command", "safe_shutdown", "notification", "comment",
}
MAX_REPEAT_ITERATIONS = 10_000
MAX_RETRIES = 10


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_scenario(nodes: list[dict], edges: list[dict]) -> ValidationResult:
    res = ValidationResult(valid=True)
    if not nodes:
        res.errors.append("scenario has no nodes")
        res.valid = False
        return res

    by_key = {n["node_key"]: n for n in nodes}
    out_edges: dict[str, list[str]] = {k: [] for k in by_key}
    in_edges: dict[str, list[str]] = {k: [] for k in by_key}
    for e in edges:
        if e["source"] not in by_key or e["target"] not in by_key:
            res.errors.append(f"edge references unknown node: {e}")
            continue
        out_edges[e["source"]].append(e["target"])
        in_edges[e["target"]].append(e["source"])

    # node-type + command validity
    starts = [n for n in nodes if n["type"] == "start"]
    ends = [n for n in nodes if n["type"] == "end"]
    if len(starts) != 1:
        res.errors.append(f"expected exactly 1 Start node, found {len(starts)}")
    if not ends:
        res.errors.append("scenario needs at least one End node")

    for n in nodes:
        if n["type"] not in NODE_TYPES:
            res.errors.append(f"unknown node type '{n['type']}' ({n['node_key']})")
        if n["type"] == "send_command":
            tid = (n.get("config") or {}).get("template_id")
            if tid not in TEMPLATES_BY_ID:
                res.errors.append(f"send_command references unknown template '{tid}'")
        if n["type"] == "repeat":
            it = (n.get("config") or {}).get("max_iterations")
            if not isinstance(it, int) or it <= 0:
                res.errors.append(f"Repeat node {n['node_key']} needs positive max_iterations")
            elif it > MAX_REPEAT_ITERATIONS:
                res.errors.append(
                    f"Repeat node {n['node_key']} max_iterations {it} exceeds bound {MAX_REPEAT_ITERATIONS}")
        retries = (n.get("config") or {}).get("retries")
        if retries is not None and (not isinstance(retries, int) or retries > MAX_RETRIES):
            res.errors.append(f"node {n['node_key']} retries exceeds bound {MAX_RETRIES}")

    # dangling: non-terminal nodes must have an outgoing edge
    for n in nodes:
        if n["type"] not in ("end", "comment") and not out_edges.get(n["node_key"]):
            res.warnings.append(f"node {n['node_key']} ({n['type']}) has no outgoing edge")

    # reachability from start
    if len(starts) == 1:
        reachable: set[str] = set()
        stack = [starts[0]["node_key"]]
        while stack:
            cur = stack.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            stack.extend(out_edges.get(cur, []))
        for n in nodes:
            if n["type"] != "comment" and n["node_key"] not in reachable:
                res.warnings.append(f"node {n['node_key']} is unreachable from Start")

    # cycle safety: any cycle must include a repeat node
    if _has_unbounded_cycle(by_key, out_edges):
        res.errors.append("unbounded loop detected (cycle without a Repeat node)")

    res.valid = not res.errors
    return res


def _has_unbounded_cycle(by_key, out_edges) -> bool:
    color: dict[str, int] = {}  # 0=white,1=gray,2=black

    def dfs(u: str) -> bool:
        color[u] = 1
        for v in out_edges.get(u, []):
            if by_key[v]["type"] == "repeat":
                # a repeat node legitimately bounds the loop -> treat as safe edge
                continue
            if color.get(v, 0) == 1:
                return True
            if color.get(v, 0) == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    return any(dfs(k) for k in by_key if color.get(k, 0) == 0)
