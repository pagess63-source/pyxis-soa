# SOA Pyxis-OP — Tableau de bord de veille stratégique

Mise à jour **automatique chaque lundi à 07h00 (CEST)** via GitHub Actions.  
Résultat accessible via GitHub Pages à l'URL de ton repo.

---

## Structure

```
pyxis-soa/
├── .github/
│   └── workflows/
│       └── soa-weekly.yml      ← Planification GitHub Actions
├── scripts/
│   └── generate_dashboard.py   ← Script de collecte + génération HTML
├── docs/
│   └── index.html              ← Dashboard généré (ne pas éditer manuellement)
├── requirements.txt
└── README.md
```

---

## Mise en place (une seule fois, ~10 minutes)

### 1. Créer le repo GitHub

1. Va sur [github.com](https://github.com) → **New repository**
2. Nom : `pyxis-soa` (ou `pyxis-op-veille`)
3. Visibilité : **Private** (recommandé — tes données de veille restent privées)
4. Ne pas initialiser avec README (tu vas pousser ce dossier)

### 2. Pousser ce dossier

```bash
cd pyxis-soa
git init
git add .
git commit -m "Initial commit — SOA Pyxis-OP"
git branch -M main
git remote add origin https://github.com/TON_USERNAME/pyxis-soa.git
git push -u origin main
```

### 3. Activer GitHub Pages

1. Dans ton repo → **Settings** → **Pages**
2. Source : **Deploy from a branch**
3. Branch : `main` / Folder : `/docs`
4. Cliquer **Save**

Ton dashboard sera accessible à :  
`https://TON_USERNAME.github.io/pyxis-soa/`

### 4. Premier test manuel

1. Onglet **Actions** de ton repo
2. Cliquer sur **SOA — Mise à jour hebdomadaire**
3. Bouton **Run workflow** → **Run workflow**
4. Attendre ~1 minute → le dashboard se génère et se déploie

---

## Modifier les sources de veille

Tout se passe dans `scripts/generate_dashboard.py`, section `AXES`.

**Ajouter un concurrent :**
```python
# Dans l'axe "aps", ajouter un tuple (url_rss, "Nom affiché") :
("https://news.google.com/rss/search?q=NomConcurrent+planification&hl=fr&gl=FR&ceid=FR:fr", "NomConcurrent"),
```

**Changer la fenêtre temporelle :**
```python
MAX_AGE_DAYS = 14   # Modifier ce nombre (7, 21, 30...)
```

**Changer le nombre d'articles par axe :**
```python
"max_items": 8,   # Dans la définition de l'axe
```

---

## Déclenchement

| Événement | Quand |
|---|---|
| Automatique | Chaque lundi à 07h00 CEST |
| Manuel | Onglet Actions → Run workflow |

---

## Notes techniques

- Données : flux RSS publics via Google News (aucune API payante)
- Dépendance unique : `feedparser` (parsing RSS)
- Aucune donnée stockée côté serveur — le HTML est statique
- Articles filtrés sur les 14 derniers jours (modifiable)
- Déduplication automatique par titre normalisé

---

*Pyxis-OP Agility Sàrl · La Chaux-de-Fonds, Suisse*
