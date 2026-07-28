import os
import sqlite3
from datetime import datetime

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
    cur.execute('''CREATE TABLE IF NOT EXISTS sauvegarde_historique (date_str TEXT, nom TEXT, ms TEXT, me TEXT, aes TEXT, aee TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS demandes_interim (id INTEGER PRIMARY KEY AUTOINCREMENT, absent TEXT, date_creation TEXT, dates_resume TEXT, grille_data TEXT)''')
    conn.commit()
    conn.close()

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

def get_mission_score(nom):
    conn = get_db_connection()
    res = conn.execute("SELECT total FROM compteur_missions WHERE nom=?", (nom,)).fetchone()
    conn.close()
    return res['total'] if res else 0

def inc_mission_score(nom):
    conn = get_db_connection()
    score = get_mission_score(nom)
    conn.execute("INSERT OR REPLACE INTO compteur_missions VALUES (?,?)", (nom, score + 1))
    conn.commit()
    conn.close()
