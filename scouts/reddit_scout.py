#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reddit-scout — builder subreddits mined for startup-worthy projects & real demand.

r/SideProject, r/SaaS, r/startups etc. are where builders post "I built X" (a launched
product a builder audience upvoted) and "is there a tool for Y" (real demand people would
pay to solve). Both are strong startup signals — and, unlike stars, they come with a
crowd reacting. Same idea model (what / why-good / commercial value / risk), no predictions.

Auth: userless OAuth (application-only, client_credentials) with a Reddit 'script' app.
Needs env REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET. Absent -> skips cleanly (exits 0)."""
import os, json, base64, urllib.parse, urllib.request, urllib.error
import scout_lib as S

SUBS = ["SideProject", "SaaS", "startups", "microsaas", "Entrepreneur"]
UA = "future-scout/1.0 by u/jerryma521 (+https://github.com/zqf1314/idea)"
LAUNCH = ["i built", "i made", "i created", "launched", "launching", "my app", "my saas",
          "my tool", "we built", "we launched", "show:", "built a", "made a", "open-sourced",
          "open sourced", "released"]
NEED = ["is there a", "are there any", "how do you", "how do i", "what do you use",
        "looking for a", "tool for", "alternative to", "wish there was", "anyone know of",
        "recommend a", "struggling with", "how to automate"]
KILL = ["who is hiring", "hiring", " job", "salary", "giveaway", "discount code", "promo code",
        "black friday", "upvote", "follow me", "roast my", "rate my resume", "cofounder wanted",
        "looking for cofounder", "for sale", "acquired", "milestone", "AMA"]
VALUE = {"agent-infra": "infra AI products need — usage-based API + hosted tier",
         "consumer-ai": "a workflow people pay a monthly seat for",
         "edge-ai": "on-device kills cloud cost + unlocks privacy buyers",
         "research": "productize the method for teams who can't build it",
         "pain-points": "turn a manual workaround into subscription revenue",
         "other": "a paid wedge if it owns one workflow end-to-end"}

def _token(cid, secret):
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request("https://www.reddit.com/api/v1/access_token", data=body,
        headers={"Authorization": f"Basic {basic}", "User-Agent": UA,
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("access_token")

def _top(sub, tok):
    url = f"https://oauth.reddit.com/r/{sub}/top?t=week&limit=25"
    req = urllib.request.Request(url, headers={"Authorization": f"bearer {tok}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("data", {}).get("children", [])

def build():
    cid = os.environ.get("REDDIT_CLIENT_ID"); secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        print("[reddit-scout] no REDDIT_CLIENT_ID/SECRET — skipping"); return []
    tok = _token(cid, secret)
    if not tok:
        print("[reddit-scout] auth failed — skipping"); return []
    out = []
    for sub in SUBS:
        try:
            posts = _top(sub, tok)
        except Exception as e:
            print(f"  [r/{sub} skip] {e!r}"); continue
        for p in posts:
            d = p.get("data") or {}
            title = (d.get("title") or "").strip()
            if not title:
                continue
            low = title.lower()
            if any(k in low for k in KILL):
                continue
            body = (d.get("selftext") or "")
            ups = d.get("ups") or d.get("score") or 0
            nc = d.get("num_comments") or 0
            ext = d.get("url_overridden_by_dest") or d.get("url") or ""
            perma = "https://reddit.com" + (d.get("permalink") or "")
            is_launch = any(k in low for k in LAUNCH)
            is_need = any(k in low for k in NEED)
            if not (is_launch or is_need):
                continue                      # only clear launches or clear needs
            dom = S.infer_domain(f"{title} {body}", "pain-points" if is_need else "consumer-ai")
            has_product = bool(ext) and "reddit.com" not in ext
            sc = {
                "interest": 2 if ups >= 300 else (1 if ups >= 100 else 0),
                "engage":   2 if nc >= 80 else (1 if nc >= 25 else 0),
                "shape":    2 if (is_launch or is_need) else 1,
                "buyer":    2 if dom in ("agent-infra", "consumer-ai", "edge-ai", "pain-points") else 1,
                "substance": 2 if (has_product or len(body) > 220) else 1,
            }
            score = sum(sc.values())
            if score < 7:
                continue
            kind = "launch" if is_launch else "unmet need"
            out.append({
                "_score": score, "_ups": ups,
                "title": title[:110],
                "claim": f"r/{sub} ({kind}): {title[:140]}",
                "score": score,
                "why_good": (f"{ups} upvotes and {nc} comments in r/{sub} — a builder audience "
                             f"reacted to this {kind}, not just the person who posted it."),
                "value": VALUE.get(dom, VALUE["other"]),
                "risk": ("Reddit skews technical and early — validate that non-Reddit users will pay, "
                         "and that it isn't a feature a bigger tool absorbs."),
                "evidence": ([ext] if has_product else []) +
                            [perma, f"{ups} upvotes in r/{sub}", f"{nc} comments"],
                "method": "reddit api (builder subs, top/week) + startup-worthiness score",
                "domain": dom, "model": "future-scout/reddit", "operator": "@ourword-ai",
                "tags": [f"r/{sub}", kind.replace(" ", "-")]})
    out.sort(key=lambda f: (f["_score"], f["_ups"]), reverse=True)
    for f in out:
        f.pop("_score", None); f.pop("_ups", None)
    return out

if __name__ == "__main__":
    try:
        cands = build()
    except urllib.error.HTTPError as e:
        print(f"[reddit-scout] HTTP {e.code} — skipping: {e.read()[:200]!r}"); cands = []
    except Exception as e:
        print(f"[reddit-scout] source unavailable, skipping: {e!r}"); cands = []
    posted = S.post_ideas(cands, "reddit-scout", cap=8)
    print(json.dumps({"scout": "reddit-scout", "posted": len(posted)}))
