#!/usr/bin/env python3
"""Собрать пул тренажёра из корпусов в один файл для страницы.

Читает:
  40_ab_factory/vk-style/cases_mvp_v2/    (кейсы + _trap_labels.json)
  40_ab_factory/vk-style/cases_trainer/   (догенерированные ship-кейсы)
  docs/data/trainer_texts.json            (список механизмов пула и тексты)
  docs/data/corpus_660.json               (решение правила, опционально)
  docs/data/corpus_trainer.json           (то же для догенерированных)

Пишет:
  docs/data/trainer_pool.json

Пул — это не весь корпус. В нём только механизмы, решаемые по таблице:
улика в числах, а не в notes, и обман объясним одной фразой без статистики.
Критерий и обоснование по каждому механизму — в BACKLOG.md.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VK = REPO / "40_ab_factory" / "vk-style"
DATA = REPO / "docs" / "data"

CORPORA = ("cases_mvp_v2", "cases_trainer")

# Эталон опирается на суждение «любая просадка денег перевешивает рост кликов»,
# которого в контракте нет: просадка выручки не доходит до предела guardrail,
# и по таблице эти кейсы решаются в пользу «катить». Пользователь сделал бы
# всё правильно и получил бы «неверно».
EXCLUDE = {"case_089", "case_562", "case_611", "case_652"}

# Метрики, у которых в data.csv есть своя колонка. Guardrail на что-то другое
# (retention, dau, ltv) объявлен в контракте у 122 кейсов, но данных под ним
# нет — показывать такой guardrail нельзя, пользователь пойдёт искать строку,
# которой не существует.
METRIC_COLUMNS = {"revenue", "cpm", "fillrate", "ctr", "shows", "n_users"}


def _f(row: dict, key: str):
    v = row.get(key)
    if v in (None, ""):
        return None
    return float(v)


def _pct(v, digits: int = 2) -> str:
    return "—" if v is None else f"{v * 100:+.{digits}f}%"


def _rule_decisions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("corpus_660.json", "corpus_trainer.json"):
        p = DATA / name
        if not p.exists():
            continue
        for c in json.load(open(p, encoding="utf-8")):
            if c.get("decision"):
                out[c["case_id"]] = c["decision"]
    return out


def build_case(case_dir: Path, mechanism: str, rule: dict[str, str]) -> dict:
    contract = json.load(open(case_dir / "contract.json", encoding="utf-8"))
    truth = json.load(open(case_dir / "truth.json", encoding="utf-8"))
    with open(case_dir / "data.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    columns = set(rows[0].keys()) if rows else set()

    def pick(seg: str, var: str):
        return next((r for r in rows if r["segment"] == seg and r["variant"] == var), None)

    segments = [s for s in dict.fromkeys(r["segment"] for r in rows) if s != "all"]
    total_c = sum(int(pick(s, "control")["n_users"]) for s in segments) or None
    total_t = sum(int(pick(s, "test")["n_users"]) for s in segments) or None

    table = []
    for seg in ["all"] + segments:
        c, t = pick(seg, "control"), pick(seg, "test")
        nc, nt = int(c["n_users"]), int(t["n_users"])
        table.append({
            "segment": seg,
            "n_control": nc, "n_test": nt,
            "share_control": (nc / total_c) if (seg != "all" and total_c) else None,
            "share_test": (nt / total_t) if (seg != "all" and total_t) else None,
            "rpu_control": round(_f(c, "revenue") / nc, 3),
            "rpu_test": round(_f(t, "revenue") / nt, 3),
            "rev_delta": _f(t, "revenue_effect_relative"),
            "rev_p": _f(t, "revenue_p_value"),
            "ctr_control": _f(c, "ctr"), "ctr_test": _f(t, "ctr"),
            "ctr_delta": _f(t, "ctr_effect_relative"),
            "ctr_p": _f(t, "ctr_p_value"),
        })

    guardrails = [
        {"name": g["name"], "max_drop": g.get("max_drop_relative")}
        for g in contract.get("guardrails", [])
        if g["name"] in columns and g["name"] in METRIC_COLUMNS
        and g.get("max_drop_relative") is not None
    ]
    dropped = [g["name"] for g in contract.get("guardrails", [])
               if g["name"] not in columns]

    agg = table[0]
    primary = contract["primary_metric"]["name"]
    primary_delta = agg["ctr_delta"] if primary == "ctr" else agg["rev_delta"]
    threshold = contract["decision_framework"]["practical_threshold_relative"]

    vars_ = {
        "primary_delta": _pct(primary_delta),
        "revenue_delta": _pct(agg["rev_delta"]),
        "ctr_delta": _pct(agg["ctr_delta"]),
        "threshold": f"{threshold:.1%}",
        "alpha": str(contract["stats"]["alpha"]),
    }
    for g in guardrails:
        vars_[f"{g['name']}_limit"] = f"{g['max_drop']:.0%}"
    for i, seg in enumerate(segments, 1):
        row = next(r for r in table if r["segment"] == seg)
        vars_[f"seg{i}_name"] = seg
        vars_[f"seg{i}_delta"] = _pct(row["rev_delta"])
        vars_[f"seg{i}_share_control"] = f"{row['share_control']:.1%}"
        vars_[f"seg{i}_share_test"] = f"{row['share_test']:.1%}"

    return {
        "case_id": contract["case_id"],
        "corpus": case_dir.parent.name,
        "mechanism": mechanism,
        "expected": truth["expected_decision"],
        "rule_decision": rule.get(contract["case_id"]),
        "title": contract["title"],
        "primary": primary,
        "horizon_days": contract["time"]["horizon_days"],
        "unit": contract.get("unit", "user"),
        "alpha": contract["stats"]["alpha"],
        "threshold": threshold,
        "guardrails": guardrails,
        "guardrails_without_data": dropped,
        "table": table,
        "vars": vars_,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the trainer case pool")
    ap.add_argument("--out", default="trainer_pool.json",
                    help="Имя файла в docs/data/ (по умолчанию trainer_pool.json)")
    args = ap.parse_args()

    texts = json.load(open(DATA / "trainer_texts.json", encoding="utf-8"))
    wanted = set(texts["mechanisms"])
    rule = _rule_decisions()

    cases = []
    for corpus in CORPORA:
        root = VK / corpus
        labels_path = root / "_trap_labels.json"
        if not labels_path.exists():
            raise SystemExit(f"нет {labels_path} — пересоберите корпус генератором")
        labels = json.load(open(labels_path, encoding="utf-8"))
        for case_id, mechanism in sorted(labels.items()):
            if mechanism not in wanted or case_id in EXCLUDE:
                continue
            cases.append(build_case(root / case_id, mechanism, rule))

    by_decision: dict[str, int] = {}
    by_mechanism: dict[str, int] = {}
    for c in cases:
        by_decision[c["expected"]] = by_decision.get(c["expected"], 0) + 1
        by_mechanism[c["mechanism"]] = by_mechanism.get(c["mechanism"], 0) + 1

    out = {
        "n_cases": len(cases),
        "by_decision": by_decision,
        "by_mechanism": dict(sorted(by_mechanism.items())),
        "excluded": sorted(EXCLUDE),
        "cases": cases,
    }
    path = DATA / args.out
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"  {path.relative_to(REPO)}  {len(cases)} кейсов")
    print(f"  по вердиктам: {by_decision}")
    print(f"  по механизмам: {out['by_mechanism']}")
    missing = sum(1 for c in cases if not c["rule_decision"])
    if missing:
        print(f"  без решения правила: {missing} (соберите индексы корпусов)")
    hidden = sorted({g for c in cases for g in c["guardrails_without_data"]})
    if hidden:
        print(f"  guardrail без данных, скрыты в интерфейсе: {hidden}")


if __name__ == "__main__":
    main()
