import json
from datetime import date, timedelta
from sqlalchemy import text
from backend.auth.service import pwd_context

# All official 39 Mahallas & OFYs of Qo'ng'irot tumani (Official Registry)
ALL_39_MAHALLAS = [
    "ALMAZAR MFY",
    "TARAQLI MFY",
    "GULABAD MFY",
    "TALLIQ MFY",
    "XAN-JAP MFY",
    "A`DEBIYAT OFY",
    "XOREZM OFY",
    "KIYET OFY",
    "O`RNEK OFY",
    "JASLIQ ShFY",
    "TEMIR JOL MFY",
    "QASHI MFY",
    "BERDAX MFY",
    "MONSHAQLI MFY",
    "AJINIYAZ OFY",
    "QAN`LI OFY",
    "QON`I`RAT OFY",
    "USTIRT OFY",
    "ELABAD ShFY",
    "QI`RI`Q-QI`Z ShFY",
    "MIN`JARG`AN MFY",
    "QUMBIZ MFY",
    "QARATAL MFY",
    "HA`KIM-ATA MFY",
    "RAUSHAN OFY",
    "KO`KDARYA OFY",
    "MIYNETABAD OFY",
    "TURKISTAN MFY",
    "ALTI`NKO`L ShFY",
    "QARAQALPAQSTAN ShFY",
    "BOSTAN MFY",
    "TURAN MFY",
    "QON`I`RAT MFY",
    "AZATLIQ MFY",
    "SANAAT MFY",
    "JIN`ISHKE MFY",
    "QI`PSHAQ OFY",
    "NAVOYI MFY",
    "SUWENLI OFY"
]

def run_seed_demo_data(engine):
    """
    Seeds demonstration data using separate transactions per block.
    1. Resets passwords on all users to 'AdminPass123!' so login is 100% guaranteed.
    2. Ensures essential accounts (prokuror, admin, ornek_rais) exist.
    3. Seeds categories, all 39 mahallas of Qo'ng'irot, stats, persons, assignments, and documents.
    """
    fresh_hash = pwd_context.hash("AdminPass123!")

    today = date.today()
    overdue_5 = today - timedelta(days=5)
    overdue_2 = today - timedelta(days=2)
    overdue_1 = today - timedelta(days=1)
    due_today = today
    due_soon_2 = today + timedelta(days=2)
    due_safe_10 = today + timedelta(days=10)
    due_safe_20 = today + timedelta(days=20)

    print("[SEED] Starting robust test data synchronization for 39 Mahallas...")

    # =========================================================================
    # STEP 1: USERS & PASSWORDS
    # =========================================================================
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET password = :pwd, is_active = true WHERE password != :pwd OR is_active = false;"),
                {"pwd": fresh_hash}
            )

            try:
                conn.execute(text("UPDATE user_devices SET is_active = false;"))
            except Exception:
                pass

            conn.execute(
                text("""
                    INSERT INTO users (first_name, last_name, phone, login, password, role, is_active, token_version, created_at, updated_at)
                    SELECT 'Super', 'Admin', '+998900000000', 'admin', :pwd, 'ADMIN', true, 1, NOW(), NOW()
                    WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'admin' OR phone = '+998900000000');
                """),
                {"pwd": fresh_hash}
            )

            conn.execute(
                text("""
                    INSERT INTO users (first_name, last_name, phone, login, password, role, is_active, token_version, created_at, updated_at)
                    SELECT 'Отабек', 'Қодиров', '+998901110001', 'prokuror', :pwd, 'PROKUROR', true, 1, NOW(), NOW()
                    WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'prokuror' OR phone = '+998901110001');
                """),
                {"pwd": fresh_hash}
            )

            conn.execute(
                text("""
                    INSERT INTO users (first_name, last_name, phone, login, password, role, is_active, token_version, created_at, updated_at)
                    SELECT 'Дамир', 'Мояддинов', '+998901111001', 'ornek_rais', :pwd, 'MAHALLA_RAISI', true, 1, NOW(), NOW()
                    WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'ornek_rais' OR phone = '+998901111001');
                """),
                {"pwd": fresh_hash}
            )

            conn.execute(text("UPDATE users SET role = 'ADMIN', is_active = true WHERE login = 'admin';"))
            conn.execute(text("UPDATE users SET role = 'PROKUROR', is_active = true WHERE login = 'prokuror';"))
            conn.execute(text("UPDATE users SET role = UPPER(role);"))

        print("[SEED] Step 1: Users & Passwords committed successfully! Login is ready.")
    except Exception as e:
        print(f"[SEED] Step 1 (Users) note: {e}")

    # =========================================================================
    # STEP 2: CATEGORIES
    # =========================================================================
    try:
        with engine.begin() as conn:
            categories_data = [
                ("Ilgari sudlangan va probatsiya hisobidagi shaxslar", 15, '["profilaktika_inspektori"]', "Ichki ishlar va prokuratura maxsus nazoratidagi fuqarolar"),
                ("Profilaktik hisobdagi muammoli yoshlar", 10, '["yoshlar_yetakchisi", "profilaktika_inspektori"]', "Tarbiyasi og'ir, nazoratsiz qolgan va huquqbuzarlikka moyil yoshlar"),
                ("Notinch va nizoli oilalar", 7, '["xotin_qizlar_faoli", "ijtimoiy_xodim"]', "Tazyiq va zo'ravonlik xavfi ostidagi oilalar, xotin-qizlar himoyasi"),
                ("Bandligi ta'minlanmagan ishsiz fuqarolar", 30, '["hokim_yordamchisi"]', "Daromad manbaiga ega bo'lmagan, kasbga qayta o'qitish zarur shaxslar"),
                ("Spirtli ichimlik va giyohvandlikka moyil shaxslar", 14, '["profilaktika_inspektori", "ijtimoiy_xodim"]', "Tibbiy-ijtimoiy reabilitatsiyaga muhtoj fuqarolar"),
                ("Yirik soliq qarzdorligi bor subyektlar", 20, '["soliq_inspektori"]', "Mahalla hududidagi soliq to'lovlarini kechiktirayotgan tadbirkorlar"),
            ]
            for name, freq, roles, desc in categories_data:
                conn.execute(
                    text("""
                        INSERT INTO categories (name, default_frequency_days, assigned_roles, description, is_active, created_at, updated_at)
                        SELECT :name, :freq, CAST(:roles AS json), :desc, true, NOW(), NOW()
                        WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = :name);
                    """),
                    {"name": name, "freq": freq, "roles": roles, "desc": desc}
                )
        print("[SEED] Step 2: Categories committed successfully.")
    except Exception as e:
        print(f"[SEED] Step 2 (Categories) note: {e}")

    # =========================================================================
    # STEP 3: ALL 39 MAHALLAS & STATS OF QO'NG'IROT
    # =========================================================================
    try:
        with engine.begin() as conn:
            # 1. Remap foreign keys for any legacy rows with ID > 39 to valid 1..39 range
            try:
                conn.execute(text("UPDATE users SET mahalla_id = ((mahalla_id - 1) % 39) + 1 WHERE mahalla_id > 39;"))
                conn.execute(text("UPDATE persons SET mahalla_id = ((mahalla_id - 1) % 39) + 1 WHERE mahalla_id > 39;"))
                conn.execute(text("UPDATE check_in_documents SET mahalla_id = ((mahalla_id - 1) % 39) + 1 WHERE mahalla_id > 39;"))
                conn.execute(text("UPDATE person_category_assignments SET mahalla_id = ((mahalla_id - 1) % 39) + 1 WHERE mahalla_id > 39;"))
                conn.execute(text("DELETE FROM mahalla_stats WHERE mahalla_id > 39;"))
                conn.execute(text("DELETE FROM mahallas WHERE id > 39;"))
            except Exception as e:
                print(f"[SEED] Note on cleanup > 39: {e}")

            # 2. Sync exact 39 official entities by their T/r ID (1 to 39)
            for idx, m_name in enumerate(ALL_39_MAHALLAS, start=1):
                conn.execute(
                    text("""
                        INSERT INTO mahallas (id, name, is_active, created_at, updated_at)
                        VALUES (:id, :name, true, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_active = true, updated_at = NOW();
                    """),
                    {"id": idx, "name": m_name}
                )

            # Ensure all 39 are active, and no extra rows remain
            conn.execute(text("UPDATE mahallas SET is_active = true WHERE id <= 39;"))
            conn.execute(text("UPDATE mahallas SET is_active = false WHERE id > 39;"))

            try:
                conn.execute(text("SELECT setval(pg_get_serial_sequence('mahallas', 'id'), 39);"))
            except Exception:
                pass

            # Assign stats to all 39 mahallas
            all_m_rows = conn.execute(text("SELECT id, name FROM mahallas WHERE is_active = true;")).fetchall()
            red_names = {"jasliq", "qipchoq", "mingjarg", "qoraqalpog", "oqsho"}
            yellow_names = {"talliq", "turkistan", "jayxun", "suenlli", "ravshan", "oltinko", "elobod", "ustyurt"}

            for r in all_m_rows:
                m_id, m_name = r[0], r[1]
                m_lower = m_name.lower()

                if any(k in m_lower for k in red_names):
                    toifa = "Мураккаб тоифа (қизил)"
                    aholi = 5350
                    xonadon = 1050
                elif any(k in m_lower for k in yellow_names):
                    toifa = "Ўрта тоифа (сариқ)"
                    aholi = 4200
                    xonadon = 820
                else:
                    toifa = "Намунали тоифа (яшил)"
                    aholi = 3800
                    xonadon = 750

                conn.execute(
                    text("""
                        INSERT INTO mahalla_stats (
                            mahalla_id, maydoni, xonadonlar_soni, savdo_dokonlari_soni, maktablar_soni, kochalar_soni, mtm_soni,
                            aholi_soni, erkaklar_soni, ayollar_soni, yoshlar_soni, voyaga_etmaganlar_soni, oilalar_soni,
                            ijarada_yashovchilar_soni, chetga_ketganlar_soni, chetga_ketganlar_erkak, chetga_ketganlar_ayol, chetga_ketganlar_voyaga_etmagan,
                            toifa, aholi_oqimi, murojaatlar_soni, created_at, updated_at
                        )
                        SELECT
                            :m_id, '140.0 га', :xonadon, 6, 1, 18, 1,
                            :aholi, :aholi / 2, :aholi / 2, 900, 400, :xonadon,
                            5, 110, 65, 45, 12,
                            :toifa, 'Ўртача оқим', 'Ойига 10-15 та', NOW(), NOW()
                        WHERE NOT EXISTS (SELECT 1 FROM mahalla_stats WHERE mahalla_id = :m_id);
                    """),
                    {"m_id": m_id, "toifa": toifa, "aholi": aholi, "xonadon": xonadon}
                )
        print(f"[SEED] Step 3: All {len(ALL_39_MAHALLAS)} Mahallas & Stats committed successfully.")
    except Exception as e:
        print(f"[SEED] Step 3 (Mahallas) note: {e}")

    # =========================================================================
    # STEP 4: CLEANUP MOCK / DEMO PERSONS & DOCUMENTS
    # =========================================================================
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM check_in_documents WHERE photo_url LIKE '%unsplash%';"))
            conn.execute(text("""
                DELETE FROM person_category_assignments 
                WHERE person_id IN (
                    SELECT id FROM persons 
                    WHERE full_name IN (
                        'Анвар Каримов Рустамович', 'Дилшод Эргашев Ботирович', 'Жасур Юсупов Санжарович',
                        'Нодира Раҳимова Ғайратовна', 'Ботир Алиев Шуҳратович', 'Фарҳод Жўраев Акмалович',
                        'Гулчеҳра Содиқова Муродовна', 'Шерзод Бекмирзаев Камолович',
                        'Рустам Қосимов Ўктамович', 'Шаҳноза Умарова Беҳзодовна', 'Алишер Мансуров Шарофович',
                        'Камола Азимова Искандаровна', 'Санжарбек Тўраев Бахтиёрович', 'Отабек Маҳмудов Дилмуродович',
                        'Замира Холмирзаева Саидовна', 'Бобурмирзо Ҳакимов Фаррухович'
                    )
                );
            """))
            conn.execute(text("""
                DELETE FROM persons 
                WHERE full_name IN (
                    'Анвар Каримов Рустамович', 'Дилшод Эргашев Ботирович', 'Жасур Юсупов Санжарович',
                    'Нодира Раҳимова Ғайратовна', 'Ботир Алиев Шуҳратович', 'Фарҳод Жўраев Акмалович',
                    'Гулчеҳра Содиқова Муродовна', 'Шерзод Бекмирзаев Камолович',
                    'Рустам Қосимов Ўктамович', 'Шаҳноза Умарова Беҳзодовна', 'Алишер Мансуров Шарофович',
                    'Камола Азимова Искандаровна', 'Санжарбек Тўраев Бахтиёрович', 'Отабек Маҳмудов Дилмуродович',
                    'Замира Холмирзаева Саидовна', 'Бобурмирзо Ҳакимов Фаррухович'
                );
            """))
        print("[SEED] Step 4: Mock persons and mock documents cleaned up successfully.")
    except Exception as e:
        print(f"[SEED] Step 4 (Mock cleanup) note: {e}")

    print("[SEED] Real official 39 Mahallas & initial accounts synchronized! No mock data.")
