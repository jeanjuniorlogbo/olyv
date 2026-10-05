'use strict';
const $ = (s, r = document) => r.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const DAYS = ['', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
const LABELS = {
    pending: 'En attente', confirmed: 'Confirmé', rejected: 'Refusé', cancelled: 'Annulé', completed: 'Terminé',
    no_show: 'Absent', accepted: 'Accepté', active: 'Actif', revoked: 'Retiré', expired: 'Expiré', open: 'En cours',
    closed: 'Clôturée', requested: 'Demandé', in_progress: 'En cours', reviewing: 'En examen', resolved: 'Résolu',
    dismissed: 'Classé', mild: 'Légère', moderate: 'Modérée', severe: 'Sévère', allowed: 'Autorisé', denied: 'Refusé',
    doctor: 'Médecin', trusted_person: 'Personne de confiance', patient: 'Patient', medecin: 'Médecin',
    etablissement: 'Établissement', admin: 'Administrateur',
};
const SCOPE_LABELS = {
    'record.read': 'Lire le dossier',
    'record.write': 'Écrire dans le dossier',
    'documents.read': 'Lire les documents',
    'documents.write': 'Ajouter des documents'
};
const fmtDate = v => v ? new Date(String(v).length === 10 ? v + 'T00:00:00' : v)
    .toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
const fmtTime = v => v ? String(v).slice(0, 5) : '';
const fmtDateTime = v => v ? new Date(v).toLocaleString('fr-FR',
    { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
const fullName = (f, l) => `${f || ''} ${l || ''}`.trim();
const initials = (f, l) => (((f || '?')[0] || '?') + ((l || '')[0] || '')).toUpperCase();

const MARK = '<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><line class="mark-link" x1="16" y1="16" x2="16" y2="5"/><line class="mark-link" x1="16" y1="16" x2="25.5" y2="21.5"/><line class="mark-link" x1="16" y1="16" x2="6.5" y2="21.5"/><circle class="mark-node" cx="16" cy="5" r="2.4"/><circle class="mark-node" cx="25.5" cy="21.5" r="2.4"/><circle class="mark-node" cx="6.5" cy="21.5" r="2.4"/><circle class="mark-node is-center" cx="16" cy="16" r="3.4"/></svg>';
const svg = d => `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
    menu: svg('<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>'),
    bell: svg('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>'),
    sound: svg('<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a10 10 0 0 1 0 14"/>'),
    mute: svg('<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>'),
    sun: svg('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.2" y1="4.2" x2="5.6" y2="5.6"/><line x1="18.4" y1="18.4" x2="19.8" y2="19.8"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.2" y1="19.8" x2="5.6" y2="18.4"/><line x1="18.4" y1="5.6" x2="19.8" y2="4.2"/>'),
    moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>'),
};
const initialsOf = name => {
    const [a = '?', b = ''] = String(name || '').trim().split(/\s+/);
    return ((a[0] || '?') + (b[0] || '')).toUpperCase();
};

const sfx = (() => {
    let ctx = null;
    let on = true;
    try { on = localStorage.getItem('sound') !== 'off'; } catch (e) { }
    const tone = (freq, dur, vol = 0.05, wait = 0) => {
        if (!on) return;
        try {
            ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
            const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + wait;
            o.frequency.value = freq;
            g.gain.setValueAtTime(0, t);
            g.gain.linearRampToValueAtTime(vol, t + 0.01);
            g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
            o.connect(g);
            g.connect(ctx.destination);
            o.start(t);
            o.stop(t + dur + 0.02);
        } catch (e) { }
    };
    return {
        tick: () => tone(700, 0.05, 0.035),
        ok: () => { tone(523, 0.12); tone(784, 0.18, 0.05, 0.09); },
        nf: () => { tone(880, 0.14); tone(1175, 0.22, 0.05, 0.12); },
        err: () => tone(220, 0.24, 0.06),
        isOn: () => on,
        toggle: () => {
            on = !on;
            try { localStorage.setItem('sound', on ? 'on' : 'off'); } catch (e) { }
            return on;
        },
    };
})();

function shell() {
    const themeBtn = (t, icon, label) => `<button type="button" data-theme="${t}" aria-label="${label}">${icon}</button>`;
    document.body.insertAdjacentHTML('afterbegin', `
    <div class="app-loader" id="app-loader">${MARK}<span>Olyvera</span></div>
    <div class="bubbles-bg">${'<div class="bubble"></div>'.repeat(4)}</div>
    <div class="app-shell">
        <header class="top-header">
            <div class="header-left">
                <button type="button" class="icon-btn burger-btn" id="burger-menu" aria-label="Menu" aria-expanded="false">${ICON.menu}</button>
                <div class="brand">${MARK}<span>Olyvera</span></div>
            </div>
            <div class="header-actions">
                <div class="theme-toggle" id="theme-toggle">${themeBtn('light', ICON.sun, 'Thème clair')}${themeBtn('dark', ICON.moon, 'Thème sombre')}</div>
                <button type="button" class="icon-btn" id="sound-btn" aria-label="Activer ou couper les sons"></button>
                <button type="button" class="icon-btn" id="bell-btn" aria-label="Notifications" aria-expanded="false">${ICON.bell}<em id="bell-count" hidden>0</em></button>
                <div class="header-profile"><div class="avatar" id="header-avatar">U</div><span id="who-header">Utilisateur</span></div>
            </div>
        </header>
        <div class="layout-grid">
            <aside class="sidebar-left" id="sidebar-left">
                <div id="side-info"></div>
                <nav id="nav"></nav>
                <button type="button" class="btn ghost" data-action="logout">Se déconnecter</button>
            </aside>
            <main class="col-center" id="content"><p class="muted">Chargement…</p></main>
        </div>
    </div>
    <div class="scrim" id="scrim"></div>
    <div class="notif-panel" id="notif-panel" role="dialog" aria-label="Notifications"></div>
    <div id="toast" aria-live="polite"></div>`);
}
shell();

let pendingRequests = 0;
function updateTopLoader() {
    let bar = document.getElementById('top-loader');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'top-loader';
        document.body.appendChild(bar);
    }
    if (pendingRequests > 0) bar.classList.add('active');
    else bar.classList.remove('active');
}

async function api(path, method = 'GET', body) {
    const options = { method, credentials: 'same-origin', headers: {} };
    if (body === undefined && method === 'POST') body = {};
    if (body !== undefined) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }
    pendingRequests++;
    updateTopLoader();
    let response, data = null;
    try {
        response = await fetch(path, options);
        try { data = await response.json(); } catch (e) { }
    } finally {
        pendingRequests--;
        updateTopLoader();
    }
    if (response.status === 401) { window.location.href = '/login'; throw new Error('Session expirée.'); }
    if (!response.ok || !data || data.success === false) {
        throw new Error((data && data.message) || 'Une erreur est survenue.');
    }
    return data;
}

const TOAST_ICONS = {
    ok: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`,
    warn: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`,
};

function toast(message, type = 'ok', duration = 4200) {
    const kind = (type === 'error') ? 'error' : (type === 'warn' ? 'warn' : (type === 'info' ? 'info' : 'ok'));
    const el = document.createElement('div');
    el.className = 'toast toast-' + kind;
    el.innerHTML = `
        <span class="toast-icon">${TOAST_ICONS[kind]}</span>
        <span class="toast-text">${esc(message)}</span>
        <button type="button" class="toast-close" aria-label="Fermer">&times;</button>
        <span class="toast-progress" style="animation-duration:${duration}ms;"></span>`;

    const container = $('#toast');
    if (!container) return;

    container.appendChild(el);
    (kind === 'error' ? sfx.err : kind === 'ok' ? sfx.ok : sfx.tick)();
    requestAnimationFrame(() => el.classList.add('show'));

    const remove = () => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 220);
    };
    const timer = setTimeout(remove, duration);
    el.querySelector('.toast-close').addEventListener('click', () => { clearTimeout(timer); remove(); });
}

function readBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1]);
        reader.onerror = () => reject(new Error('Lecture du fichier impossible.'));
        reader.readAsDataURL(file);
    });
}

const badge = s => `<span class="badge ${esc(s)}">${esc(LABELS[s] || s)}</span>`;
const empty = t => `<p class="empty">${esc(t)}</p>`;
const stat = (label, value) => `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`;
const card = (title, body, extra = '') =>
    `<section class="card"><div class="card-head"><h2>${esc(title)}</h2>${extra}</div>${body}</section>`;
const table = (heads, rows) => rows.length
    ? `<div class="table-wrap"><table><thead><tr>${heads.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${
        rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '';
const fld = (name, label, value = '', o = {}) =>
    `<label class="field ${o.wide ? 'wide' : ''}"><span>${esc(label)}</span><input name="${name}" type="${o.type || 'text'}" value="${esc(value)}" ${o.required ? 'required' : ''} ${o.attrs || ''}></label>`;
const area = (name, label, value = '', o = {}) =>
    `<label class="field wide"><span>${esc(label)}</span><textarea name="${name}" ${o.required ? 'required' : ''}>${esc(value)}</textarea></label>`;
const sel = (name, label, options, value = '', o = {}) =>
    `<label class="field ${o.wide ? 'wide' : ''}"><span>${esc(label)}</span><select name="${name}" ${o.required ? 'required' : ''}>${
        options.map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(value) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label>`;
const btn = (label, action, data = {}, cls = '') =>
    `<button type="button" class="btn sm ${cls}" data-action="${action}" ${Object.entries(data)
        .map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')}>${esc(label)}</button>`;
const asList = v => v === undefined ? [] : [].concat(v);
const isFuture = (d, t) => new Date(`${d}T${t}`) > new Date();
const GENDER_OPTIONS = [['prefer_not_to_say', 'Non précisé'], ['female', 'Femme'], ['male', 'Homme'], ['other', 'Autre']];

const skeleton = (lines = 3) =>
    `<div class="skeleton-list">${Array.from({ length: lines }).map(() =>
        `<div class="skeleton-row"><div class="skeleton-avatar"></div><div class="skeleton-text">
            <div class="skeleton-bar" style="width:60%"></div>
            <div class="skeleton-bar" style="width:40%"></div>
        </div></div>`).join('')}</div>`;

const skeletonTable = (rows = 4) =>
    `<div class="skeleton-table">${Array.from({ length: rows }).map(() =>
        `<div class="skeleton-line" style="width:${60 + Math.random() * 30}%"></div>`).join('')}</div>`;

const ModalStack = [];

function modalRoot() {
    let root = document.getElementById('modal-root');
    if (!root) {
        root = document.createElement('div');
        root.id = 'modal-root';
        document.body.appendChild(root);
    }
    return root;
}

function focusables(container) {
    return container.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
}

function modal({ title, body, actions = [], size = 'md', dismissible = true, onOpen }) {
    const root = modalRoot();
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    const box = document.createElement('div');
    box.className = `modal modal-${size}`;
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');

    const headHtml = `
        <div class="modal-head">
            <h3>${esc(title || '')}</h3>
            ${dismissible ? '<button type="button" class="modal-close" aria-label="Fermer">&times;</button>' : ''}
        </div>`;

    const footHtml = actions.length
        ? `<div class="modal-foot">${actions.map(a =>
            `<button type="button" class="btn ${a.cls || ''}" data-modal-action="${esc(a.id)}">${esc(a.label)}</button>`
        ).join('')}</div>`
        : '';

    box.innerHTML = headHtml + `<div class="modal-body">${body || ''}</div>` + footHtml;
    overlay.appendChild(box);
    root.appendChild(overlay);

    const entry = { overlay, box, dismissible, onClose: null };
    ModalStack.push(entry);

    requestAnimationFrame(() => overlay.classList.add('show'));

    const previouslyFocused = document.activeElement;

    function close(result) {
        if (!entry.dismissible && result === undefined) return;
        overlay.classList.remove('show');
        setTimeout(() => {
            overlay.remove();
            const idx = ModalStack.indexOf(entry);
            if (idx >= 0) ModalStack.splice(idx, 1);
            if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
            if (entry.onClose) entry.onClose(result);
        }, 180);
    }
    entry.close = close;

    if (dismissible) {
        overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
        const closeBtn = box.querySelector('.modal-close');
        if (closeBtn) closeBtn.addEventListener('click', () => close());
    }

    box.querySelectorAll('[data-modal-action]').forEach(b => {
        b.addEventListener('click', async () => {
            const id = b.dataset.modalAction;
            const spec = actions.find(a => a.id === id);
            if (spec && typeof spec.onClick === 'function') {
                const original = b.innerHTML;
                b.disabled = true;
                b.innerHTML = `<span class="btn-spinner"></span>${esc(spec.label)}`;
                try {
                    await spec.onClick({ close, modalBox: box });
                } finally {
                    b.disabled = false;
                    b.innerHTML = original;
                }
            } else {
                close(id);
            }
        });
    });

    document.addEventListener('keydown', escHandler);
    function escHandler(e) {
        if (ModalStack[ModalStack.length - 1] !== entry) return;
        if (e.key === 'Escape' && entry.dismissible) close();
        if (e.key === 'Tab') {
            const f = focusables(box);
            if (!f.length) return;
            const first = f[0], last = f[f.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
    }
    overlay._escHandler = escHandler;

    setTimeout(() => {
        const f = focusables(box);
        if (f.length) f[0].focus();
        if (typeof onOpen === 'function') onOpen({ modalBox: box, close });
    }, 50);

    return { close, box };
}

function closeModal() {
    const top = ModalStack[ModalStack.length - 1];
    if (top) top.close();
}

function confirmAction({
    title = 'Confirmer',
    message = '',
    confirmLabel = 'Confirmer',
    cancelLabel = 'Annuler',
    danger = false,
    requireText = null,
} = {}) {
    return new Promise(resolve => {
        const body = `
            <p class="modal-message">${message}</p>
            ${requireText ? `
                <label class="field wide" style="margin-top:14px;">
                    <span>Pour confirmer, tapez « ${esc(requireText)} »</span>
                    <input type="text" data-modal-confirm-input autocomplete="off">
                </label>` : ''}
        `;

        const m = modal({
            title,
            body,
            size: 'sm',
            dismissible: true,
            actions: [
                { id: 'cancel', label: cancelLabel, cls: 'ghost', onClick: ({ close }) => { close(); resolve(false); } },
                {
                    id: 'confirm', label: confirmLabel, cls: danger ? 'danger' : '',
                    onClick: ({ close, modalBox }) => {
                        if (requireText) {
                            const inp = modalBox.querySelector('[data-modal-confirm-input]');
                            if (!inp || inp.value.trim() !== requireText) {
                                inp.classList.add('shake');
                                setTimeout(() => inp.classList.remove('shake'), 400);
                                return;
                            }
                        }
                        close();
                        resolve(true);
                    },
                },
            ],
        });

        m.box._onResolve = resolve;
        const overlayClose = m.box.parentElement;
        const obs = new MutationObserver(() => {
            if (!document.body.contains(overlayClose)) {
                obs.disconnect();
                resolve(false);
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });

        if (requireText) {
            setTimeout(() => {
                const inp = m.box.querySelector('[data-modal-confirm-input]');
                if (inp) inp.focus();
            }, 80);
        }
    });
}

function promptForm({ title, fields = [], confirmLabel = 'Valider', cancelLabel = 'Annuler' } = {}) {
    return new Promise(resolve => {
        const body = `<form data-modal-prompt class="grid">${fields.map(f => {
            const common = `name="${esc(f.name)}" ${f.required ? 'required' : ''} ${f.attrs || ''}`;
            if (f.type === 'textarea') {
                return `<label class="field wide"><span>${esc(f.label)}</span><textarea ${common}>${esc(f.value || '')}</textarea></label>`;
            }
            if (f.type === 'select') {
                return `<label class="field ${f.wide ? 'wide' : ''}"><span>${esc(f.label)}</span><select ${common}>${
                    (f.options || []).map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(f.value) ? 'selected' : ''}>${esc(l)}</option>`).join('')
                }</select></label>`;
            }
            return `<label class="field ${f.wide ? 'wide' : ''}"><span>${esc(f.label)}</span><input type="${f.type || 'text'}" ${common} value="${esc(f.value || '')}"></label>`;
        }).join('')}</form>`;

        const m = modal({
            title,
            body,
            size: 'md',
            actions: [
                { id: 'cancel', label: cancelLabel, cls: 'ghost', onClick: ({ close }) => { close(); resolve(null); } },
                {
                    id: 'confirm', label: confirmLabel, cls: '',
                    onClick: ({ close, modalBox }) => {
                        const form = modalBox.querySelector('form[data-modal-prompt]');
                        if (!form.reportValidity()) return;
                        const out = {};
                        new FormData(form).forEach((v, k) => { out[k] = v; });
                        close();
                        resolve(out);
                    },
                },
            ],
        });

        const overlayClose = m.box.parentElement;
        const obs = new MutationObserver(() => {
            if (!document.body.contains(overlayClose)) { obs.disconnect(); resolve(null); }
        });
        obs.observe(document.body, { childList: true, subtree: true });
    });
}

function recordHtml(r) {
    if (!r) return empty('Dossier non disponible.');
    const rec = r.record || {};
    const consultations = r.consultations || [];
    const prescriptions = r.prescriptions || [];
    const allergies = r.allergies || [];
    const treatments = r.treatments || [];
    const exams = r.exams || [];
    const documents = r.documents || [];
    const diagnoses = r.diagnoses || [];

    const cons = consultations.map(c => `<div class="item">
        <div class="row"><b>${fmtDate(c.c_date)}</b> ${badge(c.status)} <span class="muted">Dr ${esc(c.doctor)} — ${esc(c.d_specialty)} · ${esc(c.hf_name)}</span></div>
        ${c.c_reason ? `<div><span class="muted">Motif :</span> ${esc(c.c_reason)}</div>` : ''}
        ${c.c_observations ? `<div><span class="muted">Observations :</span> ${esc(c.c_observations)}</div>` : ''}
        ${c.c_conclusion ? `<div><span class="muted">Conclusion :</span> ${esc(c.c_conclusion)}</div>` : ''}
        ${diagnoses.filter(d => d.dg_consultation_id === c.c_id).map(d => `<div>▸ <b>${esc(d.dg_name)}</b> ${esc(d.dg_description || '')}</div>`).join('')}
    </div>`).join('');

    const pres = prescriptions.map(p => `<div class="item">
        <div class="row"><b>${fmtDate(p.pr_date)}</b><span class="muted">Dr ${esc(p.doctor)}</span></div>
        ${table(['Médicament', 'Posologie', 'Fréquence', 'Durée', 'Instructions'], (p.items || []).map(i => [
            esc(i.pri_medicine_name), esc(i.pri_dosage), esc(i.pri_frequency), esc(i.pri_duration), esc(i.pri_instructions)
        ]))}
        ${p.pr_notes ? `<div class="muted">${esc(p.pr_notes)}</div>` : ''}</div>`).join('');

    return `
    ${card('Groupe sanguin', rec.blood_group
        ? `<b>${esc(rec.blood_group)}</b> <span class="muted">— validé par Dr ${esc(rec.validated_by)} le ${fmtDate(rec.validated_at)}</span>`
        : empty('Non renseigné : seul un professionnel de santé peut le valider.'))}
    ${card('Allergies', allergies.length ? allergies.map(a => `<div class="item"><b>${esc(a.al_name)}</b> ${a.severity ? badge(a.severity) : ''}
        <div class="muted">${esc(a.al_description || '')} — Dr ${esc(a.doctor)}</div></div>`).join('') : empty('Aucune allergie enregistrée.'))}
    ${card('Traitements', treatments.length ? treatments.map(t => `<div class="item"><b>${esc(t.tr_name)}</b> ${t.tr_status ? badge('active') : ''}
        <div class="muted">${fmtDate(t.tr_start_date)} → ${t.tr_end_date ? fmtDate(t.tr_end_date) : 'en cours'} — ${esc(t.tr_description || '')}</div></div>`).join('') : empty('Aucun traitement.'))}
    ${card('Consultations et diagnostics', cons || empty('Aucune consultation.'))}
    ${card('Ordonnances', pres || empty('Aucune ordonnance.'))}
    ${card('Examens', exams.length ? exams.map(e => `<div class="item"><b>${esc(e.me_name)}</b> ${badge(e.status)}
        <div class="muted">${fmtDate(e.me_requested_at)} — Dr ${esc(e.doctor)} ${esc(e.me_description || '')}</div>
        ${e.me_result ? `<div><span class="muted">Résultat (${fmtDate(e.me_result_date)}) :</span> ${esc(e.me_result)}</div>` : ''}</div>`).join('') : empty('Aucun examen.'))}
    ${card('Documents', documents.length ? documents.map(d => `<div class="item"><b>${esc(d.md_title)}</b>
        <span class="muted">${esc((d.type || '').replace('_', ' '))} — ${fmtDate(d.md_created_at)}${d.doctor ? ' — Dr ' + esc(d.doctor) : ''}</span>
        <div><a href="/api/documents/${d.md_id}/download">Télécharger${d.md_file_name ? ' « ' + esc(d.md_file_name) + ' »' : ''}</a></div></div>`).join('') : empty('Aucun document.'))}`;
}

const unread = s => (s.notifications || []).filter(n => !n.n_is_read).length;
const lrow = ({ title, text = '', date = '', side = '', dot = null }) =>
    `<div class="lrow">${dot === null ? '' : `<span class="dot ${dot ? '' : 'read'}"></span>`}
        <div class="lrow-main"><b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ''}</div>
        <div class="lrow-side">${date ? `<span class="lrow-date">${esc(date)}</span>` : ''}${side}</div></div>`;
const notifRow = n => lrow({
    title: n.n_title, text: n.n_message, date: fmtDateTime(n.n_created_at), dot: !n.n_is_read,
    side: n.n_is_read ? '' : btn('Marquer comme lu', 'readOne', { id: n.n_id }, 'ghost'),
});
const notifList = (list, max = 99) => list.length ? list.slice(0, max).map(notifRow).join('') : empty('Aucune notification.');
const notificationsSection = () => ({
    id: 'notifications', label: 'Notifications', badge: unread,
    render: s => card('Notifications', notifList(s.notifications || []),
        unread(s) ? btn('Tout marquer comme lu', 'readAll', {}, 'ghost') : ''),
});
const accountCard = (withPhoto = true) => card('Sécurité et compte',
    `<form data-form="password" class="grid">
        ${fld('current_password', 'Mot de passe actuel', '', { type: 'password', required: true, attrs: 'autocomplete="current-password"' })}
        ${fld('new_password', 'Nouveau mot de passe (8 caractères min.)', '', { type: 'password', required: true, attrs: 'autocomplete="new-password" minlength="8"' })}
        ${fld('new_password_confirmation', 'Confirmation', '', { type: 'password', required: true, attrs: 'autocomplete="new-password"' })}
        <button class="btn">Changer le mot de passe</button></form>
     <p class="muted">Vos autres appareils seront déconnectés.</p>
     ${withPhoto ? `<h3>Photo</h3><input type="file" accept="image/png,image/jpeg" data-change="photo">` : ''}
     <h3>Signaler un problème</h3>
     <form data-form="report" class="grid">${fld('subject', 'Sujet', '', { required: true })}
        ${area('description', 'Description', '', { required: true })}<button class="btn ghost">Envoyer à l’équipe</button></form>`);

const actions = {};
const App = { state: null, cfg: null };

async function reload() {
    App.state = (await api(App.cfg.endpoint)).data;
    draw();
}
const currentSection = () => App.cfg.sections.find(s => s.id === location.hash.slice(1)) || App.cfg.sections[0];

function paintAvatar() {
    const el = $('#header-avatar');
    const name = App.cfg.who(App.state);
    const photo = App.cfg.photo ? App.cfg.photo(App.state) : null;
    el.textContent = initialsOf(name);
    if (!photo) return;
    const img = new Image();
    img.alt = '';
    img.onload = () => { el.textContent = ''; el.appendChild(img); };
    img.src = photo;
}

function paintNotifs() {
    const list = App.state.notifications || [];
    const n = unread(App.state);
    const count = $('#bell-count');
    count.textContent = n > 9 ? '9+' : n;
    count.hidden = !n;
    $('#notif-panel').innerHTML = `<div class="notif-head"><b>Notifications</b>${n ? btn('Tout marquer comme lu', 'readAll', {}, 'ghost') : ''}</div>
        ${notifList(list, 6)}<a class="notif-all" href="#notifications">Voir tout</a>`;
    if (App.unread !== undefined && n > App.unread) sfx.nf();
    App.unread = n;
}

function draw() {
    if (!App.state) return;
    const cur = currentSection();
    $('#nav').innerHTML = App.cfg.sections.map(s => {
        const n = s.badge ? s.badge(App.state) : 0;
        return `<a href="#${s.id}" class="${s === cur ? 'active' : ''}">${esc(s.label)}${n ? `<em>${n}</em>` : ''}</a>`;
    }).join('');
    $('#who-header').textContent = App.cfg.who(App.state);
    paintAvatar();
    paintNotifs();

    const result = cur.render(App.state);
    const split = result && typeof result === 'object' && result.center;
    const content = $('#content');
    content.classList.remove('section-enter');
    void content.offsetWidth;
    content.classList.add('section-enter');
    content.innerHTML = split ? result.center : result;

    const side = $('#side-info');
    side.innerHTML = (split ? result.right : App.cfg.rightDefault && App.cfg.rightDefault(App.state)) || '';
    side.querySelectorAll('.rdv-card').forEach(c =>
        c.classList.toggle('folded', App.folded.has(c.querySelector('h3').textContent)));

    if (typeof cur.after === 'function') cur.after(App.state);
}

async function boot(cfg) {
    App.cfg = cfg;
    App.folded = new Set();
    document.title = 'Olyvera — ' + cfg.role;

    const side = $('#sidebar-left'), scrim = $('#scrim'), panel = $('#notif-panel');
    const bell = $('#bell-btn'), burger = $('#burger-menu'), soundBtn = $('#sound-btn');
    const setDrawer = open => {
        side.classList.toggle('open', open);
        scrim.classList.toggle('on', open);
        burger.setAttribute('aria-expanded', open);
    };
    const setPanel = open => {
        panel.classList.toggle('on', open);
        bell.setAttribute('aria-expanded', open);
    };
    const closeUi = () => { setDrawer(false); setPanel(false); };
    const paintSound = () => { soundBtn.innerHTML = sfx.isOn() ? ICON.sound : ICON.mute; };

    window.addEventListener('hashchange', () => { closeUi(); draw(); });
    burger.addEventListener('click', () => setDrawer(!side.classList.contains('open')));
    scrim.addEventListener('click', closeUi);
    bell.addEventListener('click', () => setPanel(!panel.classList.contains('on')));
    soundBtn.addEventListener('click', () => { sfx.toggle(); paintSound(); sfx.tick(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeUi(); });
    document.addEventListener('click', e => {
        if (!panel.contains(e.target) && !bell.contains(e.target)) setPanel(false);
        if (e.target.closest('#nav a, .icon-btn, .theme-toggle button, .rdv-card h3')) sfx.tick();
    });
    $('#side-info').addEventListener('click', e => {
        const title = e.target.closest('.rdv-card h3');
        if (!title) return;
        const folded = title.parentElement.classList.toggle('folded');
        App.folded[folded ? 'add' : 'delete'](title.textContent);
    });
    paintSound();

    try {
        await reload();
    } catch (e) {
        $('#content').innerHTML = `<p class="error">${esc(e.message)}</p>`;
    } finally {
        const loader = $('#app-loader');
        loader.classList.add('hidden');
        setTimeout(() => loader.remove(), 500);
    }
}

async function run(fn, el, data) {
    if (!fn || el._busy) return;
    if (el.dataset && el.dataset.confirm && !window.confirm(el.dataset.confirm)) return;
    el._busy = true;

    let original = null;
    if (el.tagName === 'BUTTON') {
        original = el.innerHTML;
        el.disabled = true;
        el.innerHTML = `<span class="btn-spinner"></span>${el.textContent.trim()}`;
    }

    try {
        const message = await fn(el, data);
        if (message) toast(message);
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        el._busy = false;
        if (original !== null) {
            el.disabled = false;
            el.innerHTML = original;
        }
    }
}

function collect(form, submitter) {
    const out = {};
    for (const [k, v] of new FormData(form, submitter || undefined)) {
        if (typeof v !== 'string') continue;
        out[k] = k in out ? [].concat(out[k], v) : v;
    }
    return out;
}

document.addEventListener('click', ev => {
    const el = ev.target.closest('[data-action]');
    if (el) { ev.preventDefault(); run(actions[el.dataset.action], el); }
});
document.addEventListener('submit', ev => {
    const form = ev.target.closest('form[data-form]');
    if (form) { ev.preventDefault(); run(actions[form.dataset.form], form, collect(form, ev.submitter)); }
});
document.addEventListener('change', ev => {
    const el = ev.target.closest('[data-change]');
    if (el) run(actions[el.dataset.change], el, { value: el.value });
});

actions.logout = async () => { await api('/logout', 'POST'); window.location.href = '/login'; };
actions.readAll = async () => { await api('/api/notifications/read', 'POST', { all: true }); await reload(); sfx.ok(); };
actions.readOne = async el => { await api('/api/notifications/read', 'POST', { id: Number(el.dataset.id) }); await reload(); sfx.ok(); };
actions.password = async (form, d) => { await api('/api/account/password', 'POST', d); form.reset(); return 'Mot de passe modifié.'; };
actions.report = async (form, d) => { await api('/api/reports', 'POST', d); form.reset(); return 'Signalement envoyé.'; };
actions.photo = async el => {
    const file = el.files[0];
    if (!file) return;
    if (file.size > 400000) throw new Error('Photo trop lourde (400 Ko maximum).');
    await api('/api/account/photo', 'POST', { content_base64: await readBase64(file) });
    await reload();
    return 'Photo mise à jour.';
};