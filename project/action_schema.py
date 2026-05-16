from __future__ import annotations


ACTION_RANK = {
    "diagnostic_only": 0,
    "wait": 1,
    "watch": 2,
    "buy_window": 3,
}

ACTION_LABELS_JA = {
    "buy_window": "買い検討ゾーン",
    "watch": "監視継続",
    "wait": "待機",
    "diagnostic_only": "診断用",
}


def action_label_ja(value: str) -> str:
    return ACTION_LABELS_JA.get(value, value)


def action_rank(value: str, default: int = 1) -> int:
    return ACTION_RANK.get(value, default)


def runtime_cap_action(max_action: str) -> str:
    return "wait" if max_action == "diagnostic_only" else max_action
