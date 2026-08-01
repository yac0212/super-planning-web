import os
import sqlite3
from datetime import datetime, timedelta

DATA_DIR = os.environ.get('DATA_DIR', '.')

# Noms de base historiques : la prod utilise supermarche_data.db, les postes de
# developpement supermarche_dev.db. On reprend le fichier qui existe deja plutot
# que d'imposer un nom : sinon init_db() cree une base vide a cote de la vraie et
# l'application demarre sans aucune donnee.
_NOMS_BASE = ["supermarche_data.db", "supermarche_dev.db"]

def _resoudre_db():
    impose = os.environ.get('DB_NAME')
    if impose:
        return os.path.join(DATA_DIR, impose)
    for nom in _NOMS_BASE:
        chemin = os.path.join(DATA_DIR, nom)
        if os.path.exists(chemin) and os.path.getsize(chemin) > 0:
            return chemin
    return os.path.join(DATA_DIR, _NOMS_BASE[0])

DB_FILE = _resoudre_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS employes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        nom TEXT UNIQUE, 
        statut TEXT, 
        restriction_cls BOOLEAN, 
        restriction_handicap TEXT,
        heures_contrat REAL DEFAULT 35.0,
        type_contrat TEXT DEFAULT 'CDI',
        forme_caisse BOOLEAN DEFAULT 1,
        forme_cls BOOLEAN DEFAULT 0,
        articles_minute REAL DEFAULT 0.0,
        note_manager REAL DEFAULT 5.0,
        repos_fixes TEXT DEFAULT ''
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS historique_fermeture (date_str TEXT PRIMARY KEY, nom_employe TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS compteur_missions (nom TEXT PRIMARY KEY, total INTEGER)''')
    # Missions datees. Remplace compteur_missions, qui etait un cumul a vie sans
    # dates : impossible d'en tirer une fenetre glissante, et surtout incremente
    # a CHAQUE generation. Cinq brouillons du meme jour comptaient cinq journees
    # de mission pour la meme personne, ce qui faussait durablement l'equite.
    # Ici les lignes sont remplacees par date : regenerer ne cumule plus.
    # jour est au format ISO (AAAA-MM-JJ) pour pouvoir comparer les dates ;
    # date_str garde le format d'affichage JJ/MM/AAAA du reste de l'application.
    cur.execute('''CREATE TABLE IF NOT EXISTS historique_missions (
        date_str TEXT, jour TEXT, nom TEXT, mission TEXT)''')
    cur.execute('''CREATE INDEX IF NOT EXISTS idx_missions_jour
                   ON historique_missions (jour)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS sauvegarde_historique (date_str TEXT, nom TEXT, ms TEXT, me TEXT, aes TEXT, aee TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS demandes_interim (id INTEGER PRIMARY KEY AUTOINCREMENT, absent TEXT, date_creation TEXT, dates_resume TEXT, grille_data TEXT)''')
    migrer_schema(cur)
    semer_preferences(cur)
    conn.commit()
    conn.close()

# Colonnes ajoutees apres la mise en service. CREATE TABLE IF NOT EXISTS ne
# modifie PAS une table existante : sur une base creee avant ces ajouts, la
# lecture fonctionne mais l'ajout et la modification d'un salarie echouent avec
# "no such column: heures_contrat", et l'interface recoit une page d'erreur HTML
# au lieu de JSON.
COLONNES_AJOUTEES = [
    ("heures_contrat",  "REAL DEFAULT 35.0"),
    ("type_contrat",    "TEXT DEFAULT 'CDI'"),
    ("forme_caisse",    "BOOLEAN DEFAULT 1"),
    ("forme_cls",       "BOOLEAN DEFAULT 0"),
    ("articles_minute", "REAL DEFAULT 0.0"),
    ("note_manager",    "REAL DEFAULT 5.0"),
    ("repos_fixes",     "TEXT DEFAULT ''"),
    # Preferences par personne, remontees du code vers la base le 2026-08-01.
    # Elles remplacent des regles qui portaient des noms en dur dans algo.py et
    # obligeaient a rouvrir le code a chaque mouvement de personnel.
    # caisses_evitees : "1:5000,2:3000" — numero de caisse : penalite.
    # evite_cls : PREFERENCE de ne pas prendre le CLS, a ne pas confondre avec
    #   restriction_cls qui est une interdiction ferme.
    ("caisses_evitees", "TEXT DEFAULT ''"),
    ("evite_cls",       "BOOLEAN DEFAULT 0"),
    ("evite_pause",     "BOOLEAN DEFAULT 0"),
]

def migrer_schema(cur):
    """Ajoute les colonnes manquantes a la table employes, sans toucher aux
    donnees existantes. Idempotent : relancable a chaque demarrage."""
    existantes = {ligne[1] for ligne in cur.execute("PRAGMA table_info(employes)")}
    for nom_colonne, definition in COLONNES_AJOUTEES:
        if nom_colonne not in existantes:
            cur.execute(f"ALTER TABLE employes ADD COLUMN {nom_colonne} {definition}")


# Valeurs de depart des preferences remontees du code vers la base le 2026-08-01.
# Ce sont les regles qui etaient ecrites en dur dans algo.py, transcrites une
# derniere fois ici pour ne pas les perdre a la migration : sans cette etape, les
# colonnes se creent vides et le comportement change du jour au lendemain sans
# que personne ne s'en apercoive.
#
# La cle est un fragment de nom ; elle n'est utilisee qu'UNE fois, au premier
# demarrage suivant la migration. Ce n'est pas une regle metier, c'est une
# reprise de donnees. Le detail est dans REGLES_METIER.md section 8.
PREFERENCES_INITIALES = [
    ("yacine", "1:5000,2:5000,13:3000,14:3000", 1, 0),
    ("ethan",  "1:3000,2:3000,13:3000,14:3000", 0, 0),
    ("dalya",  "1:2000,2:2000",                 0, 0),
    ("andré",  "",                              0, 1),
]


def _mots(texte):
    return set(m for m in (texte or "").lower().replace("-", " ").split() if m)


def semer_preferences(cur):
    """Applique PREFERENCES_INITIALES, une seule fois.

    Le passage est trace dans la table `parametres` : sans ce marqueur, un
    utilisateur qui viderait volontairement une preference la verrait revenir au
    redemarrage suivant.
    """
    cur.execute("CREATE TABLE IF NOT EXISTS parametres (cle TEXT PRIMARY KEY, valeur TEXT)")
    deja = cur.execute("SELECT valeur FROM parametres WHERE cle='preferences_semees'").fetchone()
    if deja:
        return

    employes = cur.execute("SELECT id, nom FROM employes").fetchall()
    applique = 0
    for cle, caisses, sans_cls, sans_pause in PREFERENCES_INITIALES:
        # correspondance sur des mots ENTIERS, et refus si le fragment designe
        # plusieurs personnes : mieux vaut ne rien poser que de viser le mauvais
        # salarie ("emmanuel" avait deja fait ce genre de degat).
        cibles = [e for e in employes if _mots(cle).issubset(_mots(e[1]))]
        if len(cibles) != 1:
            continue
        cur.execute("UPDATE employes SET caisses_evitees=?, evite_cls=?, evite_pause=? WHERE id=?",
                    (caisses, sans_cls, sans_pause, cibles[0][0]))
        applique += 1
    cur.execute("INSERT OR REPLACE INTO parametres VALUES ('preferences_semees', ?)",
                (str(applique),))

init_db()

# Employes
def get_employes():
    conn = get_db_connection()
    emps = conn.execute("SELECT * FROM employes ORDER BY nom").fetchall()
    conn.close()
    return [dict(e) for e in emps]

def add_employe(nom, statut, restriction_cls, restriction_handicap, heures_contrat=35.0, type_contrat='CDI', forme_caisse=True, forme_cls=False, articles_minute=0.0, note_manager=5.0, repos_fixes=''):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO employes (nom, statut, restriction_cls, restriction_handicap, heures_contrat, type_contrat, forme_caisse, forme_cls, articles_minute, note_manager, repos_fixes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                     (nom, statut, restriction_cls, restriction_handicap, heures_contrat, type_contrat, forme_caisse, forme_cls, articles_minute, note_manager, repos_fixes))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "Cet employé existe déjà"
    finally:
        conn.close()

def delete_employe(emp_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM employes WHERE id=?", (emp_id,))
    conn.commit()
    conn.close()

def update_employe(emp_id, nom, statut, restriction_cls, restriction_handicap, heures_contrat=35.0, type_contrat='CDI', forme_caisse=True, forme_cls=False, articles_minute=0.0, note_manager=5.0, repos_fixes=''):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE employes SET nom=?, statut=?, restriction_cls=?, restriction_handicap=?, heures_contrat=?, type_contrat=?, forme_caisse=?, forme_cls=?, articles_minute=?, note_manager=?, repos_fixes=? WHERE id=?", 
                     (nom, statut, restriction_cls, restriction_handicap, heures_contrat, type_contrat, forme_caisse, forme_cls, articles_minute, note_manager, repos_fixes, emp_id))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "Ce nom est déjà pris"
    finally:
        conn.close()

# Saisie Journaliere
def get_sauvegarde_dates():
    conn = get_db_connection()
    dates = conn.execute("SELECT DISTINCT date_str FROM sauvegarde_historique ORDER BY date_str DESC").fetchall()
    conn.close()
    return [d['date_str'] for d in dates]

def get_sauvegarde(date_str):
    conn = get_db_connection()
    historique = conn.execute("SELECT nom, ms, me, aes, aee FROM sauvegarde_historique WHERE date_str=?", (date_str,)).fetchall()
    conn.close()
    return [dict(h) for h in historique]

def get_sauvegarde_employe(date_str, nom):
    conn = get_db_connection()
    historique = conn.execute("SELECT nom, ms, me, aes, aee FROM sauvegarde_historique WHERE date_str=? AND LOWER(nom)=LOWER(?)", (date_str, nom)).fetchone()
    conn.close()
    return dict(historique) if historique else None

def get_historique_employe(nom):
    conn = get_db_connection()
    historique = conn.execute("SELECT date_str, ms, me, aes, aee FROM sauvegarde_historique WHERE LOWER(nom)=LOWER(?)", (nom,)).fetchall()
    conn.close()
    return [dict(h) for h in historique]

def save_planning(date_str, inputs):
    conn = get_db_connection()
    conn.execute("DELETE FROM sauvegarde_historique WHERE date_str=?", (date_str,))
    for inp in inputs:
        ms, me, aes, aee = inp.get('ms', ''), inp.get('me', ''), inp.get('aes', ''), inp.get('aee', '')
        if ms or aes:
            conn.execute("INSERT INTO sauvegarde_historique VALUES (?,?,?,?,?,?)", 
                         (date_str, inp['nom'], ms, me, aes, aee))
    conn.commit()
    conn.close()

# Interim
def add_demande_interim(absent, dates_resume, grille_data):
    conn = get_db_connection()
    date_creation = datetime.now().strftime("%d/%m à %H:%M")
    conn.execute("INSERT INTO demandes_interim (absent, date_creation, dates_resume, grille_data) VALUES (?,?,?,?)", 
                 (absent, date_creation, dates_resume, grille_data))
    conn.commit()
    conn.close()

def get_demandes_interim():
    conn = get_db_connection()
    demandes = conn.execute("SELECT * FROM demandes_interim ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(d) for d in demandes]

def delete_demande_interim(req_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM demandes_interim WHERE id=?", (req_id,))
    conn.commit()
    conn.close()

def transfer_horaires(nom_absent, nom_remplacant, date_jour, m1, m2, a1, a2):
    conn = get_db_connection()
    conn.execute("DELETE FROM sauvegarde_historique WHERE date_str=? AND LOWER(nom)=LOWER(?)", (date_jour, nom_remplacant))
    conn.execute("UPDATE sauvegarde_historique SET nom=? WHERE LOWER(nom)=LOWER(?) AND date_str=?", (nom_remplacant, nom_absent, date_jour))
    verif = conn.execute("SELECT 1 FROM sauvegarde_historique WHERE LOWER(nom)=LOWER(?) AND date_str=?", (nom_remplacant, date_jour)).fetchone()
    if not verif:
        conn.execute("INSERT INTO sauvegarde_historique VALUES (?,?,?,?,?,?)", (date_jour, nom_remplacant, m1, m2, a1, a2))
    conn.commit()
    conn.close()

# Missions / Fermeture
def get_historique_fermeture(date_str):
    conn = get_db_connection()
    res = conn.execute("SELECT nom_employe FROM historique_fermeture WHERE date_str=?", (date_str,)).fetchone()
    conn.close()
    return res['nom_employe'] if res else ""

def save_historique_fermeture(date_str, nom):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO historique_fermeture VALUES (?,?)", (date_str, nom))
    conn.commit()
    conn.close()

# Nombre de jours pris en compte pour l'equite des missions. Un cumul a vie
# penalisait a perpetuite les anciens : 15 missions pour l'un contre 1 pour un
# arrivant recent, qui se retrouvait donc choisi en priorite pendant des mois.
FENETRE_EQUITE_JOURS = 30

def _iso(date_str):
    """JJ/MM/AAAA -> AAAA-MM-JJ, comparable comme du texte."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""

def get_scores_missions(reference=None):
    """Nombre de missions par personne sur les FENETRE_EQUITE_JOURS derniers jours.

    Lu UNE fois au debut d'une generation, plus a chaque candidat comme avant :
    l'ancienne version rouvrait la base depuis la boucle de selection des pauses.
    """
    fin = datetime.strptime(reference, "%d/%m/%Y") if reference else datetime.now()
    debut = (fin - timedelta(days=FENETRE_EQUITE_JOURS)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    lignes = conn.execute(
        "SELECT nom, COUNT(*) AS total FROM historique_missions "
        "WHERE jour >= ? AND jour <= ? GROUP BY nom",
        (debut, fin.strftime("%Y-%m-%d"))).fetchall()
    conn.close()
    return {l['nom']: l['total'] for l in lignes}

def enregistrer_missions(date_str, affectations):
    """Remplace les missions du jour. `affectations` : liste de (nom, mission).

    Idempotent par date : regenerer dix fois le meme planning laisse le meme
    etat en base. C'est ce qui empeche les brouillons de fausser l'equite.
    """
    jour = _iso(date_str)
    conn = get_db_connection()
    conn.execute("DELETE FROM historique_missions WHERE date_str=?", (date_str,))
    conn.executemany(
        "INSERT INTO historique_missions (date_str, jour, nom, mission) VALUES (?,?,?,?)",
        [(date_str, jour, nom, mission) for nom, mission in affectations])
    conn.commit()
    conn.close()
