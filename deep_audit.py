#!/usr/bin/env python3
"""Deep audit for Hindi/Devanagari presence, option uniqueness, year consistency, and cross-topic duplicates."""

import json
import os
import re

Q_DIR = "/Users/anshu_macmini/Downloads/bihar-let-practice/questions"
TOPICS = [
    "t01_history.json", "t02_libtypes.json", "t03_legislation.json",
    "t04_management.json", "t05_ddc_udc.json", "t06_cc_schemes.json",
    "t07_cataloguing.json", "t08_reference.json", "t09_automation.json",
    "t10_digital_networks.json", "t11_biblio_ir.json", "t12_advanced.json",
]
DEV_RE = re.compile(r"[\u0900-\u097F]")


def norm(s: str) -> str:
    return re.sub(r"[\s\.,\?\!\"'\(\)\-–—:;।]+", " ", (s or "").lower()).strip()


def main():
    en_seen = {}
    hi_seen = {}
    en_dups, hi_dups = [], []
    opt_dups, no_dev, yr_issues = [], [], []
    total = 0

    for fn in TOPICS:
        with open(os.path.join(Q_DIR, fn), "r", encoding="utf-8") as f:
            d = json.load(f)
        total += len(d)
        for q in d:
            qid = q["id"]
            ne = norm(q["qe"])
            nh = norm(q["qh"])
            if ne in en_seen:
                en_dups.append((en_seen[ne], f"{fn}#{qid}", q["qe"][:70]))
            else:
                en_seen[ne] = f"{fn}#{qid}"
            if nh in hi_seen:
                hi_dups.append((hi_seen[nh], f"{fn}#{qid}", q["qh"][:70]))
            else:
                hi_seen[nh] = f"{fn}#{qid}"

            opts_en = [q[k][0].lower().strip() for k in ("a", "b", "c", "d")]
            if len(set(opts_en)) < 4:
                opt_dups.append((f"{fn}#{qid}", opts_en))

            if not DEV_RE.search(q["qh"]) or not DEV_RE.search(q["ch"]):
                no_dev.append((f"{fn}#{qid}", "qh/ch"))
            for wk, wv in q["wh"].items():
                if not DEV_RE.search(wv):
                    no_dev.append((f"{fn}#{qid}", f"wh[{wk}]"))

            yr = q.get("yr")
            if yr is not None:
                ans = q["ans"]
                blob = f"{q.get('yre') or ''} {q['ce']} {q[ans][0]} {q['qe']}"
                if str(yr) not in blob:
                    yr_issues.append((f"{fn}#{qid}", yr, q["qe"][:50], q.get("yre")))
                if not q.get("yre") or not q.get("yrh"):
                    yr_issues.append((f"{fn}#{qid}", yr, "missing yre/yrh", None))

    print(f"Total audited: {total}")
    print(f"English dups: {len(en_dups)}")
    for x in en_dups:
        print("  EN_DUP:", x)
    print(f"Hindi-only dups (beyond EN): {len([h for h in hi_dups if h[1] not in {e[1] for e in en_dups}])}")
    for x in hi_dups:
        if x[1] not in {e[1] for e in en_dups}:
            print("  HI_DUP:", x)
    print(f"Internal duplicate options: {len(opt_dups)}")
    for x in opt_dups[:10]:
        print("  OPT_DUP:", x)
    print(f"Missing Devanagari: {len(no_dev)}")
    for x in no_dev[:10]:
        print("  NO_DEV:", x)
    print(f"Year mismatches/missing yre: {len(yr_issues)}")
    for x in yr_issues[:20]:
        print("  YR_ISSUE:", x)


if __name__ == "__main__":
    main()
