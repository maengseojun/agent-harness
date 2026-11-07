"""Route and role resolver: policy/roles.json -> the candidate to launch (MAE-323 bundle 2, S2).

Stdlib only and no maeng imports: the Decisions scripts in maeng-tools load this file by path. There is no default
pair here; a missing row, resource or model raises RoutingError and the caller starts nothing."""
import json
from pathlib import Path

FAMILIES = {"codex": "gpt-", "claude": "claude-"}  # a family name matches every model id with the prefix
PLANNER_ROLES = ("plan", "parent")  # reviews that also skip the planner's model


class RoutingError(ValueError):
    pass


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RoutingError(f"cannot read roles and routes from {path}: {exc}") from exc
    for key in ("roles", "routes", "resources"):
        if not isinstance(data, dict) or not isinstance(data.get(key), dict):
            raise RoutingError(f"invalid {path}: {key} must be an object")
    return data


def candidates(data, name):
    """-> [{model, effort, resource, row}] of roles.<name> or routes.<name>: the row itself, then its standby in order.
    A standby entry without a model (an agent) is not a model candidate."""
    section = next((s for s in ("roles", "routes") if isinstance(data[s].get(name), dict)), None)
    if section is None:
        raise RoutingError(f"no roles.{name} or routes.{name} row in the routing table")
    row, where, out = data[section][name], f"{section}.{name}", []
    for pair in [row, *(row.get("standby") or [])]:
        if not isinstance(pair, dict) or not pair.get("model"):
            if pair is row:
                raise RoutingError(f"{where} names no model; resolve one of its roles instead")
            continue
        resource = pair.get("resource")
        if pair["model"] not in (data["resources"].get(resource) or {}).get("models", []):
            raise RoutingError(f"{where}: {pair['model']} is not a model of resource {resource!r}")
        out.append({"model": pair["model"], "effort": pair.get("effort"), "resource": resource, "row": where})
    return out


def _match(model, identity):
    """How a candidate is the same as an identity: "model" (both exact ids), "family" (a family name), or None."""
    if identity in FAMILIES:
        return "family" if model.startswith(FAMILIES[identity]) else None
    dated = identity.startswith(model + "-") and identity[len(model) + 1:].isdigit()  # claude-opus-5-5-20261101
    return "model" if model == identity or dated else None


def resolve(data, name, *, route=None, author=None, planner=None, only=None, unavailable=None):
    """-> the first candidate no rule skips: {model, effort, resource, row, route, skipped}. `model` is None (blocked)
    when every candidate is skipped. Rules: candidates in table order; skip the actual author's model; for plan and
    parent also the planner's; advance only on those or on `unavailable` ({model: reason}). `only` ("codex" or
    "claude") is the user's own pin (MAENG_REVIEW_BACKEND=claude). Identities are exact model ids or a family name."""
    if route is not None and not isinstance(data["routes"].get(route), dict):
        raise RoutingError(f"no routes.{route} row in the routing table")
    if name in PLANNER_ROLES and not planner:
        raise RoutingError(f"roles.{name} skips the planner's model, so the planner's model must be given "
                           f"(maeng-review: --planner-model <model id>)")
    if only is not None and only not in FAMILIES:
        raise RoutingError(f"unknown backend family {only!r}")
    skipped, cands = [], candidates(data, name)
    who = (("author", author),) + ((("planner", planner),) if name in PLANNER_ROLES else ())
    for c in cands:
        hit = next(((role, m, ident) for role, ident in who if ident and (m := _match(c["model"], ident))), None)
        if only and not c["model"].startswith(FAMILIES[only]):
            why = {"reason": f"pinned to the {only} backend"}
        elif hit:
            why = {"reason": f"same {hit[1]} as the {hit[0]} ({hit[2]})", "match": hit[1]}
        elif c["model"] in (unavailable or {}):
            why = {"reason": f"unavailable: {unavailable[c['model']]}"}
        else:
            return {**c, "route": f"routes.{route}" if route else None, "skipped": skipped}
        skipped.append({"model": c["model"], "effort": c["effort"], "resource": c["resource"], **why})
    return {"model": None, "effort": None, "resource": None, "row": cands[0]["row"],
            "route": f"routes.{route}" if route else None, "skipped": skipped}
