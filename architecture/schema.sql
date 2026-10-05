-- Olyvera — schéma PostgreSQL 15+
-- Utilisation :  createdb Olyvera  &&  psql -d Olyvera -f architecture/schema.sql
-- (l'extension btree_gist est fournie par postgresql-contrib)

create extension if not exists btree_gist;

-- ───────────── Types ─────────────
create type user_role           as enum ('patient','medecin','etablissement','admin');
create type gender_type         as enum ('male','female','other','prefer_not_to_say');
create type facility_type       as enum ('hopital','clinique','cabinet','centre_de_sante');
create type appointment_status  as enum ('pending','confirmed','rejected','cancelled','completed','no_show');
create type family_status       as enum ('pending','accepted','rejected','removed');
create type access_status       as enum ('active','revoked','expired');
create type access_kind         as enum ('doctor','trusted_person');
create type document_type       as enum ('rapport_medical','resultat_examen','ordonnance','certificat','autre');
create type notification_type   as enum ('appointment','family','medical_access','security','system');
create type severity_type       as enum ('mild','moderate','severe');
create type exam_status         as enum ('requested','in_progress','completed','cancelled');
create type consultation_status as enum ('open','closed');
create type report_status       as enum ('pending','reviewing','resolved','dismissed');

-- ───────────── Rôles & permissions ─────────────
create table roles (
    r_id         integer generated always as identity primary key,
    r_type       user_role unique not null,
    r_created_at timestamptz not null default now()
);
insert into roles (r_type) values ('patient'),('medecin'),('etablissement'),('admin');

create table permissions (
    pm_id         integer generated always as identity primary key,
    pm_name       varchar(100) unique not null,
    pm_description text,
    pm_created_at timestamptz not null default now()
);

create table role_permissions (
    rp_id            integer generated always as identity primary key,
    rp_role_id       integer not null references roles(r_id) on delete cascade,
    rp_permission_id integer not null references permissions(pm_id) on delete cascade,
    unique (rp_role_id, rp_permission_id)
);

insert into permissions (pm_name, pm_description) values
    ('profile.manage_own',      'Gérer son propre profil'),
    ('appointments.create',     'Demander / annuler ses rendez-vous'),
    ('appointments.manage',     'Traiter les demandes de rendez-vous'),
    ('records.read_own',        'Lire son propre dossier médical'),
    ('records.write',           'Renseigner des données médicales (sous autorisation patient)'),
    ('access.manage_own',       'Gérer les autorisations d''accès à son dossier'),
    ('family.manage_own',       'Gérer ses relations familiales'),
    ('availabilities.manage',   'Gérer ses disponibilités'),
    ('facility.manage',         'Gérer un établissement et ses médecins'),
    ('users.manage',            'Gérer les comptes utilisateurs'),
    ('reports.manage',          'Traiter les signalements'),
    ('security.logs.read',      'Consulter les journaux techniques et de sécurité'),
    ('platform.settings',       'Gérer les paramètres de la plateforme');

insert into role_permissions (rp_role_id, rp_permission_id)
select r.r_id, p.pm_id
from (values
    ('patient','profile.manage_own'), ('patient','appointments.create'), ('patient','records.read_own'),
    ('patient','access.manage_own'),  ('patient','family.manage_own'),
    ('medecin','profile.manage_own'), ('medecin','appointments.manage'), ('medecin','records.write'),
    ('medecin','availabilities.manage'),
    ('etablissement','profile.manage_own'), ('etablissement','facility.manage'),
    ('etablissement','appointments.manage'),
    ('admin','profile.manage_own'), ('admin','users.manage'), ('admin','reports.manage'),
    ('admin','security.logs.read'), ('admin','platform.settings')
) as v(role, perm)
join roles r on r.r_type = v.role::user_role
join permissions p on p.pm_name = v.perm;

-- ───────────── Comptes ─────────────
create table users (
    u_id            integer generated always as identity primary key,
    u_email         varchar(255) not null,
    u_phone         varchar(30) unique not null,
    u_password      varchar(255) not null,
    u_role_id       integer not null references roles(r_id),
    u_is_active     boolean not null default true,
    u_created_at    timestamptz not null default now(),
    u_updated_at    timestamptz not null default now(),
    u_last_login_at timestamptz
);
create unique index uq_users_email_lower on users (lower(u_email));

create table sessions (
    s_id         bigint generated always as identity primary key,
    s_token      varchar(128) not null unique,      -- hash SHA-256 du jeton
    s_user_id    integer not null references users(u_id) on delete cascade,
    s_expires_at timestamptz not null,
    s_created_at timestamptz not null default now()
);
create index idx_sessions_user    on sessions (s_user_id);
create index idx_sessions_expires on sessions (s_expires_at);

create table patients (
    p_id                integer generated always as identity primary key,
    p_user_id           integer unique not null references users(u_id),
    p_first_name        varchar(100) not null,
    p_last_name         varchar(100) not null,
    p_date_of_birth     date check (p_date_of_birth <= current_date),
    p_gender            gender_type not null default 'prefer_not_to_say',
    p_address           text,
    p_city              varchar(100),
    p_country           varchar(100),
    p_profile_photo_url varchar(500),
    p_created_at        timestamptz not null default now(),
    p_updated_at        timestamptz not null default now()
);

create table doctors (
    d_id                  integer generated always as identity primary key,
    d_user_id             integer unique not null references users(u_id),
    d_first_name          varchar(100) not null,
    d_last_name           varchar(100) not null,
    d_professional_id     varchar(100) unique not null,
    d_specialty           varchar(255) not null,
    d_qualifications      text,
    d_bio                 text,
    d_date_of_birth       date,
    d_gender              gender_type not null default 'prefer_not_to_say',
    d_address             text,
    d_city                varchar(100),
    d_country             varchar(100),
    d_profile_photo_url   varchar(500),
    d_verification_status boolean not null default false,
    d_is_active           boolean not null default true,
    d_created_at          timestamptz not null default now(),
    d_updated_at          timestamptz not null default now()
);

create table health_facilities (
    hf_id          integer generated always as identity primary key,
    hf_user_id     integer unique references users(u_id),   -- compte « établissement » gestionnaire
    hf_name        varchar(255) not null,
    hf_type        facility_type not null,
    hf_phone       varchar(30) unique not null,
    hf_email       varchar(255) unique,
    hf_address     text not null,
    hf_city        varchar(100) not null,
    hf_country     varchar(100) not null,
    hf_description text,
    hf_logo_url    varchar(500),
    hf_services    text,
    hf_specialties text,
    hf_opening_hours text,
    hf_status      boolean not null default true,
    hf_verification_status boolean not null default false,
    hf_created_at  timestamptz not null default now(),
    hf_updated_at  timestamptz not null default now()
);

create table doctor_facilities (
    df_id          integer generated always as identity primary key,
    df_doctor_id   integer not null references doctors(d_id),
    df_facility_id integer not null references health_facilities(hf_id),
    df_position    varchar(100),
    df_start_date  date not null default current_date,
    df_end_date    date,
    df_status      boolean not null default true,
    df_pending     boolean not null default false,   -- invitation en attente de réponse du médecin
    df_created_at  timestamptz not null default now(),
    unique (df_doctor_id, df_facility_id),
    check (df_end_date is null or df_end_date >= df_start_date)
);
create index idx_df_facility on doctor_facilities (df_facility_id);

create table doctor_availabilities (
    da_id           integer generated always as identity primary key,
    da_doctor_id    integer not null references doctors(d_id),
    da_facility_id  integer not null references health_facilities(hf_id),
    da_day_of_week  integer not null check (da_day_of_week between 1 and 7),
    da_start_time   time not null,
    da_end_time     time not null,
    da_slot_minutes integer not null default 30 check (da_slot_minutes between 10 and 240),
    da_status       boolean not null default true,
    da_created_at   timestamptz not null default now(),
    da_updated_at   timestamptz not null default now(),
    check (da_end_time > da_start_time)
);
create index idx_da_doctor on doctor_availabilities (da_doctor_id, da_facility_id, da_day_of_week);

-- ───────────── Rendez-vous ─────────────
create table appointments (
    a_id           integer generated always as identity primary key,
    a_patient_id   integer not null references patients(p_id),
    a_doctor_id    integer not null references doctors(d_id),
    a_facility_id  integer not null references health_facilities(hf_id),
    a_date         date not null,
    a_start_time   time not null,
    a_end_time     time not null,
    a_reason       text not null,
    a_status       appointment_status not null default 'pending',
    a_patient_note text,
    a_created_at   timestamptz not null default now(),
    a_updated_at   timestamptz not null default now(),
    check (a_end_time > a_start_time),
    -- un médecin ne peut pas avoir deux rendez-vous actifs qui se chevauchent
    constraint appointments_no_overlap exclude using gist (
        a_doctor_id with =,
        tsrange(a_date + a_start_time, a_date + a_end_time) with &&
    ) where (a_status in ('pending','confirmed'))
);
create index idx_appointments_patient on appointments (a_patient_id, a_date);
create index idx_appointments_doctor  on appointments (a_doctor_id, a_date);
create index idx_appointments_facility on appointments (a_facility_id, a_date);

-- ───────────── Famille ─────────────
create table family_relationships (
    fr_id              integer generated always as identity primary key,
    fr_patient_id      integer not null references patients(p_id),
    fr_related_user_id integer not null references users(u_id),
    fr_relationship    varchar(50) not null,
    fr_status          family_status not null default 'pending',
    fr_created_at      timestamptz not null default now(),
    fr_updated_at      timestamptz not null default now(),
    unique (fr_patient_id, fr_related_user_id)
);
create index idx_family_related on family_relationships (fr_related_user_id);

-- ───────────── Dossier médical (écrit par les professionnels) ─────────────
create table medical_records (
    mr_id           integer generated always as identity primary key,
    mr_patient_id   integer unique not null references patients(p_id),
    mr_blood_group  varchar(10),
    mr_validated_by integer references doctors(d_id),   -- auteur de la valeur
    mr_validated_at timestamptz,
    mr_created_at   timestamptz not null default now(),
    mr_updated_at   timestamptz not null default now()
);

create table consultations (
    c_id             integer generated always as identity primary key,
    c_patient_id     integer not null references patients(p_id),
    c_doctor_id      integer not null references doctors(d_id),
    c_facility_id    integer not null references health_facilities(hf_id),
    c_appointment_id integer unique references appointments(a_id),
    c_status         consultation_status not null default 'open',
    c_date           timestamptz not null default now(),
    c_reason         text,
    c_observations   text,
    c_conclusion     text,
    c_closed_at      timestamptz,
    c_created_at     timestamptz not null default now(),
    c_updated_at     timestamptz not null default now()
);
create index idx_consultations_patient on consultations (c_patient_id, c_date desc);
create index idx_consultations_doctor  on consultations (c_doctor_id);

create table diagnoses (
    dg_id              integer generated always as identity primary key,
    dg_consultation_id integer not null references consultations(c_id),
    dg_created_by      integer not null references doctors(d_id),
    dg_name            varchar(255) not null,
    dg_description     text,
    dg_created_at      timestamptz not null default now()
);
create index idx_diagnoses_consultation on diagnoses (dg_consultation_id);

create table allergies (
    al_id          integer generated always as identity primary key,
    al_patient_id  integer not null references patients(p_id),
    al_name        varchar(255) not null,
    al_description text,
    al_severity    severity_type,
    al_status      boolean not null default true,
    al_created_by  integer not null references doctors(d_id),
    al_created_at  timestamptz not null default now(),
    al_updated_at  timestamptz not null default now()
);
create index idx_allergies_patient on allergies (al_patient_id);

create table treatments (
    tr_id              integer generated always as identity primary key,
    tr_patient_id      integer not null references patients(p_id),
    tr_consultation_id integer references consultations(c_id),
    tr_name            varchar(255) not null,
    tr_description     text,
    tr_start_date      date,
    tr_end_date        date,
    tr_status          boolean not null default true,
    tr_created_by      integer not null references doctors(d_id),
    tr_created_at      timestamptz not null default now(),
    tr_updated_at      timestamptz not null default now()
);
create index idx_treatments_patient on treatments (tr_patient_id);

create table prescriptions (
    pr_id              integer generated always as identity primary key,
    pr_patient_id      integer not null references patients(p_id),
    pr_doctor_id       integer not null references doctors(d_id),
    pr_consultation_id integer references consultations(c_id),
    pr_date            timestamptz not null default now(),
    pr_notes           text,
    pr_created_at      timestamptz not null default now()
);
create index idx_prescriptions_patient on prescriptions (pr_patient_id, pr_date desc);

create table prescription_items (
    pri_id              integer generated always as identity primary key,
    pri_prescription_id integer not null references prescriptions(pr_id) on delete cascade,
    pri_medicine_name   varchar(255) not null,
    pri_dosage          varchar(100),
    pri_frequency       varchar(100),
    pri_duration        varchar(100),
    pri_instructions    text
);
create index idx_pri_prescription on prescription_items (pri_prescription_id);

create table medical_exams (
    me_id              integer generated always as identity primary key,
    me_patient_id      integer not null references patients(p_id),
    me_doctor_id       integer not null references doctors(d_id),
    me_consultation_id integer references consultations(c_id),
    me_name            varchar(255) not null,
    me_description     text,
    me_requested_at    timestamptz not null default now(),
    me_result          text,
    me_result_date     timestamptz,
    me_status          exam_status not null default 'requested'
);
create index idx_exams_patient on medical_exams (me_patient_id, me_requested_at desc);

create table medical_documents (
    md_id              integer generated always as identity primary key,
    md_patient_id      integer not null references patients(p_id),
    md_doctor_id       integer references doctors(d_id),
    md_consultation_id integer references consultations(c_id),
    md_type            document_type not null,
    md_title           varchar(255) not null,
    md_description     text,
    md_storage_key     varchar(255) not null,   -- clé dans storage/documents (jamais une URL publique)
    md_file_name       varchar(255),
    md_mime_type       varchar(100),
    md_created_at      timestamptz not null default now(),
    md_updated_at      timestamptz not null default now()
);
create index idx_documents_patient on medical_documents (md_patient_id, md_created_at desc);

-- ───────────── Autorisations patient → professionnel / personne de confiance ─────────────
create table medical_access (
    ma_id                 integer generated always as identity primary key,
    ma_patient_id         integer not null references patients(p_id),
    ma_granted_to_user_id integer not null references users(u_id),
    ma_granted_by_user_id integer not null references users(u_id),
    ma_kind               access_kind not null default 'doctor',
    ma_status             access_status not null default 'active',
    ma_scopes             text[] not null default '{}'
        check (ma_scopes <@ array['record.read','record.write','documents.read','documents.write']::text[]),
    ma_start_at           timestamptz not null default now(),
    ma_end_at             timestamptz,
    ma_created_at         timestamptz not null default now(),
    ma_updated_at         timestamptz not null default now(),
    check (ma_granted_to_user_id <> ma_granted_by_user_id),
    check (ma_end_at is null or ma_end_at > ma_start_at)
);
-- une seule autorisation active par (patient, bénéficiaire)
create unique index uq_medical_access_active
    on medical_access (ma_patient_id, ma_granted_to_user_id) where ma_status = 'active';
create index idx_medical_access_user on medical_access (ma_granted_to_user_id);

-- ───────────── Journal (ajout seul) ─────────────
create table access_logs (
    alog_id          bigint generated always as identity primary key,
    alog_user_id     integer references users(u_id),
    alog_patient_id  integer references patients(p_id),
    alog_action      varchar(100) not null,
    alog_resource    varchar(100) not null,
    alog_resource_id integer,
    alog_result      varchar(50) not null,
    alog_ip_address  inet,
    alog_user_agent  text,
    alog_created_at  timestamptz not null default now()
);
create index idx_access_logs_patient on access_logs (alog_patient_id, alog_created_at desc);
create index idx_access_logs_user    on access_logs (alog_user_id, alog_created_at desc);

create function forbid_change() returns trigger language plpgsql as $$
begin
    raise exception 'Table % en ajout seul', tg_table_name;
end $$;
create trigger trg_access_logs_immutable
    before update or delete on access_logs
    for each row execute function forbid_change();

-- ───────────── Notifications & signalements ─────────────
create table notifications (
    n_id         bigint generated always as identity primary key,
    n_user_id    integer not null references users(u_id),
    n_type       notification_type not null,
    n_title      varchar(255) not null,
    n_message    text not null,
    n_is_read    boolean not null default false,
    n_created_at timestamptz not null default now(),
    n_read_at    timestamptz
);
create index idx_notifications_user on notifications (n_user_id, n_is_read, n_created_at desc);

create table reports (
    rp_id               bigint generated always as identity primary key,
    rp_reporter_user_id integer not null references users(u_id),
    rp_reported_user_id integer references users(u_id),
    rp_subject          varchar(255) not null,
    rp_description      text not null,
    rp_status           report_status not null default 'pending',
    rp_created_at       timestamptz not null default now(),
    rp_updated_at       timestamptz not null default now()
);

-- ───────────── Paramètres de la plateforme ─────────────
create table platform_settings (
    ps_key        varchar(60) primary key,
    ps_value      text not null,
    ps_updated_at timestamptz not null default now()
);
insert into platform_settings (ps_key, ps_value) values
    ('support_email', ''), ('maintenance_message', ''), ('registration_open', '1');

-- ───────────── updated_at automatique ─────────────
create function touch_updated_at() returns trigger language plpgsql as $$
begin
    new := jsonb_populate_record(new, jsonb_build_object(tg_argv[0], now()));
    return new;
end $$;

do $$
declare t record;
begin
    for t in select * from (values
        ('users','u_updated_at'), ('patients','p_updated_at'), ('doctors','d_updated_at'),
        ('health_facilities','hf_updated_at'), ('doctor_availabilities','da_updated_at'),
        ('appointments','a_updated_at'), ('family_relationships','fr_updated_at'),
        ('medical_records','mr_updated_at'), ('consultations','c_updated_at'),
        ('allergies','al_updated_at'), ('treatments','tr_updated_at'),
        ('medical_documents','md_updated_at'), ('medical_access','ma_updated_at'),
        ('reports','rp_updated_at')
    ) as v(tbl, col) loop
        execute format(
            'create trigger trg_touch before update on %I for each row execute function touch_updated_at(%L)',
            t.tbl, t.col);
    end loop;
end $$;
