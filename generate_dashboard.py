#!/usr/bin/env python3
"""
SOA Pyxis-OP — Générateur de tableau de bord de veille stratégique
Exécuté chaque lundi à 07h00 (CEST) via GitHub Actions
"""

import feedparser
import html as html_lib
import time
import re
from datetime import datetime, timezone
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# CONFIGURATION — Modifier ici pour ajouter/retirer des sources
# ══════════════════════════════════════════════════════════════

AXES = [
    {
        "id": "oplit",
        "label": "Oplit",
        "sublabel": "ALERTE PRIORITAIRE — Financé par Vi Partners (CH), cible Suisse, déjà chez Vaucher Manufacture",
        "color": "#ef4444",
        "accent": "239,68,68",
        "icon": "⚠",
        "max_items": 6,
        "feeds": [
            ("https://news.google.com/rss/search?q=Oplit+planification+industrie&hl=fr&gl=FR&ceid=FR:fr", "Google News FR"),
            ("https://news.google.com/rss/search?q=Oplit+manufacturing&hl=en&gl=CH&ceid=CH:en", "Google News CH"),
            ("https://news.google.com/rss/search?q=Oplit+ordonnancement+Suisse&hl=fr&gl=CH&ceid=CH:fr", "Google News CH-FR"),
        ],
    },
    {
        "id": "aps",
        "label": "APS — Concurrents directs",
        "sublabel": "DELMIA Ortems · Siemens Opcenter APS · Visual Planning · Planilog · Asprova · ROB-EX",
        "color": "#f59e0b",
        "accent": "245,158,11",
        "icon": "◈",
        "max_items": 8,
        "feeds": [
            ("https://news.google.com/rss/search?q=DELMIA+Ortems+planification+ordonnancement&hl=fr&gl=FR&ceid=FR:fr", "Ortems / Dassault"),
            ("https://news.google.com/rss/search?q=Siemens+Opcenter+APS+scheduling&hl=en&gl=US&ceid=US:en", "Siemens Opcenter"),
            ("https://news.google.com/rss/search?q=%22Visual+Planning%22+production+industrie&hl=fr&gl=FR&ceid=FR:fr", "Visual Planning"),
            ("https://news.google.com/rss/search?q=Planilog+ordonnancement+production&hl=fr&gl=FR&ceid=FR:fr", "Planilog"),
            ("https://news.google.com/rss/search?q=Asprova+APS+planning&hl=en&gl=US&ceid=US:en", "Asprova"),
        ],
    },
    {
        "id": "erp",
        "label": "ERP — Marché suisse & risques de substitution",
        "sublabel": "Abacus · SAP Business One · Microsoft Dynamics 365 · Sage X3 · Odoo · Epicor",
        "color": "#3b82f6",
        "accent": "59,130,246",
        "icon": "◉",
        "max_items": 7,
        "feeds": [
            ("https://news.google.com/rss/search?q=Abacus+ERP+Suisse+production+planning&hl=fr&gl=CH&ceid=CH:fr", "Abacus CH"),
            ("https://news.google.com/rss/search?q=SAP+Business+One+PME+Suisse&hl=fr&gl=CH&ceid=CH:fr", "SAP B1 CH"),
            ("https://news.google.com/rss/search?q=Microsoft+Dynamics+365+industrie+Suisse&hl=fr&gl=CH&ceid=CH:fr", "MS Dynamics CH"),
            ("https://news.google.com/rss/search?q=Odoo+manufacturing+Suisse&hl=fr&gl=CH&ceid=CH:fr", "Odoo CH"),
            ("https://news.google.com/rss/search?q=Sage+X3+industrie+planification&hl=fr&gl=FR&ceid=FR:fr", "Sage X3"),
        ],
    },
    {
        "id": "marche",
        "label": "Marché — PME industrielle suisse",
        "sublabel": "Swissmem · KOF · CVCI · GIM · Industrie romande · Conjoncture",
        "color": "#06b6d4",
        "accent": "6,182,212",
        "icon": "⬡",
        "max_items": 8,
        "feeds": [
            ("https://news.google.com/rss/search?q=PME+industrielle+Suisse+production+digitalisation&hl=fr&gl=CH&ceid=CH:fr", "PME industrielle CH"),
            ("https://news.google.com/rss/search?q=Swissmem+industrie+conjoncture&hl=fr&gl=CH&ceid=CH:fr", "Swissmem"),
            ("https://news.google.com/rss/search?q=industrie+suisse+romande+agilite+planification&hl=fr&gl=CH&ceid=CH:fr", "Industrie romande"),
            ("https://news.google.com/rss/search?q=KOF+conjoncture+industrie+suisse&hl=fr&gl=CH&ceid=CH:fr", "KOF ETH"),
            ("https://news.google.com/rss/search?q=CVCI+GIM+industrie+Vaud+Neuchatel&hl=fr&gl=CH&ceid=CH:fr", "CVCI / GIM"),
        ],
    },
    {
        "id": "tech",
        "label": "Tech & IA — Planification industrielle",
        "sublabel": "AI scheduling · Industry 4.0 · GenAI manufacturing · APS trends 2025",
        "color": "#10b981",
        "accent": "16,185,129",
        "icon": "✦",
        "max_items": 6,
        "feeds": [
            ("https://news.google.com/rss/search?q=intelligence+artificielle+planification+production+industrie&hl=fr&gl=FR&ceid=FR:fr", "IA planification FR"),
            ("https://news.google.com/rss/search?q=AI+advanced+planning+scheduling+manufacturing&hl=en&gl=US&ceid=US:en", "AI APS EN"),
            ("https://news.google.com/rss/search?q=GenAI+ERP+manufacturing+planning+2025&hl=en&gl=US&ceid=US:en", "GenAI ERP"),
            ("https://news.google.com/rss/search?q=agilite+operationnelle+industrie+PME&hl=fr&gl=FR&ceid=FR:fr", "Agilité opérationnelle"),
        ],
    },
]

MAX_AGE_DAYS = 14  # Articles plus vieux que N jours ignorés

# ══════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════

def strip_tags(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def parse_date(entry):
    for attr in ('published_parsed', 'updated_parsed'):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def age_label(days):
    if days == 0:
        return "Aujourd'hui", "#10b981"
    elif days == 1:
        return "Hier", "#10b981"
    elif days <= 3:
        return f"{days} jours", "#06b6d4"
    elif days <= 7:
        return f"{days} jours", "#f59e0b"
    else:
        return f"{days} jours", "#94a3b8"

MONTHS_FR = ["jan", "fév", "mar", "avr", "mai", "juin",
             "juil", "août", "sep", "oct", "nov", "déc"]

def fmt_date(dt):
    return f"{dt.day} {MONTHS_FR[dt.month - 1]} {dt.year}"

# ══════════════════════════════════════════════════════════════
# COLLECTE
# ══════════════════════════════════════════════════════════════

def fetch_feed(url, source_label):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Pyxis-OP SOA/1.0"})
        now = datetime.now(timezone.utc)
        for entry in feed.entries[:12]:
            pub = parse_date(entry)
            age = (now - pub).days
            if age > MAX_AGE_DAYS:
                continue
            title = strip_tags(entry.get("title", ""))
            link  = entry.get("link", "#")
            summary = strip_tags(entry.get("summary", ""))
            # Google News wraps real URL — keep as-is, it redirects fine
            if title:
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary[:180],
                    "source": source_label,
                    "date": pub,
                    "age": age,
                })
    except Exception as exc:
        print(f"  ⚠  {source_label}: {exc}")
    return articles

def collect_axis(axis):
    all_items, seen = [], set()
    for url, label in axis["feeds"]:
        for art in fetch_feed(url, label):
            key = art["title"].lower()[:70]
            if key not in seen:
                seen.add(key)
                all_items.append(art)
        time.sleep(0.6)
    all_items.sort(key=lambda x: x["date"], reverse=True)
    return all_items[:axis["max_items"]]

# ══════════════════════════════════════════════════════════════
# GÉNÉRATION HTML
# ══════════════════════════════════════════════════════════════

def render_article(art):
    age_txt, age_color = age_label(art["age"])
    title   = html_lib.escape(art["title"])
    link    = html_lib.escape(art["link"])
    source  = html_lib.escape(art["source"])
    summary = html_lib.escape(art["summary"])
    date_s  = fmt_date(art["date"])
    return f"""
        <a class="card" href="{link}" target="_blank" rel="noopener noreferrer">
          <div class="card-top">
            <span class="card-source">{source}</span>
            <span class="card-age" style="color:{age_color}">{age_txt}</span>
          </div>
          <div class="card-title">{title}</div>
          {"" if not summary else f'<div class="card-summary">{summary}…</div>'}
          <div class="card-date">{date_s}</div>
        </a>"""

def render_section(axis, articles):
    n = len(articles)
    count_s = f"{n} article{'s' if n != 1 else ''}"
    cards = "".join(render_article(a) for a in articles) if articles else \
        '<p class="empty">Aucun article trouvé cette semaine pour cet axe.</p>'
    return f"""
    <section class="axis" id="{axis['id']}">
      <div class="axis-hd" style="border-left:3px solid {axis['color']}">
        <div class="axis-hd-row">
          <h2 class="axis-title">
            <span class="axis-icon" style="color:{axis['color']}">{axis['icon']}</span>
            {html_lib.escape(axis['label'])}
          </h2>
          <span class="axis-count" style="background:rgba({axis['accent']},0.12);color:{axis['color']}">{count_s}</span>
        </div>
        <p class="axis-sub">{html_lib.escape(axis['sublabel'])}</p>
      </div>
      <div class="cards-grid">{cards}</div>
    </section>"""

def build_nav(axes):
    items = ""
    for ax in axes:
        items += f'<a class="nav-ax" href="#{ax["id"]}" style="--c:{ax["color"]}">{ax["icon"]} {html_lib.escape(ax["label"])}</a>\n'
    return items

def generate(axes_data):
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%A %d %B %Y — %H:%M UTC").capitalize()

    # Compute global stats
    total_arts = sum(len(arts) for _, arts in axes_data)
    new_arts   = sum(1 for _, arts in axes_data for a in arts if a["age"] <= 2)

    sections = "".join(render_section(ax, arts) for ax, arts in axes_data)
    nav      = build_nav([ax for ax, _ in axes_data])

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SOA Pyxis-OP — Veille stratégique</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --dark:#0f172a; --dark2:#1e293b; --dark3:#1c2440;
  --white:#fff; --gray-300:#cbd5e1; --gray-400:#94a3b8;
  --gray-500:#64748b; --gray-600:#475569; --gray-800:#1e293b;
  --blue:#2563eb; --cyan:#06b6d4;
  --font:'Plus Jakarta Sans',-apple-system,sans-serif;
  --mono:'JetBrains Mono',monospace;
  --radius:12px; --radius-sm:8px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth;font-size:16px}}
body{{font-family:var(--font);background:var(--dark);color:var(--gray-300);-webkit-font-smoothing:antialiased;min-height:100vh}}

/* ── TOP BAR ── */
.topbar{{
  position:sticky;top:0;z-index:100;
  background:rgba(15,23,42,.92);backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(255,255,255,.06);
  padding:12px 40px;
  display:flex;align-items:center;justify-content:space-between;gap:24px;
}}
.topbar-logo{{font-size:1.1rem;font-weight:800;letter-spacing:-.02em;white-space:nowrap}}
.topbar-logo .p{{color:#fff}}.topbar-logo .dash{{color:var(--blue);font-weight:300}}.topbar-logo .op{{color:var(--blue)}}
.topbar-logo .tag{{font-family:var(--mono);font-size:.6rem;letter-spacing:.12em;color:var(--gray-500);display:block;margin-top:1px}}
.topbar-update{{font-family:var(--mono);font-size:.65rem;color:var(--gray-500);white-space:nowrap}}
.topbar-stats{{display:flex;gap:12px}}
.stat-pill{{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:.68rem;font-weight:600;font-family:var(--mono)}}

/* ── AXIS NAV ── */
.axis-nav{{
  display:flex;gap:8px;flex-wrap:wrap;
  padding:16px 40px;
  border-bottom:1px solid rgba(255,255,255,.04);
  background:rgba(15,23,42,.5);
}}
.nav-ax{{
  display:inline-flex;align-items:center;gap:6px;
  padding:6px 14px;border-radius:20px;
  font-size:.73rem;font-weight:600;text-decoration:none;
  border:1px solid rgba(255,255,255,.06);
  color:var(--gray-400);
  transition:all .2s;
}}
.nav-ax:hover{{color:var(--c);border-color:var(--c);background:rgba(255,255,255,.03)}}

/* ── MAIN ── */
main{{max-width:1280px;margin:0 auto;padding:40px 40px 80px}}

/* ── AXIS SECTION ── */
.axis{{margin-bottom:48px}}
.axis-hd{{padding:20px 20px 14px;margin-bottom:16px;background:rgba(255,255,255,.02);border-radius:var(--radius)}}
.axis-hd-row{{display:flex;align-items:center;gap:12px;margin-bottom:6px}}
.axis-icon{{font-size:1rem;width:20px;text-align:center}}
.axis-title{{font-size:1rem;font-weight:700;color:#fff}}
.axis-count{{font-size:.65rem;font-weight:700;font-family:var(--mono);padding:3px 9px;border-radius:12px}}
.axis-sub{{font-size:.72rem;color:var(--gray-500);padding-left:32px;line-height:1.5}}

/* ── CARDS ── */
.cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
.card{{
  display:block;text-decoration:none;
  background:var(--dark2);border:1px solid rgba(255,255,255,.05);
  border-radius:var(--radius-sm);padding:16px;
  transition:all .25s;
}}
.card:hover{{background:var(--dark3);border-color:rgba(255,255,255,.1);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.card-source{{font-family:var(--mono);font-size:.6rem;font-weight:500;color:var(--gray-500);letter-spacing:.06em;text-transform:uppercase}}
.card-age{{font-family:var(--mono);font-size:.6rem;font-weight:600}}
.card-title{{font-size:.84rem;font-weight:600;color:#e2e8f0;line-height:1.45;margin-bottom:8px}}
.card-summary{{font-size:.73rem;color:var(--gray-500);line-height:1.55;margin-bottom:8px}}
.card-date{{font-family:var(--mono);font-size:.6rem;color:var(--gray-600)}}
.empty{{font-size:.8rem;color:var(--gray-600);padding:24px 0;font-style:italic}}

/* ── FOOTER ── */
footer{{
  text-align:center;padding:24px 40px;
  border-top:1px solid rgba(255,255,255,.04);
  font-family:var(--mono);font-size:.62rem;color:var(--gray-600);
}}

@media(max-width:768px){{
  .topbar,.axis-nav,main{{padding-left:16px;padding-right:16px}}
  .topbar{{flex-wrap:wrap;gap:8px}}
  .topbar-update,.topbar-stats{{font-size:.6rem}}
}}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-logo">
    <span><span class="p">Pyxis</span><span class="dash">-</span><span class="op">OP</span></span>
    <span class="tag">TABLEAU DE BORD SOA · VEILLE STRATÉGIQUE</span>
  </div>
  <div class="topbar-stats">
    <span class="stat-pill" style="background:rgba(37,99,235,.12);color:#3b82f6">{total_arts} articles</span>
    <span class="stat-pill" style="background:rgba(16,185,129,.12);color:#10b981">{new_arts} récents (≤2j)</span>
  </div>
  <div class="topbar-update">Mis à jour le {now_str}</div>
</header>

<nav class="axis-nav">
{nav}
</nav>

<main>
{sections}
</main>

<footer>
  Pyxis-OP Agility Sàrl · La Chaux-de-Fonds, Suisse ·
  Données issues de flux RSS publics · Mise à jour automatique chaque lundi 07h00 CEST ·
  Généré le {now.strftime("%d.%m.%Y à %H:%M UTC")}
</footer>

</body>
</html>"""

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*60}")
    print(f"  SOA Pyxis-OP — Génération du tableau de bord")
    print(f"  {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}")
    print(f"{'='*60}\n")

    axes_data = []
    for axis in AXES:
        print(f"  Axe : {axis['label']}")
        articles = collect_axis(axis)
        axes_data.append((axis, articles))
        print(f"    → {len(articles)} articles collectés\n")

    html = generate(axes_data)

    out = Path(__file__).parent.parent / "docs" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    total = sum(len(a) for _, a in axes_data)
    print(f"  ✓ Dashboard généré : {out}")
    print(f"  ✓ {total} articles au total")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
