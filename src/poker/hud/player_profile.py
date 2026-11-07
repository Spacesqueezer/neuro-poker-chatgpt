"""Conservative Russian summaries of verified observed actions, without storage."""


def describe_style(actions, hands):
    total = sum(actions.values())
    if total < 20 or hands < 5:
        return "Стиль пока неизвестен — мало подтверждённых действий."
    aggressive = actions.get("bet", 0) + actions.get("raise", 0)
    passive = actions.get("check", 0) + actions.get("call", 0)
    if aggressive / total >= 0.5:
        label = "В наблюдённых действиях часто ставит и повышает"
    elif passive / total >= 0.65:
        label = "В наблюдённых действиях чаще чекает и уравнивает"
    else:
        label = "В наблюдённых действиях смешанное поведение"
    return f"{label} ({total} действий, {hands} рук)."
