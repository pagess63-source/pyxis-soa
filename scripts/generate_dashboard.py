#!/usr/bin/env python3
"""
SOA Pyxis-OP v2 — Générateur de tableau de bord de veille stratégique
Exécuté chaque lundi à 07h00 (CEST) via GitHub Actions

Fonctionnalités :
  - Collecte RSS sur 5 axes (APS, ERP, marché CH, tech/IA)
  - Scraping direct de 3 sites surveillés (BOS-Software, Codatic, Kapia)
  - Alerte email automatique si mots-clés critiques détectés (Option B)
"""

import feedparser
import html as html_lib
import os
import re
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════════
# CONFIGURATION RSS
# ══════════════════════════════════════════════════════════════

AXES = [
    {
        "id": "oplit", "label": "Oplit",
        "sublabel": "ALERTE PRIORITAIRE — Financé par Vi Partners (CH), cible Suisse, déjà chez Vaucher Manufacture",
        "color": "#ef4444", "accent": "239,68,68", "icon": "⚠", "max_items": 6,
        "feeds": [
            ("https://news.google.com/rss/search?q=Oplit+planification+industrie&hl=fr&gl=FR&ceid=FR:fr", "Google News FR"),
            ("https://news.google.com/rss/search?q=Oplit+manufacturing&hl=en&gl=CH&ceid=CH:en", "Google News CH"),
            ("https://news.google.com/rss/search?q=Oplit+ordonnancement+Suisse&hl=fr&gl=CH&ceid=CH:fr", "Google News CH-FR"),
        ],
    },
    {
        "id": "aps", "label": "APS — Concurrents directs",
        "sublabel": "DELMIA Ortems · Siemens Opcenter APS · Visual Planning · Planilog · Asprova",
        "color": "#f59e0b", "accent": "245,158,11", "icon": "◈", "max_items": 8,
        "feeds": [
            ("https://news.google.com/rss/search?q=DELMIA+Ortems+planification+ordonnancement&hl=fr&gl=FR&ceid=FR:fr", "Ortems"),
            ("https://news.google.com/rss/search?q=Siemens+Opcenter+APS+scheduling&hl=en&gl=US&ceid=US:en", "Siemens Opcenter"),
            ("https://news.google.com/rss/search?q=%22Visual+Planning%22+production+industrie&hl=fr&gl=FR&ceid=FR:fr", "Visual Planning"),
            ("https://news.google.com/rss/search?q=Planilog+ordonnancement+production&hl=fr&gl=FR&ceid=FR:fr", "Planilog"),
            ("https://news.google.com/rss/search?q=Asprova+APS+planning&hl=en&gl=US&ceid=US:en", "Asprova"),
        ],
    },
    {
        "id": "erp", "label": "ERP — Marché suisse & risques de substitution",
        "sublabel": "Abacus · SAP Business One · Microsoft Dynamics 365 · Sage X3 · Odoo",
        "color": "#3b82f6", "accent": "59,130,246", "icon": "◉", "max_items": 7,
        "feeds": [
            ("https://news.google.com/rss/search?q=Abacus+ERP+Suisse+production+planning&hl=fr&gl=CH&ceid=CH:fr", "Abacus CH"),
            ("https://news.google.com/rss/search?q=SAP+Business+One+PME+Suisse&hl=fr&gl=CH&ceid=CH:fr", "SAP B1"),
            ("https://news.google.com/rss/search?q=Microsoft+Dynamics+365+industrie+Suisse&hl=fr&gl=CH&ceid=CH:fr", "MS Dynamics"),
            ("https://news.google.com/rss/search?q=Odoo+manufacturing+Suisse&hl=fr&gl=CH&ceid=CH:fr", "Odoo CH"),
            ("https://news.google.com/rss/search?q=Sage+X3+industrie+planification&hl=fr&gl=FR&ceid=FR:fr", "Sage X3"),
        ],
    },
    {
        "id": "marche", "label": "Marché — PME industrielle suisse",
        "sublabel": "Swissmem · KOF · CVCI · GIM · Industrie romande · Conjoncture",
        "color": "#06b6d4", "accent": "6,182,212", "icon": "⬡", "max_items": 8,
        "feeds": [
            ("https://news.google.com/rss/search?q=PME+industrielle+Suisse+production+digitalisation&hl=fr&gl=CH&ceid=CH:fr", "PME CH"),
            ("https://news.google.com/rss/search?q=Swissmem+industrie+conjoncture&hl=fr&gl=CH&ceid=CH:fr", "Swissmem"),
            ("https://news.google.com/rss/search?q=industrie+suisse+romande+agilite+planification&hl=fr&gl=CH&ceid=CH:fr", "Industrie romande"),
            ("https://news.google.com/rss/search?q=KOF+conjoncture+industrie+suisse&hl=fr&gl=CH&ceid=CH:fr", "KOF ETH"),
        ],
    },
    {
        "id": "tech", "label": "Tech & IA — Planification industrielle",
        "sublabel": "AI scheduling · Industry 4.0 · GenAI manufacturing · APS trends",
        "color": "#10b981", "accent": "16,185,129", "icon": "✦", "max_items": 6,
        "feeds": [
            ("https://news.google.com/rss/search?q=intelligence+artificielle+planification+production+industrie&hl=fr&gl=FR&ceid=FR:fr", "IA planification"),
            ("https://news.google.com/rss/search?q=AI+advanced+planning+scheduling+manufacturing&hl=en&gl=US&ceid=US:en", "AI APS"),
            ("https://news.google.com/rss/search?q=GenAI+ERP+manufacturing+planning&hl=en&gl=US&ceid=US:en", "GenAI ERP"),
            ("https://news.google.com/rss/search?q=agilite+operationnelle+industrie+PME&hl=fr&gl=FR&ceid=FR:fr", "Agilité opérationnelle"),
        ],
    },
]

# ══════════════════════════════════════════════════════════════
# SITES À SURVEILLER DIRECTEMENT
# ══════════════════════════════════════════════════════════════

WATCHED_SITES = [
    {
        "id": "bos", "label": "BOS-Software",
        "url": "https://www.bos-software.com",
        "note": "Ancien associé · ScreeN MES · St-Imier",
        "color": "#f43f5e", "accent": "244,63,94",
        "extra_urls": ["https://www.bos-software.com/actualites",
                       "https://www.bos-software.com/news"],
    },
    {
        "id": "codatic", "label": "Codatic",
        "url": "https://www.codatic.com",
        "note": "Dr. Stéphane Ménard · ABIS App · CANTWAIT · WATCH512",
        "color": "#a855f7", "accent": "168,85,247",
        "extra_urls": [],
    },
    {
        "id": "kapia", "label": "Kapia",
        "url": "https://www.kapia.ch",
        "note": "Logiciel industriel suisse",
        "color": "#64748b", "accent": "100,116,139",
        "extra_urls": [],
    },
]

# ══════════════════════════════════════════════════════════════
# RÈGLES D'ALERTE — Email envoyé UNIQUEMENT si déclenchement
# ══════════════════════════════════════════════════════════════

ALERT_RULES = [
    # CRITIQUE
    {"keywords": ["oplit", "suisse"],           "level": "CRITIQUE",  "label": "Oplit détecté en Suisse"},
    {"keywords": ["oplit", "swiss"],            "level": "CRITIQUE",  "label": "Oplit détecté en Suisse (EN)"},
    {"keywords": ["abacus", "aps"],             "level": "CRITIQUE",  "label": "Abacus annonce un module APS"},
    {"keywords": ["abacus", "ordonnancement"],  "level": "CRITIQUE",  "label": "Abacus + ordonnancement"},
    {"keywords": ["abacus", "planning", "ia"],  "level": "CRITIQUE",  "label": "Abacus + IA planning"},
    # IMPORTANT
    {"keywords": ["aps", "suisse"],             "level": "IMPORTANT", "label": "APS concurrent sur marché suisse"},
    {"keywords": ["ordonnancement", "suisse"],  "level": "IMPORTANT", "label": "Ordonnancement en Suisse"},
    {"keywords": ["visual planning", "suisse"], "level": "IMPORTANT", "label": "Visual Planning en Suisse"},
    {"keywords": ["ortems", "suisse"],          "level": "IMPORTANT", "label": "DELMIA Ortems en Suisse"},
    # INFO — sites surveillés
    {"keywords": ["bos-software"],              "level": "INFO",      "label": "BOS-Software : nouveau contenu"},
    {"keywords": ["screeen"],                   "level": "INFO",      "label": "ScreeN (BOS) mentionné"},
    {"keywords": ["codatic"],                   "level": "INFO",      "label": "Codatic : nouveau contenu"},
    {"keywords": ["cantwait"],                  "level": "INFO",      "label": "CANTWAIT (Codatic) mentionné"},
    {"keywords": ["kapia"],                     "level": "INFO",      "label": "Kapia : nouveau contenu"},
]

MAX_AGE_DAYS   = 14
DASHBOARD_URL  = "https://pagess63-source.github.io/pyxis-soa/"
LEVEL_COLOR    = {"CRITIQUE": "#ef4444", "IMPORTANT": "#f59e0b", "INFO": "#06b6d4"}
LEVEL_ICON     = {"CRITIQUE": "🔴",      "IMPORTANT": "🟠",      "INFO": "🔵"}
MONTHS_FR      = ["jan","fév","mar","avr","mai","juin","juil","août","sep","oct","nov","déc"]

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
    if days == 0:   return "Aujourd'hui", "#10b981"
    elif days == 1: return "Hier",        "#10b981"
    elif days <= 3: return f"{days}j",    "#06b6d4"
    elif days <= 7: return f"{days}j",    "#f59e0b"
    else:           return f"{days}j",    "#94a3b8"

def fmt_date(dt):
    return f"{dt.day} {MONTHS_FR[dt.month - 1]} {dt.year}"

def check_alerts(text):
    low = text.lower()
    return [r for r in ALERT_RULES if all(kw in low for kw in r["keywords"])]

# ══════════════════════════════════════════════════════════════
# COLLECTE RSS
# ══════════════════════════════════════════════════════════════

def fetch_feed(url, source_label):
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Pyxis-OP SOA/2.0"})
        now  = datetime.now(timezone.utc)
        for entry in feed.entries[:12]:
            pub  = parse_date(entry)
            age  = (now - pub).days
            if age > MAX_AGE_DAYS:
                continue
            title   = strip_tags(entry.get("title", ""))
            link    = entry.get("link", "#")
            summary = strip_tags(entry.get("summary", ""))[:200]
            if title:
                articles.append({
                    "title": title, "link": link, "summary": summary,
                    "source": source_label, "date": pub, "age": age,
                    "alerts": check_alerts(f"{title} {summary}"),
                })
    except Exception as exc:
        print(f"  ⚠  RSS {source_label}: {exc}")
    return articles

def collect_axis(axis):
    all_items, seen = [], set()
    for url, label in axis["feeds"]:
        for art in fetch_feed(url, label):
            key = art["title"].lower()[:70]
            if key not in seen:
                seen.add(key)
                all_items.append(art)
        time.sleep(0.5)
    all_items.sort(key=lambda x: x["date"], reverse=True)
    return all_items[:axis["max_items"]]

# ══════════════════════════════════════════════════════════════
# SCRAPING SITES SURVEILLÉS
# ══════════════════════════════════════════════════════════════

REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PyxisSOA/2.0; +https://pyxis-op.ch)",
    "Accept-Language": "fr-CH,fr;q=0.9",
}

def scrape_url(url):
    snippets = []
    try:
        r = requests.get(url, headers=REQ_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        for sel in ["article", ".news", ".actualites", ".blog", "main", "#content"]:
            section = soup.select(sel)
            if section:
                for el in section[:3]:
                    for p in el.find_all(["p", "h2", "h3"])[:6]:
                        t = p.get_text(" ", strip=True)
                        if len(t) > 50:
                            snippets.append(t[:280])
                if snippets:
                    break
        if not snippets:
            meta = soup.find("meta", {"name": "description"}) or \
                   soup.find("meta", {"property": "og:description"})
            if meta and meta.get("content"):
                snippets.append(meta["content"][:280])
    except Exception as exc:
        print(f"    ⚠  {url}: {exc}")
    return snippets[:5]

def collect_site(site):
    all_snippets = []
    for url in [site["url"]] + site.get("extra_urls", []):
        snips = scrape_url(url)
        all_snippets.extend(snips)
        if all_snippets:
            break
        time.sleep(0.5)
    full_text = " ".join(all_snippets)
    return {
        "site":     site,
        "snippets": all_snippets[:5],
        "alerts":   check_alerts(full_text),
        "ok":       len(all_snippets) > 0,
    }

# ══════════════════════════════════════════════════════════════
# EMAIL D'ALERTE
# ══════════════════════════════════════════════════════════════

def build_email_html(unique_alerts):
    now_str   = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    critique  = [a for a in unique_alerts if a["rule"]["level"] == "CRITIQUE"]
    important = [a for a in unique_alerts if a["rule"]["level"] == "IMPORTANT"]
    info      = [a for a in unique_alerts if a["rule"]["level"] == "INFO"]

    def rows(alerts):
        html = ""
        for a in alerts:
            c = LEVEL_COLOR[a["rule"]["level"]]
            i = LEVEL_ICON[a["rule"]["level"]]
            lnk = html_lib.escape(a.get("link", "#"))
            ttl = html_lib.escape(a.get("title", "")[:120])
            html += f"""<tr><td style="padding:10px 0;border-bottom:1px solid #1e293b">
              <span style="color:{c};font-weight:700;font-size:.72rem">{i} {a['rule']['level']}</span><br>
              <span style="color:#e2e8f0;font-size:.84rem;font-weight:600">{html_lib.escape(a['rule']['label'])}</span><br>
              <span style="color:#64748b;font-size:.73rem">{ttl}</span><br>
              <a href="{lnk}" style="color:#3b82f6;font-size:.7rem">Lire →</a>
            </td></tr>"""
        return html

    def block(title, alerts, color):
        if not alerts:
            return ""
        return f"""<tr><td style="padding:14px 0 4px">
          <span style="color:{color};font-weight:800;font-size:.88rem">{title} ({len(alerts)})</span>
        </td></tr>{rows(alerts)}"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"></head>
<body style="background:#0f172a;color:#e2e8f0;font-family:Arial,sans-serif;margin:0;padding:20px">
<table width="580" cellpadding="0" cellspacing="0" style="margin:0 auto;background:#1e293b;border-radius:12px;overflow:hidden">
  <tr><td style="background:linear-gradient(135deg,#1e3a5f,#1c2440);padding:26px 30px">
    <div style="font-size:1.3rem;font-weight:800;color:#fff">Pyxis<span style="color:#3b82f6;font-weight:300">-</span><span style="color:#3b82f6">OP</span></div>
    <div style="font-size:.58rem;letter-spacing:.15em;color:#475569">ALERTE SOA · VEILLE STRATÉGIQUE</div>
    <div style="font-size:.78rem;color:#94a3b8;margin-top:6px">{len(unique_alerts)} signal(s) — {now_str}</div>
  </td></tr>
  <tr><td style="padding:22px 30px">
    <table width="100%" cellpadding="0" cellspacing="0">
      {block("🔴 ALERTES CRITIQUES", critique, "#ef4444")}
      {block("🟠 ALERTES IMPORTANTES", important, "#f59e0b")}
      {block("🔵 INFORMATIONS", info, "#06b6d4")}
    </table>
    <div style="margin-top:22px;text-align:center">
      <a href="{DASHBOARD_URL}" style="display:inline-block;background:#2563eb;color:#fff;padding:11px 26px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.83rem">
        Voir le dashboard complet →
      </a>
    </div>
  </td></tr>
  <tr><td style="padding:14px 30px;border-top:1px solid #334155;font-size:.6rem;color:#475569;text-align:center">
    Pyxis-OP Agility Sàrl · La Chaux-de-Fonds · SOA automatique chaque lundi
  </td></tr>
</table></body></html>"""

def send_alert_email(unique_alerts):
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    alert_to   = os.environ.get("ALERT_EMAIL", gmail_user)

    if not gmail_user or not gmail_pass:
        print("  ⚠  Email non configuré (secrets GitHub manquants)")
        return

    n_crit  = sum(1 for a in unique_alerts if a["rule"]["level"] == "CRITIQUE")
    subject = (f"🔴 SOA Pyxis-OP — {n_crit} alerte(s) CRITIQUE(S)" if n_crit
               else f"🟠 SOA Pyxis-OP — {len(unique_alerts)} signal(s) détecté(s)")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"SOA Pyxis-OP <{gmail_user}>"
    msg["To"]      = alert_to
    msg.attach(MIMEText(f"SOA Pyxis-OP — {len(unique_alerts)} alerte(s). Dashboard : {DASHBOARD_URL}", "plain", "utf-8"))
    msg.attach(MIMEText(build_email_html(unique_alerts), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, alert_to, msg.as_string())
        print(f"  ✓ Email envoyé à {alert_to}")
    except Exception as exc:
        print(f"  ✗ Erreur email : {exc}")

# ══════════════════════════════════════════════════════════════
# GÉNÉRATION HTML
# ══════════════════════════════════════════════════════════════

def render_article(art):
    age_txt, age_color = age_label(art["age"])
    badge = ""
    if art.get("alerts"):
        top = art["alerts"][0]
        c   = LEVEL_COLOR[top["level"]]
        badge = f'<span class="abadge" style="background:rgba(0,0,0,.25);color:{c}">{LEVEL_ICON[top["level"]]} {top["label"]}</span>'
    return f"""<a class="card" href="{html_lib.escape(art['link'])}" target="_blank" rel="noopener">
  <div class="ctop"><span class="csrc">{html_lib.escape(art['source'])}</span><span class="cage" style="color:{age_color}">{age_txt}</span></div>
  {badge}<div class="ctitle">{html_lib.escape(art['title'])}</div>
  {"" if not art['summary'] else f'<div class="csum">{html_lib.escape(art["summary"])}…</div>'}
  <div class="cdate">{fmt_date(art['date'])}</div></a>"""

def render_axis(axis, articles):
    n = len(articles)
    cards = "".join(render_article(a) for a in articles) or '<p class="empty">Aucun article trouvé cette semaine.</p>'
    return f"""<section class="axis" id="{axis['id']}">
  <div class="ahd" style="border-left:3px solid {axis['color']}">
    <div class="arow"><h2 class="atitle"><span style="color:{axis['color']}">{axis['icon']}</span> {html_lib.escape(axis['label'])}</h2>
    <span class="acount" style="background:rgba({axis['accent']},.12);color:{axis['color']}">{n} article{'s' if n!=1 else ''}</span></div>
    <p class="asub">{html_lib.escape(axis['sublabel'])}</p></div>
  <div class="cgrid">{cards}</div></section>"""

def render_site(sd):
    s = sd["site"]
    snips = "".join(f'<div class="snip">{html_lib.escape(t)}</div>' for t in sd["snippets"]) or \
            '<p class="empty">Site inaccessible ou contenu non extractible.</p>'
    abadges = "".join(
        f'<span class="abadge" style="background:rgba(0,0,0,.3);color:{LEVEL_COLOR[r["level"]]}">{LEVEL_ICON[r["level"]]} {r["label"]}</span> '
        for r in sd["alerts"]
    )
    return f"""<div class="scard" id="{s['id']}">
  <div class="ahd" style="border-left:3px solid {s['color']}">
    <div class="arow">
      <h3 class="atitle"><span style="color:{s['color']}">●</span> {html_lib.escape(s['label'])}
        <a href="{html_lib.escape(s['url'])}" target="_blank" rel="noopener" class="slink">↗</a>
      </h3>
      <span class="acount" style="background:rgba({s['accent']},.12);color:{s['color']}">Scraping direct</span>
    </div>
    <p class="asub">{html_lib.escape(s['note'])}</p>
    {f'<div style="margin-top:5px">{abadges}</div>' if abadges else ""}
  </div>
  <div class="snips">{snips}</div></div>"""

def generate_html(axes_data, sites_data, unique_alerts):
    now     = datetime.now(timezone.utc)
    now_str = now.strftime("%d.%m.%Y — %H:%M UTC")
    total   = sum(len(a) for _, a in axes_data)
    n_alrt  = len(unique_alerts)

    sections = "".join(render_axis(ax, arts) for ax, arts in axes_data)
    sites_html = "".join(render_site(sd) for sd in sites_data)

    if unique_alerts:
        n_crit = sum(1 for a in unique_alerts if a["rule"]["level"] == "CRITIQUE")
        banner = (f'<div class="banner crit">🔴 {n_crit} alerte(s) CRITIQUE(S) — email envoyé</div>' if n_crit
                  else f'<div class="banner warn">🟠 {n_alrt} signal(s) détecté(s) — email envoyé</div>')
    else:
        banner = '<div class="banner ok">✅ Aucun signal critique cette semaine</div>'

    nav = "".join(f'<a class="nax" href="#{ax["id"]}" style="--c:{ax["color"]}">{ax["icon"]} {html_lib.escape(ax["label"])}</a>\n'
                  for ax, _ in axes_data)
    nav += '<a class="nax" href="#sites" style="--c:#f43f5e">● Sites surveillés</a>\n'

    pill_alrt = (f'<span class="spill" style="background:rgba(239,68,68,.12);color:#ef4444">{n_alrt} alerte{"s" if n_alrt>1 else ""}</span>'
                 if n_alrt else "")

    return f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SOA Pyxis-OP — Veille stratégique</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--d:#0f172a;--d2:#1e293b;--d3:#1c2440;--g3:#cbd5e1;--g4:#94a3b8;--g5:#64748b;--g6:#475569;--fn:'Plus Jakarta Sans',-apple-system,sans-serif;--mo:'JetBrains Mono',monospace;--r:12px;--rs:8px}}
*{{margin:0;padding:0;box-sizing:border-box}}html{{scroll-behavior:smooth}}
body{{font-family:var(--fn);background:var(--d);color:var(--g3);-webkit-font-smoothing:antialiased}}
.topbar{{position:sticky;top:0;z-index:100;background:rgba(15,23,42,.95);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,255,255,.06);padding:12px 40px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.logo{{font-size:1.1rem;font-weight:800}}.logo .p{{color:#fff}}.logo .dash{{color:#2563eb;font-weight:300}}.logo .op{{color:#2563eb}}.logo .tag{{font-family:var(--mo);font-size:.58rem;letter-spacing:.12em;color:var(--g5);display:block;margin-top:1px}}
.pills{{display:flex;gap:10px}}.spill{{display:inline-flex;align-items:center;padding:4px 10px;border-radius:20px;font-size:.68rem;font-weight:600;font-family:var(--mo)}}
.spill.blue{{background:rgba(37,99,235,.12);color:#3b82f6}}
.tsup{{font-family:var(--mo);font-size:.62rem;color:var(--g5)}}
.banner{{padding:9px 40px;font-size:.77rem;font-weight:600;text-align:center}}
.banner.crit{{background:rgba(239,68,68,.12);color:#fca5a5;border-bottom:1px solid rgba(239,68,68,.18)}}
.banner.warn{{background:rgba(245,158,11,.1);color:#fcd34d;border-bottom:1px solid rgba(245,158,11,.12)}}
.banner.ok{{background:rgba(16,185,129,.07);color:#6ee7b7;border-bottom:1px solid rgba(16,185,129,.1)}}
.anav{{display:flex;gap:8px;flex-wrap:wrap;padding:13px 40px;border-bottom:1px solid rgba(255,255,255,.04);background:rgba(15,23,42,.5)}}
.nax{{display:inline-flex;align-items:center;gap:5px;padding:5px 13px;border-radius:20px;font-size:.72rem;font-weight:600;text-decoration:none;border:1px solid rgba(255,255,255,.06);color:var(--g4);transition:all .2s}}
.nax:hover{{color:var(--c);border-color:var(--c)}}
main{{max-width:1280px;margin:0 auto;padding:34px 40px 80px}}
.axis{{margin-bottom:42px}}
.ahd{{padding:16px 16px 11px;margin-bottom:12px;background:rgba(255,255,255,.02);border-radius:var(--r)}}
.arow{{display:flex;align-items:center;gap:12px;margin-bottom:4px}}
.atitle{{font-size:.93rem;font-weight:700;color:#fff}}
.acount{{font-size:.63rem;font-weight:700;font-family:var(--mo);padding:3px 9px;border-radius:12px}}
.asub{{font-size:.69rem;color:var(--g5);padding-left:26px;line-height:1.5}}
.cgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:10px}}
.card{{display:block;text-decoration:none;background:var(--d2);border:1px solid rgba(255,255,255,.05);border-radius:var(--rs);padding:13px;transition:all .2s}}
.card:hover{{background:var(--d3);border-color:rgba(255,255,255,.1);transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,.3)}}
.ctop{{display:flex;justify-content:space-between;margin-bottom:6px}}
.csrc{{font-family:var(--mo);font-size:.57rem;font-weight:500;color:var(--g5);text-transform:uppercase;letter-spacing:.06em}}
.cage{{font-family:var(--mo);font-size:.57rem;font-weight:600}}
.abadge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.6rem;font-weight:700;margin-bottom:5px}}
.ctitle{{font-size:.81rem;font-weight:600;color:#e2e8f0;line-height:1.4;margin-bottom:5px}}
.csum{{font-size:.7rem;color:var(--g5);line-height:1.5;margin-bottom:5px}}
.cdate{{font-family:var(--mo);font-size:.57rem;color:var(--g6)}}
.empty{{font-size:.77rem;color:var(--g6);padding:18px 0;font-style:italic}}
.scard{{background:var(--d2);border:1px solid rgba(255,255,255,.05);border-radius:var(--r);padding:18px}}
.sgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}}
.slink{{color:var(--g5);font-size:.73rem;text-decoration:none;margin-left:5px}}
.slink:hover{{color:#2563eb}}
.snips{{display:flex;flex-direction:column;gap:7px;margin-top:12px}}
.snip{{font-size:.72rem;color:var(--g4);line-height:1.55;padding:9px 11px;background:rgba(255,255,255,.02);border-radius:6px;border-left:2px solid rgba(255,255,255,.07)}}
footer{{text-align:center;padding:18px 40px;border-top:1px solid rgba(255,255,255,.04);font-family:var(--mo);font-size:.59rem;color:var(--g6)}}
@media(max-width:768px){{.topbar,.anav,main{{padding-left:16px;padding-right:16px}}}}
</style></head><body>
<header class="topbar">
  <div class="logo"><span><span class="p">Pyxis</span><span class="dash">-</span><span class="op">OP</span></span><span class="tag">TABLEAU DE BORD SOA · VEILLE STRATÉGIQUE</span></div>
  <div class="pills">
    <span class="spill blue">{total} articles RSS</span>
    {pill_alrt}
  </div>
  <div class="tsup">Mis à jour le {now_str}</div>
</header>
{banner}
<nav class="anav">{nav}</nav>
<main>
{sections}
<div id="sites" style="margin-bottom:42px">
  <div class="ahd" style="border-left:3px solid #f43f5e;margin-bottom:14px">
    <div class="arow"><h2 class="atitle"><span style="color:#f43f5e">●</span> Sites surveillés directement</h2>
    <span class="acount" style="background:rgba(244,63,94,.12);color:#f43f5e">Scraping hebdomadaire</span></div>
    <p class="asub">BOS-Software · Codatic · Kapia — contenu extrait à chaque mise à jour</p>
  </div>
  <div class="sgrid">{sites_html}</div>
</div>
</main>
<footer>Pyxis-OP Agility Sàrl · La Chaux-de-Fonds · Mise à jour automatique chaque lundi 07h00 CEST · {now.strftime("%d.%m.%Y %H:%M UTC")}</footer>
</body></html>"""

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*62}")
    print(f"  SOA Pyxis-OP v2 — {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}")
    print(f"{'='*62}\n")

    axes_data = []
    for axis in AXES:
        print(f"  RSS › {axis['label']}")
        articles = collect_axis(axis)
        axes_data.append((axis, articles))
        print(f"       → {len(articles)} articles\n")

    sites_data = []
    print("  Sites surveillés :")
    for site in WATCHED_SITES:
        print(f"    › {site['label']}")
        result = collect_site(site)
        sites_data.append(result)
        print(f"      → {len(result['snippets'])} snippets" +
              (f" — ⚠ {len(result['alerts'])} alerte(s)" if result["alerts"] else ""))

    # Collecte globale des alertes (dédoublonnées)
    raw_alerts = []
    for _, arts in axes_data:
        for art in arts:
            for rule in art.get("alerts", []):
                raw_alerts.append({**art, "rule": rule})
    for sd in sites_data:
        for rule in sd["alerts"]:
            raw_alerts.append({"title": sd["site"]["label"],
                                "link": sd["site"]["url"], "rule": rule})
    seen, unique_alerts = set(), []
    for a in raw_alerts:
        key = f"{a['rule']['label']}|{str(a.get('title',''))[:50]}"
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)

    print(f"\n  Alertes : {len(unique_alerts)}")
    for a in unique_alerts:
        print(f"    {LEVEL_ICON[a['rule']['level']]} {a['rule']['label']}")

    if unique_alerts:
        print("\n  Envoi de l'email d'alerte...")
        send_alert_email(unique_alerts)
    else:
        print("\n  Aucune alerte — pas d'email.")

    html = generate_html(axes_data, sites_data, unique_alerts)
    out  = Path(__file__).parent.parent / "docs" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\n  ✓ Dashboard : {out}")
    print(f"{'='*62}\n")

if __name__ == "__main__":
    main()
