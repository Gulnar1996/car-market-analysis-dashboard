# Bu Python kodunun məqsədi sorğu nəticələrinə əsaslanaraq respondentlərin elektrik avtomobil (EV) almağa hazırlıq səviyyəsini və bazar davranışı üzrə klasterlərini avtomatik şəkildə hesablamadır. Kod aşağıdakı analitik funksiyaları yerinə yetirir:

# 🔹 1. Sorğu məlumatlarının təmizlənməsi

# Fayl sistemdən oxunur

# Sütun adlarında olan artıq boşluqlar silinir

# Məlumat analitik hesablama üçün standart formaya gətirilir

# Bu addım Power BI və digər analiz mərhələləri üçün dataset-i təmiz və stabil edir.

# 🔹 2. EV Readiness Score-un (0–100 bal) hesablanması

# Kod 17-ci, 19-cu, 9-cu və 7-ci suallara əsaslanaraq hər respondent üçün EV Readiness Score yaradır.
# Bal aşağıdakı faktorlarla müəyyən edilir:

# EV alma niyyəti (17-ci sual)

# EV almama baryerləri — şarj stansiyaları, akkumulyator ömrü, ilkin qiymət, servis (19-cu sual)

# Alıcı büdcəsi (9-cu sual)

# Avtomobil seçimi meyarları — yanacaq sərfiyyatı, təhlükəsizlik, qiymət və s. (7-ci sual)

# Bu model bazar reallığına və istehlakçı davranışına uyğun bal verir.

# 🔹 3. Respondentlərin klasterləşdirilməsi

# Kod hər respondentə 2 səviyyədə klaster təyin edir:

# ✔ Klaster 1 – Avtomobil sahibləri
# ✔ Klaster 2 – Avtomobili olmayan potensial alıcılar
# ✔ Klaster 3 – EV-yə yüksək hazır olanlar (EV score ≥ 70)

# Bu klasterlər bazarda alıcı seqmentlərini aydın şəkildə ayırmağa imkan verir.

# 🔹 4. Analiz üçün yeni, təmiz Excel faylının yaradılması

# Kod bütün hesablamaları tamamladıqdan sonra:

# EV_Readiness_Score

# Klaster_basic

# EV_segment

# Klaster_final

# kimi əlavə sütunlarla birlikdə yeni dataset formalaşdırır və nəticəni Excel faylı kimi yadda saxlayır.

# Bu fayl sonradan Power BI dashboard, vizuallar və analitik hesabat üçün hazır olur.

# ⭐ Nəticə

# Bu kod sorğu məlumatlarını xam vəziyyətdən çıxarıb:

# təmizlənmiş

# modelləşdirilmiş

# seqmentləşdirilmiş

# təhlilə hazır

# profesional analitik dataset yaradır.



import pandas as pd

# 1) GİRİŞ FAYLI – SƏNİN GÖNDƏRDİYİN TAM YOL
file_name = r"C:\Users\Admin\Desktop\Car data\Azərbaycan Avtomobil Bazarında Alıcı Seçimləri və Bazar Trendlərinin Analizi.xlsx"

df = pd.read_excel(file_name)

# Sütun adlarının sonundakı boşluqları təmizləyək
df.columns = [c.strip() for c in df.columns]

# Sənin başlıqlara uyğun sütun adları:
COL_HAS_CAR   = "4. Hal-hazırda şəxsi avtomobiliniz varmı?"
COL_REASON_EV = "19. Elektrik avtomobil almasaydınız, bunun əsas səbəbləri nələr olardı?"
COL_EV_INTENT = "17. Elektrik avtomobil almağı düşünürsünüzmü?"
COL_BUDGET    = "9. Yeni avtomobil alışı üçün münasib hesab etdiyiniz qiymət aralığı hansıdır?"
COL_CRITERIA  = "7. Yeni avtomobil alarkən sizin üçün ən vacib üç amil hansılardır?"

def norm(s: str) -> str:
    return s.strip() if isinstance(s, str) else ""

# 2) EV READINESS SCORE FUNKSİYASI

def compute_ev_score(row):
    score = 0

    # ---- 17-ci sual: EV alma niyyəti ----
    ev = norm(row.get(COL_EV_INTENT, ""))

    if "Artıq sahibəm" in ev:
        score += 100
    elif "Bəli, yaxın illərdə planlaşdırıram" in ev and "Bəli, amma qiymət əlverişli olarsa" in ev:
        score += 85
    elif "Bəli, yaxın illərdə planlaşdırıram" in ev:
        score += 80
    elif "Bəli, amma qiymət əlverişli olarsa" in ev:
        score += 70
    elif "Xeyr, hələ düşünmürəm" in ev:
        score += 10
    elif "Digər" in ev:
        score += 40
    else:
        score += 40  # neytral default

    # ---- 19-cu sual: EV almamaq səbəbləri ----
    reasons = norm(row.get(COL_REASON_EV, ""))

    if "Şarj stansiyalarının çatışmazlığı" in reasons:
        score -= 15
    if "Akkumulyator ömrü ilə bağlı narahatlıq" in reasons:
        score -= 15
    if "Yüksək ilkin qiymət" in reasons:
        score -= 10
    if "Servis sisteminin zəifliyi" in reasons:
        score -= 10
    if "Etibarlılıq problemi" in reasons:
        score -= 5
    if "Bu problemlərin heç biri məni narahat etmir" in reasons:
        score += 20

    # ---- 9-cu sual: Büdcə ----
    budget = norm(row.get(COL_BUDGET, ""))

    if "70 000 AZN və yuxarı" in budget:
        score += 20
    elif "40 000–70 000 AZN" in budget:
        score += 15
    elif "20 000–40 000 AZN" in budget:
        score += 10
    elif "10 000–20 000 AZN" in budget:
        score += 0
    elif "10 000 AZN-dən az" in budget:
        score -= 5

    # ---- 7-ci sual: Seçim meyarları ----
    crit = norm(row.get(COL_CRITERIA, ""))

    if "Yanacaq sərfiyyatı" in crit:
        score += 10
    if "Texnologiya və təhlükəsizlik" in crit:
        score += 5
    if "Qiymət və əlçatanlıq" in crit:
        score -= 5
    if "Ehtiyat hissələrinin qiyməti" in crit:
        score -= 5

    # 0–100 aralığına salaq
    score = max(0, min(100, score))
    return score

# 3) EV SCORE SÜTUNU YARAT
df["EV_Readiness_Score"] = df.apply(compute_ev_score, axis=1)

# 4) KLASTERLƏR

def assign_basic_cluster(row):
    has_car = norm(row.get(COL_HAS_CAR, "")).lower()
    if "bəli" in has_car:
        return "Klaster 1 - Avtomobil sahibidir"
    elif "xeyr" in has_car:
        return "Klaster 2 - Potensial alıcı"
    else:
        return "Klaster 0 - Naməlum"

df["Klaster_basic"] = df.apply(assign_basic_cluster, axis=1)

def assign_ev_segment(score):
    if score >= 70:
        return "EV-yə yüksək hazırdır"
    elif score >= 40:
        return "EV-yə orta hazırdır"
    else:
        return "EV-yə hazır deyil"

df["EV_segment"] = df["EV_Readiness_Score"].apply(assign_ev_segment)

def assign_final_cluster(row):
    score = row["EV_Readiness_Score"]
    if score >= 70:
        return "Klaster 3 - EV-yə ən yaxın alıcılar"
    else:
        return row["Klaster_basic"]

df["Klaster_final"] = df.apply(assign_final_cluster, axis=1)

# 5) ÇIXIŞ FAYLI – EYNİ QOVLUĞA YAZIRIQ
output_file = r"C:\Users\Admin\Desktop\Car data\Azerbaycan_Avtomobil_Bazari_EV_Klaster_FINAL_DUZGUN.xlsx"
df.to_excel(output_file, index=False)

print("Hazırdır! Yeni fayl yaradıldı:", output_file)
