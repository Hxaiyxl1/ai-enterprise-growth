# -*- coding: utf-8 -*-
"""
价格快照幂等合并：只追加，不覆盖；同一次观测重跑不会产生重复记录。

用法:
    python merge_snapshots.py <历史快照.json> <本期新增.json> [-o 输出.json]
        [-b 批次号]

幂等键 = 平台 | 店铺 | 型号 | 购买条件 | 观测日期(YYYY-MM-DD)
同一幂等键已存在且字段完全一致 -> 跳过
同一幂等键已存在但价格不同 -> 记入 conflicts，由人工判断（不自动覆盖）
"""
import json, sys, argparse
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
KEY_FIELDS = ("platform", "seller", "model", "purchase_condition")
PRICE_FIELDS = ("price_value", "price_text_raw", "price_type")


def load(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict):
        return d.get("price_snapshots", [])
    return d


def obs_day(rec):
    t = rec.get("observed_at") or rec.get("observedAt") or ""
    return str(t)[:10]


def key_of(rec):
    parts = [str(rec.get(k) or "").strip().lower() for k in KEY_FIELDS]
    return "|".join(parts) + "|" + obs_day(rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("history")
    ap.add_argument("incoming")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("-b", "--batch", default=None, help="观测批次号，默认用当前北京时间日期")
    a = ap.parse_args()

    batch = a.batch or datetime.now(TZ).strftime("%Y-%m-%d")
    hist = load(a.history)
    new = load(a.incoming)

    index = {}
    for r in hist:
        index.setdefault(key_of(r), []).append(r)

    added, dup, conflicts = [], [], []
    for r in new:
        r.setdefault("batch", batch)
        r.setdefault("status", "待归档")
        k = key_of(r)
        if k not in index:
            hist.append(r)
            index[k] = [r]
            added.append(r)
            continue
        prev = index[k][0]
        if all(prev.get(f) == r.get(f) for f in PRICE_FIELDS):
            dup.append(r)
        else:
            conflicts.append({
                "key": k,
                "prev": {f: prev.get(f) for f in PRICE_FIELDS},
                "incoming": {f: r.get(f) for f in PRICE_FIELDS},
            })

    out = a.out or a.history
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"price_snapshots": hist}, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "batch": batch,
        "history_before": len(hist) - len(added),
        "incoming": len(new),
        "added": len(added),
        "duplicated_skipped": len(dup),
        "conflicts": len(conflicts),
        "history_after": len(hist),
        "output": out,
    }, ensure_ascii=False, indent=2))

    for c in conflicts:
        print("CONFLICT", c["key"], c["prev"], "->", c["incoming"], file=sys.stderr)


if __name__ == "__main__":
    main()
