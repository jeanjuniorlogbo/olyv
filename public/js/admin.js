'use strict';

function rightSidebar(s) {
    const pendingReports = (s.reports || []).filter(r => r.status === 'pending');
    const stats = s.stats || {};

    return `
        <div class="rdv-card">
            <h3>Vue rapide</h3>
            <div class="auth-item">
                <div><b>Comptes actifs</b><div class="muted" style="font-size:0.78rem;">sur ${stats.active_users + stats.inactive_users} inscrits</div></div>
                <span style="font-family:var(--font-serif); font-size:1.15rem; color:var(--gold-600);">${stats.active_users}</span>
            </div>
            <div class="auth-item">
                <div><b>Médecins en attente</b><div class="muted" style="font-size:0.78rem;">vérification requise</div></div>
                <span style="font-family:var(--font-serif); font-size:1.15rem; color:var(--gold-600);">${stats.doctors_pending || 0}</span>
            </div>
            <div class="auth-item">
                <div><b>Établissements en attente</b><div class="muted" style="font-size:0.78rem;">vérification requise</div></div>
                <span style="font-family:var(--font-serif); font-size:1.15rem; color:var(--gold-600);">${stats.facilities_pending || 0}</span>
            </div>
            <div class="auth-item">
                <div><b>Signalements ouverts</b><div class="muted" style="font-size:0.78rem;">à traiter</div></div>
                <span style="font-family:var(--font-serif); font-size:1.15rem; color:var(--brick-600);">${pendingReports.length}</span>
            </div>
        </div>

        <div class="rdv-card">
            <h3>Signalements en attente</h3>
            ${pendingReports.length ? pendingReports.slice(0, 3).map(r => `
                <div class="auth-item">
                    <div>
                        <b>${esc(r.rp_subject)}</b>
                        <div class="muted" style="font-size:0.78rem;">Par ${esc(r.reporter_email)} — ${fmtDate(r.rp_created_at)}</div>
                    </div>
                    ${badge(r.status)}
                </div>
            `).join('') : '<p class="muted" style="font-size:0.85rem;">Aucun signalement en attente.</p>'}
            ${pendingReports.length ? `<button class="btn-full" style="margin-top:12px;" onclick="location.hash='#reports'">Voir tous les signalements</button>` : ''}
        </div>
    `;
}

function rightDefault(s) {
    return rightSidebar(s);
}

function showPasswordModal({ title, label, password }) {
    const body = password
        ? `
            <p class="modal-message"><b>${esc(label)}</b></p>
            <p class="modal-message" style="margin-top:8px;">
                Communiquez ce mot de passe au titulaire du compte. Il ne sera plus jamais affiché.
            </p>
            <div class="row" style="margin-top:14px; align-items:center; gap:10px;">
                <code style="font-size:1.1rem; padding:8px 14px; background:var(--gold-050); border:1px solid var(--gold-100); border-radius:8px; letter-spacing:0.05em;">${esc(password)}</code>
                <button type="button" class="btn ghost sm" data-action="copyPassword" data-value="${esc(password)}">Copier</button>
            </div>`
        : `
            <p class="modal-message"><b>${esc(label)}</b></p>
            <p class="modal-message" style="margin-top:8px;">
                Le mot de passe choisi a été appliqué (non généré, donc non ré-affiché).
            </p>`;

    modal({
        title,
        body,
        size: 'sm',
        actions: [
            { id: 'close', label: 'Fermer', cls: 'ghost', onClick: ({ close }) => close() },
        ],
    });
}
actions.copyPassword = async el => {
    try { await navigator.clipboard.writeText(el.dataset.value); toast('Mot de passe copié.'); }
    catch (e) { toast('Impossible de copier automatiquement.', 'error'); }
};

function openCreateDoctorModal() {
    const body = `
        <form data-modal-prompt class="grid">
            ${fld('last_name', 'Nom', '', { required: true })}
            ${fld('first_name', 'Prénom', '', { required: true })}
            ${fld('email', 'E-mail', '', { type: 'email', required: true })}
            ${fld('phone', 'Téléphone', '', { required: true })}
            ${fld('professional_id', 'Identifiant professionnel', '', { required: true })}
            ${fld('specialty', 'Spécialité', '', { required: true })}
            ${fld('password', 'Mot de passe (laisser vide pour générer)', '', { type: 'password', wide: true })}
        </form>`;

    const m = modal({
        title: 'Nouveau compte médecin',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'next', label: 'Continuer', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    close();
                    await confirmCreateDoctor(d);
                },
            },
        ],
    });
    return m;
}

async function confirmCreateDoctor(d) {
    const ok = await confirmAction({
        title: 'Confirmer la création',
        message: `
            Vous êtes sur le point de créer un <b>compte médecin vérifié</b>.<br><br>
            <b>Nom :</b> Dr ${esc(fullName(d.first_name, d.last_name))}<br>
            <b>Spécialité :</b> ${esc(d.specialty)}<br>
            <b>N° professionnel :</b> ${esc(d.professional_id)}<br>
            <b>E-mail :</b> ${esc(d.email)}<br><br>
            Ce compte sera immédiatement actif et pourra se connecter.`,
        confirmLabel: 'Créer le compte',
    });
    if (!ok) { openCreateDoctorModal(); return; }

    try {
        if (!d.password) delete d.password;
        const res = await api('/api/admin/doctors', 'POST', d);
        showPasswordModal({
            title: 'Compte médecin créé',
            label: 'Le compte a été créé et vérifié.',
            password: res.data && res.data.password,
        });
        toast('Compte médecin créé.');
    } catch (e) {
        toast(e.message, 'error');
        openCreateDoctorModal();
    }
}

function openCreateFacilityModal() {
    const body = `
        <form data-modal-prompt class="grid">
            ${fld('name', 'Nom de l’établissement', '', { required: true, wide: true })}
            ${sel('facility_type', 'Type', [['hopital', 'Hôpital'], ['clinique', 'Clinique'], ['cabinet', 'Cabinet'], ['centre_de_sante', 'Centre de santé']])}
            ${fld('email', 'E-mail', '', { type: 'email', required: true })}
            ${fld('phone', 'Téléphone', '', { required: true })}
            ${fld('address', 'Adresse', '', { required: true, wide: true })}
            ${fld('city', 'Ville', '', { required: true })}
            ${fld('country', 'Pays', '', { required: true })}
            ${fld('password', 'Mot de passe (laisser vide pour générer)', '', { type: 'password', wide: true })}
        </form>`;

    modal({
        title: 'Nouveau compte établissement',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'next', label: 'Continuer', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    close();
                    await confirmCreateFacility(d);
                },
            },
        ],
    });
}

async function confirmCreateFacility(d) {
    const typeLabel = { hopital: 'Hôpital', clinique: 'Clinique', cabinet: 'Cabinet', centre_de_sante: 'Centre de santé' }[d.facility_type] || d.facility_type;
    const ok = await confirmAction({
        title: 'Confirmer la création',
        message: `
            Vous êtes sur le point de créer un <b>compte établissement vérifié</b>.<br><br>
            <b>Nom :</b> ${esc(d.name)}<br>
            <b>Type :</b> ${esc(typeLabel)}<br>
            <b>Ville :</b> ${esc(d.city)}, ${esc(d.country)}<br>
            <b>E-mail :</b> ${esc(d.email)}<br><br>
            Ce compte sera immédiatement actif et visible des patients.`,
        confirmLabel: 'Créer le compte',
    });
    if (!ok) { openCreateFacilityModal(); return; }

    try {
        if (!d.password) delete d.password;
        const res = await api('/api/admin/facilities', 'POST', d);
        showPasswordModal({
            title: 'Compte établissement créé',
            label: 'Le compte a été créé et vérifié.',
            password: res.data && res.data.password,
        });
        toast('Compte établissement créé.');
    } catch (e) {
        toast(e.message, 'error');
        openCreateFacilityModal();
    }
}

function accountsSection() { return {
    id: 'accounts', label: 'Créer un compte pro',
    render: () => `
        <section class="card">
            <div class="card-head"><h2>Comptes professionnels</h2></div>
            <p class="muted" style="margin-top:-6px; margin-bottom:20px;">
                Les comptes médecins et établissements sont créés ici, déjà vérifiés.
                Chaque création ouvre une fenêtre de confirmation.
            </p>
            <div class="actions-grid">
                <button type="button" class="action-tile" data-action="openCreateDoctor">
                    <div class="action-tile-icon">
                        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                            <path d="M12 8v6"></path><path d="M9 11h6"></path>
                        </svg>
                    </div>
                    <div class="action-tile-text">
                        <b>Nouveau médecin</b>
                        <span>Créer un compte professionnel de santé vérifié</span>
                    </div>
                </button>

                <button type="button" class="action-tile" data-action="openCreateFacility">
                    <div class="action-tile-icon">
                        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 21h18"></path>
                            <path d="M5 21V7l8-4v18"></path>
                            <path d="M19 21V11l-6-4"></path>
                        </svg>
                    </div>
                    <div class="action-tile-text">
                        <b>Nouvel établissement</b>
                        <span>Créer un compte structure de soins vérifié</span>
                    </div>
                </button>
            </div>
        </section>
    `,
}; }

actions.openCreateDoctor = () => openCreateDoctorModal();
actions.openCreateFacility = () => openCreateFacilityModal();

function usersSection() { return {
    id: 'users', label: 'Utilisateurs',
    render: () => card('Rechercher un utilisateur', `
        <form data-form="searchUsers" class="grid">
            ${fld('q', 'E-mail ou téléphone')}
            ${sel('role', 'Rôle', [['', 'Tous'], ['patient', 'Patient'], ['medecin', 'Médecin'], ['etablissement', 'Établissement'], ['admin', 'Administrateur']])}
            <button class="btn">Rechercher</button>
        </form>
        <div id="user-results" style="margin-top:16px;"></div>
    `),
}; }

async function renderUsers(query) {
    const data = (await api(`/api/admin/users?${query}`)).data;
    const users = data.users || [];
    const target = $('#user-results');
    if (!target) return;
    target.innerHTML = users.length ? `
        <div class="doc-list">
            ${users.map(u => `
                <div class="doc-item">
                    <div class="avatar">${initials((u.u_email || '?')[0], '')}</div>
                    <div class="doc-info">
                        <b>${esc(u.u_email || u.u_phone || '—')}</b>
                        <span>${esc(u.u_phone || '')} · Créé le ${fmtDate(u.u_created_at)}</span>
                    </div>
                    <div class="row">
                        ${badge(u.role)}
                        ${u.u_is_active ? badge('active') : badge('revoked')}
                        ${btn(u.u_is_active ? 'Désactiver' : 'Activer', 'toggleUser',
                            { id: u.u_id, active: u.u_is_active ? 0 : 1 },
                            u.u_is_active ? 'danger sm' : 'sm')}
                        ${btn('Réinitialiser le mot de passe', 'resetPassword', { id: u.u_id }, 'ghost sm')}
                    </div>
                </div>
            `).join('')}
        </div>
    ` : empty('Aucun utilisateur trouvé.');
}

actions.searchUsers = async (form, d) => { await renderUsers(new URLSearchParams(d)); };

actions.resetPassword = async el => {
    const ok = await confirmAction({
        title: 'Réinitialiser le mot de passe ?',
        message: 'Le titulaire du compte sera immédiatement déconnecté et devra utiliser le nouveau mot de passe.',
        confirmLabel: 'Réinitialiser',
        danger: true,
    });
    if (!ok) return;
    const res = await api(`/api/admin/users/${el.dataset.id}/reset-password`, 'POST', {});
    showPasswordModal({
        title: 'Mot de passe réinitialisé',
        label: 'Nouveau mot de passe :',
        password: res.data && res.data.password,
    });
};

actions.toggleUser = async el => {
    const active = el.dataset.active === '1';
    const ok = await confirmAction({
        title: active ? 'Réactiver ce compte ?' : 'Désactiver ce compte ?',
        message: active
            ? 'Le compte pourra à nouveau se connecter.'
            : 'Le titulaire sera immédiatement déconnecté et ne pourra plus se connecter.',
        confirmLabel: active ? 'Réactiver' : 'Désactiver',
        danger: !active,
    });
    if (!ok) return;
    await api(`/api/admin/users/${el.dataset.id}/status`, 'POST', { active });
    await renderUsers('');
    toast('Statut mis à jour.');
};

function verificationsSection() { return {
    id: 'verifications', label: 'Vérifications',
    render: s => {
        const doctors = s.doctors || [];
        const facilities = s.facilities || [];
        return card('Médecins', doctors.length ? `
            <div class="doc-list">
                ${doctors.map(d => `
                    <div class="doc-item">
                        <div class="avatar">${initials(d.d_first_name, d.d_last_name)}</div>
                        <div class="doc-info">
                            <b>Dr ${esc(fullName(d.d_first_name, d.d_last_name))}</b>
                            <span>${esc(d.d_specialty || '')} · N° ${esc(d.d_professional_id || '—')} · ${esc(d.u_email || '')}</span>
                        </div>
                        <div class="row">
                            ${d.d_verification_status ? badge('active') : badge('pending')}
                            ${btn(d.d_verification_status ? 'Suspendre' : 'Vérifier', 'verifyDoctor',
                                { id: d.d_id, verified: d.d_verification_status ? 0 : 1 },
                                d.d_verification_status ? 'danger sm' : 'sm')}
                        </div>
                    </div>
                `).join('')}
            </div>
        ` : empty('Aucun médecin.'))
        + card('Établissements', facilities.length ? `
            <div class="doc-list">
                ${facilities.map(f => `
                    <div class="doc-item">
                        <div class="avatar">${initials(f.hf_name, '')}</div>
                        <div class="doc-info">
                            <b>${esc(f.hf_name)}</b>
                            <span>${esc(f.hf_type || '')} · ${esc(f.hf_city || '')} · ${esc(f.hf_phone || '')}</span>
                        </div>
                        <div class="row">
                            ${f.hf_verification_status ? badge('active') : badge('pending')}
                            ${btn(f.hf_verification_status ? 'Suspendre' : 'Vérifier', 'verifyFacility',
                                { id: f.hf_id, verified: f.hf_verification_status ? 0 : 1 },
                                f.hf_verification_status ? 'danger sm' : 'sm')}
                        </div>
                    </div>
                `).join('')}
            </div>
        ` : empty('Aucun établissement.'));
    },
}; }

actions.verifyDoctor = async el => {
    const verified = el.dataset.verified === '1';
    const ok = await confirmAction({
        title: verified ? 'Vérifier ce médecin ?' : 'Suspendre ce médecin ?',
        message: verified
            ? 'Il pourra rejoindre des établissements et accéder aux dossiers des patients qui l’autorisent.'
            : 'Il ne pourra plus accéder à aucun dossier patient tant qu’il n’est pas revérifié.',
        confirmLabel: verified ? 'Vérifier' : 'Suspendre',
        danger: !verified,
    });
    if (!ok) return;
    await api(`/api/admin/doctors/${el.dataset.id}/verify`, 'POST', { verified });
    await reload();
    return 'Vérification mise à jour.';
};

actions.verifyFacility = async el => {
    const verified = el.dataset.verified === '1';
    const ok = await confirmAction({
        title: verified ? 'Vérifier cet établissement ?' : 'Suspendre cet établissement ?',
        message: verified
            ? 'Il deviendra visible des patients dans les recherches.'
            : 'Il ne sera plus visible des patients dans les recherches.',
        confirmLabel: verified ? 'Vérifier' : 'Suspendre',
        danger: !verified,
    });
    if (!ok) return;
    await api(`/api/admin/facilities/${el.dataset.id}/verify`, 'POST', { verified });
    await reload();
    return 'Vérification mise à jour.';
};

const REPORT_STATUSES = [['pending', 'En attente'], ['reviewing', 'En examen'], ['resolved', 'Résolu'], ['dismissed', 'Classé']];

function reportsSection() { return {
    id: 'reports', label: 'Signalements', badge: s => s.reports.filter(r => r.status === 'pending').length,
    render: s => card('Signalements', s.reports.length ? s.reports.map(r => `
        <div class="item">
            <div class="row"><b>${esc(r.rp_subject)}</b> ${badge(r.status)}<span class="muted">${fmtDateTime(r.rp_created_at)}</span></div>
            <div style="margin:6px 0;">${esc(r.rp_description)}</div>
            <div class="muted">Par ${esc(r.reporter_email)}${r.reported_email ? ' — contre ' + esc(r.reported_email) : ''}</div>
            <form data-form="reportStatus" class="inline" style="margin-top:8px">
                <input type="hidden" name="id" value="${r.rp_id}">
                ${sel('status', '', REPORT_STATUSES, r.status)}
                <button class="btn sm">Mettre à jour</button>
            </form>
        </div>
    `).join('') : empty('Aucun signalement.')),
}; }

actions.reportStatus = async (form, d) => {
    await api(`/api/admin/reports/${d.id}/status`, 'POST', { status: d.status });
    await reload();
    return 'Signalement mis à jour.';
};

function logsSection() { return {
    id: 'logs', label: 'Journal technique',
    render: () => card('Journal technique (aucune donnée médicale)', `<div id="logs-table"></div>`, btn('Actualiser', 'loadLogs', {}, 'ghost')),
    after: () => actions.loadLogs(),
}; }

actions.loadLogs = async () => {
    const target = $('#logs-table');
    if (!target) return;
    target.innerHTML = skeletonTable(5);
    try {
        const rows = (await api('/api/admin/logs')).data || [];
        if (!$('#logs-table')) return;
        target.innerHTML = rows.length ? table(['Date', 'Compte', 'Action', 'Ressource', 'Résultat', 'IP'], rows.map(l => [
            fmtDateTime(l.created_at),
            esc(l.actor_email || '—'),
            esc(l.action),
            esc(l.resource),
            badge(l.result),
            esc(l.ip || '—')
        ])) : empty('Aucune entrée.');
    } catch (e) {
        target.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
};

function settingsSection() { return {
    id: 'settings', label: 'Paramètres',
    render: s => card('Paramètres de la plateforme', (s.settings || []).map(st => `
        <form data-form="setting" class="grid" style="margin-bottom:10px;">
            <input type="hidden" name="key" value="${esc(st.ps_key)}">
            <label class="field wide"><span>${esc(st.ps_key)}</span><input name="value" value="${esc(st.ps_value)}"></label>
            <button class="btn sm">Enregistrer</button>
        </form>
    `).join('') || empty('Aucun paramètre.')),
}; }

actions.setting = async (form, d) => {
    await api('/api/admin/settings', 'POST', d);
    await reload();
    return 'Paramètre enregistré.';
};

function overviewSection() { return {
    id: 'overview', label: 'Vue d’ensemble',
    render: s => {
        const stats = s.stats || {};
        const centerHtml = `
            <div>
                <h2 class="welcome-title">Vue d’ensemble</h2>
                <p class="welcome-sub">Administration de la plateforme</p>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></div>
                        <div class="stat-info"><b>${stats.active_users || 0}</b><span>Comptes actifs</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg></div>
                        <div class="stat-info"><b>${stats.inactive_users || 0}</b><span>Comptes désactivés</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg></div>
                        <div class="stat-info"><b>${stats.patients || 0}</b><span>Patients</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg></div>
                        <div class="stat-info"><b>${stats.doctors || 0}</b><span>Médecins vérifiés</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18"></path><path d="M5 21V7l8-4v18"></path><path d="M19 21V11l-6-4"></path></svg></div>
                        <div class="stat-info"><b>${stats.facilities || 0}</b><span>Établissements vérifiés</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                        <div class="stat-info"><b>${stats.doctors_pending || 0}</b><span>Médecins en attente</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>
                        <div class="stat-info"><b>${stats.facilities_pending || 0}</b><span>Établissements en attente</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg></div>
                        <div class="stat-info"><b>${stats.reports_open || 0}</b><span>Signalements ouverts</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
                        <div class="stat-info"><b>${stats.appointments_upcoming || 0}</b><span>RDV à venir</span></div>
                    </div>
                </div>
            </div>

            ${card('Note de confidentialité', `<p class="muted">L’administration ne donne accès à aucune donnée médicale des patients : seuls le patient et les professionnels qu’il autorise peuvent la consulter.</p>`)}
        `;
        return { center: centerHtml, right: rightSidebar(s) };
    }
}; }

boot({
    role: 'Administrateur',
    endpoint: '/api/admin/dashboard',
    who: () => 'Administration',
    rightDefault: rightDefault,
    sections: [
        overviewSection(),
        accountsSection(),
        usersSection(),
        verificationsSection(),
        reportsSection(),
        logsSection(),
        notificationsSection(),
        settingsSection(),
    ],
});