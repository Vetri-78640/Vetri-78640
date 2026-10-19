"""Render the two language donut cards in greyscale.

github-profile-summary-cards draws its donut slices from a hardcoded GitHub
language-colour map, and no theme parameter overrides them, so the stock cards
are always coloured. These reproduce the same two queries and the same 340x200
layout, with a white-to-grey ramp instead.
"""
import json
import math
import os
import sys
import urllib.request

API = "https://api.github.com/graphql"
USER = os.environ.get("GH_USERNAME", "Vetri-78640")
TOKEN = os.environ["GH_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

BG, BORDER, TITLE, TEXT = "#0d1117", "#30363d", "#ffffff", "#b1bac4"
RAMP = ["#ffffff", "#c9c9c9", "#9e9e9e", "#787878", "#565656"]
FONT = "'Segoe UI', Ubuntu, \"Helvetica Neue\", Sans-Serif"


def query(q, **vars):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": q, "variables": vars}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def repos_per_language():
    counts, cursor = {}, None
    while True:
        d = query(
            """query($login:String!,$cursor:String){user(login:$login){
                 repositories(isFork:false,privacy:PUBLIC,first:100,after:$cursor,ownerAffiliations:OWNER){
                   nodes{primaryLanguage{name}} pageInfo{endCursor hasNextPage}}}}""",
            login=USER, cursor=cursor,
        )["user"]["repositories"]
        for n in d["nodes"]:
            if n["primaryLanguage"]:
                counts[n["primaryLanguage"]["name"]] = counts.get(n["primaryLanguage"]["name"], 0) + 1
        if not d["pageInfo"]["hasNextPage"]:
            return counts
        cursor = d["pageInfo"]["endCursor"]


def commits_per_language():
    years = query(
        "query($login:String!){user(login:$login){contributionsCollection{contributionYears}}}",
        login=USER,
    )["user"]["contributionsCollection"]["contributionYears"]
    counts = {}
    for y in years:
        d = query(
            """query($login:String!,$from:DateTime,$to:DateTime){user(login:$login){
                 contributionsCollection(from:$from,to:$to){
                   commitContributionsByRepository(maxRepositories:100){
                     repository{isPrivate primaryLanguage{name}} contributions{totalCount}}}}}""",
            login=USER, **{"from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]["commitContributionsByRepository"]
        for n in d:
            lang = n["repository"]["primaryLanguage"]
            if lang and not n["repository"]["isPrivate"]:
                counts[lang["name"]] = counts.get(lang["name"], 0) + n["contributions"]["totalCount"]
    return counts


def arc(cx, cy, r_out, r_in, a0, a1):
    """Donut segment path. Angles in radians, clockwise from 12 o'clock."""
    def pt(r, a):
        return f"{cx + r * math.sin(a):.3f},{cy - r * math.cos(a):.3f}"
    big = 1 if (a1 - a0) > math.pi else 0
    return (
        f"M{pt(r_out, a0)}A{r_out},{r_out},0,{big},1,{pt(r_out, a1)}"
        f"L{pt(r_in, a1)}A{r_in},{r_in},0,{big},0,{pt(r_in, a0)}Z"
    )


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(title, counts):
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in top) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="200" viewBox="0 0 340 200">',
        f"<style>* {{ font-family: {FONT} }}</style>",
        f'<rect x="1" y="1" rx="5" ry="5" width="338" height="198" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>',
        f'<text x="30" y="40" font-size="22px" fill="{TITLE}">{esc(title)}</text>',
        '<g transform="translate(0,40)">',
    ]
    for i, (name, _) in enumerate(top):
        y = 18 + 25.2 * i
        parts.append(
            f'<rect x="40" y="{y:.1f}" width="14" height="14" fill="{RAMP[i]}" stroke="{BG}" stroke-width="1"/>'
            f'<text x="56.8" y="{y + 12:.1f}" font-size="14px" fill="{TEXT}">{esc(name)}</text>'
        )
    a = 0.0
    for i, (_, v) in enumerate(top):
        a1 = a + 2 * math.pi * v / total
        # A full circle is degenerate as an arc; draw it as two rings instead.
        d = arc(230, 80, 60, 35, a, a1 if len(top) > 1 else math.pi) if len(top) > 1 else None
        if d is None:
            parts.append(
                f'<circle cx="230" cy="80" r="47.5" fill="none" stroke="{RAMP[i]}" stroke-width="25"/>'
            )
        else:
            parts.append(f'<path d="{d}" fill="{RAMP[i]}" stroke="{BG}" stroke-width="1"/>')
        a = a1
    parts.append("</g></svg>")
    return "".join(parts)


os.makedirs(OUT, exist_ok=True)
for fname, title, data in [
    ("top-languages-by-repo.svg", "Top Languages by Repo", repos_per_language()),
    ("top-languages-by-commit.svg", "Top Languages by Commit", commits_per_language()),
]:
    svg = card(title, data)
    with open(os.path.join(OUT, fname), "w") as f:
        f.write(svg)
    print(f"{fname}: {len(svg)} bytes")
