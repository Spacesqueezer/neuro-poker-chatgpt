"""Interpretable policy diagnostics; no training, Torch or private engine state."""

from collections import Counter, defaultdict

from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import decode


def action_report(confusion):
    per_action = {}
    for index, action in enumerate(ACTIONS):
        support = sum(confusion[index])
        predicted = sum(row[index] for row in confusion)
        correct = confusion[index][index]
        per_action[action] = {
            "support": support,
            "predicted": predicted,
            "correct": correct,
            "recall": correct / support if support else None,
            "precision": correct / predicted if predicted else None,
        }
    recalls = [row["recall"] for row in per_action.values() if row["support"]]
    return {
        "per_action": per_action,
        "balanced_accuracy_present_classes": sum(recalls) / len(recalls) if recalls else None,
    }


class PolicyMetrics:
    def __init__(self):
        self.confusion = [[0] * len(ACTIONS) for _ in ACTIONS]
        self.streets = defaultdict(Counter)
        self.sizing = Counter()

    def add(self, row, predicted, fraction):
        observation = row["observation"]
        expected = row["action_index"]
        self.confusion[expected][predicted] += 1
        self.streets[observation.street]["samples"] += 1
        self.streets[observation.street]["correct"] += predicted == expected
        if not row["sizing_mask"]:
            return None
        # Conditional sizing diagnostic: use the labelled action, even for missed bets.
        gold = decode(observation, expected, row["sizing_fraction"]).amount_to
        amount = decode(observation, expected, fraction).amount_to
        low = observation.legal[ACTIONS[expected] + "_to_min"]
        error = abs(amount - gold) / observation.big_blind
        self.sizing["labels"] += 1
        self.sizing["absolute_error_bb"] += error
        self.sizing["minimum_baseline_absolute_error_bb"] += abs(low - gold) / observation.big_blind
        if predicted == expected:
            self.sizing["matching_actions"] += 1
            self.sizing["matching_absolute_error_bb"] += error
        return {
            "target_amount_to": gold,
            "conditional_amount_to": amount,
            "absolute_error_bb": error,
        }

    def report(self):
        count, matched = self.sizing["labels"], self.sizing["matching_actions"]
        return {
            **action_report(self.confusion),
            "by_street": {
                street: {**values, "action_agreement": values["correct"] / values["samples"]}
                for street, values in self.streets.items()
            },
            "sizing": {
                "labels": count,
                "matching_actions": matched,
                "conditional_mae_bb": self.sizing["absolute_error_bb"] / count if count else None,
                "minimum_baseline_mae_bb": self.sizing["minimum_baseline_absolute_error_bb"] / count
                if count
                else None,
                "matching_actions_mae_bb": self.sizing["matching_absolute_error_bb"] / matched
                if matched
                else None,
            },
        }


def evaluation_text(result):
    """Keep rare-action and monetary failures visible alongside headline accuracy."""
    diagnostics = result["diagnostics"]
    lines = [
        "# Проверка модели на отложенных данных",
        "",
        f"Совпадение с эвристическим учителем: {result['action_agreement']:.2%}; "
        f"базовый выбор: {result['legal_majority_baseline_agreement']:.2%}.",
        "",
        "| Действие | Совпало / всего | Выбрано моделью |",
        "| --- | ---: | ---: |",
    ]
    for action, values in diagnostics["per_action"].items():
        lines.append(
            f"| {action} | {values['correct']} / {values['support']} | {values['predicted']} |"
        )
    size = diagnostics["sizing"]
    if size["labels"]:
        lines.extend(
            [
                "",
                f"Ошибка размера на {size['labels']} метках bet/raise: "
                f"{size['conditional_mae_bb']:.2f} ББ; у минимальной суммы — "
                f"{size['minimum_baseline_mae_bb']:.2f} ББ.",
                "Это условная проверка размера с действием учителя; "
                "модель могла выбрать check/call.",
            ]
        )
    if result.get("variants"):
        lines.extend(
            [
                "",
                "| Тип раздачи | Решений | Совпадение с учителем |",
                "| --- | ---: | ---: |",
            ]
        )
        for name, group in result["variants"].items():
            label = "Обычная" if name == "standard" else "Взрывная, один борд"
            lines.append(
                f"| {label} | {group['counts']['samples']} | {group['action_agreement']:.2%} |"
            )
    lines.extend(["", "Это проверка имитации, не доходности. К HUD модель не подключается.", ""])
    return "\n".join(lines)
