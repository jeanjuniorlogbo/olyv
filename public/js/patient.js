'use strict';
const SCOPE_OPTIONS = Object.entries(SCOPE_LABELS);

function apptRow(a) {
    const who = `Dr ${fullName(a.d_first_name, a.d_last_name)}`;
    const future = isFuture(a.a_date, a.a_end_time);
    const actions = (a.status === 'pending' || a.status === 'confirmed') && future
        ? btn('Annuler', 'cancelAppt', { id: a.a_id }, 'danger sm') : '';
    return {
        date: `${fmtDate(a.a_date)} · ${fmtTime(a.a_start_time)}`,
        who: esc(who),
        location: a.hf_name ? esc(a.hf_name) : '',
        reason: esc(a.a_reason || ''),
        status: badge(a.status),
        actions: actions
    };
}

function rightSidebar(s) {
    const upcoming = s.appointments.filter(a => ['pending', 'confirmed'].includes(a.status) && isFuture(a.a_date, a.a_end_time));
    const nextRdv = upcoming.length > 0 ? upcoming[0] : null;
    const activeAccess = s.access.filter(a => a.status === 'active');

    return `
        ${nextRdv ? `
        <div class="rdv-card">
            <h3>Prochain rendez-vous</h3>
            <div class="rdv-doctor">
                <div class="avatar">${initials(nextRdv.d_first_name, nextRdv.d_last_name)}</div>
                <div><b>Dr ${esc(fullName(nextRdv.d_first_name, nextRdv.d_last_name))}</b><span>${esc(nextRdv.d_specialty || 'Médecin')}</span></div>
            </div>
            <div class="rdv-details">
                <div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> ${fmtDate(nextRdv.a_date)} à ${fmtTime(nextRdv.a_start_time)}</div>
                ${nextRdv.hf_name ? `<div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${esc(nextRdv.hf_name)}</div>` : ''}
            </div>
            <button class="btn-full" onclick="location.hash='#appointments'">Voir détails RDV</button>
        </div>` : ''}

        <div class="rdv-card">
            <h3>Autorisations</h3>
            <p class="muted" style="font-size:0.78rem; margin-top:-8px; margin-bottom:12px;">Qui peut voir vos données</p>
            ${activeAccess.length ? activeAccess.slice(0, 4).map(a => `
                <div class="auth-item">
                    <div>
                        <b>${esc(a.name)}</b>
                        <div class="muted" style="font-size:0.78rem;">${a.kind === 'doctor' ? 'Médecin' : 'Personne de confiance'}</div>
                    </div>
                </div>
            `).join('') : '<p class="muted" style="font-size:0.85rem;">Aucune autorisation active.</p>'}
            <button class="btn-full" style="margin-top:10px;" onclick="location.hash='#access'">Gérer les autorisations</button>
        </div>
    `;
}

function overviewSection() { return {
    id: 'overview', label: 'Mon espace',
    render: s => {
        const upcoming = s.appointments.filter(a => ['pending', 'confirmed'].includes(a.status) && isFuture(a.a_date, a.a_end_time));
        const nextRdv = upcoming.length > 0 ? upcoming[0] : null;
        const centerHtml = `
            <div>
                <h2 class="welcome-title">Bonjour ${esc(s.patient.p_first_name)}</h2>
                <p class="welcome-sub">Patient</p>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
                        <div class="stat-info"><b>${nextRdv ? fmtTime(nextRdv.a_start_time) : '--:--'}</b><span>Prochain RDV</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg></div>
                        <div class="stat-info"><b>${s.documents.length}</b><span>Documents</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></div>
                        <div class="stat-info"><b>${s.family.length}</b><span>Famille</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg></div>
                        <div class="stat-info"><b>${s.access.filter(a => a.status === 'active').length}</b><span>Accès actifs</span></div>
                    </div>
                </div>
            </div>

            ${card('Mes documents récents', `
                <div class="card-head"><h2>Mes documents récents</h2><a href="#record" style="color:var(--gold-600); font-size:0.84rem; font-weight:600; text-decoration:none;">Voir tout &rsaquo;</a></div>
                ${s.documents.slice(0, 3).map(d => `
                    <div class="doc-item">
                        <div class="doc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg></div>
                        <div class="doc-info">
                            <b>${esc(d.md_title || 'Document')}</b>
                            <span>Ajouté le ${fmtDate(d.md_created_at)}</span>
                        </div>
                        <a class="doc-action" href="/api/documents/${d.md_id}/download">Télécharger</a>
                    </div>
                `).join('') || empty('Aucun document.')}
            `)}

            ${familySection().render(s)}
        `;
        return { center: centerHtml, right: rightSidebar(s) };
    }
}; }

function appointmentsSection() { return {
    id: 'appointments', label: 'Rendez-vous',
    render: s => {
        const rows = s.appointments.map(a => apptRow(a));
        if (!rows.length) return card('Vos rendez-vous', empty('Aucun rendez-vous. Prenez-en un depuis « Trouver un médecin ».'));
        return card('Vos rendez-vous', `
            <div class="doc-list">
                ${rows.map(r => `
                    <div class="doc-item">
                        <div class="doc-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
                        <div class="doc-info">
                            <b>${r.date}</b>
                            <span>${r.who}${r.location ? ' — ' + r.location : ''}${r.reason ? ' · ' + r.reason : ''}</span>
                        </div>
                        <div class="row">${r.status}${r.actions}</div>
                    </div>
                `).join('')}
            </div>
        `);
    }
}; }

function bookingSection() { return {
    id: 'booking', label: 'Trouver un médecin',
    render: () => card('Rechercher un médecin',
        `<form data-form="searchDoctors" class="grid">
            ${fld('q', 'Nom ou spécialité')}
            ${fld('city', 'Ville')}
            <button class="btn">Rechercher</button>
        </form>
        <div id="doctor-results" style="margin-top:20px;"></div>`),
    after: () => { actions.searchDoctors(null, {}); },
}; }

function doctorCard(dr) {
    const facilities = dr.facilities || [];
    const facilityNames = facilities.map(f => f.name).slice(0, 3).join(', ') + (facilities.length > 3 ? '…' : '');
    return `
        <div class="person-card" data-doctor="${dr.d_id}">
            <div class="person-card-top">
                <div class="avatar person-avatar">${initials(dr.d_first_name, dr.d_last_name)}</div>
                <div class="person-card-name">
                    <b>Dr ${esc(fullName(dr.d_first_name, dr.d_last_name))}</b>
                    <span>${esc(dr.d_specialty || 'Médecin')}</span>
                </div>
            </div>
            <div class="person-card-scopes">
                ${facilities.length
                    ? facilities.map(f => `<span class="scope-badge">${esc(f.name)}</span>`).join('')
                    : '<span class="muted" style="font-size:0.78rem;">Aucun établissement disponible</span>'}
            </div>
            <div class="person-card-actions">
                <button type="button" class="btn sm" data-action="openBookingModal" data-id="${dr.d_id}" ${facilities.length ? '' : 'disabled'}>
                    Prendre rendez-vous
                </button>
            </div>
        </div>`;
}

actions.searchDoctors = async (form, d) => {
    d = d || {};
    const target = $('#doctor-results');
    if (target) target.innerHTML = '<p class="muted">Recherche en cours…</p>';

    let doctors = [];
    try {
        const params = new URLSearchParams();
        if (d.q) params.set('q', d.q);
        if (d.city) params.set('city', d.city);
        doctors = (await api(`/api/doctors?${params.toString()}`)).data || [];
    } catch (e) {
        if (target) target.innerHTML = `<p class="error">${esc(e.message)}</p>`;
        return;
    }

    if (!target) return;
    target.innerHTML = doctors.length
        ? `<div class="people-grid">${doctors.map(doctorCard).join('')}</div>`
        : empty('Aucun médecin ne correspond à votre recherche.');
};

actions.openBookingModal = async el => {
    const doctorId = Number(el.dataset.id);
    let doctors = [];
    try {
        doctors = (await api(`/api/doctors?id=${doctorId}`)).data || [];
    } catch (e) {
        const card = el.closest('.person-card');
        if (card) {
            const name = card.querySelector('.person-card-name b').textContent.replace(/^Dr\s+/, '');
            toast('Médecin : ' + name, 'error');
        }
        toast(e.message, 'error');
        return;
    }
    const doctor = doctors.find(d => d.d_id === doctorId) || doctors[0];
    if (!doctor) { toast('Médecin introuvable.', 'error'); return; }

    const facilities = doctor.facilities || [];
    if (!facilities.length) { toast('Aucun établissement disponible.', 'error'); return; }

    const today = new Date().toISOString().slice(0, 10);

    const body = `
        <div class="booking-modal">
            <div class="booking-doctor">
                <div class="avatar person-avatar">${initials(doctor.d_first_name, doctor.d_last_name)}</div>
                <div>
                    <b>Dr ${esc(fullName(doctor.d_first_name, doctor.d_last_name))}</b>
                    <span class="muted">${esc(doctor.d_specialty || 'Médecin')}</span>
                </div>
            </div>

            <form data-modal-prompt class="grid" style="margin-top:8px;">
                ${sel('facility_id', 'Établissement', facilities.map(f => [f.id, `${f.name}${f.city ? ' (' + f.city + ')' : ''}`]), facilities[0].id, { required: true, wide: true })}
                ${fld('date', 'Date souhaitée', today, { type: 'date', attrs: `min="${today}"`, required: true, wide: true })}
            </form>

            <div class="booking-slots" style="margin-top:16px;">
                <p class="muted" style="font-size:0.84rem;">Sélectionnez un créneau :</p>
                <div id="booking-slots-list" class="row" style="gap:8px; flex-wrap:wrap;"></div>
            </div>

            <form data-modal-booking class="grid" style="margin-top:16px;" hidden>
                <input type="hidden" name="doctor_id" value="${doctorId}">
                <input type="hidden" name="facility_id">
                <input type="hidden" name="date">
                <input type="hidden" name="start_time">
                ${area('reason', 'Motif de la consultation', '', { required: true })}
                ${area('patient_note', 'Note pour le médecin (optionnel)')}
            </form>
        </div>`;

    const m = modal({
        title: 'Prendre rendez-vous',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Fermer', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'confirm', label: 'Confirmer la demande', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-booking]');
                    if (!form) return;
                    if (form.hidden) { toast('Sélectionnez d’abord un créneau.', 'error'); return; }
                    if (!form.reportValidity()) return;

                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    d.doctor_id = Number(d.doctor_id);
                    d.facility_id = Number(d.facility_id);

                    const facName = (facilities.find(f => String(f.id) === String(d.facility_id)) || {}).name || '';
                    const ok = await confirmAction({
                        title: 'Confirmer la demande ?',
                        message: `
                            <b>Médecin :</b> Dr ${esc(fullName(doctor.d_first_name, doctor.d_last_name))}<br>
                            <b>Établissement :</b> ${esc(facName)}<br>
                            <b>Date :</b> ${fmtDate(d.date)} à ${fmtTime(d.start_time)}<br>
                            <b>Motif :</b> ${esc(d.reason)}<br><br>
                            La demande sera envoyée au médecin, qui devra la confirmer.`,
                        confirmLabel: 'Envoyer la demande',
                    });
                    if (!ok) return;

                    try {
                        await api('/api/patient/appointments', 'POST', d);
                        close();
                        location.hash = '#appointments';
                        await reload();
                        toast('Demande de rendez-vous envoyée.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });

    const box = m.box;
    const facilitySel = box.querySelector('select[name="facility_id"]');
    const dateInput = box.querySelector('input[name="date"]');
    const slotsList = box.querySelector('#booking-slots-list');
    const bookingForm = box.querySelector('form[data-modal-booking]');

    async function loadSlots() {
        const fid = facilitySel.value;
        const date = dateInput.value;
        if (!fid || !date) return;
        slotsList.innerHTML = '<div class="skeleton-bar" style="width:200px;"></div>';
        bookingForm.hidden = true;
        try {
            const slots = (await api(`/api/doctors/${doctorId}/slots?facility_id=${fid}&date=${date}`)).data || [];
            slotsList.innerHTML = slots.length
                ? slots.map(s => `<button type="button" class="btn slot sm" data-action="pickBookingSlot" data-start="${esc(s.start)}">${esc(s.start)}</button>`).join('')
                : '<p class="empty">Aucun créneau disponible ce jour.</p>';
        } catch (e) {
            slotsList.innerHTML = `<p class="error">${esc(e.message)}</p>`;
        }
    }

    facilitySel.addEventListener('change', loadSlots);
    dateInput.addEventListener('change', loadSlots);

    m.box._bookingContext = { bookingForm, doctorId };

    await loadSlots();
};

actions.pickBookingSlot = el => {
    const overlay = el.closest('.modal-overlay');
    if (!overlay) return;
    const box = overlay.querySelector('.modal');
    const ctx = box._bookingContext;
    if (!ctx) return;

    box.querySelectorAll('.slot').forEach(b => b.classList.remove('on'));
    el.classList.add('on');

    const form = ctx.bookingForm;
    form.hidden = false;
    form.start_time.value = el.dataset.start;

    const facilitySel = box.querySelector('select[name="facility_id"]');
    const dateInput = box.querySelector('input[name="date"]');
    form.facility_id.value = facilitySel.value;
    form.date.value = dateInput.value;

    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};

actions.cancelAppt = async el => {
    const ok = await confirmAction({
        title: 'Annuler ce rendez-vous ?',
        message: 'Le médecin sera prévenu de l’annulation. Cette action est définitive.',
        confirmLabel: 'Annuler le RDV',
        danger: true,
    });
    if (!ok) return;
    await api(`/api/patient/appointments/${el.dataset.id}/cancel`, 'POST');
    await reload();
    return 'Rendez-vous annulé.';
};

function familySection() { return {
    id: 'family', label: 'Famille',
    render: s => {
        const familyHtml = s.family.length ? s.family.map(f => `
            <div class="family-card">
                <div class="avatar">${initials(f.p_first_name, f.p_last_name)}</div>
                <b>${esc(fullName(f.p_first_name, f.p_last_name))}</b>
                <span>${esc(f.fr_relationship)}</span>
                ${badge(f.status)}
                ${f.direction === 'received' ? '<span class="muted" style="display:block;font-size:0.7rem;">(demande reçue)</span>' : ''}
                <div style="margin-top:10px; display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                    ${f.status === 'pending' && f.direction === 'received'
                        ? btn('Accepter', 'familyAccept', { id: f.fr_id }, 'sm') + btn('Refuser', 'familyReject', { id: f.fr_id }, 'ghost sm')
                        : ''}
                    ${f.status !== 'pending' ? btn('Retirer', 'familyRemove', { id: f.fr_id }, 'danger sm') : ''}
                </div>
            </div>
        `).join('') : empty('Aucune relation familiale. Un lien familial ne donne accès à rien : ajoutez une autorisation séparément.');

        return card('Relations familiales', `
            <button type="button" class="btn" data-action="openFamilyRequest" style="margin-bottom:16px;">
                + Demander une relation familiale
            </button>
            <div class="family-grid">${familyHtml}</div>
        `);
    }
}; }

function openFamilyRequestModal() {
    modal({
        title: 'Demander une relation familiale',
        body: `
            <form data-modal-prompt class="grid">
                ${fld('identifier', 'E-mail ou téléphone du proche', '', { required: true, wide: true })}
                ${fld('relationship', 'Lien (ex. Mère, Frère)', '', { required: true, wide: true })}
                <p class="muted" style="grid-column:1/-1; margin-top:6px;">
                    Une relation familiale n’ouvre aucun accès à votre dossier. Elle facilite seulement
                    la navigation entre vos comptes respectifs.
                </p>
            </form>`,
        size: 'md',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'send', label: 'Envoyer la demande', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    close();
                    try {
                        await api('/api/patient/family', 'POST', d);
                        await reload();
                        toast('Demande envoyée.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });
}
actions.openFamilyRequest = () => openFamilyRequestModal();

actions.familyAccept = async el => {
    const ok = await confirmAction({
        title: 'Accepter la relation ?',
        message: 'Votre proche apparaîtra comme relation familiale. Cela n’ouvre <b>aucun accès</b> à votre dossier médical.',
        confirmLabel: 'Accepter',
    });
    if (!ok) return;
    await api(`/api/patient/family/${el.dataset.id}/respond`, 'POST', { accept: true });
    await reload();
    return 'Demande acceptée.';
};

actions.familyReject = async el => {
    await api(`/api/patient/family/${el.dataset.id}/respond`, 'POST', { accept: false });
    await reload();
    return 'Demande refusée.';
};

actions.familyRemove = async el => {
    const ok = await confirmAction({
        title: 'Retirer cette relation ?',
        message: 'Le lien familial sera supprimé. Cela ne change rien aux autorisations d’accès en cours.',
        confirmLabel: 'Retirer',
        danger: true,
    });
    if (!ok) return;
    await api(`/api/patient/family/${el.dataset.id}/remove`, 'POST');
    await reload();
    return 'Relation supprimée.';
};

function accessSection() { return {
    id: 'access', label: 'Autorisations',
    render: s => {
        const activeAccess = s.access.filter(a => a.status === 'active');
        const historyAccess = s.access.filter(a => a.status !== 'active');

        return card('Qui peut consulter votre dossier', `
            <button type="button" class="btn" data-action="openGrantAccess" style="margin-bottom:20px;">
                + Autoriser un accès
            </button>

            <h3>Accès actifs</h3>
            ${activeAccess.length ? activeAccess.map(a => `
                <div class="auth-item">
                    <div>
                        <b>${esc(a.name)}</b> ${badge(a.kind)}
                        ${a.d_specialty ? `<span class="muted"> · ${esc(a.d_specialty)}</span>` : ''}
                        <div class="muted" style="font-size:0.78rem;">${a.scopes.map(sc => SCOPE_LABELS[sc] || sc).join(', ')}${a.ma_end_at ? ` — jusqu’au ${fmtDate(a.ma_end_at)}` : ''}</div>
                    </div>
                    <div>${btn('Retirer', 'revokeAccess', { id: a.ma_id, name: a.name }, 'danger sm')}</div>
                </div>
            `).join('') : empty('Aucun accès actif accordé actuellement.')}

            <h3 style="margin-top:20px;">Historique</h3>
            ${historyAccess.length ? historyAccess.map(a =>
                `<div class="item muted">${esc(a.name)} — ${badge(a.status)}</div>`).join('') : empty('—')}

            <h3 style="margin-top:20px;">Dossiers partagés avec vous</h3>
            ${s.shared.length ? s.shared.map(x => `<div class="item"><a href="#shared-${x.patient_id}" data-action="openShared" data-id="${x.patient_id}">
                ${esc(fullName(x.p_first_name, x.p_last_name))}</a></div>`).join('') : empty('Aucun.')}
        `);
    }
}; }

function openGrantAccessModal() {
    const scopesHtml = SCOPE_OPTIONS.map(([v, l]) =>
        `<label><input type="checkbox" name="scopes" value="${v}"> ${esc(l)}</label>`).join('');

    const body = `
        <form data-modal-prompt class="grid">
            ${sel('kind', 'Type de personne', [['doctor', 'Médecin'], ['trusted_person', 'Personne de confiance']], 'doctor', { required: true })}
            ${fld('identifier', 'Identifiant (n° professionnel du médecin, ou e-mail/téléphone)', '', { required: true, wide: true })}
            ${fld('days', 'Durée en jours (vide = sans limite)', '', { type: 'number', attrs: 'min="1" max="365"', wide: true })}
            <div class="field wide">
                <span>Ce que cette personne pourra faire</span>
                <div class="checks" style="margin-top:6px;">${scopesHtml}</div>
            </div>
        </form>`;

    modal({
        title: 'Autoriser un accès',
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
                    const scopes = [];
                    new FormData(form).forEach((v, k) => {
                        if (k === 'scopes') scopes.push(v);
                        else d[k] = v;
                    });
                    if (!scopes.length) {
                        toast('Sélectionnez au moins une portée.', 'error');
                        return;
                    }
                    d.scopes = scopes;

                    close();
                    await confirmGrantAccess(d);
                },
            },
        ],
    });
}
actions.openGrantAccess = () => openGrantAccessModal();

async function confirmGrantAccess(d) {
    const kindLabel = d.kind === 'doctor' ? 'Médecin' : 'Personne de confiance';
    const scopeList = d.scopes.map(s => `<li>${esc(SCOPE_LABELS[s] || s)}</li>`).join('');
    const duration = d.days ? `jusqu’à expiration dans <b>${esc(d.days)} jours</b>` : 'sans limite de durée';

    const ok = await confirmAction({
        title: 'Confirmer l’autorisation',
        message: `
            <b>Type :</b> ${esc(kindLabel)}<br>
            <b>Identifiant :</b> ${esc(d.identifier)}<br>
            <b>Durée :</b> ${duration}<br><br>
            <b>Cette personne pourra :</b>
            <ul style="margin:8px 0 0 20px;">${scopeList}</ul>
            <br>
            Vous pourrez retirer cet accès à tout moment depuis cette page.`,
        confirmLabel: 'Autoriser',
    });
    if (!ok) { openGrantAccessModal(); return; }

    try {
        const payload = { ...d };
        if (d.days === '') delete payload.days; else payload.days = Number(payload.days);
        if (d.kind === 'doctor') {
            payload.professional_id = d.identifier;
            delete payload.identifier;
        }
        await api('/api/patient/access', 'POST', payload);
        await reload();
        toast('Autorisation enregistrée.');
    } catch (e) {
        toast(e.message, 'error');
        openGrantAccessModal();
    }
}

actions.revokeAccess = async el => {
    const name = el.dataset.name || 'cette personne';
    const ok = await confirmAction({
        title: 'Retirer cet accès ?',
        message: `<b>${esc(name)}</b> ne pourra plus consulter votre dossier immédiatement.`,
        confirmLabel: 'Retirer l’accès',
        danger: true,
    });
    if (!ok) return;
    await api(`/api/patient/access/${el.dataset.id}/revoke`, 'POST');
    await reload();
    return 'Accès retiré.';
};

actions.openShared = async el => {
    const id = el.dataset.id;
    const existing = document.getElementById(`shared-${id}`);
    if (existing) { existing.remove(); return; }
    const r = (await api(`/api/patient/shared/${id}/record`)).data;
    const content = $('#content');
    if (content) content.insertAdjacentHTML('beforeend', `<div id="shared-${id}">${recordHtml(r)}</div>`);
};

function logsSection() { return {
    id: 'logs', label: 'Journal d’accès',
    render: s => card('Qui a consulté votre dossier',
        table(['Date', 'Rôle', 'Nom', 'Action', 'Résultat'], (s.access_logs || []).map(l => [
            fmtDateTime(l.created_at),
            esc(LABELS[l.actor_role] || l.actor_role || '—'),
            esc(l.actor_name || '—'),
            esc(l.action),
            badge(l.result)
        ])) || empty('Aucun accès enregistré pour le moment.')),
}; }

function profileSection() { return {
    id: 'profile', label: 'Profil',
    render: s => {
        const p = s.patient;
        return card('Informations personnelles',
            `<form data-form="profile" class="grid">
                ${fld('first_name', 'Prénom', p.p_first_name, { required: true })}
                ${fld('last_name', 'Nom', p.p_last_name, { required: true })}
                ${fld('phone', 'Téléphone', p.u_phone, { required: true })}
                ${fld('date_of_birth', 'Date de naissance', p.p_date_of_birth || '', { type: 'date' })}
                ${sel('gender', 'Genre', GENDER_OPTIONS, p.p_gender)}
                ${fld('city', 'Ville', p.p_city)}
                ${fld('country', 'Pays', p.p_country)}
                ${fld('address', 'Adresse', p.p_address, { wide: true })}
                <button class="btn">Enregistrer</button>
            </form>` + accountCard());
    }
}; }

actions.profile = async (form, d) => { await api('/api/patient/profile', 'POST', d); await reload(); return 'Profil mis à jour.'; };

function recordSectionDef() {
    return { id: 'record', label: 'Mon dossier', render: s => recordHtml(s.record) };
}

boot({
    role: 'Patient',
    endpoint: '/api/patient/dashboard',
    who: s => fullName(s.patient.p_first_name, s.patient.p_last_name),
    rightDefault: s => rightSidebar(s),
    photo: s => s.patient.p_profile_photo_url,
    sections: [
        overviewSection(),
        appointmentsSection(),
        bookingSection(),
        recordSectionDef(),
        familySection(),
        accessSection(),
        logsSection(),
        notificationsSection(),
        profileSection(),
    ],
});