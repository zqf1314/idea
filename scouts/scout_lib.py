#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Future scout — shared library.

First-party scouts that seed the commons with REAL, verifiable, dated findings.
Each scout builds candidate findings from a live public source, dedups against the
existing corpus using the SAME barter engine, opens a real `finding` issue, and lets
the engine pay it back + record it. Fault-tolerant by design: any single failure is
skipped, never aborts the run.
"""
from __future__ import annotations
import os, sys, time, json, re, subprocess as sp, urllib.request, urllib.parse, urllib.error

# import the barter engine from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.getcwd())
import barter_engine as engine  # noqa: E402

MIN_NOVELTY = 0.30   # skip candidates too similar to something already in the commons
DRY = os.environ.get("SCOUT_DRY") == "1"

DOMAIN_KW = [
    ("edge-ai",     ["on-device", "on device", "edge", "local-first", "local model", "offline",
                     "quantiz", "ggml", "llama.cpp", "raspberry", "esp32", "gguf", "webgpu"]),
    ("agent-infra", ["agent", "mcp", "orchestrat", "tool-use", "tool use", "workflow", "harness",
                     "sdk", "framework", "runtime", "autonomous", "multi-agent"]),
    ("consumer-ai", ["app", "chat", "voice", "image", "video", "photo", "note", "browser",
                     "assistant", "editor", "desktop"]),
    ("research",    ["benchmark", "dataset", "paper", "arxiv", "sota", "fine-tun", "distill",
                     "diffusion", "transformer", "reasoning"]),
]

def has_kw(text: str, kws) -> bool:
    """Word-boundary keyword match (avoids 'ai' matching 'plain', 'app' matching 'mapped')."""
    t = (text or "").lower()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t) for k in kws)

def infer_domain(text: str, default="other") -> str:
    for dom, kws in DOMAIN_KW:
        if has_kw(text, kws):
            return dom
    return default

def http_get(url, headers=None, retries=3, timeout=30):
    h = {"User-Agent": "future-scout/1.0 (+https://github.com/zqf1314/idea)"}
    if headers: h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e; time.sleep(3 * (i + 1))
    raise last

def finding_to_body(f: dict) -> str:
    ev = "\n".join(f.get("evidence", []) or [])
    return (
        f"### Claim\n\n{f['claim']}\n\n"
        f"### Evidence\n\n{ev}\n\n"
        f"### Method\n\n{f.get('method','')}\n\n"
        f"### Domain\n\n{f.get('domain','other')}\n\n"
        f"### Confidence\n\n{f.get('confidence',0.6)}\n\n"
        f"### Model\n\n{f.get('model','future-scout')}\n\n"
        f"### Operator (optional handle)\n\n{f.get('operator','@ourword-ai')}\n"
    )

def _gh_create(title, body, label="finding"):
    try:
        p = sp.run(["gh", "issue", "create", "--title", title, "--label", label, "--body", body],
                   capture_output=True, text=True)
    except FileNotFoundError:
        return None                       # no gh CLI (e.g. backfill) — finding still gets written
    if p.returncode != 0:
        print(f"[gh create fail] {p.stderr.strip()[-300:]}", file=sys.stderr)
        return None
    return p.stdout.strip().splitlines()[-1].strip()

def _gh_headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "future-scout/1.0"}
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h

def metric_value(pred):
    """Fetch the current real value of a prediction's metric (the verification oracle)."""
    m = pred.get("metric")
    if m == "github_stars":
        d = json.loads(http_get(f"https://api.github.com/repos/{pred['target_id']}", _gh_headers()))
        return d.get("stargazers_count")
    return None  # unknown metric -> resolver skips (stays pending)

def _agent_accuracy(findings, agent):
    res = [f for f in findings if f.get("agent") == agent and f.get("status") in ("hit", "miss")]
    hits = sum(1 for f in res if f.get("status") == "hit")
    return hits, len(res)

def prediction_body(f):
    p = f.get("prediction") or {}
    ev = "\n".join(f.get("evidence", []) or [])
    return (
        f"### Claim\n\n{f['claim']}\n\n"
        f"### Prediction (auto-resolved)\n\n"
        f"- metric: `{p.get('metric')}`\n- subject: `{p.get('target_id')}`\n"
        f"- resolves: **{p.get('target_id')} {p.get('op')} {p.get('target')}** on **{p.get('resolve_on')}**\n\n"
        f"### Evidence\n\n{ev}\n\n"
        f"### Method\n\n{f.get('method','')}\n\n"
        f"### Domain\n\n{f.get('domain','other')}\n\n"
        f"### Operator\n\n{f.get('operator','@ourword-ai')}\n"
    )

def _gh_comment(number):
    sp.run(["gh", "issue", "comment", str(number), "--body-file", "comment.md"],
           capture_output=True, text=True)

DOMAIN_LABEL = {
    "agent-infra": "Agent infrastructure", "edge-ai": "On-device / edge AI",
    "consumer-ai": "Consumer AI apps", "research": "Fresh research",
    "pain-points": "Pain points", "health": "Health", "other": "Other signals",
}

def rebuild_clusters():
    """Honest 'what agents are noticing': a theme only shows when >=2 DIFFERENT scouts
    independently land in the same domain this cycle (real convergence, never faked)."""
    path = "findings/feed.json"
    if not os.path.exists(path):
        return
    feed = json.load(open(path, encoding="utf-8"))
    finds = feed.get("findings", [])
    by_dom = {}
    for f in finds:
        by_dom.setdefault(f.get("domain", "other"), []).append(f)
    clusters = []
    for dom, items in sorted(by_dom.items(), key=lambda kv: -len(kv[1])):
        agents = sorted({i.get("agent") for i in items if i.get("agent")})
        if len(items) < 2 or len(agents) < 2:
            continue  # not convergence — a single source doesn't count
        clusters.append({
            "name": DOMAIN_LABEL.get(dom, dom),
            "desc": f"{len(agents)} independent scouts both surfaced {dom} signals this cycle.",
            "n": len(agents),
            "members": [i["id"] for i in items][:8],
        })
    feed["clusters"] = clusters
    json.dump(feed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def rebuild_scoreboard():
    """Board summary for the Idea list: how many ideas, across how many domains &
    sources, and the average startup-worthiness score."""
    path = "findings/feed.json"
    if not os.path.exists(path):
        return
    feed = json.load(open(path, encoding="utf-8"))
    fs = feed.get("findings", [])
    from collections import Counter
    per = Counter(f.get("agent") for f in fs if f.get("agent"))
    scores = [f.get("score") for f in fs if isinstance(f.get("score"), (int, float))]
    feed["scoreboard"] = [{"agent": a, "ideas": n} for a, n in per.most_common()]
    feed["board"] = {"ideas": len(fs),
                     "domains": len({f.get("domain") for f in fs if f.get("domain")}),
                     "sources": len(per),
                     "avg_score": round(sum(scores) / len(scores), 1) if scores else 0}
    json.dump(feed, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def idea_body(f):
    ev = "\n".join(f.get("evidence", []) or [])
    return (f"### What\n\n{f['claim']}\n\n"
            f"### Why it's good\n\n{f.get('why_good','')}\n\n"
            f"### Commercial value\n\n{f.get('value','')}\n\n"
            f"### Risk\n\n{f.get('risk','')}\n\n"
            f"### Startup-worthiness\n\n{f.get('score','')}/10\n\n"
            f"### Evidence\n\n{ev}\n")

def _fetch_readme(f):
    """Best-effort README text (main then master) for grounding, HTML/img-stripped, truncated."""
    repo=None; t=f.get("title") or ""
    if "/" in t and " " not in t and not t.startswith("http"):
        repo=t
    else:
        for e in (f.get("evidence") or []):
            m=re.search(r"github\.com/([^/\s]+/[^/\s#?]+)", str(e))
            if m: repo=m.group(1); break
    if not repo: return ""
    for br in ("main","master"):
        try:
            req=urllib.request.Request(f"https://raw.githubusercontent.com/{repo}/{br}/README.md",
                                       headers={"User-Agent":"future-scout"})
            with urllib.request.urlopen(req, timeout=12) as r:
                txt=r.read().decode("utf-8","ignore")
            txt=re.sub(r"<[^>]+>"," ",txt); txt=re.sub(r"!\[[^\]]*\]\([^)]*\)"," ",txt)
            return txt[:5000]
        except Exception:
            continue
    return ""

# ---------------------------------------------------------------------------
# LLM transport. GitHub Models (models.github.ai) was FULLY RETIRED 2026-07-30, so
# the provider is configurable: point LLM_BASE_URL / LLM_API_KEY / LLM_MODEL at any
# OpenAI-compatible endpoint. Without a working provider every card call fails and the
# scouts hold every candidate — a silent 0-posted run. That failure is made loud below.
# ---------------------------------------------------------------------------
LLM_BASE_URL = (os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference").rstrip("/")
LLM_DEAD = ""        # reason string once the provider says retired/unauthorised; stops retrying

def _llm_key():
    return (os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN") or "")

def _llm_model(default="openai/gpt-4o-mini"):
    return os.environ.get("LLM_MODEL") or os.environ.get("GH_MODELS_MODEL") or default

def _llm_chat(prompt, model=None, max_tokens=800, temperature=0.0, timeout=45):
    """One OpenAI-compatible chat completion. Returns the text, or None when the provider
    is unusable. A 401/403/404/410 trips a process-wide breaker, so a retired endpoint
    costs one call per run instead of three per candidate."""
    global LLM_DEAD
    if LLM_DEAD:
        return None
    key = _llm_key()
    if not key:
        LLM_DEAD = "no API key (set LLM_API_KEY)"
        return None
    body = json.dumps({"model": model or _llm_model(), "temperature": temperature,
                       "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(LLM_BASE_URL + "/chat/completions", data=body,
          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                   "User-Agent": "future-scout"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 410):
            LLM_DEAD = f"HTTP {e.code} from {LLM_BASE_URL} — provider gone or key rejected"
            print(f"  [llm] provider unusable: {LLM_DEAD}", file=sys.stderr)
        raise

def llm_down_note():
    """One actionable line for the run log when nothing could be written."""
    return (f"0 cards written — LLM provider unusable ({LLM_DEAD}). GitHub Models was retired "
            "2026-07-30; set repo secret LLM_API_KEY and vars LLM_BASE_URL / LLM_MODEL to any "
            "OpenAI-compatible endpoint.")

def llm_copy(f):
    """Product-first, BILINGUAL, README-grounded card copy in ONE GitHub Models call. Returns
    does/edge/why_use/value/risk (+hook) plus f['i18n']['zh']; None on failure (keep heuristic)."""
    if not _llm_key(): return None
    model=_llm_model()
    ev=", ".join(f.get("evidence", []) or [])
    readme=_fetch_readme(f)
    voices_txt = "\n".join(f"- [{v.get('kind')}] {v.get('quote','')[:200]} ({v.get('url','')})"
                            for v in (f.get("voices") or [])) or "(none)"
    prompt=(
        "You write cards for a board whose ONE job is to surface product opportunities a solo "
        "founder could copy and build now (see docs/STANDARD.md). Write PRODUCT-FIRST, SPECIFIC copy "
        "grounded in the README below - never generic, never invented.\n"
        "The reader spends ten minutes a day here and asks one question: is this worth me building?\n"
        "BANNED (never output): 'could pay for premium features', 'subscription model', 'a bigger "
        "player could integrate', 'the market is competitive', 'leverages ... technology', "
        "'streamline workflows'. Replace with the concrete buyer / wedge / incumbent / weakness.\n\n"
        "Reply with ONLY a JSON object. English values first, then faithful 中文 in the *_zh keys:\n"
        "  hook: WHO IS IN PAIN, AND IN PAIN ENOUGH TO PAY - one concrete sentence naming the people "
        "and the pain. This is the first line the reader sees. Not a slogan, not a feature list.\n"
        "  does: what it concretely is and its standout capability, MERGED into 1-2 tight sentences "
        "from the README (overview + the thing it does that others do not).\n"
        "  why_use: the concrete reason to pick THIS over the alternatives; if first-hand quotes are "
        "supplied below, lean on what they actually complain about.\n"
        "  gap: why it is NOT solved well yet - one sentence, the entry point for a new builder. Use "
        "one of: only geeks can use it (CLI/self-host, no product around it); the Chinese/local-market "
        "case is empty; it hits a real pain but solves it imperfectly. Be specific about what is missing.\n"
        "  counter: the case AGAINST building it, and make it sting - who already owns this, whether a "
        "platform kills it with one feature, why it may be a feature and not a company. No hedging.\n"
        "  differentiator: what YOU would do differently to win - the wedge (package it for ordinary "
        "people / a local-private version / the Chinese-market version), concrete, one sentence.\n"
        "  value: who EXACTLY pays and for what specific outcome (name the buyer and the wedge).\n"
        "  risk: the single concrete reason it fails - name the incumbent or the exact weakness.\n"
        "  claim_zh, hook_zh, does_zh, why_use_zh, gap_zh, counter_zh, differentiator_zh, value_zh, "
        "risk_zh: faithful 中文 (the operator reads 中文 first for China-market entries).\n\n"
        f"First-hand quotes mined from issues/HN - quote or lean on these, do NOT invent any:\n{voices_txt}\n\n"
        f"Project: {f.get('title','')} - {f.get('claim','')}\n"
        f"Signals: {ev}\nDomain: {f.get('domain','')}\n\n"
        f"README (for grounding):\n{readme}\n\nJSON only.")
    fallback=os.environ.get("LLM_MODEL_FALLBACK") or os.environ.get("GH_MODELS_FALLBACK","openai/gpt-4o")
    for _i, _mdl in enumerate((model, model, fallback)):   # retry, then a stronger fallback model
        if LLM_DEAD:
            break
        try:
            txt=_llm_chat(prompt, model=_mdl, max_tokens=1100, temperature=0.4)
            if txt is None:
                break
            obj=json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            if all(obj.get(k) for k in ("does","value","risk")):
                out={k:str(obj[k]).strip()[:500] for k in ("does","value","risk")}
                out["why_good"]=out["does"]
                for _k,_lim in (("why_use",400),("gap",400),("counter",400),
                                ("differentiator",400),("edge",500),("hook",220)):
                    if obj.get(_k): out[_k]=str(obj[_k]).strip()[:_lim]
                zh={}
                for _src,dst in (("claim_zh","claim"),("hook_zh","hook"),("does_zh","does"),
                                ("edge_zh","edge"),("why_use_zh","why_use"),("gap_zh","gap"),
                                ("counter_zh","counter"),("differentiator_zh","differentiator"),
                                ("value_zh","value"),("risk_zh","risk")):
                    if obj.get(_src): zh[dst]=str(obj[_src]).strip()[:500]
                if zh.get("does"): zh["why_good"]=zh["does"]
                if zh: out["i18n"]={"zh":zh}
                return out
            raise ValueError("incomplete copy fields")
        except Exception as e:
            print(f"  [llm_copy attempt {_i+1} ({_mdl}) failed: {e!r}]", file=sys.stderr)
            time.sleep(4*(_i+1))
    return None
# ---------------------------------------------------------------------------
# Integrity + originality gate. The board recommends what is worth BUILDING, so
# projects whose core value depends on abusing someone else's service, or that are
# renamed forks with no substantive delta, never ship — regardless of star count.
# Deterministic (runs before any LLM call) so it cannot be talked around.
# ---------------------------------------------------------------------------
INTEGRITY_VETO = [
    ("account-farming",  r"(batch|bulk|mass|auto)[\s_-]?(regist|signup|sign-up)|account (generator|creator|farm|pool)|批量注册|养号|账号\s*(池|工厂)"),
    ("captcha-evasion",  r"\b(re)?captcha\b.{0,40}\b(solv|bypass|break)|\b(bypass|evade|defeat)\b.{0,25}\b(rate limit|ban|detection|risk control)|验证码.{0,10}(识别|绕过|破解)|风控绕过"),
    ("temp-identity",    r"(temp(orary)?[\s_-]?(mail|email|phone|sms)|sms.{0,10}(verification|receive)).{0,60}(regist|signup|account)|接码平台|临时邮箱.{0,20}注册"),
    ("paid-api-resale",  r"\b(free|unlimited)\b.{0,25}\b(api|quota|credits?|tokens?)\b.{0,25}\b(pool|proxy|mirror|unlimited|forever)|reverse[\s_-]?prox\w*.{0,30}(openai|anthropic|claude|grok|gemini|chatgpt)|\w*2api\b|白嫖|免费.{0,8}(额度|接口|key)"),
    ("platform-account-abuse", r"云微信|微信(多开|分身|托管)|(cloud|hosted)[\s_-]?wechat|wechat[\s_-]?(bot|automation|multi[\s_-]?account)|whatsapp.{0,40}(bulk|mass|blast|broadcasts?)"),
    ("credential-pool",  r"(cookie|session|token|credential|account)\s*(pool|farm)|号池|cookie池|共享账号"),
    ("piracy",           r"\b(keygen|nulled|activator|cracked)\b|licen[cs]e\s*(crack|patch|bypass)|破解|激活码"),
    ("engagement-farm",  r"(auto|bulk|mass)[\s_-]?(like|follow|view|upvote|retweet)\w*|\b(like|follow|view|engagement)[\s_-](bot|farm|booster)\b|刷(粉|赞|量|播放|阅读)|涨粉神器"),
    ("impersonation",    r"(deepfake|face[\s_-]?swap|voice[\s_-]?clon\w+).{0,40}(anyone|celebrit|politic|kyc|verification|scam)|换脸.{0,10}(冒充|诈骗)"),
    ("pii-harvest",      r"(email|phone|contact|lead)s?\s*(list|database|dump)\s*(scrap|extract|harvest)|scrap\w*[^.。!?]{0,30}\b(personal data|pii|resell)\b|爬取[^。]{0,12}(售卖|出售)"),
    ("location-spoofing", r"(spoof|fake|forge|modif\w+|overrid\w+)\W{0,12}(gps|geo ?location|location)\b|\b(gps|location)[\s_-]?(spoof|faker?|changer)|(virtual|fake)[\s_-]?location|(修改|伪造|虚拟)[^。]{0,8}(定位|位置)|\bgs-loc\b"),
]
# Renamed forks / cosmetic derivatives of an existing well-known project.
DERIVATIVE_NAME = re.compile(
    r"[-_](improved|enhanced|plus|promax|pro-max|better|ultimate|reborn|remake|clone|mirror|copy|fork)$"
    r"|^(open|free)(ai|claude|codex|cursor|grok|gemini|chatgpt|copilot|devin|manus|clawde|claude-?code)\b",
    re.I)
# Content, not product: the board's own rule, enforced deterministically too.
COLLECTION_NAME = re.compile(r"^(awesome|curated)[-_]|(^|[-_])(awesome|cheatsheet|cheat-sheet|handbook|guide|tutorials?|course|notes|roadmap|anthology|gallery|prompts?|skins?|themes?|skills?)$|[-_]from[-_]scratch$", re.I)

def _ev_int(f, pat):
    for e in f.get("evidence") or []:
        m = re.search(pat, str(e))
        if m:
            try: return int(m.group(1).replace(",", ""))
            except Exception: return None
    return None

FAMILIES = [
    ("voice-clone",      ["tts", "voice clone", "voice-clone", "speech synthesis", "声音克隆", "配音"]),
    ("video-edit",       ["video edit", "timeline", "clip", "剪辑", "montage"]),
    ("photo-memory",     ["photo", "album", "memories", "相册", "照片", "scrapbook"]),
    ("handwriting-ink",  ["handwriting", "e-ink", "eink", "remarkable", "手写"]),
    ("local-llm",        ["llama.cpp", "gguf", "on-device", "local model", "offline llm", "端侧", "本地模型"]),
    ("agent-harness",    ["harness", "coding agent", "cli agent", "agent runtime", "orchestrat"]),
    ("personal-context", ["memory", "context", "second brain", "human.md", "第二大脑", "上下文"]),
    ("home-sensing",     ["wifi sensing", "esp32", "sensor", "presence", "感知", "睡眠"]),
    ("doc-translate",    ["lab result", "contract", "insurance", "体检", "保单", "合同"]),
    ("job-search",       ["job search", "job-search", "job application", "cover letter",
                          "cv tailor", "resume tailor", "job portal", "求职", "简历", "招聘"]),
    ("short-drama",      ["short drama", "短剧", "storyboard", "分镜", "novel to video", "小说推文"]),
]

def family_of(f):
    """Same-family label. Pile-ups are kept and tagged — the crowding is itself the signal
    (docs/STANDARD.md 3)."""
    blob = " ".join(str(x) for x in [f.get("title", ""), f.get("claim", ""), f.get("does", ""),
                                     f.get("hook", "")] + list(f.get("tags") or [])).lower()
    for name, kws in FAMILIES:
        if any(k in blob for k in kws):
            return name
    return None

def integrity_veto(f):
    """Return a veto reason string, or None if the candidate is clean."""
    zh = (f.get("i18n") or {}).get("zh") or {}
    blob = " ".join(str(x) for x in [
        f.get("title", ""), f.get("claim", ""), f.get("why_good", ""), f.get("does", ""),
        f.get("edge", ""), f.get("value", ""), f.get("hook", ""),
        zh.get("claim", ""), zh.get("hook", ""), zh.get("does", ""), zh.get("value", ""),
    ] + list(f.get("tags") or [])).lower()
    core = " ".join(str(x) for x in [
        f.get("title", ""), f.get("claim", ""), f.get("why_good", ""), f.get("does", ""),
        f.get("edge", ""), f.get("hook", ""), zh.get("claim", ""), zh.get("hook", ""),
        zh.get("does", ""),
    ]).lower()
    for name, pat in INTEGRITY_VETO:
        # a repo merely *tagged* "2api" is not an abuse pitch — judge those on the written pitch
        hay = core if name in ("paid-api-resale", "piracy") else blob
        if re.search(pat, hay, re.I):
            return f"integrity:{name}"
    repo = (f.get("title") or "")
    slug = repo.split("/")[-1] if "/" in repo else repo
    contributors = _ev_int(f, r"(\d[\d,]*)\s*contributors?")
    commits = _ev_int(f, r"(\d[\d,]*)\s*commits")
    if DERIVATIVE_NAME.search(slug) and (contributors is None or contributors <= 2) \
       and (commits is None or commits <= 30):
        return "derivative: renamed fork with no substantive delta"
    if COLLECTION_NAME.search(slug):
        return "collection: content/list, not a product"
    return None

def load_marks(path="marks.json"):
    """Operator ⭐/❌ marks (docs/STANDARD.md 5). Reference signal only — never auto-scores."""
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d.get("marks") or {}
    except Exception:
        return {}

_PAY = re.compile(r"(would|i'?d|happily)\s+pay|pay(ing)?\s+for\s+this|take my money|"
                  r"是否收费|多少钱|愿意付费|想付钱|付费版|有没有付费|求托管|求个 ?saas", re.I)
_PAIN = re.compile(r"\b(i (hate|gave up|wasted|struggle)|"
                   r"i can'?t (get|use|find|make|install|run|figure|open|import|load)|"
                   r"so (annoying|painful|frustrating)|"
                   r"every ?(day|time) i|no (good|other) (tool|way)|too (hard|complicated) (to|for))|"
                   r"太麻烦|受不了|折腾|一直没找到|痛点|劝退", re.I)

_SEARCH_OK = True   # GitHub issue search is a shared 30/min budget; disabled after a refusal


def _bot(text, user=""):
    """Bot chatter (coderabbit summaries, CI bots) drowns out real users in the latest-comment
    window — drop it before matching."""
    u = (user or "").lower()
    if u.endswith("[bot]") or u in ("coderabbitai", "dependabot", "github-actions", "codecov-commenter"):
        return True
    t = (text or "")[:400].lower()
    return ("auto-generated comment" in t or "summarize by coderabbit" in t
            or t.startswith("<!--") or "walkthrough" in t and "coderabbit" in t)


def _clean(t):
    t = re.sub(r"```.*?```", " ", str(t or ""), flags=re.S)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def demand_voices(f, cap=3):
    """Mine first-hand demand quotes for a candidate that already passed the cheap gates
    (docs/STANDARD.md 4). Willingness-to-pay first, then genuine pain. Search first (high hit
    rate on the phrases that matter), then the newest comments, then the HN thread.
    Cheap by design: a handful of public API calls, no extra LLM call."""
    out, seen = [], set()
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    hdr = {"User-Agent": "future-scout", "Accept": "application/vnd.github+json"}
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"

    def _get(url):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"  [voices {url[:70]}: {e!r}]", file=sys.stderr)
            return None

    def _add(text, url, src, user=""):
        if len(out) >= cap or _bot(text, user):
            return
        t = _clean(text)
        if len(t) < 20:
            return
        kind = "pay" if _PAY.search(t) else ("pain" if _PAIN.search(t) else None)
        if not kind:
            return
        m = _PAY.search(t) or _PAIN.search(t)
        a, b = max(0, m.start() - 90), min(len(t), m.end() + 130)
        quote = ("…" if a else "") + t[a:b].strip() + ("…" if b < len(t) else "")
        key = quote[:60]
        if key in seen:
            return
        seen.add(key)
        out.append({"quote": quote[:260], "url": url, "src": src, "kind": kind})

    repo = None
    for x in [f.get("title", "")] + (f.get("evidence") or []):
        m = re.search(r"github\.com/([^/\s]+)/([^/\s#?\"']+)", str(x))
        if m:
            repo = f"{m.group(1)}/{m.group(2)}"
            break
    if repo is None and re.fullmatch(r"[\w.-]+/[\w.-]+", str(f.get("title", "") or "")):
        repo = f["title"]

    if repo:
        # 1) targeted phrase search — finds the sentence we care about wherever it lives
        for phrase in ('"would pay"', '"willing to pay"', '"pay for this"', '"take my money"',
                       '"付费" OR "多少钱"', '"gave up" OR "so annoying" OR frustrating'):
            if len(out) >= cap:
                break
            q = urllib.parse.urlencode({"q": f"repo:{repo} is:issue {phrase}", "per_page": 4})
            r = _get(f"https://api.github.com/search/issues?{q}")
            for it in ((r or {}).get("items") or []):
                _add((it.get("title") or "") + " — " + (it.get("body") or ""),
                     it.get("html_url") or f"https://github.com/{repo}/issues",
                     "github", ((it.get("user") or {}).get("login") or ""))
        # 2) newest comments (bots filtered), then the most-discussed issues
        if len(out) < cap:
            for c in (_get(f"https://api.github.com/repos/{repo}/issues/comments"
                           f"?per_page=100&sort=created&direction=desc") or []):
                _add(c.get("body"), c.get("html_url") or f"https://github.com/{repo}/issues",
                     "github", ((c.get("user") or {}).get("login") or ""))
        if len(out) < cap:
            for it in (_get(f"https://api.github.com/repos/{repo}/issues"
                            f"?state=all&per_page=30&sort=comments&direction=desc") or []):
                _add((it.get("title") or "") + " — " + (it.get("body") or ""),
                     it.get("html_url") or f"https://github.com/{repo}/issues",
                     "github", ((it.get("user") or {}).get("login") or ""))

    # 3) Show HN / Ask HN threads carry the loudest first-hand pain
    hn = next((e for e in (f.get("evidence") or []) if "news.ycombinator.com" in str(e)), None)
    if hn and len(out) < cap:
        m = re.search(r"id=(\d+)", str(hn))
        if m:
            d = _get(f"https://hn.algolia.com/api/v1/items/{m.group(1)}")

            def walk(node, depth=0):
                if len(out) >= cap or depth > 2 or not isinstance(node, dict):
                    return
                _add(node.get("text"), f"https://news.ycombinator.com/item?id={node.get('id')}",
                     "hn", node.get("author") or "")
                for ch in (node.get("children") or []):
                    walk(ch, depth + 1)
            walk(d)

    out.sort(key=lambda v: 0 if v["kind"] == "pay" else 1)   # willingness-to-pay first
    return out[:cap]


def behaviour_signal(f):
    """Behaviour is weaker than a quote but still first-hand: people forking to self-host, a
    maintained project with several contributors, a busy issue tracker. Used so a genuinely
    wanted project is not stuck in the archive just because its users never write 'I would pay'."""
    def n(pat):
        for e in f.get("evidence") or []:
            m = re.search(pat, str(e))
            if m:
                try:
                    return int(m.group(1).replace(",", ""))
                except Exception:
                    return None
        return None
    stars, forks = n(r"([\d,]+)\s*(?:★|stars)"), n(r"([\d,]+)\s*forks")
    contrib, commits = n(r"(\d[\d,]*)\s*contributors?"), n(r"(\d[\d,]*)\s*commits")
    out = []
    if stars and forks and stars >= 200 and forks / stars >= 0.35:
        out.append(f"forks/stars {forks}/{stars} — people are standing up their own copies, not bookmarking")
    if (contrib or 0) >= 5 and (commits or 0) >= 20:
        out.append(f"{contrib} contributors, {commits} commits/30d — maintained, others build on it")
    return "; ".join(out)


def editor_pick(f, voices=None):
    """The Standard (docs/STANDARD.md 1 & 3) as a single judgement call.

    A useful entry = verified pain x a nameable gap x a wedge open to the operator.
    Returns (pick, reason, score, extra) with extra carrying verdict/workload/gap/
    consumer_angle; (None, None, None, {}) if the model is unavailable -> the caller holds the
    candidate for the next run rather than shipping it unvetted."""
    if not _llm_key():
        return None, None, None, {}
    model = _llm_model()
    ev = ", ".join(f.get("evidence", []) or [])
    vq = "\n".join(f"- [{v.get('kind')}] {v.get('quote','')[:180]}" for v in (voices or [])) or "(none found)"
    bh = behaviour_signal(f)
    prompt = (
        "You are the editor of a board whose ONE job is to surface product opportunities a solo "
        "founder could copy and build now. Judge the project against this standard.\n\n"
        "A front-page entry needs ALL THREE:\n"
        " (1) VERIFIED PAIN — first-hand evidence real people want this: someone saying they'd pay, "
        "someone genuinely complaining, people forking it to run their own. Stars are attention, NOT "
        "demand. Repo age is irrelevant: an older project with real users beats a fresh star spike.\n"
        " (2) A GAP YOU CAN NAME IN ONE SENTENCE — one of: only geeks can use it (CLI/self-host, no "
        "product around the capability); the Chinese/local-market case is empty; it hits a real pain "
        "but solves it imperfectly.\n"
        " (3) A WEDGE OPEN TO A SOLO FOUNDER — NOT hardware manufacturing, NOT a burn-money-for-speed "
        "race, NOT anything needing BD/enterprise sales to start, NOT pure B2B internal tooling.\n\n"
        "'Someone already built it' is GOOD news — it is demand evidence. The window only closes if "
        "they have also served non-technical users well.\n"
        "Developer/agent-infra tools are NOT opportunities in themselves, only capability signals: "
        "they may reach the front page only if you can state the opportunity on the ordinary-person "
        "side — put that in consumer_angle. Ordinary-person products are preferred.\n"
        "HARD VETO (verdict='drop', score<=3), popularity is no defence: core value depends on abusing "
        "another service (mass account creation, CAPTCHA/rate-limit/ban evasion, temp-mail or SMS "
        "identity farms, reselling/proxying a paid API, credential or cookie pools, piracy, engagement "
        "farming, scraping personal data for resale, impersonation); or a renamed fork / thin wrapper "
        "with no substantive delta; or content dressed as product (awesome list, guide, course, prompt "
        "gallery, cosmetic skin). A legitimate tool that merely COULD be misused is fine.\n\n"
        "verdict:\n"
        "  'build'   = all three conditions hold, the gap is concrete, workload is 2w or 2m\n"
        "  'watch'   = pain is verified but the gap or the wedge is not clear yet, or workload is heavy\n"
        "  'archive' = worth keeping as evidence — a capability signal, a crowded family, or demand "
        "that is simply not verified yet\n"
        "  'drop'    = ONLY the hard veto above. NEVER drop something merely because you found no "
        "quote or no proof of demand: collection is wide and promotion is strict, so that case is "
        "'archive'. Fresh repos usually have no comments yet — that is 'archive', not 'drop'.\n"
        "score = is it worth BUILDING, 0-10, strictly: 10 once-a-month exceptional; 9 breakout with an "
        "open market; 8 strong with a visible weakness; 7 borderline; <=6 not front-page. An empty top "
        "tier is an acceptable outcome — do NOT inflate to fill the board.\n"
        "workload = '2w' (a solo dev + AI ships a usable version in two weeks) | '2m' (about two "
        "months) | 'no' (out of reach for one person).\n"
        "pain_verified = true if EITHER a quote below shows willingness to pay or real pain, OR the "
        "behavioural evidence shows people actually running and maintaining it.\n\n"
        f"Project: {f.get('title','')} - {f.get('claim','')}\n"
        f"What it does: {f.get('does') or f.get('why_good','')}\n"
        f"Signals: {ev}\nDomain: {f.get('domain','')}\n"
        f"First-hand quotes from issues/HN (may be empty):\n{vq}\n"
        f"Behavioural demand evidence (weaker than a quote, still first-hand): {bh or '(none)'}\n\n"
        "Reply with ONLY JSON: {\"verdict\":\"build|watch|archive|drop\", \"score\":0-10, "
        "\"workload\":\"2w|2m|no\", \"pain_verified\":true|false, "
        "\"gap\":\"one sentence: why it is not solved well yet\", "
        "\"consumer_angle\":\"the ordinary-person opportunity, or empty if it already is one\", "
        "\"reason\":\"one short sentence\"}")
    try:
        txt = _llm_chat(prompt, model=model, max_tokens=320, temperature=0, timeout=40)
        if txt is None:
            return None, None, None, {}
        obj = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        verdict = str(obj.get("verdict") or "").strip().lower()
        if verdict not in ("build", "watch", "archive", "drop"):
            verdict = "archive"
        sc = obj.get("score")
        sc = int(sc) if isinstance(sc, (int, float)) and 0 <= sc <= 10 else None
        wl = str(obj.get("workload") or "").strip().lower()
        wl = wl if wl in ("2w", "2m", "no") else None
        pain = bool(obj.get("pain_verified")) or bool(voices) or bool(bh)
        # The standard is enforced here, not in the model's goodwill.
        if verdict == "build" and (not pain or wl == "no"):
            verdict = "watch"          # top tier needs verified pain and a reachable wedge
        if verdict == "drop" and not integrity_veto(f):
            verdict = "archive"        # only the red line drops; thin demand is archived
        extra = {"verdict": verdict, "pain_verified": pain}
        if wl:
            extra["workload"] = wl
        for k in ("gap", "consumer_angle"):
            if obj.get(k):
                extra[k] = str(obj[k]).strip()[:300]
        return (verdict == "build"), str(obj.get("reason", ""))[:200], sc, extra
    except Exception as e:
        print(f"  [editor_pick skip: {e!r}]", file=sys.stderr)
        return None, None, None, {}


MARKS = load_marks()   # operator ⭐/❌ (docs/STANDARD.md 5)

def post_ideas(cands, scout, cap=6):
    """Write vetted startup-worthy ideas to the board (no predictions). Dedup by repo."""
    corpus = engine.load_corpus("findings")
    have = {(f.get("title") or (f.get("evidence") or [""])[0]) for f in corpus}
    posted = []
    for f in cands:
        if len(posted) >= cap:
            break
        try:
            key = f.get("title") or (f.get("evidence") or [""])[0]
            if key in have:
                continue
            # ---- quality is settled AT INGEST: copy + editorial gate BEFORE anything ships ----
            _veto = integrity_veto(f)
            if _veto:
                print(f"  \u2717 {_veto}: {f.get('title')}", file=sys.stderr)
                continue
            _score = f.get("score") or 0
            if _score >= 7:
                # first-hand demand quotes — mined only for candidates that already passed the
                # cheap gates (docs/STANDARD.md 4: mine late, mine cheap)
                voices = demand_voices(f)
                if voices:
                    f["voices"] = voices
                c = llm_copy(f)                  # README-grounded bilingual copy (retried + fallback model)
                if c is None:                    # never ship template copy — candidate retries next run
                    print(f"  [hold] llm_copy unavailable — {f.get('title')} retried next run", file=sys.stderr)
                    continue
                zh = (c.pop("i18n", None) or {}).get("zh") or {}
                f.update(c)
                if zh:
                    f.setdefault("i18n", {}).setdefault("zh", {}).update(zh)
                pk, why, esc, extra = editor_pick(f, voices)   # the Standard, as one call
                if pk is None:                   # model unavailable — never ship unvetted (STANDARD 3)
                    print(f"  [hold] editor_pick unavailable — {f.get('title')} retried next run", file=sys.stderr)
                    continue
                if extra:
                    f.update(extra)
                if extra.get("verdict") == "drop":
                    print(f"  ✗ dropped: {f.get('title')} — {why}", file=sys.stderr)
                    continue
                if pk is not None:
                    f["pick"] = pk
                    if why:
                        f["pick_reason"] = why
                if esc is not None:
                    if esc < 7:                  # the >=7 standard is enforced at the door, not post-hoc
                        print(f"  ✗ below bar ({esc}/10): {f.get('title')}", file=sys.stderr)
                        continue
                    f["score"] = esc
                f.setdefault("family", family_of(f))
                _mk = MARKS.get(f.get("title") or "")
                if _mk and _mk.get("mark") == "no":
                    # reference, not a rule (docs/STANDARD.md 5): surface it, never auto-score
                    f["similar_marked"] = {"mark": "no", "why": (_mk.get("why") or "")[:120]}
            body = idea_body(f)
            title = "idea: " + (f.get("title") or f["claim"][:50])
            url = None
            if DRY:
                number = 90000 + len(posted); print(f"  DRY idea: {f['claim'][:70]}")
            else:
                url = _gh_create(title, body, label="idea")
                number = int(url.rstrip("/").split("/")[-1]) if url else int(time.time())
            import datetime as _dt
            fid = f"{number}-{engine.slugify(f.get('title') or f['claim'])}"
            rec = dict(f)
            rec.update({"id": fid, "agent": scout,
                        "posted_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"})
            if not DRY:   # a dry run must never leave 9000x-id artifacts in the corpus
                os.makedirs("findings", exist_ok=True)
                json.dump(rec, open(f"findings/{fid}.json", "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)
            if url and not DRY:
                with open("comment.md", "w", encoding="utf-8") as fh:
                    fh.write(f"💡 added to the Idea board: **{f.get('title','')}** — {f.get('why_good','')[:160]}")
                _gh_comment(number)
            have.add(key)
            posted.append((scout, f.get("title"), url or f"(dry {number})"))
            print(f"  ✓ idea [{scout}] {f.get('title')}")
        except Exception as e:
            print(f"  [skip one] {e!r}", file=sys.stderr)
            continue
    # A 0-posted run with a dead model is an OUTAGE, not a dry spell — fail loudly so it
    # cannot hide behind a green check for days (docs/STANDARD.md 0: missing an item is cheap,
    # a frozen board is not). SCOUT_STRICT=0 downgrades this to an annotation.
    if LLM_DEAD and not posted:
        note = llm_down_note()
        print(f"::error::{note}", file=sys.stderr)
        if os.environ.get("SCOUT_STRICT", "1") == "1" and not DRY:
            raise SystemExit(78)
    return posted

def post_predictions(cands, scout, cap=3):
    """Log falsifiable predictions as findings (status=pending) + open a public issue.
    No barter/similarity — value comes later when the resolver grades them."""
    corpus = engine.load_corpus("findings")
    open_targets = {(f.get("prediction") or {}).get("target_id")
                    for f in corpus if f.get("status") == "pending"}
    posted = []
    for f in cands:
        if len(posted) >= cap:
            break
        try:
            pred = f.get("prediction") or {}
            if not pred.get("target_id") or pred["target_id"] in open_targets:
                continue  # already an open call on this subject
            body = prediction_body(f)
            title = "prediction: " + f["claim"][:64].strip()
            url = None
            if DRY:
                number = 90000 + len(posted); print(f"  DRY predict: {f['claim'][:72]}")
            else:
                url = _gh_create(title, body, label="prediction")
                number = int(url.rstrip("/").split("/")[-1]) if url else int(time.time())
            import datetime as _dt
            fid = f"{number}-{engine.slugify(f['claim'])}"
            rec = dict(f)
            rec.update({"id": fid, "agent": scout,
                        "posted_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                        "status": "pending", "observed": None, "resolved_at": None})
            os.makedirs("findings", exist_ok=True)
            json.dump(rec, open(f"findings/{fid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            if url and not DRY:
                hits, tot = _agent_accuracy(corpus, scout)
                acc = f"{round(100*hits/tot)}% ({hits}/{tot})" if tot else "no track record yet — this is how it starts"
                with open("comment.md", "w", encoding="utf-8") as fh:
                    fh.write(f"⏳ **prediction logged** — auto-resolves **{pred.get('resolve_on')}** by re-checking "
                             f"`{pred.get('metric')} {pred.get('op')} {pred.get('target')}`.\n\n_{scout} track record: {acc}._")
                _gh_comment(number)
            open_targets.add(pred["target_id"])
            posted.append((scout, f["claim"], url or f"(dry {number})"))
            print(f"  ✓ predicted [{scout}] {f['claim'][:70]}")
        except Exception as e:
            print(f"  [skip one] {e!r}", file=sys.stderr)
            continue
    return posted

def refresh():
    """Rebuild feed.json + clusters + scoreboard — used by workflow commit steps and the
    resolver so the conflict-safe feed regeneration never drops derived views."""
    engine.rebuild_feed("findings")
    rebuild_clusters()
    rebuild_scoreboard()

def emit(candidates, scout, cap=3):
    """Dedup, open a real finding issue, let the engine pay + record it. Returns posted list."""
    corpus = engine.load_corpus("findings")
    posted = []
    for f in candidates:
        if len(posted) >= cap:
            break
        try:
            if not f.get("claim") or len(f["claim"]) < 12:
                continue
            _, nov, _ = engine.rank(f, corpus)
            if corpus and nov < MIN_NOVELTY:
                continue  # already known to the commons
            body = finding_to_body(f)
            title = "finding: " + f["claim"][:60].strip()
            url = None
            if DRY:
                number = 90000 + len(posted)
                print(f"  DRY would post: {title}")
            else:
                url = _gh_create(title, body)
                number = int(url.rstrip("/").split("/")[-1]) if url else int(time.time())
            res = engine.run(body, number, scout, findings_dir="findings")
            if res.get("ok"):
                with open("comment.md", "w", encoding="utf-8") as fh:
                    fh.write(res["comment"])
                if url:
                    _gh_comment(number)
                corpus = engine.load_corpus("findings")   # include what we just posted
                posted.append((scout, f["claim"], url or f"(dry {number})"))
                print(f"  ✓ posted [{scout}] {f['claim'][:70]}")
        except Exception as e:
            print(f"  [skip one] {e!r}", file=sys.stderr)
            continue
    try:
        rebuild_clusters()
    except Exception as e:
        print(f"  [clusters skip] {e!r}", file=sys.stderr)
    return posted


def translate_zh(f, fields=("claim", "hook", "why_good", "value", "risk")):
    """Translate the given English card fields to Simplified Chinese via GitHub Models.
    PRESERVES the English (adds a translation, never rewrites). Returns {field: zh}
    for the requested fields, {} if nothing to do, or None on model failure/quota."""
    if not _llm_key():
        return None
    src = {k: f.get(k) for k in fields if f.get(k)}
    if not src:
        return {}
    model = _llm_model()
    prompt = (
        "Translate each value below into fluent, natural Simplified Chinese for a Chinese "
        "startup/developer audience. Keep product, repo, company and tech names in Latin "
        "script (e.g. GitHub, Figma, Claude Code, Codex). Be faithful but idiomatic, not "
        "word-for-word. Reply with ONLY a JSON object using the SAME keys.\n\n"
        + json.dumps(src, ensure_ascii=False))
    try:
        txt = _llm_chat(prompt, model=model, max_tokens=900, temperature=0.3)
        if txt is None:
            return None
        m = re.search(r"\{.*\}", txt, re.S)
        obj = json.loads(m.group(0))
        return {k: str(obj[k]).strip()[:400] for k in src if obj.get(k)}
    except Exception as e:
        print(f"  [translate_zh skip: {e!r}]", file=sys.stderr)
        return None


def translate_missing(cap=8):
    """Hourly bilingual safety-net: find findings whose i18n.zh is missing/incomplete and
    fill it in — newest first so fresh items get translated fast. Idempotent (skips already
    complete), capped per run so it never bursts the free GitHub Models quota; on quota
    exhaustion it stops cleanly and the next run continues. Writes findings/*.json only;
    the workflow rebuilds feed.json."""
    import glob
    recs = []
    for p in sorted(glob.glob("findings/*.json")):
        if os.path.basename(p) == "feed.json":
            continue
        try:
            recs.append((p, json.load(open(p, encoding="utf-8"))))
        except Exception:
            pass
    recs.sort(key=lambda x: x[1].get("posted_at", ""), reverse=True)
    done = 0
    for p, f in recs:
        if done >= cap:
            break
        z = (f.get("i18n") or {}).get("zh") or {}
        need = [k for k in ("claim", "hook", "why_good", "value", "risk") if f.get(k) and not z.get(k)]
        if not need:
            continue
        tr = translate_zh(f, tuple(need))
        if tr is None:
            print("  [translate_missing] model limited — stopping (next run continues)", file=sys.stderr)
            break
        if not tr:
            continue
        f.setdefault("i18n", {}).setdefault("zh", {}).update(tr)
        json.dump(f, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        done += 1
        print(f"  译 {(f.get('title') or f.get('id') or '')[:46]} -> {list(tr)}")
        time.sleep(2)
    print(f"translated={done}")
    return done


_TPL_VALUES = {
    "infra every AI product needs — monetizes as a usage-based API + a hosted/managed tier",
    "a finished workflow prosumers pay a monthly seat for, with a team upsell",
    "on-device kills cloud cost and unlocks privacy-regulated buyers who pay a premium",
    "first to productize the method captures the teams who can't reproduce it themselves",
    "people already spend time/tools on this — a product turns that into subscription revenue",
    "a clear paid wedge if it owns one workflow end-to-end",
}
_TPL_RISK_PREFIX = ("could be a feature, not a company", "already a crowded race")

def needs_copy(f):
    """Detect idea findings still carrying the scout's heuristic template copy."""
    if f.get("does") or f.get("prediction") or f.get("status") == "pending":
        return False
    if not isinstance(f.get("score"), (int, float)):
        return False
    risk = (f.get("risk") or "").strip().lower()
    if any(risk.startswith(t) for t in _TPL_RISK_PREFIX):
        return True
    if (f.get("value") or "").strip() in _TPL_VALUES:
        return True
    why = f.get("why_good") or ""
    return bool(re.search(r"forks \(\d+% of stars\)|commits/30d|★/day|^[\d,]+★, [\d,]+ forks", why))

def copy_fill(cap=6):
    """Hourly self-healing: any idea still showing heuristic template copy (e.g. the model
    was rate-limited at ingest) gets the README-grounded bilingual copy — newest first,
    capped per run, stops cleanly on quota so the next run continues."""
    import glob
    recs = []
    for p in sorted(glob.glob("findings/*.json")):
        if os.path.basename(p) == "feed.json":
            continue
        try:
            recs.append((p, json.load(open(p, encoding="utf-8"))))
        except Exception:
            pass
    recs.sort(key=lambda x: x[1].get("posted_at", ""), reverse=True)
    done = 0
    for p, f in recs:
        if done >= cap:
            break
        if not needs_copy(f):
            continue
        c = llm_copy(f)
        if c is None:
            print("  [copy_fill] model limited — stopping (next run continues)", file=sys.stderr)
            break
        zh = (c.pop("i18n", None) or {}).get("zh") or {}
        f.update(c)
        if zh:
            f.setdefault("i18n", {}).setdefault("zh", {}).update(zh)
        json.dump(f, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        done += 1
        print(f"  ✍ re-copy {(f.get('title') or f.get('id') or '')[:46]}")
        time.sleep(2)
    print(f"copy_filled={done}")
    return done


SEO_SITE_BASE = "https://zqf1314.github.io/idea/"

def _seo_url(f):
    for e in (f.get("evidence") or []):
        if isinstance(e, str) and e.startswith("http"):
            return e
    t = f.get("title") or ""
    if "/" in t and " " not in t and not t.startswith("http"):
        return "https://github.com/" + t
    return SEO_SITE_BASE

def _seo_esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def build_seo(base=None):
    """Regenerate crawlable SEO/GEO content — JSON-LD (WebSite + ItemList of every idea)
    plus a <noscript> text list — between <!--SEO:START--> and <!--SEO:END--> in both
    index.html files, and (re)write sitemap.xml. Static + deterministic (stable order so
    unchanged data => byte-identical => no spurious commits); needs no network."""
    base = base or SEO_SITE_BASE
    path = "findings/feed.json"
    if not os.path.exists(path):
        return 0
    feed = json.load(open(path, encoding="utf-8"))
    items = [f for f in (feed.get("findings") or [])
             if (f.get("title") or f.get("claim")) and f.get("status") != "pending"]
    items.sort(key=lambda f: ((f.get("score") or 0), f.get("posted_at", "")), reverse=True)
    items = items[:200]
    li, arts = [], []
    for i, f in enumerate(items, 1):
        title = (f.get("title") or f.get("claim") or "")[:120]
        desc = (f.get("why_good") or f.get("claim") or "")[:240]
        url = _seo_url(f)
        li.append({"@type": "ListItem", "position": i,
                   "item": {"@type": "SoftwareApplication", "name": title, "description": desc,
                            "url": url, "applicationCategory": "DeveloperApplication"}})
        arts.append(f'<article><h3><a href="{_seo_esc(url)}">{_seo_esc(title)}</a></h3>'
                    f'<p>{_seo_esc(desc)}</p></article>')
    website = {"@context": "https://schema.org", "@type": "WebSite", "name": "Idea", "url": base,
               "description": "A live, hourly board of promising open-source projects, AI agents, "
                              "developer tools and Claude/MCP skills worth building."}
    itemlist = {"@context": "https://schema.org", "@type": "ItemList", "name": "Ideas worth building",
                "url": base, "numberOfItems": len(li), "itemListElement": li}
    block = ("<!--SEO:START-->"
             '<script type="application/ld+json">' + json.dumps(website, ensure_ascii=False) + "</script>"
             '<script type="application/ld+json">' + json.dumps(itemlist, ensure_ascii=False) + "</script>"
             '<noscript><section id="ideas-index">'
             '<h1>Ideas worth building — open-source projects, AI tools and skills</h1>'
             '<p>An hourly-updated board of promising open-source projects, AI agents, developer '
             'tools and Claude/MCP skills from GitHub, Show HN and Product Hunt.</p>'
             + "".join(arts) +
             "</section></noscript>"
             "<!--SEO:END-->")
    n = 0
    for fp in ("index.html", "site/index.html"):
        if not os.path.exists(fp):
            continue
        s = open(fp, encoding="utf-8").read()
        new = re.sub(r"<!--SEO:START-->.*?<!--SEO:END-->", lambda m: block, s, count=1, flags=re.S)
        if new != s:
            open(fp, "w", encoding="utf-8").write(new)
            n += 1
    gen = feed.get("generated_at") or ""
    lastmod = gen[:10] if gen else ""
    sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          f'  <url><loc>{base}</loc>'
          + (f'<lastmod>{lastmod}</lastmod>' if lastmod else '')
          + '<changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
          '</urlset>\n')
    open("sitemap.xml", "w", encoding="utf-8").write(sm)
    return n
