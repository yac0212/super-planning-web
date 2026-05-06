document.addEventListener('DOMContentLoaded', () => {
    // === TABS NAVIGATION ===
    const navBtns = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            navBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            const targetId = `tab-${btn.dataset.tab}`;
            document.getElementById(targetId).classList.add('active');
            
            // Refresh specifics
            if (btn.dataset.tab === 'equipe') loadEmployees();
            if (btn.dataset.tab === 'planning' && !document.getElementById('planning-list').hasChildNodes()) refreshPlanning();
            if (btn.dataset.tab === 'interim') loadInterimData();
            if (btn.dataset.tab === 'archives') loadArchives();
        });
    });

    // === GLOBAL STATE ===
    let currentDate = new Date();
    
    function formatDate(date) {
        return `${date.getDate().toString().padStart(2, '0')}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getFullYear()}`;
    }
    
    document.getElementById('planning-date').value = formatDate(currentDate);

    document.getElementById('btn-prev-day').addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() - 1);
        document.getElementById('planning-date').value = formatDate(currentDate);
        refreshPlanning();
    });
    
    document.getElementById('btn-next-day').addEventListener('click', () => {
        currentDate.setDate(currentDate.getDate() + 1);
        document.getElementById('planning-date').value = formatDate(currentDate);
        refreshPlanning();
    });

    // === API HELPERS ===
    async function apiCall(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) options.body = JSON.stringify(body);
        
        try {
            const res = await fetch(url, options);
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.message || 'Erreur serveur');
            }
            return await res.json();
        } catch (e) {
            alert(e.message);
            return null;
        }
    }

    // === EMPLOYEES ===
    async function loadEmployees() {
        const emps = await apiCall('/api/employees');
        if (!emps) return;
        
        const list = document.getElementById('employee-list');
        list.innerHTML = '';
        
        emps.forEach(emp => {
            const card = document.createElement('div');
            card.className = 'emp-card';
            card.innerHTML = `
                <div class="emp-info">
                    <i data-lucide="user"></i>
                    <span>${emp.nom}</span>
                    <span class="emp-badge">${emp.statut}</span>
                    ${emp.restriction_cls ? '<span class="emp-badge" style="background: rgba(255, 71, 87, 0.2); color: var(--danger)">No CLS</span>' : ''}
                    ${emp.restriction_handicap !== 'Aucun' ? `<span class="emp-badge" style="background: rgba(255, 165, 2, 0.2); color: var(--warning)">${emp.restriction_handicap}</span>` : ''}
                </div>
                <div class="emp-actions">
                    <button class="btn-icon edit" onclick="openEditModal(${emp.id}, '${emp.nom.replace(/'/g, "\\'")}', '${emp.statut}', ${emp.restriction_cls}, '${emp.restriction_handicap}')"><i data-lucide="edit-2"></i></button>
                    <button class="btn-icon delete" onclick="deleteEmployee(${emp.id})"><i data-lucide="x"></i></button>
                </div>
            `;
            list.appendChild(card);
        });
        lucide.createIcons();
    }

    document.getElementById('add-emp-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            nom: document.getElementById('emp-nom').value,
            statut: document.getElementById('emp-statut').value,
            restriction_cls: document.getElementById('emp-cls').checked,
            restriction_handicap: document.getElementById('emp-handicap').value
        };
        const res = await apiCall('/api/employees', 'POST', data);
        if (res) {
            document.getElementById('emp-nom').value = '';
            loadEmployees();
        }
    });

    window.deleteEmployee = async (id) => {
        if (confirm('Supprimer cet employé ?')) {
            await apiCall(`/api/employees/${id}`, 'DELETE');
            loadEmployees();
        }
    };

    window.openEditModal = (id, nom, statut, cls, handicap) => {
        document.getElementById('edit-emp-id').value = id;
        document.getElementById('edit-emp-nom').value = nom;
        document.getElementById('edit-emp-statut').value = statut;
        document.getElementById('edit-emp-cls').checked = cls;
        document.getElementById('edit-emp-handicap').value = handicap;
        document.getElementById('edit-emp-modal').classList.add('active');
    };

    window.closeModal = (id) => {
        document.getElementById(id).classList.remove('active');
    };

    document.getElementById('edit-emp-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('edit-emp-id').value;
        const data = {
            nom: document.getElementById('edit-emp-nom').value,
            statut: document.getElementById('edit-emp-statut').value,
            restriction_cls: document.getElementById('edit-emp-cls').checked,
            restriction_handicap: document.getElementById('edit-emp-handicap').value
        };
        const res = await apiCall(`/api/employees/${id}`, 'PUT', data);
        if (res) {
            closeModal('edit-emp-modal');
            loadEmployees();
        }
    });

    // === PLANNING ===
    async function refreshPlanning() {
        const emps = await apiCall('/api/employees');
        if (!emps) return;
        
        const list = document.getElementById('planning-list');
        list.innerHTML = '';
        
        emps.forEach(emp => {
            const row = document.createElement('div');
            row.className = 'planning-row';
            row.dataset.nom = emp.nom;
            
            row.innerHTML = `
                <div class="name">${emp.nom}</div>
                <div class="time-inputs matin">
                    <input type="text" class="m1" placeholder="09:00">
                    <input type="text" class="m2" placeholder="13:00">
                </div>
                <div class="time-inputs aprem">
                    <input type="text" class="a1" placeholder="14:00">
                    <input type="text" class="a2" placeholder="19:00">
                </div>
            `;
            list.appendChild(row);
        });
    }
    
    document.getElementById('btn-refresh-planning').addEventListener('click', refreshPlanning);

    function getPlanningInputs() {
        const rows = document.querySelectorAll('.planning-row');
        const inputs = {};
        const inputsList = [];
        
        rows.forEach(row => {
            const nom = row.dataset.nom;
            const m1 = row.querySelector('.m1').value.trim();
            const m2 = row.querySelector('.m2').value.trim();
            const a1 = row.querySelector('.a1').value.trim();
            const a2 = row.querySelector('.a2').value.trim();
            
            if (m1 || a1) {
                inputs[nom] = { ms: m1, me: m2, aes: a1, aee: a2 };
                inputsList.push({ nom, ms: m1, me: m2, aes: a1, aee: a2 });
            }
        });
        return { inputs, inputsList };
    }

    document.getElementById('btn-save-planning').addEventListener('click', async () => {
        const dateStr = document.getElementById('planning-date').value;
        const { inputsList } = getPlanningInputs();
        
        const res = await apiCall(`/api/planning/${dateStr.replace(/\//g, '-')}`, 'POST', inputsList);
        if (res) alert('Horaires enregistrés !');
    });

    document.getElementById('btn-load-planning').addEventListener('click', async () => {
        const dates = await apiCall('/api/planning/dates');
        if (!dates || dates.length === 0) {
            alert('Aucune sauvegarde trouvée.');
            return;
        }
        
        const dateStr = prompt(`Dates disponibles: \n${dates.join('\n')}\nEntrez la date (JJ/MM/YYYY):`, dates[0]);
        if (dateStr) {
            const data = await apiCall(`/api/planning/${dateStr.replace(/\//g, '-')}`);
            if (data && data.length > 0) {
                document.getElementById('planning-date').value = dateStr;
                const parts = dateStr.split('/');
                currentDate = new Date(`${parts[2]}-${parts[1]}-${parts[0]}`);
                
                await refreshPlanning();
                
                const rows = document.querySelectorAll('.planning-row');
                const nomsDejaRemplis = new Set();
                
                // Correspondance flexible : exacte d'abord, puis partielle
                rows.forEach(row => {
                    const nomRow = row.dataset.nom.toLowerCase().trim();
                    
                    // 1. Correspondance exacte
                    let saved = data.find(d => d.nom.toLowerCase().trim() === nomRow);
                    
                    // 2. Correspondance partielle (l'un contient l'autre)
                    if (!saved) {
                        saved = data.find(d => {
                            const nomSaved = d.nom.toLowerCase().trim();
                            return nomRow.includes(nomSaved) || nomSaved.includes(nomRow);
                        });
                    }
                    
                    if (saved) {
                        row.querySelector('.m1').value = saved.ms || '';
                        row.querySelector('.m2').value = saved.me || '';
                        row.querySelector('.a1').value = saved.aes || '';
                        row.querySelector('.a2').value = saved.aee || '';
                        nomsDejaRemplis.add(saved.nom.toLowerCase().trim());
                    }
                });
                
                // Ajouter les entrées sauvegardées sans correspondance dans l'équipe actuelle
                const list = document.getElementById('planning-list');
                data.forEach(saved => {
                    if (nomsDejaRemplis.has(saved.nom.toLowerCase().trim())) return;
                    if (!saved.ms && !saved.aes) return;
                    
                    const row = document.createElement('div');
                    row.className = 'planning-row';
                    row.dataset.nom = saved.nom;
                    row.innerHTML = `
                        <div class="name" style="color: var(--warning);">${saved.nom} <small>(non inscrit)</small></div>
                        <div class="time-inputs matin">
                            <input type="text" class="m1" placeholder="09:00" value="${saved.ms || ''}">
                            <input type="text" class="m2" placeholder="13:00" value="${saved.me || ''}">
                        </div>
                        <div class="time-inputs aprem">
                            <input type="text" class="a1" placeholder="14:00" value="${saved.aes || ''}">
                            <input type="text" class="a2" placeholder="19:00" value="${saved.aee || ''}">
                        </div>
                    `;
                    list.appendChild(row);
                });
            }
        }
    });

    document.getElementById('btn-generate-pauses').addEventListener('click', async () => {
        const { inputs } = getPlanningInputs();
        const data = {
            date: document.getElementById('planning-date').value,
            inputs: inputs
        };
        const res = await apiCall('/api/generate_pauses', 'POST', data);
        if (res && res.url) window.open(res.url, '_blank');
    });

    document.getElementById('btn-generate-planning').addEventListener('click', async () => {
        const { inputs } = getPlanningInputs();
        if (Object.keys(inputs).length === 0) {
            alert("Veuillez saisir au moins un horaire.");
            return;
        }
        const data = {
            date: document.getElementById('planning-date').value,
            inputs: inputs
        };
        const res = await apiCall('/api/generate_planning', 'POST', data);
        if (res && res.url) window.open(res.url, '_blank');
    });

    // === INTERIM ===
    async function loadInterimData() {
        const emps = await apiCall('/api/employees');
        const selAbsent = document.getElementById('interim-absent');
        selAbsent.innerHTML = '';
        emps.forEach(e => {
            const opt = document.createElement('option');
            opt.value = e.nom; opt.textContent = e.nom;
            selAbsent.appendChild(opt);
        });
        
        document.getElementById('interim-start').value = document.getElementById('planning-date').value;
        document.getElementById('interim-end').value = document.getElementById('planning-date').value;
        
        loadInterimRequests();
    }

    document.getElementById('btn-generate-interim-grid').addEventListener('click', () => {
        // Simplification for the web demo: just generate the requested dates rows manually
        const start = document.getElementById('interim-start').value;
        const end = document.getElementById('interim-end').value;
        
        const grid = document.getElementById('interim-grid');
        grid.innerHTML = '';
        
        // Let's just create 1 row for simplicity, or we can parse dates. 
        // For MVP frontend, we do 1 row representing the period
        grid.innerHTML = `
            <div class="interim-grid-row" data-date="${start}">
                <span>${start} :</span>
                <input type="text" class="im1" placeholder="09:00">
                <input type="text" class="im2" placeholder="13:00">
                <input type="text" class="ia1" placeholder="14:00">
                <input type="text" class="ia2" placeholder="19:00">
            </div>
        `;
    });

    document.getElementById('btn-write-email').addEventListener('click', () => {
        const absent = document.getElementById('interim-absent').value;
        document.getElementById('interim-email').value = `Bonjour,\n\nSuite à l'absence de ${absent}, voici nos besoins en remplacement :\n\nMerci de confirmer.`;
    });

    document.getElementById('btn-save-interim').addEventListener('click', async () => {
        const absent = document.getElementById('interim-absent').value;
        const start = document.getElementById('interim-start').value;
        const end = document.getElementById('interim-end').value;
        
        const row = document.querySelector('.interim-grid-row');
        if(!row) return alert("Veuillez générer la grille d'abord");
        
        const m1 = row.querySelector('.im1').value;
        const m2 = row.querySelector('.im2').value;
        const a1 = row.querySelector('.ia1').value;
        const a2 = row.querySelector('.ia2').value;
        
        const grille_data = `${start};${m1};${m2};${a1};${a2}`;
        
        const res = await apiCall('/api/interim', 'POST', {
            absent,
            dates_resume: `Du ${start} au ${end}`,
            grille_data
        });
        
        if (res) loadInterimRequests();
    });

    async function loadInterimRequests() {
        const reqs = await apiCall('/api/interim');
        const emps = await apiCall('/api/employees');
        const interims = emps.filter(e => e.statut === 'Interimaire');
        
        const list = document.getElementById('interim-requests-list');
        list.innerHTML = '';
        
        if (!reqs) return;
        
        reqs.forEach(req => {
            const div = document.createElement('div');
            div.className = 'form-row';
            div.style.background = 'rgba(0,0,0,0.2)';
            div.style.padding = '10px';
            div.style.borderRadius = '8px';
            div.style.justifyContent = 'space-between';
            
            let options = interims.map(i => `<option value="${i.nom}">${i.nom}</option>`).join('');
            if(options === '') options = '<option>Aucun Intérim</option>';
            
            div.innerHTML = `
                <span><b>${req.absent}</b><br><small>${req.dates_resume}</small></span>
                <select id="assign-${req.id}">${options}</select>
                <div style="display:flex; gap:5px;">
                    <button class="btn btn-primary" onclick="assignInterim(${req.id}, '${req.absent}', '${req.grille_data}')"><i data-lucide="check"></i></button>
                    <button class="btn btn-icon delete" onclick="deleteInterim(${req.id})"><i data-lucide="x"></i></button>
                </div>
            `;
            list.appendChild(div);
        });
        lucide.createIcons();
    }

    window.assignInterim = async (req_id, nom_absent, grille_data) => {
        const nom_remplacant = document.getElementById(`assign-${req_id}`).value;
        if (nom_remplacant === 'Aucun Intérim') return;
        
        const res = await apiCall('/api/interim/assign', 'POST', {
            req_id, nom_absent, nom_remplacant, grille_data
        });
        if (res) {
            alert('Horaires transférés !');
            loadInterimRequests();
            refreshPlanning();
        }
    };

    window.deleteInterim = async (req_id) => {
        if(confirm('Supprimer cette demande ?')) {
            await apiCall(`/api/interim/${req_id}`, 'DELETE');
            loadInterimRequests();
        }
    };

    // === STATS & ARCHIVES ===
    document.getElementById('btn-load-stats').addEventListener('click', async () => {
        const dateStr = document.getElementById('planning-date').value;
        const res = await apiCall(`/api/stats/${dateStr.replace(/\//g, '-')}`);
        
        const container = document.getElementById('stats-container');
        if (!res || res.fichiers_trouves === 0) {
            container.innerHTML = '<p>Aucun planning trouvé sur les 7 derniers jours.</p>';
            return;
        }
        
        let html = `<p style="margin-bottom: 15px; color: var(--text-muted);">Basé sur ${res.fichiers_trouves} jours glissants.</p>`;
        html += `<table class="stats-table">
            <thead>
                <tr><th>Employé</th><th>C1</th><th>C2</th><th>CLS</th></tr>
            </thead><tbody>`;
            
        res.stats.forEach(s => {
            html += `<tr><td><b>${s.nom}</b></td><td>${s.c1}</td><td>${s.c2}</td><td>${s.cls}</td></tr>`;
        });
        
        html += `</tbody></table>`;
        container.innerHTML = html;
    });

    async function loadArchives() {
        const res = await apiCall('/api/archives');
        const grid = document.getElementById('archives-list');
        grid.innerHTML = '';
        
        if (!res || res.length === 0) {
            grid.innerHTML = '<p>Aucune archive trouvée.</p>';
            return;
        }
        
        res.forEach(f => {
            const card = document.createElement('div');
            card.className = 'archive-card';
            let icon = f.type === 'pauses' ? 'coffee' : 'calendar';
            let displayName = f.name.replace('Planning_A4_', 'Planning ').replace('Feuille_Pauses_', 'Pauses ');
            
            card.innerHTML = `
                <div class="archive-icon"><i data-lucide="${icon}"></i></div>
                <div style="font-weight: 600">${displayName}</div>
            `;
            card.addEventListener('click', () => {
                window.open(`/files/${f.type}/${f.filename}`, '_blank');
            });
            grid.appendChild(card);
        });
        lucide.createIcons();
    }

    // === UPLOAD FICHIERS ===
    document.getElementById('btn-upload-files').addEventListener('click', () => {
        document.getElementById('upload-input').click();
    });

    document.getElementById('upload-input').addEventListener('change', async (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        const statusDiv = document.getElementById('upload-status');
        statusDiv.style.display = 'block';
        statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color: var(--text-muted);">⏳ Envoi de ${files.length} fichier(s) en cours...</div>`;

        const formData = new FormData();
        for (let f of files) {
            formData.append('files', f);
        }

        try {
            const res = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await res.json();

            if (data.success) {
                let msg = `<div class="glass-card" style="padding:12px;">`;
                msg += `<p style="color:#16a34a; font-weight:600;">✅ ${data.uploaded.length} fichier(s) importé(s) avec succès !</p>`;
                if (data.uploaded.length > 0) {
                    msg += `<ul style="font-size:12px; color: var(--text-muted); margin-top:5px;">` + data.uploaded.map(f => `<li>${f}</li>`).join('') + `</ul>`;
                }
                if (data.errors.length > 0) {
                    msg += `<p style="color:#dc2626; margin-top:8px;">⚠️ Erreurs : ${data.errors.join(', ')}</p>`;
                }
                msg += `</div>`;
                statusDiv.innerHTML = msg;
                loadArchives(); // Rafraîchir la liste
            } else {
                statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color:#dc2626;">❌ Erreur : ${data.message}</div>`;
            }
        } catch (err) {
            statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color:#dc2626;">❌ Erreur de connexion.</div>`;
        }

        // Réinitialiser l'input pour permettre de re-sélectionner les mêmes fichiers
        e.target.value = '';
    });

    // === RECONSTRUIRE LA BDD ===
    document.getElementById('btn-rebuild-db').addEventListener('click', async () => {
        if (!confirm('Ceci va analyser tous vos plannings importés et reconstruire l\'historique des horaires dans la base de données.\n\nContinuer ?')) return;
        
        const statusDiv = document.getElementById('upload-status');
        statusDiv.style.display = 'block';
        statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color: var(--text-muted);">⏳ Analyse des fichiers en cours, cela peut prendre quelques secondes...</div>`;
        
        try {
            const res = await fetch('/api/rebuild_db', { method: 'POST' });
            const data = await res.json();
            
            if (data.success) {
                statusDiv.innerHTML = `<div class="glass-card" style="padding:12px;">
                    <p style="color:#16a34a; font-weight:600;">✅ Base de données reconstruite !</p>
                    <p style="font-size:13px; color: var(--text-muted); margin-top:5px;">${data.message}</p>
                    <p style="font-size:12px; color: var(--text-muted); margin-top:5px;">Vous pouvez maintenant utiliser "Charger" dans l'onglet Planification pour retrouver vos horaires.</p>
                </div>`;
            } else {
                statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color:#dc2626;">❌ Erreur : ${data.message}</div>`;
            }
        } catch (err) {
            statusDiv.innerHTML = `<div class="glass-card" style="padding:12px; color:#dc2626;">❌ Erreur de connexion.</div>`;
        }
    });

    // Init
    refreshPlanning();
});
