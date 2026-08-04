#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arxiv-scout — very recent papers that could be PRODUCTIZED into a startup."""
import datetime
import json
import re
import xml.etree.ElementTree as ET

import scout_lib as S

ATOM = "{http://www.w3.org/2005/Atom}"
CATS = ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.SE", "cs.HC"]
APPLIED = [
    "system", "framework", "toolkit", "pipeline", "agent", "benchmark", "dataset",
    "library", "engine", "we build", "we present", "we introduce", "end-to-end",
    "real-time", "deploy", "production", "tool", "assistant",
]
THEORY_ONLY = [
    "we prove", "theorem", "lower bound", "upper bound", "regret bound",
    "convergence rate", "pac-bayes", "generalization bound",
]
GH_RE = re.compile(r"https?://github\.com/[\w.\-]+/[\w.\-]+")
CODE_KW = [
    "code is available", "code available", "we release", "we open-source",
    "we open source", "open-sourced", "our code", "code and models",
    "publicly available at", "code:", "project page",
]


def _txt(node):
    return re.sub(r"\s+", " ", (node.text or "")).strip() if node is not None else ""


def build():
    q = "+OR+".join(f"cat:{c}" for c in CATS)
    url = (
        f"https://export.arxiv.org/api/query?search_query={q}"
        "&sortBy=submittedDate&sortOrder=descending&max_results=120"
    )
    xml = S.http_get(url, {"Accept": "application/atom+xml"}, retries=5)
    root = ET.fromstring(xml)
    today = datetime.date.today()
    out = []
    for e in root.findall(f"{ATOM}entry"):
        title = _txt(e.find(f"{ATOM}title"))
        summ = _txt(e.find(f"{ATOM}summary"))
        absurl = _txt(e.find(f"{ATOM}id"))
        pub = _txt(e.find(f"{ATOM}published"))[:10]
        if not title or not summ:
            continue
        blob = (title + " " + summ).lower()
        gh = GH_RE.search(summ)
        code_released = bool(gh) or any(k in blob for k in CODE_KW)
        if not code_released:
            continue
        if not any(k in blob for k in APPLIED):
            continue
        if any(k in blob for k in THEORY_ONLY) and not gh:
            continue
        try:
            age = (today - datetime.date.fromisoformat(pub)).days
        except Exception:
            age = 999
        if age > 30:
            continue
        dom = S.infer_domain(blob, "research")
        score = sum({
            "code": 2,
            "applied": 2,
            "recency": 2 if age <= 10 else (1 if age <= 30 else 0),
            "concrete": 2 if gh else 1,
            "buyer": 2 if dom in ("agent-infra", "edge-ai", "consumer-ai") else 1,
        }.values())
        if score < 7:
            continue
        ev = [absurl]
        if gh:
            ev.append(gh.group(0))
        ev += [f"submitted {pub}", "arXiv " + "/".join(CATS[:4])]
        out.append({
            "_score": score,
            "_age": age,
            "title": re.sub(r"\s*\(.*?\)\s*$", "", title)[:120],
            "claim": f"Productizable research: {title[:150]}",
            "score": score,
            "why_good": (
                f"Ships released code ({gh.group(0)}) — reproducible today, so a team can "
                "productize the method now instead of re-deriving it."
                if gh else
                "Authors released code, so the method is reproducible today rather than a promise."
            ),
            "value": "first to productize the method captures the teams who can't reproduce it themselves.",
            "risk": (
                "research-stage: no users yet, and the method may not survive contact with "
                "real-world data — or a well-funded incumbent ships it first."
            ),
            "evidence": ev,
            "method": "arxiv recent (<=30d), gated on released code + concrete-system shape",
            "domain": dom,
            "model": "future-scout/arxiv",
            "operator": "@ourword-ai",
            "tags": ["arxiv", "research-to-product"],
        })
    out.sort(key=lambda f: (f["_score"], -f["_age"]), reverse=True)
    for f in out:
        f.pop("_score", None)
        f.pop("_age", None)
    return out


if __name__ == "__main__":
    try:
        cands = build()
    except Exception as e:
        print(f"[arxiv-scout] source unavailable, skipping: {e!r}")
        cands = []
    posted = S.post_ideas(cands, "arxiv-scout", cap=4)
    print(json.dumps({"scout": "arxiv-scout", "posted": len(posted)}))
