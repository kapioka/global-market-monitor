from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

STAGE_RANK = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
RANK_STAGE = {value: key for key, value in STAGE_RANK.items()}


def default_risk_domain_state_path(reports_dir: str | Path) -> Path:
    return Path(reports_dir) / "risk_engine_v2_state.json"


def load_risk_domain_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {"schema_version": "2.0", "domains": {}, "global": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "2.0", "domains": {}, "global": {}, "load_error": True}
    if not isinstance(payload, dict):
        return {"schema_version": "2.0", "domains": {}, "global": {}, "load_error": True}
    payload.setdefault("schema_version", "2.1")
    payload.setdefault("domains", {})
    payload.setdefault("global", {})
    return payload


def write_risk_domain_state(path: str | Path, state: dict[str, Any]) -> Path:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


def apply_risk_domain_persistence(
    risk_domains: dict[str, Any],
    *,
    previous_state: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = deepcopy(risk_domains)
    state = previous_state or {"schema_version": "2.0", "domains": {}, "global": {}}
    domains_state = state.get("domains", {}) if isinstance(state.get("domains"), dict) else {}
    persistence = (settings or {}).get("persistence", {}) if isinstance(settings, dict) else {}
    rules = _rules(persistence)
    observed_at = generated_at or datetime.now().isoformat(timespec="seconds")

    next_domains: dict[str, Any] = {}
    for domain in updated.get("domains", []):
        domain_id = str(domain.get("domain_id"))
        previous = domains_state.get(domain_id, {}) if isinstance(domains_state.get(domain_id), dict) else {}
        persisted, next_state = _apply_domain(domain, previous, rules, observed_at)
        domain.update(persisted)
        next_domains[domain_id] = next_state

    previous_global = state.get("global", {}) if isinstance(state.get("global"), dict) else {}
    updated["candidate_stage"] = str(updated.get("candidate_stage") or updated.get("stage") or "normal")
    global_persisted, next_global_state = _apply_global(updated["candidate_stage"], previous_global, rules, observed_at)
    updated.update(global_persisted)
    updated["stage"] = updated["confirmed_stage"]
    updated["persistence_policy"] = {
        "warning_entry_observations": rules["warning_entry_observations"],
        "warning_entry_window": rules["warning_entry_window"],
        "danger_entry_consecutive": rules["danger_entry_consecutive"],
        "exit_consecutive": rules["exit_consecutive"],
        "expected_cadence_days": rules["expected_cadence_days"],
        "max_gap_days": rules["max_gap_days"],
    }

    next_state = {
        "schema_version": "2.1",
        "updated_at": observed_at,
        "global": next_global_state,
        "domains": next_domains,
    }
    return updated, next_state


def _apply_global(
    candidate: str,
    previous: dict[str, Any],
    rules: dict[str, int],
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    persisted, next_state = _apply_stage(
        candidate=candidate,
        stage_eligible=True,
        previous=previous,
        rules=rules,
        observed_at=observed_at,
        scope="global",
    )
    return persisted, next_state


def _apply_domain(
    domain: dict[str, Any],
    previous: dict[str, Any],
    rules: dict[str, int],
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    stage_eligible = bool(domain.get("stage_eligible", False))
    persisted, next_state = _apply_stage(
        candidate=str(domain.get("candidate_stage") or domain.get("stage") or "normal"),
        stage_eligible=stage_eligible,
        previous=previous,
        rules=rules,
        observed_at=observed_at,
        scope=str(domain.get("domain_id") or "domain"),
    )
    return persisted, {**next_state, "stage_eligible": stage_eligible}


def _apply_stage(
    *,
    candidate: str,
    stage_eligible: bool,
    previous: dict[str, Any],
    rules: dict[str, int],
    observed_at: str,
    scope: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous_confirmed = str(previous.get("confirmed_stage") or "normal")
    previous_observations = _normalize_observations(previous.get("observations", []))
    max_history = max(
        rules["warning_entry_window"],
        rules["danger_entry_consecutive"],
        rules["exit_consecutive"],
    )
    observations = previous_observations[-max_history:]
    gap_days = _gap_days(observations[-1]["observed_at"] if observations else previous.get("updated_at"), observed_at)
    gap_reset = gap_days is not None and gap_days > rules["max_gap_days"]
    if gap_reset:
        observations = []
        previous_confirmed = "normal"

    if not stage_eligible:
        confirmed = previous_confirmed
        entry_rule = "not_evaluable_no_state_change"
        next_observations = observations
    else:
        next_observations = (observations + [{"stage": candidate, "observed_at": observed_at}])[-max_history:]
        confirmed, entry_rule = _confirmed_stage(candidate, previous_confirmed, next_observations, rules)

    previous_candidate = str(previous.get("candidate_stage") or "normal")
    previous_episode = str(previous.get("episode_id") or f"{scope}:0")
    episode_id = _next_episode_id(previous_episode, scope) if gap_reset or candidate != previous_candidate else previous_episode
    previous_confirmed_since = previous.get("confirmed_since") if confirmed == str(previous.get("confirmed_stage") or "normal") else None

    return (
        {
            "candidate_stage": candidate,
            "confirmed_stage": confirmed,
            "stage": confirmed,
            "previous_stage": str(previous.get("confirmed_stage") or "normal"),
            "previous_confirmed_stage": str(previous.get("confirmed_stage") or "normal"),
            "stage_changed": confirmed != str(previous.get("confirmed_stage") or "normal"),
            "persistence_count": _consecutive_count(next_observations, candidate),
            "entry_rule": entry_rule,
            "exit_rule": f"{rules['exit_consecutive']}_consecutive_lower_or_equal",
            "candidate_since": previous.get("candidate_since") if candidate == previous_candidate and not gap_reset else observed_at,
            "confirmed_since": previous_confirmed_since or observed_at,
            "consecutive_eligible_count": (
                _eligible_count(next_observations) if stage_eligible else int(previous.get("consecutive_eligible_count", 0) or 0)
            ),
            "episode_id": episode_id,
            "gap_reset": gap_reset,
            "gap_days": gap_days,
            "expected_cadence_days": rules["expected_cadence_days"],
            "max_gap_days": rules["max_gap_days"],
        },
        {
            "candidate_stage": candidate,
            "confirmed_stage": confirmed,
            "previous_confirmed_stage": str(previous.get("confirmed_stage") or "normal"),
            "observations": next_observations,
            "stage_eligible": stage_eligible,
            "updated_at": observed_at,
            "entry_rule": entry_rule,
            "candidate_since": previous.get("candidate_since") if candidate == previous_candidate and not gap_reset else observed_at,
            "confirmed_since": previous_confirmed_since or observed_at,
            "consecutive_eligible_count": (
                _eligible_count(next_observations) if stage_eligible else int(previous.get("consecutive_eligible_count", 0) or 0)
            ),
            "episode_id": episode_id,
            "gap_reset": gap_reset,
            "gap_days": gap_days,
            "expected_cadence_days": rules["expected_cadence_days"],
            "max_gap_days": rules["max_gap_days"],
        },
    )


def _confirmed_stage(candidate: str, previous: str, observations: list[dict[str, str]], rules: dict[str, int]) -> tuple[str, str]:
    candidate_rank = STAGE_RANK.get(candidate, 0)
    previous_rank = STAGE_RANK.get(previous, 0)
    if candidate_rank == previous_rank:
        return candidate, "same_stage_confirmed"
    if candidate_rank > previous_rank:
        if candidate_rank >= STAGE_RANK["danger"]:
            required = rules["danger_entry_consecutive"]
            if _consecutive_at_least(observations, candidate_rank) >= required:
                return candidate, f"{required}_consecutive_danger_or_higher"
            return previous, f"awaiting_{required}_consecutive_danger_or_higher"
        required = rules["warning_entry_observations"]
        window = rules["warning_entry_window"]
        if _count_at_least(observations[-window:], candidate_rank) >= required:
            return candidate, f"{required}_of_{window}_warning_or_higher"
        return previous, f"awaiting_{required}_of_{window}_warning_or_higher"

    required = rules["exit_consecutive"]
    if _consecutive_at_most(observations, candidate_rank) >= required:
        return candidate, f"{required}_consecutive_exit"
    return previous, f"awaiting_{required}_consecutive_exit"


def _rules(persistence: dict[str, Any]) -> dict[str, int]:
    return {
        "warning_entry_observations": max(1, int(persistence.get("warning_entry_observations", 2) or 2)),
        "warning_entry_window": max(1, int(persistence.get("warning_entry_window", 3) or 3)),
        "danger_entry_consecutive": max(1, int(persistence.get("danger_entry_consecutive", 2) or 2)),
        "exit_consecutive": max(1, int(persistence.get("exit_consecutive", 2) or 2)),
        "expected_cadence_days": max(1, int(persistence.get("expected_cadence_days", 1) or 1)),
        "max_gap_days": max(1, int(persistence.get("max_gap_days", 7) or 7)),
    }


def _count_at_least(observations: list[dict[str, str]], rank: int) -> int:
    return sum(1 for item in observations if _stage_rank(item) >= rank)


def _consecutive_at_least(observations: list[dict[str, str]], rank: int) -> int:
    count = 0
    for item in reversed(observations):
        if _stage_rank(item) >= rank:
            count += 1
        else:
            break
    return count


def _consecutive_at_most(observations: list[dict[str, str]], rank: int) -> int:
    count = 0
    for item in reversed(observations):
        if _stage_rank(item) <= rank:
            count += 1
        else:
            break
    return count


def _consecutive_count(observations: list[dict[str, str]], stage: str) -> int:
    count = 0
    for item in reversed(observations):
        if item.get("stage") == stage:
            count += 1
        else:
            break
    return count


def _eligible_count(observations: list[dict[str, str]]) -> int:
    return len(observations)


def _stage_rank(observation: dict[str, str]) -> int:
    return STAGE_RANK.get(str(observation.get("stage") or "normal"), 0)


def _normalize_observations(observations: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(observations, list):
        return normalized
    for item in observations:
        if isinstance(item, dict):
            stage = str(item.get("stage") or "")
            observed_at = str(item.get("observed_at") or "")
        else:
            stage = str(item)
            observed_at = ""
        if stage in STAGE_RANK:
            normalized.append({"stage": stage, "observed_at": observed_at})
    return normalized


def _gap_days(previous_at: Any, observed_at: str) -> int | None:
    previous = _parse_datetime(previous_at)
    current = _parse_datetime(observed_at)
    if not previous or not current:
        return None
    return (current.date() - previous.date()).days


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(text[:10])
        except ValueError:
            return None


def _next_episode_id(previous_episode: str, scope: str) -> str:
    prefix = f"{scope}:"
    if previous_episode.startswith(prefix):
        try:
            return f"{scope}:{int(previous_episode.removeprefix(prefix)) + 1}"
        except ValueError:
            pass
    return f"{scope}:1"
