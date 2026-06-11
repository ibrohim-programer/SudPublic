# api/endpoints.py — URL va konstantalar
# SudParser v3.0 | publication.sud.uz REST API

BASE_URL = "https://publication.sud.uz"

PUBLICATIONS_URL = f"{BASE_URL}/unauthorized/publications"
TYPES_URL = f"{BASE_URL}/unauthorized/types"
CATEGORY_URL = f"{BASE_URL}/unauthorized/category"
FILE_URL = f"{BASE_URL}/api/file/download/{{file_id}}"

# Sud yo'nalishlari (court_type qiymatlari)
COURT_TYPES: dict[str, str] = {
    "ECONOMIC":               "Iqtisodiy sudlar (2024 dan keyin)",
    "ECONOMIC_OLD":           "Iqtisodiy sudlar (2024 gacha)",
    "ADMINISTRATIVE":         "Ma'muriy sudlar",
    "CIVIL":                  "Fuqarolik ishlari",
    "CRIMINAL":               "Jinoyat ishlari",
    "ADMINISTRATIVE_OFFENCE": "Ma'muriy huquqbuzarlik",
}

# Papka nomlari (court_type → papka)
COURT_FOLDERS: dict[str, str] = {
    "ECONOMIC":               "Iqtisodiy_Sudlar/2024_dan_keyin",
    "ECONOMIC_OLD":           "Iqtisodiy_Sudlar/2024_gacha",
    "ADMINISTRATIVE":         "Mamuriy_Sudlar",
    "CIVIL":                  "Fuqarolik_Ishlari",
    "CRIMINAL":               "Jinoyat_Ishlari",
    "ADMINISTRATIVE_OFFENCE": "Mamuriy_Huquqbuzarlik",
}

# Instansiya turlari
INSTANCE_TYPES: dict[str, str] = {
    "":          "Barchasi",
    "FIRST":     "Birinchi instansiya",
    "APPEAL":    "Apellatsiya",
    "CASSATION": "Kassatsiya",
}

# Hujjat turi standart ro'yxat (API dan ham yangilanadi)
DEFAULT_DOC_TYPES: list[dict] = [
    {"id": 0,    "name": "Barchasi"},
    {"id": 4,    "name": "Ҳал қилув қарори"},
    {"id": 5,    "name": "Ажрим (даъводан қолдириш)"},
    {"id": 6,    "name": "Ажрим (ишни тугатиш)"},
    {"id": 7,    "name": "Қарор"},
    {"id": 2298, "name": "Ижрочи рўйхат ҳақида ажрим"},
    {"id": 2441, "name": "Ажрим (мировой)"},
]

# Ish natijasi (result) kodlari → o'zbekcha izoh (jadvalda ko'rsatish uchun)
RESULT_LABELS: dict[str, str] = {
    "FULFILLED":                   "Qanoatlantirilgan",
    "PARTIALLY_FULFILLED":         "Qisman qanoatlantirilgan",
    "REFUSED":                     "Rad etilgan",
    "UNCONSIDERED":                "Ko'rmasdan qoldirilgan",
    "BANKRUPT":                    "Bankrot deb topilgan",
    "STOPPED":                     "Ish tugatilgan",
    "AGREEMENT":                   "Yarashuv bitimi",
    "APPEAL_UNCHANGED":            "Apellyatsiya: o'zgarishsiz",
    "APPEAL_CHANGED":              "Apellyatsiya: o'zgartirilgan",
    "APPEAL_STOPPED":              "Apellyatsiya: tugatilgan",
    "APPEAL_CANCELLED_REFUSED":    "Apellyatsiya: bekor (rad)",
    "APPEAL_CANCELLED_FULFILLED":  "Apellyatsiya: bekor (qanoat)",
    "APPEAL_CANCELLED_STOPPED":    "Apellyatsiya: bekor (tugatilgan)",
    "APPEAL_CANCELLED_AGREEMENT":  "Apellyatsiya: bekor (yarashuv)",
    "CASSATION_RETURNED":          "Kassatsiya: qaytarilgan",
    "CASSATION_UNCHANGED":         "Kassatsiya: o'zgarishsiz",
    "CASSATION_CHANGED":           "Kassatsiya: o'zgartirilgan",
    "CONTROL_PROTEST_FULFILLED":   "Nazorat: protest qanoatlantirildi",
}


def result_label(code) -> str:
    """Result kodini o'zbekcha izohga aylantirish (topilmasa kodning o'zi)."""
    if not code:
        return ""
    return RESULT_LABELS.get(str(code), str(code))