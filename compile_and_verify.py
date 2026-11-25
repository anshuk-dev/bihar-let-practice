#!/usr/bin/env python3
"""Compile, validate, deduplicate, balance options, and export 3000 Bihar LET LIS questions."""

import hashlib
import json
import os
import re
import sys
from collections import Counter

BASE_DIR = "/Users/anshu_macmini/Downloads/bihar-let-practice"
Q_DIR = os.path.join(BASE_DIR, "questions")
OUT_DIR = os.path.join(BASE_DIR, "data")

TOPICS = [
    ("t01", "t01_history.json", "Library History & Thinkers"),
    ("t02", "t02_libtypes.json", "Types of Libraries & Services"),
    ("t03", "t03_legislation.json", "Library Acts & Committees"),
    ("t04", "t04_management.json", "Library Management & Finance"),
    ("t05", "t05_ddc_udc.json", "DDC & UDC Classification"),
    ("t06", "t06_cc_schemes.json", "Colon Classification & Schemes"),
    ("t07", "t07_cataloguing.json", "Cataloguing, AACR2, CCC, RDA, MARC"),
    ("t08", "t08_reference.json", "Information Sources & Reference"),
    ("t09", "t09_automation.json", "Library Automation & LIS-IT"),
    ("t10", "t10_digital_networks.json", "Digital Libraries & Networks"),
    ("t11", "t11_biblio_ir.json", "Bibliometrics & Info Retrieval"),
    ("t12", "t12_advanced.json", "KO, Indexing, Standards & IPR"),
]

LETTER_REF_RE = re.compile(r"\b(option\s+[a-d]|विकल्प\s*[a-dअ-द])\b", re.IGNORECASE)
NON_LIS_RE = re.compile(
    r"\b(trigonometry|quadratic equation|photosynthesis|mitochondria|mughal emperor|battle of panipat|chief minister of bihar|indian penal code)\b",
    re.IGNORECASE,
)


def norm_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[\s\.,\?\!\"'\(\)\-–—:;]+", " ", s)
    return s.strip()


def deterministic_shuffle_options(q: dict, seed_str: str) -> None:
    """Balance ans across a/b/c/d cleanly if explanations do not hardcode option letters."""
    combined_exp = " ".join([
        q.get("ce", ""),
        q.get("ch", ""),
        *q.get("we", {}).values(),
        *q.get("wh", {}).values(),
    ])
    if LETTER_REF_RE.search(combined_exp):
        return  # Keep original letter assignment safely

    letters = ["a", "b", "c", "d"]
    h = hashlib.sha256(seed_str.encode("utf-8")).digest()
    # Build deterministic permutation of letters
    perm = sorted(letters, key=lambda ch: h[ord(ch) - ord("a")])
    # perm[new_idx] = old_letter
    old_opts = {l: q[l] for l in letters}
    old_ans = q["ans"]
    old_we = q["we"]
    old_wh = q["wh"]

    new_we = {}
    new_wh = {}
    new_ans = None
    for new_l, old_l in zip(letters, perm):
        q[new_l] = old_opts[old_l]
        if old_l == old_ans:
            new_ans = new_l
        else:
            new_we[new_l] = old_we[old_l]
            new_wh[new_l] = old_wh[old_l]

    q["ans"] = new_ans
    q["we"] = new_we
    q["wh"] = new_wh


def validate_question(q: dict, fname: str, idx: int) -> list[str]:
    errs = []
    ans = q.get("ans")
    if ans not in ("a", "b", "c", "d"):
        errs.append(f"{fname}[{idx}] invalid ans={ans!r}")
        return errs

    for k in ("a", "b", "c", "d"):
        val = q.get(k)
        if not (isinstance(val, list) and len(val) == 2 and all(isinstance(x, str) and x.strip() for x in val)):
            errs.append(f"{fname}[{idx}] invalid option {k}")

    for k in ("qe", "qh", "ce", "ch"):
        val = q.get(k)
        if not (isinstance(val, str) and len(val.strip()) > 3):
            errs.append(f"{fname}[{idx}] missing/short {k}")

    wrong_keys = sorted(k for k in ("a", "b", "c", "d") if k != ans)
    we = q.get("we")
    wh = q.get("wh")
    if not isinstance(we, dict) or sorted(we.keys()) != wrong_keys:
        errs.append(f"{fname}[{idx}] invalid we keys={list(we.keys()) if isinstance(we, dict) else None}")
    else:
        for k in wrong_keys:
            if not isinstance(we.get(k), str) or len(we[k].strip()) < 4:
                errs.append(f"{fname}[{idx}] empty we[{k}]")

    if not isinstance(wh, dict) or sorted(wh.keys()) != wrong_keys:
        errs.append(f"{fname}[{idx}] invalid wh keys={list(wh.keys()) if isinstance(wh, dict) else None}")
    else:
        for k in wrong_keys:
            if not isinstance(wh.get(k), str) or len(wh[k].strip()) < 4:
                errs.append(f"{fname}[{idx}] empty wh[{k}]")

    if NON_LIS_RE.search(q.get("qe", "")):
        errs.append(f"{fname}[{idx}] potential non-LIS GK question: {q.get('qe')[:70]}")

    yr = q.get("yr")
    if yr is not None and not isinstance(yr, int):
        errs.append(f"{fname}[{idx}] non-int yr={yr!r}")

    return errs


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    strict = "--strict" in sys.argv

    all_errors = []
    seen_en = {}
    seen_hi = {}
    dups = []

    set1_all = []
    set2_all = []
    topic_counts = {}

    for topic_idx, (tid, fname, tname) in enumerate(TOPICS):
        fpath = os.path.join(Q_DIR, fname)
        if not os.path.exists(fpath):
            all_errors.append(f"Missing file: {fname}")
            topic_counts[tid] = 0
            continue

        with open(fpath, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        topic_counts[tid] = len(data)
        valid_items = []

        for idx, raw in enumerate(data):
            errs = validate_question(raw, fname, idx)
            if errs:
                all_errors.extend(errs)
                continue

            nq = norm_text(raw["qe"])
            nh = norm_text(raw["qh"])
            if nq in seen_en:
                dups.append((seen_en[nq], f"{fname}#id={raw.get('id')}", raw["qe"]))
                continue
            if nh in seen_hi:
                dups.append((seen_hi[nh], f"{fname}#id={raw.get('id')}", raw["qh"]))
                continue
            seen_en[nq] = f"{fname}#id={raw.get('id')}"
            seen_hi[nh] = f"{fname}#id={raw.get('id')}"

            item = {
                "topicId": tid,
                "topicIdx": topic_idx,
                "origId": raw.get("id", idx + 1),
                "p": int(raw.get("p", 3)) if raw.get("p") in (1, 2, 3, 4, 5) else 3,
                "qe": raw["qe"].strip(),
                "qh": raw["qh"].strip(),
                "a": [raw["a"][0].strip(), raw["a"][1].strip()],
                "b": [raw["b"][0].strip(), raw["b"][1].strip()],
                "c": [raw["c"][0].strip(), raw["c"][1].strip()],
                "d": [raw["d"][0].strip(), raw["d"][1].strip()],
                "ans": raw["ans"],
                "ce": raw["ce"].strip(),
                "ch": raw["ch"].strip(),
                "we": {k: v.strip() for k, v in raw["we"].items()},
                "wh": {k: v.strip() for k, v in raw["wh"].items()},
                "yr": raw.get("yr"),
                "yre": raw.get("yre"),
                "yrh": raw.get("yrh"),
            }
            deterministic_shuffle_options(item, f"{tid}:{idx}:{nq}")
            valid_items.append(item)

        # Sort stably by priority (1 -> 5) then original id/order
        valid_items.sort(key=lambda x: (x["p"], idx_val(x["origId"])))

        half = min(125, len(valid_items) // 2) if len(valid_items) < 250 else 125
        for q in valid_items[:half]:
            q["set"] = 1
            set1_all.append(q)
        for q in valid_items[half:half + 125]:
            q["set"] = 2
            set2_all.append(q)

    # Sort Set 1 and Set 2 by (p, topicIdx, origId) so Priority 1 Basics appear first!
    set1_all.sort(key=lambda x: (x["p"], x["topicIdx"], idx_val(x["origId"])))
    set2_all.sort(key=lambda x: (x["p"], x["topicIdx"], idx_val(x["origId"])))

    for i, q in enumerate(set1_all, 1):
        q["gid"] = i
        q.pop("topicIdx", None)
        q.pop("origId", None)

    start_s2 = len(set1_all) + 1
    for i, q in enumerate(set2_all, start_s2):
        q["gid"] = i
        q.pop("topicIdx", None)
        q.pop("origId", None)

    ans_counter = Counter(q["ans"] for q in (set1_all + set2_all))
    yr_counter = sum(1 for q in (set1_all + set2_all) if q.get("yr") is not None)

    print("=== TOPIC COUNTS ===")
    for tid, fname, _ in TOPICS:
        print(f"  {fname:26s}: {topic_counts.get(tid, 0):3d}")
    print(f"Set 1 count: {len(set1_all)}")
    print(f"Set 2 count: {len(set2_all)}")
    print(f"Total valid unique: {len(set1_all) + len(set2_all)}")
    print(f"Duplicates dropped: {len(dups)}")
    print(f"Validation errors: {len(all_errors)}")
    print(f"Answer option distribution: {dict(sorted(ans_counter.items()))}")
    print(f"Chronology year entries: {yr_counter}")

    if dups:
        print("\nSample duplicates:")
        for d in dups[:15]:
            print("  DUP:", d)
    if all_errors:
        print("\nSample validation errors:")
        for e in all_errors[:15]:
            print("  ERR:", e)

    if strict and (len(all_errors) > 0 or len(set1_all) < 1500 or len(set2_all) < 1500):
        print("STRICT CHECK FAILED!")
        sys.exit(1)

    with open(os.path.join(OUT_DIR, "set1.json"), "w", encoding="utf-8") as f:
        json.dump(set1_all, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "set2.json"), "w", encoding="utf-8") as f:
        json.dump(set2_all, f, ensure_ascii=False, separators=(",", ":"))

    print("Exported data/set1.json and data/set2.json cleanly.")


def idx_val(v):
    if isinstance(v, int):
        return v
    m = re.search(r"\d+", str(v))
    return int(m.group(0)) if m else 999999


if __name__ == "__main__":
    main()
