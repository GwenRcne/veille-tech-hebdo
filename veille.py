import feedparser
import requests
import json
from datetime import datetime, timedelta
import os

# Configuration
RSS_FEEDS_FILE = "feeds.txt"
OUTPUT_FILE = "docs/index.html"
STATE_FILE = "docs/state.json"
HUGGING_FACE_API = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

def lire_flux_rss():
    """Lit la liste des flux RSS"""
    with open(RSS_FEEDS_FILE, 'r', encoding='utf-8') as f:
        return [ligne.strip() for ligne in f if ligne.strip() and not ligne.startswith('#')]

def lire_etat():
    """Lit quel site a été traité la dernière fois"""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"dernier_index": -1, "derniere_execution": None}

def sauvegarder_etat(index):
    """Sauvegarde quel site vient d'être traité"""
    etat = {
        "dernier_index": index,
        "derniere_execution": datetime.now().isoformat()
    }
    os.makedirs("docs", exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(etat, f, indent=2)

def charger_historique():
    """Charge l'historique des semaines précédentes"""
    historique_file = "docs/historique.json"
    try:
        with open(historique_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def sauvegarder_historique(historique):
    """Sauvegarde l'historique des semaines"""
    historique_file = "docs/historique.json"
    os.makedirs("docs", exist_ok=True)
    with open(historique_file, 'w', encoding='utf-8') as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)

def recuperer_articles_semaine(flux_url, jours=7, max_articles=2):
    """Récupère les 2 meilleurs articles de la semaine"""
    articles = []
    date_limite = datetime.now() - timedelta(days=jours)
    
    try:
        print(f"📡 Lecture du flux : {flux_url}")
        flux = feedparser.parse(flux_url)
        nom_site = flux.feed.get('title', flux_url)
        
        # Récupérer tous les articles récents
        articles_candidats = []
        for entree in flux.entries[:30]:  # Examiner les 30 derniers
            if hasattr(entree, 'published_parsed'):
                date_pub = datetime(*entree.published_parsed[:6])
                if date_pub < date_limite:
                    continue
            
            article = {
                'titre': entree.title,
                'lien': entree.link,
                'description': entree.get('summary', '')[:800],
                'date': entree.get('published', 'Date inconnue')
            }
            articles_candidats.append(article)
        
        # Ne garder que les 2 plus récents (LIGNE IMPORTANTE !)
        articles = articles_candidats[:max_articles]
        
        for article in articles:
            print(f"  ✅ {article['titre'][:60]}...")
        
        print(f"  📊 {len(articles)} articles sélectionnés sur {len(articles_candidats)} disponibles")
        
        return articles, nom_site
    
    except Exception as e:
        print(f"  ❌ Erreur : {e}")
        return [], flux_url

def resumer_texte(texte):
    """Résume avec l'IA Hugging Face"""
    texte = texte[:1000]
    
    try:
        headers = {"Content-Type": "application/json"}
        payload = {"inputs": texte}
        response = requests.post(HUGGING_FACE_API, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            resultat = response.json()
            if isinstance(resultat, list) and len(resultat) > 0:
                return resultat[0].get('summary_text', texte[:200])
        
        return texte[:200] + "..."
    except:
        return texte[:200] + "..."

def generer_html(articles, nom_site, numero_semaine):
    """Génère la page HTML avec historique COMPLET (toutes les semaines)"""
    
    # Charger l'historique existant
    historique = charger_historique()
    
    # Ajouter les nouveaux articles à l'historique
    nouvelle_semaine = {
        'numero_semaine': numero_semaine,
        'nom_site': nom_site,
        'date_maj': datetime.now().strftime("%d/%m/%Y"),
        'articles': articles
    }
    
    # Ajouter au début de la liste
    historique.insert(0, nouvelle_semaine)
    
    # PAS DE LIMITE ! On garde tout l'historique
    # historique = historique[:4]  ← LIGNE SUPPRIMÉE
    
    # Sauvegarder l'historique
    sauvegarder_historique(historique)
    
    # Générer le HTML pour toutes les semaines
    html_semaines = ""
    for idx, semaine_data in enumerate(historique):
        # Badge "NOUVELLE" pour la première semaine
        badge_nouveau = '<span style="background: #ff6b6b; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8em; margin-left: 10px;">✨ NOUVELLE</span>' if idx == 0 else ''
        
        html_articles = ""
        for i, article in enumerate(semaine_data['articles'], 1):
            html_articles += f"""
            <article class="article-card">
                <div class="article-number">#{i}</div>
                <h3 class="article-title">
                    <a href="{article['lien']}" target="_blank">{article['titre']}</a>
                </h3>
                <p class="article-date">📅 {article['date']}</p>
                <div class="article-summary">{article['resume']}</div>
                <a href="{article['lien']}" target="_blank" class="read-more">Lire l'article complet →</a>
            </article>
            """
        
        html_semaines += f"""
        <div class="week-section">
            <div class="week-header">
                <h2>📅 Semaine {semaine_data['numero_semaine']} - {semaine_data['date_maj']} {badge_nouveau}</h2>
                <div class="week-source">📡 Source : {semaine_data['nom_site']}</div>
            </div>
            <div class="articles-grid">
                {html_articles}
            </div>
        </div>
        """
    
    date_maj = datetime.now().strftime("%d/%m/%Y à %H:%M")
    nb_semaines = len(historique)
    nb_articles_total = sum(len(s['articles']) for s in historique)
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Veille Tech Hebdo - Archive Complète</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .header .subtitle {{
            font-size: 1.1em;
            opacity: 0.95;
            margin-top: 5px;
        }}
        
        .stats-bar {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            margin-top: 20px;
            border-radius: 10px;
            display: flex;
            justify-content: center;
            gap: 40px;
            flex-wrap: wrap;
        }}
        
        .stat-item {{
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
        }}
        
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        
        .content {{
            padding: 40px 30px;
        }}
        
        .week-section {{
            margin-bottom: 50px;
            padding-bottom: 30px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .week-section:last-child {{
            border-bottom: none;
        }}
        
        .week-header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            border-radius: 15px;
        }}
        
        .week-header h2 {{
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 10px;
        }}
        
        .week-source {{
            color: #666;
            font-size: 1.1em;
            font-weight: 500;
        }}
        
        .articles-grid {{
            display: grid;
            gap: 25px;
        }}
        
        .article-card {{
            background: #f8f9fa;
            border-radius: 15px;
            padding: 25px;
            position: relative;
            border-left: 5px solid #667eea;
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        
        .article-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        .article-number {{
            position: absolute;
            top: 15px;
            right: 15px;
            background: #667eea;
            color: white;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        
        .article-title {{
            font-size: 1.3em;
            margin-bottom: 10px;
            color: #2c3e50;
            padding-right: 50px;
        }}
        
        .article-title a {{
            color: inherit;
            text-decoration: none;
            transition: color 0.3s;
        }}
        
        .article-title a:hover {{
            color: #667eea;
        }}
        
        .article-date {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 12px;
        }}
        
        .article-summary {{
            color: #555;
            line-height: 1.8;
            margin-bottom: 15px;
        }}
        
        .read-more {{
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s;
            padding: 6px 12px;
            border-radius: 6px;
        }}
        
        .read-more:hover {{
            background: #667eea;
            color: white;
        }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #666;
        }}
        
        .back-to-top {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #667eea;
            color: white;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: all 0.3s;
            font-size: 1.5em;
        }}
        
        .back-to-top:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            .article-card {{
                padding: 20px;
            }}
            .stats-bar {{
                gap: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Veille Tech Hebdo</h1>
            <p class="subtitle">2 articles par semaine • 1 site différent</p>
            <p class="subtitle">📚 Archive complète depuis le début</p>
            
            <div class="stats-bar">
                <div class="stat-item">
                    <div class="stat-number">{nb_semaines}</div>
                    <div class="stat-label">Semaines</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{nb_articles_total}</div>
                    <div class="stat-label">Articles</div>
                </div>
            </div>
        </div>
        
        <div class="content">
            {html_semaines}
        </div>
        
        <div class="footer">
            <p>🤖 Mise à jour automatique le {date_maj}</p>
            <p>📅 Chaque lundi, un nouveau site est analysé !</p>
            <p style="margin-top: 10px; font-size: 0.9em; color: #999;">Archive permanente • Tous les articles sont conservés</p>
        </div>
    </div>
    
    <div class="back-to-top" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">
        ↑
    </div>
</body>
</html>"""
    
    return html

def main():
    print("🚀 Démarrage de la veille hebdomadaire")
    print("=" * 70)
    
    # Lire les flux et l'état
    flux_list = lire_flux_rss()
    etat = lire_etat()
    
    # Calculer quel site traiter cette semaine (rotation)
    index_actuel = (etat["dernier_index"] + 1) % len(flux_list)
    flux_actuel = flux_list[index_actuel]
    
    numero_semaine = datetime.now().isocalendar()[1]
    
    print(f"📚 {len(flux_list)} sites configurés")
    print(f"🎯 Site de cette semaine (#{index_actuel + 1}) : {flux_actuel}")
    print(f"📅 Semaine n°{numero_semaine}\n")
    
    # Récupérer les articles de la semaine
    articles, nom_site = recuperer_articles_semaine(flux_actuel, jours=7, max_articles=2)
    print(f"\n📰 {len(articles)} articles trouvés\n")
    
    if not articles:
        print("⚠️ Aucun article cette semaine, on garde la page actuelle")
        return
    
    # Résumer les articles
    print("🤖 Génération des résumés...\n")
    for article in articles:
        texte = f"{article['titre']}. {article['description']}"
        article['resume'] = resumer_texte(texte)
        print(f"  ✅ {article['titre'][:50]}...")
    
    # Générer et sauvegarder la page HTML
    print("\n📝 Génération de la page web...")
    html = generer_html(articles, nom_site, numero_semaine)
    
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    
    # Sauvegarder l'état
    sauvegarder_etat(index_actuel)
    
    print("\n" + "=" * 70)
    print("✅ Veille terminée !")
    print(f"📄 Page générée : {OUTPUT_FILE}")
    print(f"🔄 Prochain site (semaine {numero_semaine + 1}) : {flux_list[(index_actuel + 1) % len(flux_list)]}")

if __name__ == "__main__":
    main()
