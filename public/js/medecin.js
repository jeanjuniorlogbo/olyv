'use strict';

function apptActions(a) {
    const acts = [];
    if (a.status === 'pending') {
        acts.push(btn('Confirmer', 'apptAction', { id: a.a_id, verb: 'confirm' }, 'sm'));
        acts.push(btn('Refuser', 'apptAction', { id: a.a_id, verb: 'reject' }, 'ghost sm'));
    }
    if (a.status === 'confirmed' && !isFuture(a.a_date, a.a_end_time)) {
        acts.push(btn('Terminé', 'apptAction', { id: a.a_id, verb: 'complete' }, 'sm'));
        acts.push(btn('Absent', 'apptAction', { id: a.a_id, verb: 'no_show' }, 'ghost sm'));
    }
    if (a.status === 'confirmed' && !a.has_consultation) {
        acts.push(btn('Ouvrir la consultation', 'openConsultation', { appt: a.a_id, patient: a.a_patient_id }, 'sm'));
    }
    return acts.join(' ');
}

function apptRow(a) {
    return `
        <div class="doc-item">
            <div class="avatar">${initials(a.p_first_name, a.p_last_name)}</div>
            <div class="doc-info">
                <b>${esc(fullName(a.p_first_name, a.p_last_name))}</b>
                <span>${fmtDate(a.a_date)} · ${fmtTime(a.a_start_time)}–${fmtTime(a.a_end_time)} — ${esc(a.a_reason || 'Consultation')}${a.hf_name ? ' · ' + esc(a.hf_name) : ''}</span>
            </div>
            <div class="row">${badge(a.status)}${apptActions(a)}</div>
        </div>
    `;
}

function rightSidebar(s) {
    const today = new Date().toISOString().slice(0, 10);
    const todayAppts = (s.appointments || []).filter(a => a.a_date === today && ['pending', 'confirmed'].includes(a.status));
    const nextToday = todayAppts.length > 0 ? todayAppts[0] : null;
    const activeFacilities = (s.facilities || []).filter(f => f.df_status && !f.df_pending);

    return `
        ${nextToday ? `
        <div class="rdv-card">
            <h3>Prochain patient aujourd'hui</h3>
            <div class="rdv-doctor">
                <div class="avatar">${initials(nextToday.p_first_name, nextToday.p_last_name)}</div>
                <div><b>${esc(fullName(nextToday.p_first_name, nextToday.p_last_name))}</b><span>${esc(nextToday.a_reason || 'Consultation')}</span></div>
            </div>
            <div class="rdv-details">
                <div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${fmtTime(nextToday.a_start_time)} – ${fmtTime(nextToday.a_end_time)}</div>
                ${nextToday.hf_name ? `<div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${esc(nextToday.hf_name)}</div>` : ''}
                ${nextToday.p_phone ? `<div><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg> ${esc(nextToday.p_phone)}</div>` : ''}
            </div>
            <button class="btn-full" onclick="location.hash='#appointments'">Voir la file d'attente</button>
        </div>` : `
        <div class="rdv-card">
            <h3>Prochain patient</h3>
            <p class="muted" style="font-size:0.85rem;">Aucun rendez-vous prévu aujourd'hui.</p>
        </div>`}

        <div class="rdv-card">
            <h3>Mes établissements</h3>
            ${activeFacilities.length ? activeFacilities.map(f => `
                <div class="auth-item">
                    <div>
                        <b>${esc(f.hf_name)}</b>
                        <div class="muted" style="font-size:0.78rem;">${esc(f.hf_city || '')}${f.df_position ? ' — ' + esc(f.df_position) : ''}</div>
                    </div>
                </div>
            `).join('') : '<p class="muted" style="font-size:0.85rem;">Aucun établissement rattaché.</p>'}
        </div>
    `;
}

function appointmentsSection() { return {
    id: 'appointments', label: 'Rendez-vous',
    render: s => {
        const upcoming = s.appointments.filter(a => isFuture(a.a_date, a.a_end_time) || a.status === 'pending');
        const past = s.appointments.filter(a => !isFuture(a.a_date, a.a_end_time) && a.status !== 'pending');

        return card('Vos rendez-vous', `
            <h3>À venir</h3>
            ${upcoming.length ? upcoming.map(apptRow).join('') : empty('Aucun rendez-vous à venir.')}
            <h3 style="margin-top:20px;">Historique</h3>
            ${past.length ? past.slice(0, 10).map(apptRow).join('') : empty('Aucun historique.')}
        `);
    }
}; }

actions.apptAction = async el => {
    const verb = el.dataset.verb;
    const labels = { confirm: 'Confirmer ce rendez-vous ?', reject: 'Refuser ce rendez-vous ?', complete: 'Marquer comme terminé ?', no_show: 'Marquer le patient absent ?' };
    const messages = {
        confirm: 'Le patient sera prévenu de la confirmation.',
        reject: 'Le patient sera prévenu du refus et devra reprendre un rendez-vous.',
        complete: 'La consultation sera marquée comme terminée.',
        no_show: 'Le rendez-vous sera marqué comme non honoré.',
    };
    const ok = await confirmAction({
        title: labels[verb] || 'Confirmer',
        message: messages[verb] || '',
        confirmLabel: verb === 'reject' || verb === 'no_show' ? 'Confirmer' : 'Valider',
        danger: verb === 'reject' || verb === 'no_show',
    });
    if (!ok) return;
    await api(`/api/doctor/appointments/${el.dataset.id}/${verb}`, 'POST');
    await reload();
    return 'Action effectuée.';
};

actions.openConsultation = async el => {
    await api(`/api/doctor/patients/${el.dataset.patient}/consultations`, 'POST', { appointment_id: Number(el.dataset.appt) });
    location.hash = '#patients';
    await reload();
    toast('Consultation ouverte. Retrouvez-la dans « Mes patients ».');
};

function facilitiesSection() { return {
    id: 'facilities', label: 'Établissements',
    render: s => {
        const pending = s.facilities.filter(f => f.df_pending);
        const active = s.facilities.filter(f => f.df_status && !f.df_pending);
        return card('Invitations en attente', pending.length ? pending.map(f => `<div class="item row">
            <b>${esc(f.hf_name)}</b><span class="muted">${esc(f.hf_city || '')}</span>
            ${btn('Accepter', 'respondInvite', { id: f.df_id, accept: 1 }, 'sm')}${btn('Refuser', 'respondInvite', { id: f.df_id, accept: 0 }, 'ghost sm')}
            </div>`).join('') : empty('Aucune invitation en attente.'))
        + card('Vos établissements', active.length ? active.map(f => `<div class="item">${esc(f.hf_name)}
            ${f.df_position ? '— ' + esc(f.df_position) : ''} <span class="muted">${esc(f.hf_city || '')}</span></div>`).join('')
            : empty('Vous n’êtes rattaché à aucun établissement pour le moment. Un établissement doit vous inviter.'))
        + card('Vos disponibilités', `
            <form data-form="addAvailability" class="grid">
                ${sel('facility_id', 'Établissement', active.map(f => [f.hf_id, f.hf_name]))}
                ${sel('day_of_week', 'Jour', DAYS.slice(1).map((d, i) => [i + 1, d]))}
                ${fld('start_time', 'Début', '09:00', { type: 'time', required: true })}
                ${fld('end_time', 'Fin', '17:00', { type: 'time', required: true })}
                ${fld('slot_minutes', 'Durée du créneau (min)', '30', { type: 'number', attrs: 'min="10" max="240"' })}
                <button class="btn">Ajouter</button></form>
            ${table(['Établissement', 'Jour', 'Horaires', 'Créneau', ''], s.availabilities.map(a =>
                [esc(a.hf_name), DAYS[a.da_day_of_week], `${fmtTime(a.da_start_time)}–${fmtTime(a.da_end_time)}`,
                 a.da_slot_minutes + ' min', btn('Supprimer', 'deleteAvailability', { id: a.da_id }, 'danger sm')]))
            || empty('Aucune disponibilité définie.')}`);
    },
}; }

actions.respondInvite = async el => {
    const accept = el.dataset.accept === '1';
    const ok = await confirmAction({
        title: accept ? 'Accepter cette invitation ?' : 'Refuser cette invitation ?',
        message: accept
            ? 'Vous serez rattaché à cet établissement et pourrez y recevoir des patients.'
            : 'Vous ne serez pas rattaché à cet établissement.',
        confirmLabel: accept ? 'Accepter' : 'Refuser',
        danger: !accept,
    });
    if (!ok) return;
    await api(`/api/doctor/invitations/${el.dataset.id}/respond`, 'POST', { accept });
    await reload();
    return 'Réponse envoyée.';
};

actions.addAvailability = async (form, d) => {
    d.facility_id = Number(d.facility_id);
    d.day_of_week = Number(d.day_of_week);
    d.slot_minutes = Number(d.slot_minutes || 30);
    await api('/api/doctor/availabilities', 'POST', d);
    form.reset();
    await reload();
    return 'Disponibilité ajoutée.';
};

actions.deleteAvailability = async el => {
    const ok = await confirmAction({
        title: 'Supprimer cette disponibilité ?',
        message: 'Les patients ne pourront plus réserver sur ce créneau.',
        confirmLabel: 'Supprimer',
        danger: true,
    });
    if (!ok) return;
    await api(`/api/doctor/availabilities/${el.dataset.id}/delete`, 'POST');
    await reload();
    return 'Disponibilité supprimée.';
};

const DOC_TYPES = [['rapport_medical', 'Rapport médical'], ['resultat_examen', 'Résultat d’examen'],
    ['ordonnance', 'Ordonnance'], ['certificat', 'Certificat'], ['autre', 'Autre']];
const SEVERITIES = [['', '—'], ['mild', 'Légère'], ['moderate', 'Modérée'], ['severe', 'Sévère']];
const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

function scopeBadges(scopes) {
    if (!scopes || !scopes.length) return '';
    return scopes.map(s => `<span class="scope-badge scope-${esc(s.replace('.', '-'))}">${esc(SCOPE_LABELS[s] || s)}</span>`).join('');
}

function patientCard(p) {
    const scopes = p.scopes || [];
    const canWrite = scopes.includes('record.write');
    const accessLabel = canWrite ? 'Écriture' : 'Lecture seule';
    const accessClass = canWrite ? 'access-write' : 'access-read';

    return `
        <div class="person-card" data-patient="${p.p_id}">
            <div class="person-card-top">
                <div class="avatar person-avatar">${initials(p.p_first_name, p.p_last_name)}</div>
                <div class="person-card-name">
                    <b>${esc(fullName(p.p_first_name, p.p_last_name))}</b>
                    <span class="muted">${p.ma_end_at ? 'Accès jusqu’au ' + fmtDate(p.ma_end_at) : 'Accès sans limite'}</span>
                </div>
                <span class="access-pill ${accessClass}">${accessLabel}</span>
            </div>
            <div class="person-card-scopes">
                ${scopeBadges(scopes)}
            </div>
            <div class="person-card-actions">
                <button type="button" class="btn sm" data-action="openPatientModal" data-id="${p.p_id}">Ouvrir le dossier</button>
            </div>
        </div>`;
}

function patientsSection() { return {
    id: 'patients', label: 'Mes patients',
    render: s => {
        if (!s.patients.length) {
            return card('Patients vous ayant autorisé', empty('Aucun patient ne vous a encore autorisé.'));
        }
        return card('Patients vous ayant autorisé', `
            <p class="muted" style="margin-top:-6px; margin-bottom:18px;">
                ${s.patients.length} patient${s.patients.length > 1 ? 's' : ''} vous ${s.patients.length > 1 ? 'ont' : 'a'} ouvert un accès. Cliquez sur une carte pour consulter le dossier.
            </p>
            <div class="people-grid">
                ${s.patients.map(patientCard).join('')}
            </div>
        `);
    },
}; }

actions.openPatientModal = async el => {
    const id = Number(el.dataset.id);
    const p = App.state.patients.find(x => x.p_id === id);
    if (!p) { toast('Patient introuvable.', 'error'); return; }

    const m = modal({
        title: `Dossier de ${fullName(p.p_first_name, p.p_last_name)}`,
        body: skeletonTable(4),
        size: 'xl',
        actions: [],
    });

    await renderPatientRecordInModal(id, p, m.box);
};

async function renderPatientRecordInModal(id, p, modalBox) {
    let record;
    try {
        record = (await api(`/api/doctor/patients/${id}/record`)).data;
    } catch (e) {
        modalBox.querySelector('.modal-body').innerHTML = `<p class="error">${esc(e.message)}</p>`;
        return;
    }

    let scopes = p.scopes || [];
    if (record.can_write === false) scopes = scopes.filter(s => s !== 'record.write');
    if (record.can_write_documents === false) scopes = scopes.filter(s => s !== 'documents.write');

    const canWrite = scopes.includes('record.write');
    const canDocs = scopes.includes('documents.write');

    const recordBlock = recordHtml(record);

    let writeButtons = '';
    if (canWrite) {
        writeButtons = `
            <div class="modal-actions-row">
                <button type="button" class="btn sm" data-action="openAddRecord" data-pid="${id}">+ Ajouter au dossier</button>
                <button type="button" class="btn sm" data-action="openPrescription" data-pid="${id}">+ Ordonnance</button>
                <button type="button" class="btn sm" data-action="openExamResult" data-pid="${id}">+ Résultat d’examen</button>
                ${canDocs ? `<button type="button" class="btn sm" data-action="openUploadDoc" data-pid="${id}">+ Document</button>` : ''}
            </div>`;
    }

    modalBox.querySelector('.modal-body').innerHTML = writeButtons + recordBlock;
    modalBox.dataset.pid = id;
}

actions.openAddRecord = async el => {
    const pid = Number(el.dataset.pid);
    const p = App.state.patients.find(x => x.p_id === pid);
    const record = (await api(`/api/doctor/patients/${pid}/record`)).data;
    const consults = (record.consultations || []).filter(c => c.status === 'open');
    const consultOptions = [['', '—']].concat(consults.map(c => [c.c_id, fmtDateTime(c.c_date)]));

    const kindOptions = [
        ['diagnosis', 'Diagnostic'],
        ['allergy', 'Allergie'],
        ['treatment', 'Traitement'],
        ['blood_group', 'Groupe sanguin'],
        ['exam', 'Demande d’examen'],
    ];

    const body = `
        <form data-modal-prompt class="grid">
            ${sel('kind', 'Type d’élément', kindOptions, 'diagnosis', { wide: true, required: true })}
            ${sel('consultation_id', 'Consultation associée (optionnel)', consultOptions, '', { wide: true })}
            ${fld('name', 'Nom / valeur', '', { required: true, wide: true })}
            ${sel('severity', 'Sévérité (allergie uniquement)', SEVERITIES, '', { wide: true })}
            ${fld('start_date', 'Début (traitement)', '', { type: 'date' })}
            ${fld('end_date', 'Fin (traitement)', '', { type: 'date' })}
            ${area('description', 'Description', '', { required: false })}
        </form>`;

    modal({
        title: 'Ajouter au dossier',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'save', label: 'Ajouter', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });

                    const kind = d.kind;
                    const payload = { consultation_id: d.consultation_id ? Number(d.consultation_id) : undefined };
                    if (kind === 'blood_group') payload.value = d.name;
                    else if (kind === 'exam') { payload.name = d.name; payload.description = d.description; }
                    else if (kind === 'allergy') Object.assign(payload, { name: d.name, description: d.description, severity: d.severity || undefined });
                    else if (kind === 'treatment') Object.assign(payload, { name: d.name, description: d.description, start_date: d.start_date || undefined, end_date: d.end_date || undefined });
                    else Object.assign(payload, { name: d.name, description: d.description });

                    try {
                        await api(`/api/doctor/patients/${pid}/records/${kind}`, 'POST', payload);
                        close();
                        await refreshPatientModal(pid);
                        toast('Ajouté au dossier.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });
};

actions.openPrescription = async el => {
    const pid = Number(el.dataset.pid);
    const record = (await api(`/api/doctor/patients/${pid}/record`)).data;
    const consults = (record.consultations || []).filter(c => c.status === 'open');
    const consultOptions = [['', '—']].concat(consults.map(c => [c.c_id, fmtDateTime(c.c_date)]));

    const body = `
        <form data-modal-prompt class="grid">
            ${sel('consultation_id', 'Consultation associée (optionnel)', consultOptions, '', { wide: true })}
            ${fld('medicine_name', 'Médicament', '', { required: true, wide: true })}
            ${fld('dosage', 'Posologie', '')}
            ${fld('frequency', 'Fréquence', '')}
            ${fld('duration', 'Durée', '')}
            ${area('instructions', 'Instructions', '')}
        </form>`;

    modal({
        title: 'Ajouter une ordonnance',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'save', label: 'Ajouter', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    try {
                        await api(`/api/doctor/patients/${pid}/records/prescription`, 'POST', {
                            consultation_id: d.consultation_id ? Number(d.consultation_id) : undefined,
                            items: [{ medicine_name: d.medicine_name, dosage: d.dosage, frequency: d.frequency, duration: d.duration, instructions: d.instructions }]
                        });
                        close();
                        await refreshPatientModal(pid);
                        toast('Ordonnance ajoutée.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });
};

actions.openExamResult = async el => {
    const pid = Number(el.dataset.pid);
    const record = (await api(`/api/doctor/patients/${pid}/record`)).data;
    const exams = (record.exams || []).filter(e => e.status !== 'completed');
    if (!exams.length) { toast('Aucun examen en attente de résultat.', 'error'); return; }
    const options = exams.map(e => [e.me_id, e.me_name]);

    const body = `
        <form data-modal-prompt class="grid">
            ${sel('exam_id', 'Examen', options, options[0][0], { wide: true, required: true })}
            ${area('result', 'Résultat', '', { required: true })}
        </form>`;

    modal({
        title: 'Enregistrer un résultat d’examen',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'save', label: 'Enregistrer', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const d = {};
                    new FormData(form).forEach((v, k) => { d[k] = v; });
                    try {
                        await api(`/api/doctor/patients/${pid}/records/exam_result`, 'POST', { exam_id: Number(d.exam_id), result: d.result });
                        close();
                        await refreshPatientModal(pid);
                        toast('Résultat enregistré.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });
};

actions.openUploadDoc = async el => {
    const pid = Number(el.dataset.pid);
    const body = `
        <form data-modal-prompt class="grid">
            ${sel('type', 'Type de document', DOC_TYPES, 'rapport_medical', { wide: true })}
            ${fld('title', 'Titre', '', { required: true, wide: true })}
            <label class="field wide"><span>Fichier</span><input type="file" name="file" accept="application/pdf,image/png,image/jpeg" required></label>
        </form>`;

    modal({
        title: 'Ajouter un document',
        body,
        size: 'lg',
        actions: [
            { id: 'cancel', label: 'Annuler', cls: 'ghost', onClick: ({ close }) => close() },
            {
                id: 'save', label: 'Téléverser', cls: '',
                onClick: async ({ close, modalBox }) => {
                    const form = modalBox.querySelector('form[data-modal-prompt]');
                    if (!form.reportValidity()) return;
                    const file = form.file.files[0];
                    if (!file) { toast('Choisissez un fichier.', 'error'); return; }
                    if (file.size > 3000000) { toast('Fichier trop volumineux (3 Mo maximum).', 'error'); return; }
                    try {
                        await api(`/api/doctor/patients/${pid}/documents`, 'POST', {
                            type: form.type.value,
                            title: form.title.value,
                            file_name: file.name,
                            content_base64: await readBase64(file),
                        });
                        close();
                        await refreshPatientModal(pid);
                        toast('Document ajouté.');
                    } catch (e) { toast(e.message, 'error'); }
                },
            },
        ],
    });
};

async function refreshPatientModal(pid) {
    const modalBox = document.querySelector('.modal-overlay .modal[data-pid]');
    if (!modalBox) return;
    const p = App.state.patients.find(x => x.p_id === pid);
    if (!p) return;
    await renderPatientRecordInModal(pid, p, modalBox);
}

function profileSection() { return {
    id: 'profile', label: 'Profil',
    render: s => {
        const p = s.doctor;
        return card('Profil professionnel', `
            <form data-form="profile" class="grid">
                ${fld('first_name', 'Prénom', p.d_first_name, { required: true })}
                ${fld('last_name', 'Nom', p.d_last_name, { required: true })}
                ${fld('phone', 'Téléphone', p.u_phone, { required: true })}
                ${fld('specialty', 'Spécialité', p.d_specialty, { required: true })}
                ${sel('gender', 'Genre', GENDER_OPTIONS, p.d_gender)}
                ${fld('date_of_birth', 'Date de naissance', p.d_date_of_birth || '', { type: 'date' })}
                ${fld('city', 'Ville', p.d_city)}
                ${fld('country', 'Pays', p.d_country)}
                ${area('qualifications', 'Qualifications', p.d_qualifications)}
                ${area('bio', 'Présentation', p.d_bio)}
                ${fld('address', 'Adresse', p.d_address, { wide: true })}
                <button class="btn">Enregistrer</button>
            </form>
            <p class="muted">N° professionnel : <b>${esc(p.d_professional_id)}</b> — ${p.d_verification_status ? badge('active') + ' Vérifié' : badge('pending') + ' En attente de vérification'}</p>
        ` + accountCard());
    }
}; }
actions.profile = async (form, d) => { await api('/api/doctor/profile', 'POST', d); await reload(); return 'Profil mis à jour.'; };

function overviewSection() { return {
    id: 'overview', label: 'Vue d’ensemble',
    render: s => {
        if (!s.doctor.d_verification_status) {
            return `<div class="notice">Votre compte est en attente de vérification par un administrateur. Vous ne pourrez rejoindre un établissement ni accéder à un dossier avant cela.</div>`;
        }
        const upcoming = s.appointments.filter(a => isFuture(a.a_date, a.a_end_time));
        const pending = s.appointments.filter(a => a.status === 'pending');

        const centerHtml = `
            <div>
                <h2 class="welcome-title">Bonjour Dr ${esc(s.doctor.d_last_name)}</h2>
                <p class="welcome-sub">${esc(s.doctor.d_specialty || 'Médecin')}</p>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
                        <div class="stat-info"><b>${upcoming.length}</b><span>RDV à venir</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                        <div class="stat-info"><b>${pending.length}</b><span>En attente</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></div>
                        <div class="stat-info"><b>${s.patients.length}</b><span>Patients</span></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18"></path><path d="M5 21V7l8-4v18"></path><path d="M19 21V11l-6-4"></path></svg></div>
                        <div class="stat-info"><b>${s.facilities.filter(f => f.df_status && !f.df_pending).length}</b><span>Établissements</span></div>
                    </div>
                </div>
            </div>

            ${card('Rendez-vous à venir', upcoming.length ? upcoming.slice(0, 6).map(apptRow).join('') : empty('Aucun rendez-vous à venir.'))}
        `;
        return { center: centerHtml, right: rightSidebar(s) };
    }
}; }

function rightDefault(s) {
    return rightSidebar(s);
}

boot({
    role: 'Médecin',
    endpoint: '/api/doctor/dashboard',
    who: s => 'Dr ' + fullName(s.doctor.d_first_name, s.doctor.d_last_name),
    rightDefault: rightDefault,
    sections: [
        overviewSection(),
        appointmentsSection(),
        patientsSection(),
        facilitiesSection(),
        notificationsSection(),
        profileSection(),
    ],
});