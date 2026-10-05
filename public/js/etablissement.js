'use strict';
const FACILITY_TYPES = [['hopital', 'Hôpital'], ['clinique', 'Clinique'], ['cabinet', 'Cabinet'], ['centre_de_sante', 'Centre de santé']];

function rightSidebar(s) {
    const today = new Date().toISOString().slice(0, 10);
    const todayAppts = (s.appointments || []).filter(a => a.a_date === today && ['pending', 'confirmed'].includes(a.status));
    const nextToday = todayAppts.length > 0 ? todayAppts[0] : null;
    const activeDoctors = (s.doctors || []).filter(d => d.df_status && !d.df_pending);
    const pendingInvites = (s.doctors || []).filter(d => d.df_pending);

    return `
        ${nextToday ? `
        <div class="rdv-card">
            <h3>Prochain rendez-vous aujourd'hui</h3>
            <div class="rdv-doctor">
                <div class="avatar">${initials(nextToday.p_first_name, nextToday.p_last_name)}</div>
                <div><b>${esc(fullName(nextToday.p_first_name, nextToday.p_last_name))}</b><span>Dr ${esc(fullName(nextToday.d_first_name, nextToday.d_last_name))}</span></div>
            </div>
            <div class="rdv-details">
                <div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${fmtTime(nextToday.a_start_time)} – ${fmtTime(nextToday.a_end_time)}</div>
                ${nextToday.a_reason ? `<div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg> ${esc(nextToday.a_reason)}</div>` : ''}
            </div>
            <button class="btn-full" onclick="location.hash='#appointments'">Voir tous les RDV</button>
        </div>` : `
        <div class="rdv-card">
            <h3>Prochain rendez-vous</h3>
            <p class="muted" style="font-size:0.85rem;">Aucun rendez-vous prévu aujourd'hui.</p>
        </div>`}

        <div class="rdv-card">
            <h3>Équipe médicale</h3>
            <p class="muted" style="font-size:0.78rem; margin-top:-8px; margin-bottom:12px;">${activeDoctors.length} médecin${activeDoctors.length > 1 ? 's' : ''} rattaché${activeDoctors.length > 1 ? 's' : ''}${pendingInvites.length ? ` · ${pendingInvites.length} en attente` : ''}</p>
            ${activeDoctors.length ? activeDoctors.slice(0, 5).map(d => `
                <div class="auth-item">
                    <div>
                        <b>Dr ${esc(fullName(d.d_first_name, d.d_last_name))}</b>
                        <div class="muted" style="font-size:0.78rem;">${esc(d.d_specialty || '')}${d.df_position ? ' — ' + esc(d.df_position) : ''}</div>
                    </div>
                    ${d.d_verification_status ? badge('active') : badge('pending')}
                </div>
            `).join('') : '<p class="muted" style="font-size:0.85rem;">Aucun médecin rattaché.</p>'}
        </div>
    `;
}

function doctorsSection() { return {
    id: 'doctors', label: 'Médecins',
    render: s => {
        const pending = s.doctors.filter(d => d.df_pending);
        const active = s.doctors.filter(d => d.df_status && !d.df_pending);
        return card('Inviter un médecin', `
            <form data-form="invite" class="grid">
                ${fld('professional_id', 'N° professionnel du médecin', '', { required: true })}
                ${fld('position', 'Poste (optionnel)')}
                <button class="btn">Envoyer l’invitation</button>
            </form>`)
        + card('Invitations en attente', pending.length ? pending.map(d => `
            <div class="doc-item">
                <div class="avatar">${initials(d.d_first_name, d.d_last_name)}</div>
                <div class="doc-info">
                    <b>Dr ${esc(fullName(d.d_first_name, d.d_last_name))}</b>
                    <span>${esc(d.d_specialty || '')} — en attente de réponse</span>
                </div>
                <div>${badge('pending')}</div>
            </div>
        `).join('') : empty('Aucune invitation en attente.'))
        + card('Équipe médicale', active.length ? active.map(d => `
            <div class="doc-item">
                <div class="avatar">${initials(d.d_first_name, d.d_last_name)}</div>
                <div class="doc-info">
                    <b>Dr ${esc(fullName(d.d_first_name, d.d_last_name))}</b>
                    <span>${esc(d.d_specialty || '')}${d.df_position ? ' — ' + esc(d.df_position) : ''}</span>
                </div>
                <div class="row">
                    ${d.d_verification_status ? badge('active') : badge('pending')}
                    ${btn('Retirer', 'removeDoctor', { id: d.df_id }, 'danger sm')}
                </div>
            </div>
        `).join('') : empty('Aucun médecin rattaché.'));
    },
}; }
actions.invite = async (form, d) => { await api('/api/facility/doctors/invite', 'POST', d); form.reset(); await reload(); return 'Invitation envoyée.'; };
actions.removeDoctor = async el => { await api(`/api/facility/doctors/${el.dataset.id}/remove`, 'POST'); await reload(); return 'Médecin retiré.'; };

function appointmentsSection() { return {
    id: 'appointments', label: 'Rendez-vous',
    render: s => {
        const appointments = s.appointments || [];
        const today = new Date().toISOString().slice(0, 10);
        const upcoming = appointments.filter(a => a.a_date >= today);
        const past = appointments.filter(a => a.a_date < today);

        const rowHtml = a => `
            <div class="doc-item">
                <div class="avatar">${initials(a.p_first_name, a.p_last_name)}</div>
                <div class="doc-info">
                    <b>${esc(fullName(a.p_first_name, a.p_last_name))}</b>
                    <span>${fmtDate(a.a_date)} · ${fmtTime(a.a_start_time)}–${fmtTime(a.a_end_time)} — Dr ${esc(fullName(a.d_first_name, a.d_last_name))}${a.a_reason ? ' · ' + esc(a.a_reason) : ''}</span>
                </div>
                <div class="row">
                    ${badge(a.status)}
                    ${(a.status === 'pending' || a.status === 'confirmed') && isFuture(a.a_date, a.a_end_time)
                        ? btn('Annuler', 'cancelAppt', { id: a.a_id }, 'danger sm') : ''}
                </div>
            </div>
        `;

        return card('Rendez-vous de l’établissement', `
            <h3>À venir</h3>
            ${upcoming.length ? upcoming.map(rowHtml).join('') : empty('Aucun rendez-vous à venir.')}
            <h3 style="margin-top:20px;">Historique</h3>
            ${past.length ? past.slice(0, 10).map(rowHtml).join('') : empty('Aucun historique.')}
        `);
    }
}; }
actions.cancelAppt = async el => { await api(`/api/facility/appointments/${el.dataset.id}/cancel`, 'POST'); await reload(); return 'Rendez-vous annulé.'; };

function profileSection() { return {
    id: 'profile', label: 'Profil',
    render: s => {
        const f = s.facility;
        return card('Établissement', `
            <form data-form="profile" class="grid">
                ${fld('name', 'Nom', f.hf_name, { required: true })}
                ${sel('type', 'Type', FACILITY_TYPES, f.hf_type)}
                ${fld('phone', 'Téléphone', f.hf_phone, { required: true })}
                ${fld('email', 'E-mail', f.hf_email || '', { type: 'email' })}
                ${fld('city', 'Ville', f.hf_city, { required: true })}
                ${fld('country', 'Pays', f.hf_country, { required: true })}
                ${fld('address', 'Adresse', f.hf_address, { wide: true, required: true })}
                ${area('description', 'Description', f.hf_description)}
                ${area('services', 'Services proposés', f.hf_services)}
                ${area('specialties', 'Spécialités', f.hf_specialties)}
                ${area('opening_hours', 'Horaires d’ouverture', f.hf_opening_hours)}
                <button class="btn">Enregistrer</button>
            </form>
            <p class="muted">${f.hf_verification_status ? badge('active') + ' Établissement vérifié et visible aux patients.' : badge('pending') + ' En attente de vérification par un administrateur : invisible dans les recherches.'}</p>
        ` + accountCard(false));
    }
}; }
actions.profile = async (form, d) => { await api('/api/facility/profile', 'POST', d); await reload(); return 'Établissement mis à jour.'; };

function overviewSection() { return {
    id: 'overview', label: 'Vue d’ensemble',
    render: s => {
        if (!s.facility.hf_verification_status) {
            return `<div class="notice">Votre établissement est en attente de vérification par un administrateur : il n’apparaît pas encore dans les recherches des patients.</div>`;
        }
        const upcoming = s.appointments.filter(a => isFuture(a.a_date, a.a_end_time) && ['pending', 'confirmed'].includes(a.status));
        const activeDoctors = s.doctors.filter(d => d.df_status && !d.df_pending);
        const pendingInvites = s.doctors.filter(d => d.df_pending);

        const centerHtml = `
            <div>
                <h2 class="welcome-title">${esc(s.facility.hf_name)}</h2>
                <p class="welcome-sub">${esc(s.facility.hf_type || 'Établissement')}</p>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></div>
                        <div class="stat-info"><b>${activeDoctors.length}</b><span>Médecins</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                        <div class="stat-info"><b>${pendingInvites.length}</b><span>Invitations</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
                        <div class="stat-info"><b>${upcoming.length}</b><span>RDV à venir</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18"></path><path d="M5 21V7l8-4v18"></path><path d="M19 21V11l-6-4"></path></svg></div>
                        <div class="stat-info"><b>${s.facility.hf_verification_status ? 'Oui' : 'Non'}</b><span>Vérifié</span></div>
                    </div>
                </div>
            </div>

            ${card('Prochains rendez-vous', upcoming.length ? upcoming.slice(0, 6).map(a => `
                <div class="doc-item">
                    <div class="avatar">${initials(a.p_first_name, a.p_last_name)}</div>
                    <div class="doc-info">
                        <b>${esc(fullName(a.p_first_name, a.p_last_name))}</b>
                        <span>${fmtDate(a.a_date)} · ${fmtTime(a.a_start_time)} — Dr ${esc(fullName(a.d_first_name, a.d_last_name))}</span>
                    </div>
                    <div>${badge(a.status)}</div>
                </div>
            `).join('') : empty('Aucun rendez-vous à venir.'))}
        `;
        return { center: centerHtml, right: rightSidebar(s) };
    }
}; }

function rightDefault(s) {
    return rightSidebar(s);
}

boot({
    role: 'Établissement',
    endpoint: '/api/facility/dashboard',
    who: s => s.facility.hf_name,
    rightDefault: rightDefault,
    sections: [
        overviewSection(),
        doctorsSection(),
        appointmentsSection(),
        notificationsSection(),
        profileSection(),
    ],
});