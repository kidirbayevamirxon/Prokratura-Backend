-- ==============================================================================
-- Database Reset & Seed Script: Ўрнек ОФЙ (Qo'ng'irot tumani)
-- Self-contained DDL + DML: Works on both clean and existing databases
-- Frequency: No default frequency attached to assignments (frequency_days = NULL)
-- ==============================================================================
BEGIN;

-- 1. Create Tables and Indexes IF NOT EXISTS
CREATE TABLE IF NOT EXISTS mahallas (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT 't' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS mahalla_stats (
    id BIGSERIAL PRIMARY KEY,
    mahalla_id BIGINT NOT NULL REFERENCES mahallas (id) ON DELETE CASCADE,
    maydoni VARCHAR(100),
    xonadonlar_soni INTEGER,
    savdo_dokonlari_soni INTEGER,
    maktablar_soni INTEGER,
    kochalar_soni INTEGER,
    mtm_soni INTEGER,
    aholi_soni INTEGER,
    erkaklar_soni INTEGER,
    ayollar_soni INTEGER,
    yoshlar_soni INTEGER,
    voyaga_etmaganlar_soni INTEGER,
    oilalar_soni INTEGER,
    ijarada_yashovchilar_soni INTEGER,
    chetga_ketganlar_soni INTEGER,
    chetga_ketganlar_erkak INTEGER,
    chetga_ketganlar_ayol INTEGER,
    chetga_ketganlar_voyaga_etmagan INTEGER,
    toifa VARCHAR(255),
    aholi_oqimi VARCHAR(255),
    murojaatlar_soni VARCHAR(255),
    extra_data JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    icon_url VARCHAR(500),
    description VARCHAR(1000),
    assigned_roles JSON NOT NULL,
    default_frequency_days INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 't' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    phone VARCHAR NOT NULL,
    login VARCHAR,
    password VARCHAR,
    role VARCHAR(23) NOT NULL,
    is_active BOOLEAN DEFAULT 't' NOT NULL,
    token_version INTEGER DEFAULT '1' NOT NULL,
    mahalla_id BIGINT REFERENCES mahallas (id) ON DELETE SET NULL,
    photo_url VARCHAR(500),
    birth_date_text VARCHAR(100),
    appointed_date_text VARCHAR(255),
    specialization VARCHAR(255),
    previous_workplace VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS persons (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    birth_date DATE NOT NULL,
    mahalla_id BIGINT NOT NULL REFERENCES mahallas (id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT 't' NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS person_category_assignments (
    id BIGSERIAL PRIMARY KEY,
    person_id BIGINT NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    mahalla_id BIGINT NOT NULL REFERENCES mahallas (id) ON DELETE CASCADE,
    frequency_days INTEGER,
    assigned_roles JSON,
    next_check_in_due DATE,
    status VARCHAR(9) NOT NULL,
    created_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS user_devices (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    device_name VARCHAR(255),
    credential_id VARCHAR(500) NOT NULL,
    public_key TEXT NOT NULL,
    sign_count BIGINT DEFAULT '0' NOT NULL,
    aaguid VARCHAR(64),
    is_active BOOLEAN DEFAULT 't' NOT NULL,
    user_agent VARCHAR(500),
    last_ip VARCHAR(64),
    registered_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    last_login_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE IF NOT EXISTS check_in_documents (
    id BIGSERIAL PRIMARY KEY,
    assignment_id BIGINT NOT NULL REFERENCES person_category_assignments (id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES persons (id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    mahalla_id BIGINT NOT NULL REFERENCES mahallas (id) ON DELETE CASCADE,
    submitted_by_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    doc_type VARCHAR(50) NOT NULL,
    photo_url VARCHAR(500) NOT NULL,
    pdf_url VARCHAR(500),
    notes TEXT,
    check_in_date DATE NOT NULL,
    due_date DATE,
    previous_date DATE,
    requested_date DATE,
    new_date DATE,
    frequency_days INTEGER,
    status VARCHAR(8) NOT NULL,
    rejection_reason TEXT,
    reviewed_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    seen_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    seen_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS document_messages (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES check_in_documents (id) ON DELETE CASCADE,
    sender_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    requested_date DATE,
    granted_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_name ON categories (name);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_login ON users (login);
CREATE INDEX IF NOT EXISTS ix_users_mahalla_id ON users (mahalla_id);
CREATE INDEX IF NOT EXISTS ix_persons_full_name ON persons (full_name);
CREATE INDEX IF NOT EXISTS ix_persons_mahalla_id ON persons (mahalla_id);
CREATE INDEX IF NOT EXISTS ix_person_category_assignments_person_id ON person_category_assignments (person_id);
CREATE INDEX IF NOT EXISTS ix_person_category_assignments_category_id ON person_category_assignments (category_id);
CREATE INDEX IF NOT EXISTS ix_person_category_assignments_mahalla_id ON person_category_assignments (mahalla_id);
CREATE INDEX IF NOT EXISTS ix_person_category_assignments_next_check_in_due ON person_category_assignments (next_check_in_due);
CREATE UNIQUE INDEX IF NOT EXISTS ix_mahalla_stats_mahalla_id ON mahalla_stats (mahalla_id);

-- 2. Clean existing tables and restart identity sequences
TRUNCATE TABLE user_devices, document_messages, check_in_documents, person_category_assignments, persons, categories, mahalla_stats, users, mahallas RESTART IDENTITY CASCADE;

-- 3. Insert Mahalla
INSERT INTO mahallas (id, name, is_active, created_at, updated_at) VALUES (1, 'Ўрнек ОФЙ', true, NOW(), NOW());
SELECT setval('mahallas_id_seq', 1);

-- 4. Insert Mahalla Stats (Slide 2 & Slide 3)
INSERT INTO mahalla_stats (
    id, mahalla_id, maydoni, xonadonlar_soni, savdo_dokonlari_soni, maktablar_soni, kochalar_soni, mtm_soni,
    aholi_soni, erkaklar_soni, ayollar_soni, yoshlar_soni, voyaga_etmaganlar_soni, oilalar_soni,
    ijarada_yashovchilar_soni, chetga_ketganlar_soni, chetga_ketganlar_erkak, chetga_ketganlar_ayol, chetga_ketganlar_voyaga_etmagan,
    toifa, aholi_oqimi, murojaatlar_soni, extra_data, created_at, updated_at
) VALUES (
    1, 1, '141.45 га', 1006, 6, 1, 19, 1,
    5351, 2663, 2688, 921, 418, 1415,
    6, 118, 69, 47, 14,
    'Мураккаб тоифа (2 йилдан бери яшил тоифада)',
    'Аҳоли оқими паст (кунлик ўртача 10-15 киши)',
    'Мурожаатлар сони кам (ойига ўртача 14-16 та. йиллик 155-160 та)',
    '{"tuman": "Қўнғирот тумани", "bino_tavsifi": "Маҳалла биносининг умумий кўриниши мавжуд", "jalb_etilgan_kuchlar": ["Ж.М.Реймов - Орнек ОФЙга масъул", "А.О.Калиев - Орнек гузари", "С.М.Сарсенбаев - Ўатанлас (Профилактика инспектори)", "М.Қулбаев - ЙПХ"], "obektlar": ["Динар Ресторани мавжуд", "Маҳаллага кириш-чиқиш жойлари", "Маҳалла аҳолиси тўлиқ участка ҳовлиларда истиқомат қилади"], "chora_tadbirlar": ["Криминоген вазиятга салбий таъсир кўрсатувчи объектлар мавжуд эмас", "Куч ва воситаlar қайтадан тақсимланди, аниқ вазифалар белгиланди", "Кунлик амалга оширилган ишлар назоратга олинди", "Мурожаатларга тезкорлик билан муносабат билдирилди"]}'::json,
    NOW(), NOW()
);
SELECT setval('mahalla_stats_id_seq', 1);

-- 5. Insert System Users & Mahalla Yettiligi (Slide 1)
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (1, 'Super', 'Admin', '+998900000000', 'admin', '$2b$12$xCRf/Tl.jf25A9ZEVNte.eegiE83kpcqDol9zImijqXEk/vhlhP4W', 'ADMIN', true, 1, NULL, NULL, NULL, NULL, NULL, NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (2, 'Туман', 'Прокурори', '+998901110001', 'prokuror', '$2b$12$ubHbAyYqmzc55oxwBDY.6uRCc09JUmvyMu4n62E30OfC3pr/k5Sxm', 'PROKUROR', true, 1, NULL, NULL, NULL, NULL, NULL, NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (3, 'Дамир', 'Мояддинов', '+998901111001', 'ornek_rais', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'MAHALLA_RAISI', true, 1, 1, '1991 йил', '2025 йил 10-май ойидан буён', 'Инженер механик', 'Тарақли МФЙ Ёшlar етакчиси', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (4, 'Шерали', 'Ншанбаев', '+998901111002', 'ornek_hokim', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'HOKIM_YORDAMCHISI', true, 1, 1, '1998 йил', '2024 йил 27-июн ойидан буён', 'Нефт ва нефт газни кайта ишлаш', 'Алмазар МФЙ Ёшлар етакчиси', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (5, 'Азиз', 'Узаков', '+998901111003', 'ornek_yoshlar', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'YOSHLAR_YETAKCHISI', true, 1, 1, '1996 йил', '2024 йил 24-ноябрь ойидан буён', 'Нефт ва нефт газни кайта ишлаш', 'Қўнғирот сода заводи', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (6, 'Зияда', 'Айтекова', '+998901111004', 'ornek_xotinqizlar', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'XOTIN_QIZLAR_FAOLI', true, 1, 1, '1966 йил', '2018 йилдан буён', 'бухгалтерия', 'Орнек ОФЙ Хотин-қизлар фаоли', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (7, 'Саламат', 'Пахраддинов', '+998901111005', 'ornek_profilaktika', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'PROFILAKTIKA_INSPEKTORI', true, 1, 1, '1993 йил', '2024 йил 28-декабрь ойидан буён', 'Тарих', 'Кинология', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (8, 'Ислам', 'Сейтимуратов', '+998901111006', 'ornek_soliq', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'SOLIQ_INSPEKTORI', true, 1, 1, '1994 йил', '2026 йил 5-март ойидан буён', 'молия', 'Солиқ инспекцияси', NOW(), NOW());
INSERT INTO users (id, first_name, last_name, phone, login, password, role, is_active, token_version, mahalla_id, birth_date_text, appointed_date_text, specialization, previous_workplace, created_at, updated_at)
VALUES (9, 'Гулмира', 'Жуманиязова', '+998901111007', 'ornek_ijtimoiy', '$2b$12$rQI9coulMDkXMASFmStHu.2yt5sSepAS1psWrBjwx2ItASkrrVBp2', 'IJTIMOIY_XODIM', true, 1, 1, '1992 йил', '2024 йил 25-ноябрь ойидан буён', 'Агрокимё ва тупроқшунослик', 'Киет ОФЙ Хотин-қизлар фаоли', NOW(), NOW());
SELECT setval('users_id_seq', 9);

-- 6. Insert Categories (Slide 4 & Slide 5)
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (1, 'Ажрашиб ота-онаси ёки қариндошлари билан яшаётган аёллар рўйхати', 'Ажрашиб ота-онаси ёки қариндошлари билан яшаётган аёллар рўйхати', '["xotin_qizlar_faoli"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (2, 'Ажрим ёқасига келиб қолган ва низоли оилалар рўйхати', 'Ажрим ёқасига келиб қолган ва низоли оилалар рўйхати', '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (3, 'Ёрдамга муҳтож бўлган ва оғир ижтимоий аҳволга тушиб қолган хотин-қизлар рўйхати', 'Ёрдамга муҳтож бўлган ва оғир ижтимоий аҳволга тушиб қолган хотин-қизлар рўйхати', '["xotin_qizlar_faoli", "ijtimoiy_xodim"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (4, 'Мунтазам тазйиқ ва зўравонликка учраб келаётган хотин-қизлар рўйхати', 'Мунтазам тазйиқ ва зўравонликка учраб келаётган хотин-қизлар рўйхати', '["xotin_qizlar_faoli", "profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (5, 'Ота-онаси узоқ муддатга кетган васий ҳомий тайинланганлар рўйхати', 'Ота-онаси узоқ муддатга кетган васий ҳомий тайинланганлар рўйхати', '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (6, 'Муқаддам судланганлар рўйхати', 'Муқаддам судланганлар рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (7, 'Ғайриижтимоий хулқ-атворли шахслар рўйхати', 'Ғайриижтимоий хулқ-атворли шахслар рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (8, 'Проф хисоб рўйхати', 'Проф хисоб рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (9, 'Пробация ҳисобидагилар рўйхати', 'Пробация ҳисобидагилар рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (10, 'Судларда низолашаётган оилалар рўйхати', 'Судларда низолашаётган оилалар рўйхати', '["mahalla_raisi", "xotin_qizlar_faoli"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (11, 'Боқувчиси бўлмаган ёлғиз яшовчи аёллар рўйхати', 'Боқувчиси бўлмаган ёлғиз яшовчи аёллар рўйхати', '["ijtimoiy_xodim", "xotin_qizlar_faoli"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (12, 'Турмуш ўртоғи узоқ муддатга кетган шахслар сони (келинчак) рўйхати', 'Турмуш ўртоғи узоқ муддатга кетган шахслар сони (келинчак) рўйхати', '["xotin_qizlar_faoli"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (13, 'Никохсиз яшаётганлар рўйхати', 'Никохсиз яшаётганлар рўйхати', '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (14, 'Мулкини каровсиз колдирувчилар рўйхати', 'Мулкини каровсиз колдирувчилар рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
INSERT INTO categories (id, name, description, assigned_roles, default_frequency_days, is_active, created_at, updated_at)
VALUES (15, 'Чорва молларини каровсиз колдирадиганлар рўйхати', 'Чорва молларини каровсиз колдирадиганлар рўйхати', '["profilaktika_inspektori"]'::json, 7, true, NOW(), NOW());
SELECT setval('categories_id_seq', 15);

-- 7. Insert Persons (Unique individuals across categories)
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (1, 'Мнажатдинова Тазагул Аширбаевна', '1993-01-01', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (2, 'Ембергенова Сапаргул Оралбаевна', '1995-07-21', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (3, 'Усерова Умида Куандиковна', '1994-11-26', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (4, 'Усерова Сарбиноз Абдурашид қизи', '1997-05-25', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (5, 'Боранова Гулшад Асеновна', '1983-02-28', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (6, 'Гайпназарова Шохназа Адилхановна', '1992-02-08', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (7, 'Сарибаева Гоззал Раушанбековна', '1996-08-05', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (8, 'Қасимова Нилуфар Муратбай қизи', '1998-02-09', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (9, 'Абдуллаева Нодира Абдуллаевна', '1989-08-29', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (10, 'Алланиязова Қутлибике Жалгашбаевна', '1986-12-18', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (11, 'Жуманиязова Эльмира Отепбаевна', '1985-10-18', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (12, 'Қалмурзаева Гулзар Абдреймовна', '1985-07-05', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (13, 'Худайбергенов Ғуламжан Ешмуратович', '1985-08-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (14, 'Сапарова Гоззал Кунградбаевна', '1989-06-01', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (15, 'Торебаев Санжарбек Мадетович', '1982-12-10', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (16, 'Аллаярова Дилфуза Насраддиновна', '1983-01-12', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (17, 'Бекбаева Бахит Машариповна', '1971-04-29', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (18, 'Қонгиратбаева Баян Елиусиновна', '1969-05-02', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (19, 'Жуманиязова Базаргул Каримовна', '1967-03-27', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (20, 'Қалмуратова Мадина Парахат қизи', '2014-09-24', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (21, 'Қалмуратов Мадияр Параҳат ўғли', '2017-01-13', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (22, 'Амангелдиева Меҳрибону Руфат қизи', '2019-12-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (23, 'Амангелдиев Сардорбек Руфат ўғли', '2014-10-09', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (24, 'Амангелдиева Зияда Руфат қизи', '2019-12-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (25, 'Кенгешбаева Халида Азаматовна', '2012-03-30', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (26, 'Кенгешбаев Исламбек Азаматович', '2015-12-03', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (27, 'Кенгешбаев Алибек Азаматович', '2020-04-13', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (28, 'Илдаров Демир Рамилович', '2016-08-18', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (29, 'Илдаров Давлатбек Рамилович', '2019-12-29', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (30, 'Илдаров Данил Рамил ўғли', '2025-12-26', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (31, 'Кенжеали Ерлан Сарсенбай ули', '2012-12-01', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (32, 'Абдуллаев Наврўзбек Хайрулла ўғли', '2009-03-20', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (33, 'Абдуллаева Нилуфар Хайруллаевна', '2013-06-11', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (34, 'Абдуллаев Лазизжон Хайрулла ўғли', '2022-11-09', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (35, 'Фархадбаев Шоҳруҳ Ислам ули', '2015-05-17', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (36, 'Фархадбаев Фарруҳ Ислам ули', '2016-06-28', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (37, 'Уринбаева Фарангиз Палуан қизи', '2017-01-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (38, 'Матирзаева Наргиза Назарбаевна', '1985-09-23', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (39, 'Ургенчбаев Қууатбай Абдивалиевич', '1967-10-27', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (40, 'Мубараков Жамшид Қурал ўғли', '2000-02-12', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (41, 'Ешмуратов Қадирбай Назарбаевич', '1979-12-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (42, 'Жумамуратов Беҳруз Рашид ўғли', '2008-12-07', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (43, 'Исаков Атабек Махмуд улы', '2001-01-09', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (44, 'Даулетбаев Айдос Муратбаевич', '1990-07-30', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (45, 'Қалниязов Толепберген Жаббарбергенович', '1991-06-28', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (46, 'Умиров Саатбай Сабирович', '1969-07-26', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (47, 'Утемуратов Камал Азат ули', '1996-02-29', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (48, 'Кенжебаев Даулетбай Умирбай ули', '1998-04-01', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (49, 'Усманов Бегзод Латипович', '2004-02-02', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (50, 'Машерипов Саламат Машерипович', '1993-07-25', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (51, 'Османов Адилбек Айбекович', '1993-07-11', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (52, 'Реймбаев Шарофат Муратбаевич', '1994-05-07', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (53, 'Боранов Уктам Кобеевич', '1975-11-24', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (54, 'Саклапов Журабек Мэлс ули', '2001-06-14', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (55, 'Якупбаева Гулчехра Кадирбай қизи', '2004-07-23', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (56, 'Юсупбаева Лолагул Мадияровна', '1961-05-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (57, 'Юлдашова Авадан ХХХ', '1959-09-02', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (58, 'Балымбетова Базаргул Артыкбаевна', '1981-08-16', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (59, 'Юсупова Шахноза Қуанишбаевна', '1989-05-09', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (60, 'Алламуратова Ауезжан Тангирбергеновна', '1972-09-23', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (61, 'Ургенчбаев Бахтжан Абдивалиевич', '1976-01-29', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (62, 'Ешмуратов Байрамбай Назарбаевич', '1974-05-01', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (63, 'Нуримбетов Шарапат Сейтмуратович', '1978-01-05', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (64, 'Сабуров Алимжан Полатович', '1964-05-31', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (65, 'Яхшимуратов Фарид Аширбаевич', '1976-08-11', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (66, 'Ильясов Кунградбай Тореевич', '1963-09-18', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (67, 'Джуманиязов Отепбай Режепович', '1962-07-06', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (68, 'Баймуратов Жиенбай Килишбаевич', '1965-12-17', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (69, 'Алламбергенов Махсет Турсынбайевич', '1986-09-12', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (70, 'Зиваддинов Улугбек Муратбаевич', '1977-07-27', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (71, 'Тлеумаратов Оразбай ХХХ', '1948-08-17', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (72, 'Данияров Гафур Бахтиярович', '1979-02-04', 1, true, NOW(), NOW());
INSERT INTO persons (id, full_name, birth_date, mahalla_id, is_active, created_at, updated_at)
VALUES (73, 'Данияров Уктам Хайдарович', '1980-09-04', 1, true, NOW(), NOW());
SELECT setval('persons_id_seq', 73);

-- 8. Insert Person-Category Assignments (Without preset frequency or deadline)
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (1, 1, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (2, 2, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (3, 3, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (4, 4, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (5, 5, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (6, 6, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (7, 7, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (8, 8, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (9, 9, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (10, 10, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (11, 11, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (12, 12, 1, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (13, 13, 2, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (14, 14, 2, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (15, 15, 2, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (16, 16, 2, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (17, 17, 3, 1, NULL, '["xotin_qizlar_faoli", "ijtimoiy_xodim"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (18, 18, 3, 1, NULL, '["xotin_qizlar_faoli", "ijtimoiy_xodim"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (19, 19, 3, 1, NULL, '["xotin_qizlar_faoli", "ijtimoiy_xodim"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (20, 14, 4, 1, NULL, '["xotin_qizlar_faoli", "profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (21, 16, 4, 1, NULL, '["xotin_qizlar_faoli", "profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (22, 20, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (23, 21, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (24, 22, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (25, 23, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (26, 24, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (27, 25, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (28, 26, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (29, 27, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (30, 28, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (31, 29, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (32, 30, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (33, 31, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (34, 32, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (35, 33, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (36, 34, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (37, 35, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (38, 36, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (39, 37, 5, 1, NULL, '["ijtimoiy_xodim", "yoshlar_yetakchisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (40, 38, 6, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (41, 39, 6, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (42, 39, 7, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (43, 40, 7, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (44, 41, 7, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (45, 42, 7, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (46, 43, 7, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (47, 44, 8, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (48, 45, 8, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (49, 46, 8, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (50, 47, 8, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (51, 48, 8, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (52, 38, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (53, 49, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (54, 50, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (55, 51, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (56, 52, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (57, 53, 9, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (58, 54, 10, 1, NULL, '["mahalla_raisi", "xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (59, 55, 10, 1, NULL, '["mahalla_raisi", "xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (60, 56, 11, 1, NULL, '["ijtimoiy_xodim", "xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (61, 57, 11, 1, NULL, '["ijtimoiy_xodim", "xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (62, 58, 12, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (63, 59, 12, 1, NULL, '["xotin_qizlar_faoli"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (64, 60, 13, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (65, 61, 13, 1, NULL, '["xotin_qizlar_faoli", "mahalla_raisi"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (66, 62, 14, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (67, 63, 14, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (68, 64, 14, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (69, 65, 14, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (70, 66, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (71, 67, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (72, 68, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (73, 69, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (74, 70, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (75, 71, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (76, 72, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
INSERT INTO person_category_assignments (id, person_id, category_id, mahalla_id, frequency_days, assigned_roles, next_check_in_due, status, created_by_id, created_at, updated_at)
VALUES (77, 73, 15, 1, NULL, '["profilaktika_inspektori"]'::json, NULL, 'ACTIVE', 1, NOW(), NOW());
SELECT setval('person_category_assignments_id_seq', 77);

COMMIT;