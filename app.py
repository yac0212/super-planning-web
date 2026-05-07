import os
from flask import Flask, request, jsonify, render_template, send_from_directory, url_for, Response, session, redirect
from datetime import datetime, timedelta
import math
import database as db
import algo

app = Flask(__name__)
app.secret_key = "super_secret_planning_key"  # Nécessaire pour utiliser les sessions

# --- SÉCURITÉ : Mot de passe unique ---
ADMIN_PASSWORD = "inter2026"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/')
        else:
            return '''
                <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                    <h2 style="color: red;">Mot de passe incorrect</h2>
                    <a href="/login">Réessayer</a>
                </div>
            '''
    return '''
        <div style="font-family: sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; border: 1px solid #ccc; border-radius: 10px; text-align: center; background-color: #f9f9f9;">
            <h2>Accès Protégé</h2>
            <form method="post">
                <input type="password" name="password" placeholder="Mot de passe" style="padding: 10px; width: 80%; margin-bottom: 15px; border-radius: 5px; border: 1px solid #ccc;" autofocus required>
                <br>
                <button type="submit" style="padding: 10px 20px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">Se connecter</button>
            </form>
        </div>
    '''

@app.before_request
def require_login():
    # Autorise l'accès à la page de login et aux fichiers statiques sans mot de passe
    if request.path == '/login' or request.path.startswith('/static/'):
        return
    # Vérifie si l'utilisateur est connecté
    if not session.get('logged_in'):
        return redirect('/login')
# -------------------------------

DATA_DIR = os.environ.get('DATA_DIR', 'static')
PLANNINGS_DIR = os.path.join(DATA_DIR, "plannings")
PAUSES_DIR = os.path.join(DATA_DIR, "pauses")

# Assure directories exist
os.makedirs(PLANNINGS_DIR, exist_ok=True)
os.makedirs(PAUSES_DIR, exist_ok=True)

@app.route('/files/<type_dir>/<filename>')
def serve_files(type_dir, filename):
    if type_dir == "plannings":
        return send_from_directory(PLANNINGS_DIR, filename)
    elif type_dir == "pauses":
        return send_from_directory(PAUSES_DIR, filename)
    return "Not found", 404

@app.route('/')
def index():
    return render_template('index.html')

# === EMPLOYEES ===
@app.route('/api/employees', methods=['GET'])
def get_employees():
    return jsonify(db.get_employes())

@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json
    success, msg = db.add_employe(data['nom'], data['statut'], data.get('restriction_cls', False), data.get('restriction_handicap', 'Aucun'))
    return jsonify({'success': success, 'message': msg}), 200 if success else 400

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    db.delete_employe(emp_id)
    return jsonify({'success': True})

@app.route('/api/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    data = request.json
    success, msg = db.update_employe(emp_id, data['nom'], data['statut'], data.get('restriction_cls', False), data.get('restriction_handicap', 'Aucun'))
    return jsonify({'success': success, 'message': msg}), 200 if success else 400

# === PLANNING SAVES ===
@app.route('/api/planning/dates', methods=['GET'])
def get_saved_dates():
    return jsonify(db.get_sauvegarde_dates())

@app.route('/api/planning/<date_str>', methods=['GET'])
def get_planning(date_str):
    date_str_decoded = date_str.replace('-', '/')
    return jsonify(db.get_sauvegarde(date_str_decoded))

@app.route('/api/planning/<date_str>', methods=['POST'])
def save_planning(date_str):
    date_str_decoded = date_str.replace('-', '/')
    inputs = request.json
    db.save_planning(date_str_decoded, inputs)
    return jsonify({'success': True})

# === GENERATE PAUSES ===
@app.route('/api/generate_pauses', methods=['POST'])
def generate_pauses():
    data = request.json
    date_saisie = data.get('date', datetime.now().strftime("%d/%m/%Y"))
    inputs_dict = data.get('inputs', {})
    
    pauses_matin, pauses_aprem = [], []
    for nom, times in inputs_dict.items():
        e_m1, e_m2, e_a1, e_a2 = times.get('ms', ''), times.get('me', ''), times.get('aes', ''), times.get('aee', '')
        heure_debut_m = algo.get_time(e_m1)
        duree_m, heure_fin_m = algo.calc_duration(e_m1, e_m2)
        if duree_m > 0 and heure_debut_m: 
            pauses_matin.append({"nom": nom, "fin": heure_fin_m, "debut": heure_debut_m, "duree": int(duree_m * 3)})
        
        heure_debut_a = algo.get_time(e_a1)
        duree_a, heure_fin_a = algo.calc_duration(e_a1, e_a2)
        if duree_a > 0 and heure_debut_a: 
            pauses_aprem.append({"nom": nom, "fin": heure_fin_a, "debut": heure_debut_a, "duree": int(duree_a * 3)})

    pauses_matin.sort(key=lambda x: (x["fin"], x["debut"]))
    pauses_aprem.sort(key=lambda x: (x["fin"], x["debut"]))

    html = f"<html><head><meta charset='utf-8'><style>body{{font-family:'Segoe UI', sans-serif;}} table{{width:100%;border-collapse:collapse;}} th,td{{border:1px solid #aaa;padding:8px;text-align:center;}} td[contenteditable='true']{{cursor:text;outline:none;}} td:focus{{background:#e8f4f8;}} @media print{{.no-print{{display:none;}}}}</style></head><body><h2>FEUILLE DE PAUSES - {date_saisie}</h2>"
    
    html += "<h3>MATIN</h3><table><tr><th>Nom</th><th>Durée Acquise</th><th>Fin Théorique</th><th>Heure Départ</th><th>Heure Retour</th></tr>"
    for p in pauses_matin: 
        html += f"<tr><td contenteditable='true'><b>{p['nom'].title()}</b></td><td contenteditable='true'>{p['duree']} min</td><td style='color:gray;' contenteditable='true'>Fin {p['fin'].strftime('%H:%M')}</td><td contenteditable='true'></td><td contenteditable='true'></td></tr>"
    html += "</table>"
    
    html += "<h3>APRÈS-MIDI</h3><table><tr><th>Nom</th><th>Durée Acquise</th><th>Fin Théorique</th><th>Heure Départ</th><th>Heure Retour</th></tr>"
    for p in pauses_aprem: 
        html += f"<tr><td contenteditable='true'><b>{p['nom'].title()}</b></td><td contenteditable='true'>{p['duree']} min</td><td style='color:gray;' contenteditable='true'>Fin {p['fin'].strftime('%H:%M')}</td><td contenteditable='true'></td><td contenteditable='true'></td></tr>"
    html += "</table>"
    
    html += "<br><div class='no-print' style='text-align:center; display:flex; justify-content:center; gap:15px;'>"
    html += "<button onclick='window.print()' style='padding:10px 20px; font-weight:bold; cursor:pointer; background:#2CC985; color:white; border:none; border-radius:5px;'>🖨️ IMPRIMER</button>"
    html += f"<button onclick='downloadHTML()' style='padding:10px 20px; font-weight:bold; cursor:pointer; background:#3b82f6; color:white; border:none; border-radius:5px;'>💾 SAUVEGARDER SUR MON PC</button>"
    html += "</div>"
    html += """<script>
        function downloadHTML() {
            const htmlContent = document.documentElement.outerHTML;
            const blob = new Blob([htmlContent], {type: 'text/html'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '""" + f"Feuille_Pauses_{date_saisie.replace('/','-')}.html" + """';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    </script></body></html>"""
    
    nom_fichier = f"Feuille_Pauses_{date_saisie.replace('/','-')}.html"
    filepath = os.path.join(PAUSES_DIR, nom_fichier)
    with open(filepath, "w", encoding="utf-8") as f: 
        f.write(html)
        
    return jsonify({'url': f'/files/pauses/{nom_fichier}'})

# === GENERATE PLANNING ===
@app.route('/api/generate_planning', methods=['POST'])
def generate_planning():
    data = request.json
    date_saisie = data.get('date', datetime.now().strftime("%d/%m/%Y"))
    inputs_dict = data.get('inputs', {})
    
    # Load cache_emp
    employes = db.get_employes()
    cache_emp = {e['nom']: e for e in employes}
    
    res = algo.run_algo(date_saisie, inputs_dict, cache_emp)
    if "error" in res:
        return jsonify({'success': False, 'message': res['error']}), 400
        
    # Generate HTML
    slots = res['slots']
    employes_presents = res['employes_presents']
    matrice_planning = res['matrice_planning']
    plan_data = res['plan_data']
    infos_pauses = res['infos_pauses']
    closer_veille = res['closer_veille']
    emp_map = res['emp_map']
    
    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
        @page {{ size: A4 landscape; margin: 5mm; }}
        body {{ font-family: 'Poppins', sans-serif; font-size: 11px; padding: 0; margin: 0; background: #fafafa; -webkit-print-color-adjust: exact; color: #333; }}
        
        .main-container {{ background: white; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); padding: 20px; margin: 10px auto; width: 96%; }}
        h1 {{ text-align: center; color: #1a1a1a; margin: 0 0 5px 0; font-size: 26px; font-weight: 700; }}
        .sub-title-bar {{ display: flex; justify-content: space-between; align-items: center; background: #f0fdf4; border: 1px solid #dcfce7; padding: 10px 20px; border-radius: 8px; margin-bottom: 20px; color: #166534; font-size: 12px; font-weight: 600; }}
        
        table {{ border-collapse: separate; border-spacing: 0; width: 100%; table-layout: fixed; border-radius: 8px; overflow: hidden; border: 1px solid #e0e0e0; }}
        th, td {{ border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0; text-align: center; height: 26px; padding: 0; position: relative; }}
        th:last-child, td:last-child {{ border-right: none; }}
        tr:last-child td {{ border-bottom: none; }}
        
        th {{ background: #2CC985; color: white; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #24a871; padding: 8px 0; }}
        .time-range {{ display: block; font-size: 9px; opacity: 0.8; font-weight: 400; margin-top: 1px; }}
        
        .name {{ width: 160px; text-align: left; padding-left: 15px; background: #f9fafb; font-weight: 600; color: #1a1a1a; border-right: 2px solid #e0e0e0; }}
        tr:nth-child(even) td.name {{ background: #f3f4f6; }}
        
        .hour-cell {{ display: flex; width: 100%; height: 100%; position: relative; }}
        
        .sub-block {{ flex: 1; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 10px; cursor: text; outline: none; transition: background 0.2s; position: relative; margin: 2px; border-radius: 4px; border: 1px solid transparent; }}
        .sub-block:not(.bg-ABS):not(:empty) {{ box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
        
        /* Séparateur 15 min discret */
        .sub-block {{ border-right: 1px dashed rgba(0,0,0,0.08); margin: 2px 1px; }}
        .sub-block:last-child {{ border-right: none; }}
        
        .sub-block:focus {{ background: #fff !important; color: #333 !important; border: 2px solid #3498db; z-index: 10; box-shadow: 0 0 10px rgba(52, 152, 219, 0.3); }}
        
        /* Couleurs Foncées et Voyantes */
        .bg-CLS {{ background: #FACC15 !important; color: #000000 !important; border: 1px solid #CA8A04 !important; }}
        .bg-C1, .bg-C2 {{ background: #EF4444 !important; color: white !important; border: 1px solid #B91C1C !important; }}
        .bg-C5, .bg-C6 {{ background: #F97316 !important; color: white !important; border: 1px solid #C2410C !important; }}
        .bg-C13, .bg-C14 {{ background: #22C55E !important; color: white !important; border: 1px solid #15803D !important; }}
        .bg-P {{ background: #8B5CF6 !important; color: white !important; border: 1px solid #6D28D9 !important; font-size: 11px; }}
        .bg-POLY {{ background: #475569 !important; color: white !important; border: 1px solid #334155 !important; font-style: normal; }}
        .bg-ABS {{ background: #ffffff !important; color: transparent !important; }}
        
        [class^="bg-C"] {{ background: #0EA5E9 !important; color: white !important; border: 1px solid #0369A1 !important; }}
        
        @media print {{ 
            body {{ background: transparent; padding: 0; margin: 0; }}
            .main-container {{ box-shadow: none; border: none; width: 100%; padding: 0; margin: 0; }}
            table {{ border: 1px solid #ccc; }}
            .no-print {{ display: none; }}
            .sub-block {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
        .btn-container {{ text-align: center; margin-top: 25px; display: flex; justify-content: center; gap: 15px; }}
        .btn-print, .btn-download {{ padding: 12px 28px; text-decoration: none; border-radius: 30px; font-weight: 600; display: inline-block; cursor: pointer; border: none; font-size: 14px; transition: all 0.2s; color: white; }}
        .btn-print {{ background: #2CC985; box-shadow: 0 4px 10px rgba(44, 201, 133, 0.2); }}
        .btn-download {{ background: #3b82f6; box-shadow: 0 4px 10px rgba(59, 130, 246, 0.2); }}
    </style>
    </head><body>
    
    <div class="main-container">
        <h1>Planning {date_saisie}</h1>
        <div class="sub-title-bar">
            <div>Veille: {closer_veille if closer_veille else 'Inconnu'}</div>
            <div>{infos_pauses}</div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th class='name'>Employé</th>
    """
    
    for h in range(9, 20): 
        html += f"""
            <th>
                {h}H
                <span class="time-range">{h}H - {h+1}H</span>
            </th>
        """
    html += "</tr></thead><tbody>"
    
    for nom in sorted(employes_presents):
        html += f"<tr><td class='name'>{nom.title()}</td>"
        for h in range(9, 20):
            html += "<td><div class='hour-cell'>"
            
            for m in [0, 15, 30, 45]:
                time_str = f"{h:02d}:{m:02d}"
                label = "ABS"
                
                if time_str in slots:
                    idx = slots.index(time_str)
                    tache = matrice_planning[idx][emp_map[nom]]
                    if tache: 
                        label = tache
                    else:
                        heure_obj = datetime.strptime(time_str, "%H:%M")
                        present = False
                        for p in plan_data:
                            if p['nom'] == nom:
                                m_ok = (p['matin'][0] and p['matin'][1] and p['matin'][0] <= heure_obj < p['matin'][1])
                                a_ok = (p['aprem'][0] and p['aprem'][1] and p['aprem'][0] <= heure_obj < p['aprem'][1])
                                if m_ok or a_ok:
                                    present = True
                        if present: label = ""
                        
                label = label.replace("Caisse ", "C")
                if label == "PAUSE": label = "P"
                style_css = f"bg-{label}" if label in ["CLS", "C1", "C2", "C5", "C6", "C13", "C14", "P", "ABS", "POLY"] else ""
                if label != "ABS" and style_css == "" and label.startswith("C"):
                    style_css = "bg-C_OTHER"

                html += f"<div class='sub-block {style_css}' contenteditable='true'>{label if label != 'ABS' else ''}</div>"
            
            html += "</div></td>"
        html += "</tr>"
        
    html += """
            </tbody>
        </table>
    </div>
    
    <div class='no-print btn-container'>
        <button class='btn-print' onclick='window.print()'>🖨️ IMPRIMER LE PLANNING PRO</button>
        <button class='btn-download' onclick='downloadHTML()'>💾 SAUVEGARDER SUR MON PC</button>
    </div>
    
    <script>
        function downloadHTML() {
            const htmlContent = document.documentElement.outerHTML;
            const blob = new Blob([htmlContent], {type: 'text/html'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'Planning_A4_""" + f"{date_saisie.replace('/','-')}.html" + """';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        document.querySelectorAll('.sub-block').forEach(b => {
            b.addEventListener('input', function() {
                let t = this.innerText.trim().toUpperCase();
                this.className = 'sub-block'; 
                if (t === 'C1' || t === 'C2') this.classList.add('bg-C1');
                else if (t === 'C5' || t === 'C6') this.classList.add('bg-C5');
                else if (t === 'C13' || t === 'C14') this.classList.add('bg-C13');
                else if (t === 'CLS') this.classList.add('bg-CLS');
                else if (t === 'PAUSE' || t === 'MISSION PAUSE' || t === 'P') this.classList.add('bg-P');
                else if (t === 'POLY') this.classList.add('bg-POLY');
                else if (t === 'ABS' || t === '') this.classList.add('bg-ABS');
                else if (t.startsWith('C') && t.length > 1) this.classList.add('bg-C_OTHER');
            });
        });
    </script>
    </body></html>
    """
    
    nom_fichier = f"Planning_A4_{date_saisie.replace('/','-')}.html"
    filepath = os.path.join(PLANNINGS_DIR, nom_fichier)
    with open(filepath, "w", encoding="utf-8") as f: 
        f.write(html)
        
    return jsonify({'success': True, 'url': f'/files/plannings/{nom_fichier}'})

# === UPLOAD FICHIERS ===
@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun fichier reçu'}), 400
    
    files = request.files.getlist('files')
    uploaded = []
    errors = []
    
    for file in files:
        filename = file.filename
        if not filename.endswith('.html'):
            errors.append(f'{filename}: pas un fichier HTML')
            continue
        
        # Détecter si c'est un planning ou une feuille de pause
        if 'Pauses' in filename or 'pauses' in filename or 'PAUSES' in filename:
            dest = os.path.join(PAUSES_DIR, filename)
        else:
            dest = os.path.join(PLANNINGS_DIR, filename)
        
        file.save(dest)
        uploaded.append(filename)
    
    return jsonify({'success': True, 'uploaded': uploaded, 'errors': errors})

# === RECONSTRUCTION BDD DEPUIS HTML ===
@app.route('/api/rebuild_db', methods=['POST'])
def rebuild_db():
    import re
    import traceback
    
    try:
        fichiers = [f for f in os.listdir(PLANNINGS_DIR) if f.endswith('.html')]
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erreur lecture dossier: {str(e)}'}), 500
    
    total_entries = 0
    fichiers_traites = 0
    erreurs_fichiers = []
    
    slots_order = []
    for h in range(9, 20):
        for m in [0, 15, 30, 45]:
            slots_order.append((h, m))
    slots_order.append((20, 0))  # Sentinelle pour les fins à 20h
    # Index 16 = 13:00 (seuil matin/après-midi)
    IDX_MIDI = 16  # (13h - 9h) * 4 = 16
    
    for fichier in fichiers:
        try:
            match_date = re.search(r'(\d{2})-(\d{2})-(\d{4})', fichier)
            if not match_date:
                continue
            
            date_str = f"{match_date.group(1)}/{match_date.group(2)}/{match_date.group(3)}"
            filepath = os.path.join(PLANNINGS_DIR, fichier)
            
            # Essayer utf-8, puis latin-1 si ça échoue
            content = None
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(filepath, 'r', encoding=enc, errors='ignore') as f:
                        content = f.read()
                    break
                except Exception:
                    continue
            
            if not content:
                erreurs_fichiers.append(f"{fichier}: impossible de lire")
                continue
            
            # Extraire les lignes d'employés
            lignes = re.findall(r"<tr>\s*<td[^>]*class=['\"]name['\"][^>]*>(.*?)</td>(.*?)</tr>", content, re.DOTALL)
            
            if not lignes:
                # Essayer format alternatif
                lignes = re.findall(r"<tr><td class=['\"]name['\"]>(.*?)</td>(.*?)</tr>", content, re.DOTALL)
            
            if not lignes:
                continue
            
            fichiers_traites += 1
            entries = []
            
            for nom_html, contenu_ligne in lignes:
                nom = re.sub(r'<[^>]+>', '', nom_html).strip()
                if not nom or len(nom) < 2:
                    continue
                
                # Extraire les blocs 15min
                blocs = re.findall(r"<div[^>]*class=['\"][^'\"]*sub-block[^'\"]*['\"][^>]*>(.*?)</div>", contenu_ligne, re.DOTALL)
                taches = [re.sub(r'<[^>]+>', '', b).strip() for b in blocs]
                
                # Trouver les plages de travail (blocs non-vides)
                plage_active = []
                plages = []
                
                for i, t in enumerate(taches[:len(slots_order)]):
                    t_clean = t.upper().strip()
                    if t_clean and t_clean not in ['', 'ABS']:
                        plage_active.append(i)
                    else:
                        if len(plage_active) >= 2:
                            plages.append((plage_active[0], plage_active[-1]))
                        plage_active = []
                
                if len(plage_active) >= 2:
                    plages.append((plage_active[0], plage_active[-1]))
                
                ms, me, aes, aee = '', '', '', ''
                
                def get_time(idx):
                    i = min(idx, len(slots_order) - 1)
                    h_v, m_v = slots_order[i]
                    return f"{h_v:02d}:{m_v:02d}"
                
                if len(plages) == 1:
                    idx_start = plages[0][0]
                    idx_end = plages[0][1] + 1
                    # Si le bloc commence après 13h → c'est un shift après-midi/soir
                    if idx_start >= IDX_MIDI:
                        aes = get_time(idx_start)
                        aee = get_time(idx_end)
                    else:
                        ms = get_time(idx_start)
                        me = get_time(idx_end)
                
                elif len(plages) >= 2:
                    ms = get_time(plages[0][0])
                    me = get_time(plages[0][1] + 1)
                    aes = get_time(plages[1][0])
                    aee = get_time(plages[1][1] + 1)
                
                if ms or aes:
                    entries.append({'nom': nom, 'ms': ms, 'me': me, 'aes': aes, 'aee': aee})
                    total_entries += 1
            
            if entries:
                db.save_planning(date_str, entries)
        
        except Exception as e:
            erreurs_fichiers.append(f"{fichier}: {str(e)}")
            continue
    
    msg = f'{fichiers_traites} fichier(s) analysé(s), {total_entries} entrée(s) reconstruite(s).'
    if erreurs_fichiers:
        msg += f' Erreurs: {"; ".join(erreurs_fichiers[:3])}'
    
    return jsonify({'success': True, 'message': msg})

# === INTERIM ===
@app.route('/api/interim', methods=['GET'])
def get_interim():
    return jsonify(db.get_demandes_interim())

@app.route('/api/interim', methods=['POST'])
def add_interim():
    data = request.json
    db.add_demande_interim(data['absent'], data['dates_resume'], data['grille_data'])
    return jsonify({'success': True})

@app.route('/api/interim/<int:req_id>', methods=['DELETE'])
def delete_interim(req_id):
    db.delete_demande_interim(req_id)
    return jsonify({'success': True})

@app.route('/api/interim/assign', methods=['POST'])
def assign_interim():
    data = request.json
    nom_remplacant = data['nom_remplacant']
    nom_absent = data['nom_absent']
    grille_data = data['grille_data']
    
    jours = grille_data.split("|")
    for jour_data in jours:
        elements = jour_data.split(";")
        if len(elements) == 5:
            date_jour, m1, m2, a1, a2 = elements
            if not m1 and not a1: continue 
            db.transfer_horaires(nom_absent, nom_remplacant, date_jour, m1, m2, a1, a2)
            
    db.delete_demande_interim(data['req_id'])
    return jsonify({'success': True})

# === ARCHIVES ===
@app.route('/api/archives', methods=['GET'])
def get_archives():
    try:
        fichiers_plannings = [{'filename': f, 'type': 'plannings', 'name': f.replace(".html", "").replace("-", "/")} for f in os.listdir(PLANNINGS_DIR) if f.endswith(".html")]
    except FileNotFoundError:
        fichiers_plannings = []
        
    try:
        fichiers_pauses = [{'filename': f, 'type': 'pauses', 'name': f.replace(".html", "").replace("-", "/")} for f in os.listdir(PAUSES_DIR) if f.endswith(".html")]
    except FileNotFoundError:
        fichiers_pauses = []
        
    tous = sorted(fichiers_plannings + fichiers_pauses, key=lambda x: x['name'], reverse=True)
    return jsonify(tous)

# === STATS ===
@app.route('/api/stats/<date_str>', methods=['GET'])
def get_stats(date_str):
    import re
    date_str_decoded = date_str.replace('-', '/')
    try: 
        base_date = datetime.strptime(date_str_decoded, "%d/%m/%Y")
    except ValueError: 
        base_date = datetime.now()
        
    dates_html = [(base_date - timedelta(days=i)).strftime("%d-%m-%Y") for i in range(7)]
    stats = {}
    fichiers_trouves = 0
    
    for d_str in dates_html:
        nom_fichier = os.path.join(PLANNINGS_DIR, f"Planning_A4_{d_str}.html")
        if os.path.exists(nom_fichier):
            fichiers_trouves += 1
            with open(nom_fichier, "r", encoding="utf-8") as f: 
                content = f.read()
                
            lignes = re.findall(r"<tr>\s*<td class=['\"]name['\"][^>]*>(.*?)</td>(.*?)</tr>", content, re.DOTALL)
            for nom_html, contenu_ligne in lignes:
                nom = nom_html.strip().title()
                if nom not in stats: 
                    stats[nom] = {'c1': 0, 'c2': 0, 'cls': 0}
                    
                blocs = re.findall(r"<div class=['\"]sub-block([^>]*)>(.*?)</div>", contenu_ligne)
                for attributs, tache_html in blocs:
                    tache = tache_html.strip().upper()
                    if tache == 'C1': stats[nom]['c1'] += 1
                    elif tache == 'C2': stats[nom]['c2'] += 1
                    elif tache == 'CLS': stats[nom]['cls'] += 1
                    
    def formater_duree(blocs): 
        return f"{blocs * 15 // 60}h{blocs * 15 % 60:02d}" if blocs > 0 else "-"
        
    results = []
    for nom in sorted(stats.keys()):
        if stats[nom]['c1'] or stats[nom]['c2'] or stats[nom]['cls']:
            results.append({
                'nom': nom,
                'c1': formater_duree(stats[nom]['c1']),
                'c2': formater_duree(stats[nom]['c2']),
                'cls': formater_duree(stats[nom]['cls'])
            })
            
    return jsonify({
        'fichiers_trouves': fichiers_trouves,
        'stats': results
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
