"""retrievalscore —— 给检索结果排一个能逐项复核的序。

设计原则：
1. **分数必须拆开**。只给一个总分的重排器没法排查问题。
2. **规则写在配置里**。权重、来源可信度、时效衰减都能改，改完立刻生效。
3. **不打分无理由**。查不到就明说查不到，不给一个编出来的分数。

三项分：查询覆盖 / 来源可信度 / 新鲜度。

仅依赖 Python 标准库。

用法:
    python retrievalscore.py --help
    python retrievalscore.py --query "时间戳格式" --candidates results.json
    python retrievalscore.py --query "..." --candidates results.json --json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "weights": {"coverage": 0.5, "credibility": 0.3, "freshness": 0.2},
    # 来源可信度分级：域名 → 分值（0~1）。未列出的来源给 default。
    "credibility": {
        "default": 0.5,
        "docs.python.org": 0.95,
        "arxiv.org": 0.9,
        "github.com": 0.85,
        "stackoverflow.com": 0.8,
        "wikipedia.org": 0.7,
        "blog.example.com": 0.4,
    },
    # 新鲜度半衰期（天）。越大越看重新内容。
    "freshness_half_life_days": 180,
    # 新鲜度下限，避免老文档被判成 0 分
    "freshness_floor": 0.1,
}

# 中文停用词：分词时排除，否则「的」「了」会虚高覆盖率
STOPWORDS = set(
    "的 了 和 与 或 在 是 为 对 从 到 也 就 都 而 及 其 这 那 什么 怎么 如何 一个 可以 需要 使用 时 中 有 不 我 你 他".split()
)

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]+")


def tokenize(text: str) -> list[str]:
    """切词。中文按 2-gram 切（够用且不需要词典），英文按单词切。"""
    text = (text or "").lower()
    tokens: list[str] = []
    for m in TOKEN_RE.finditer(text):
        tok = m.group(0)
        if re.fullmatch(r"[A-Za-z0-9_]+", tok):
            if tok not in STOPWORDS and len(tok) > 1:
                tokens.append(tok)
        else:
            # 中文：单字 + 双字组合
            if len(tok) == 1:
                if tok not in STOPWORDS:
                    tokens.append(tok)
                continue
            for i in range(len(tok) - 1):
                bigram = tok[i:i + 2]
                if bigram not in STOPWORDS:
                    tokens.append(bigram)
    return tokens


def coverage_score(query_tokens: list[str], doc_text: str) -> tuple[float, list[str]]:
    """查询词覆盖率。返回 (得分, 命中的词)。"""
    if not query_tokens:
        return 0.0, []
    doc_tokens = set(tokenize(doc_text))
    hits = [t for t in dict.fromkeys(query_tokens) if t in doc_tokens]
    return len(hits) / len(set(query_tokens)), hits


def credibility_score(url: str, config: dict) -> tuple[float, str]:
    """来源可信度。按域名最长匹配。"""
    table = config.get("credibility", {})
    domain = ""
    m = re.match(r"https?://([^/:]+)", url or "")
    if m:
        domain = m.group(1).lower()
    best = None
    best_key = ""
    for key, val in table.items():
        if key == "default":
            continue
        if domain == key or domain.endswith("." + key):
            if best is None or len(key) > len(best_key):
                best, best_key = val, key
    if best is None:
        return float(table.get("default", 0.5)), "未登记的来源"
    return float(best), best_key


def freshness_score(timestamp: float | None, now: float,
                   config: dict) -> tuple[float, str]:
    """新鲜度。按半衰期指数衰减，并保留下限。"""
    if not timestamp:
        return float(config.get("freshness_floor", 0.1)), "无时间戳"
    half_life = float(config.get("freshness_half_life_days", 180)) * 86400
    age = max(0.0, now - float(timestamp))
    score = 0.5 ** (age / half_life)
    score = float(config.get("freshness_floor", 0.1)) + \
        (1.0 - float(config.get("freshness_floor", 0.1))) * score
    days = age / 86400
    return score, f"{days:.0f} 天前"


def score_candidate(query: str, cand: dict, config: dict,
                    now: float) -> dict:
    """给一条候选打分，返回分数构成。"""
    q_tokens = tokenize(query)
    text = " ".join(str(cand.get(k, "")) for k in ("title", "text", "snippet"))
    cov, hits = coverage_score(q_tokens, text)
    cred, cred_src = credibility_score(str(cand.get("url", "")), config)
    fresh, fresh_note = freshness_score(cand.get("timestamp"), now, config)

    weights = config.get("weights", {})
    total = (float(weights.get("coverage", 0)) * cov
             + float(weights.get("credibility", 0)) * cred
             + float(weights.get("freshness", 0)) * fresh)

    return {
        "title": cand.get("title", ""),
        "url": cand.get("url", ""),
        "total": round(total, 4),
        "parts": {
            "coverage": {"score": round(cov, 4), "weight": weights.get("coverage", 0),
                         "matched": hits[:8],
                         "detail": f"命中 {len(set(hits))}/{len(set(q_tokens))} 个查询词"},
            "credibility": {"score": round(cred, 4), "weight": weights.get("credibility", 0),
                            "detail": f"来源 {cred_src}"},
            "freshness": {"score": round(fresh, 4), "weight": weights.get("freshness", 0),
                          "detail": fresh_note},
        },
    }


def rank(query: str, candidates: list[dict], config: dict,
         now: float | None = None) -> list[dict]:
    """给候选列表排序，返回带分数构成的列表。"""
    now = now if now is not None else time.time()
    scored = [score_candidate(query, c, config, now) for c in candidates]
    scored.sort(key=lambda x: (-x["total"], x["url"]))
    for i, item in enumerate(scored, 1):
        item["rank"] = i
    return scored


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(results: list[dict]) -> str:
    if not results:
        return "候选列表是空的。"
    out: list[str] = []
    for r in results:
        out.append(f"#{r['rank']}  {r['total']:.4f}  {r['title']}")
        out.append(f"    {r['url']}")
        p = r["parts"]
        out.append(f"    覆盖 {p['coverage']['score']:.3f} × {p['coverage']['weight']}"
                   f"   {p['coverage']['detail']}")
        out.append(f"    可信 {p['credibility']['score']:.3f} × {p['credibility']['weight']}"
                   f"   {p['credibility']['detail']}")
        out.append(f"    新鲜 {p['freshness']['score']:.3f} × {p['freshness']['weight']}"
                   f"   {p['freshness']['detail']}")
        out.append("")
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="retrievalscore",
        description="给检索结果排一个可解释的序（仅依赖标准库）",
        epilog=(
            "候选文件是 JSON 数组，每项可含 title / text / url / timestamp：\n"
            "  [{\"title\":\"...\",\"url\":\"https://...\",\"timestamp\":1760000000}]\n"
            "  python retrievalscore.py --query '时间戳格式' --candidates results.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--query", required=True, help="查询词")
    ap.add_argument("--candidates", required=True, help="候选列表 JSON 文件")
    ap.add_argument("--config", help="规则配置 JSON 文件（覆盖默认权重与可信度表）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    config = dict(DEFAULT_CONFIG)
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            print(f"读不了配置文件：{e}", file=sys.stderr)
            return 2

    try:
        with open(args.candidates, "r", encoding="utf-8") as f:
            candidates = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"读不了候选文件：{e}", file=sys.stderr)
        return 2

    if not isinstance(candidates, list):
        print("候选文件应该是一个 JSON 数组。", file=sys.stderr)
        return 2

    results = rank(args.query, candidates, config)

    if args.json:
        print(json.dumps({"query": args.query, "results": results},
                         ensure_ascii=False, indent=2))
        return 0
    print(render(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
