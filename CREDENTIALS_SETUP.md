# AGÜ FCEV Multi-Agent — Credential Kurulum Rehberi

Bu rehber Sponsor ve Code cycle'larını gerçek modda çalıştırmak için ihtiyaç duyulan
3 credential'ın nasıl alınacağını adım adım açıklar.

---

## Hızlı Başlangıç

```powershell
cd C:\Users\VICTUS\OneDrive\Desktop\proje\formula-future
python setup_credentials.py
```

Bu script seni adım adım yönlendirir. Manuel yapmak istersen aşağıya bak.

---

## 1. Gmail + Google Calendar OAuth (`credentials.json` → `token.json`)

Sponsor sistemi e-posta göndermek ve takvime toplantı eklemek için
Google'ın OAuth 2.0 akışını kullanır.

### 1a. Google Cloud Console'dan credentials.json indir

1. Git: https://console.cloud.google.com/apis/credentials
2. Sol menüden projeyi seç: `formula-student-autonomus`
3. Üstte **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
4. Application type: **Desktop app**
5. Name: `AGU FCEV Agent`
6. **CREATE** → açılan pencerede **"DOWNLOAD JSON"**
7. İndirilen dosyayı şu konuma kaydet:

```
formula-future/
└── credentials/
    └── credentials.json   ← buraya
```

> **Not:** Bu dosyayı GitHub'a commit ETME — `.gitignore` engelliyor.

### 1b. API'leri Etkinleştir

Aynı Google Cloud projesinde şunları etkinleştir:

- https://console.cloud.google.com/apis/library/gmail.googleapis.com
- https://console.cloud.google.com/apis/library/calendar-json.googleapis.com

### 1c. token.json oluştur (bir kez yapılır)

```powershell
python setup_credentials.py
```

Script tarayıcı açar, Gmail + Calendar izinlerini onaylamanı ister.
Onayladıktan sonra `credentials/token.json` otomatik oluşur.

Token 7 günde bir yenilenir — otomatik yapılır, bir şey yapman gerekmez.

---

## 2. GitHub Personal Access Token (`GITHUB_TOKEN`)

Code agent GitHub'dan commit çeker ve Issue açar.

1. Git: https://github.com/settings/tokens/new
2. **Note:** `AGU FCEV Code Agent`
3. **Expiration:** 90 days
4. **Scopes:**
   - ✅ `repo` (commit okuma, issue açma)
5. **Generate token** → `ghp_...` ile başlayan token'ı kopyala

### Token'ı kalıcı olarak ayarla

**Sadece bu oturum (geçici):**
```powershell
$env:GITHUB_TOKEN = "ghp_..."
```

**Kalıcı (Windows Sistem Değişkeni):**
```powershell
[System.Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_...", "User")
```

---

## 3. Gemini API Key (`GEMINI_API_KEY`)

✅ **Zaten çalışıyor!** `AQ.Ab8...` formatındaki key AI Studio'dan alınmış ve
`gemini-2.5-flash` modeli ile test edildi.

Kalıcı yapmak için:
```powershell
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AQ.Ab8...", "User")
```

---

## 4. Tüm Değişkenlerin Özeti

| Değişken | Değer | Nereden |
|---|---|---|
| `GEMINI_API_KEY` | `AQ.Ab8...` | aistudio.google.com ✅ |
| `GITHUB_TOKEN` | `ghp_...` | github.com/settings/tokens |
| `GOOGLE_CLOUD_PROJECT` | `formula-student-autonomus` | GCP Console |
| `GOOGLE_APPLICATION_CREDENTIALS` | `credentials/service-account-key.json` | GCP → IAM → Service Accounts |

---

## 5. Doğrulama

Tüm credential'lar hazır olunca:

```powershell
# Tüm env değişkenlerini ayarla
$env:GEMINI_API_KEY = "AQ.Ab8..."
$env:GITHUB_TOKEN = "ghp_..."
$env:GOOGLE_CLOUD_PROJECT = "formula-student-autonomus"

# Sistemi gerçek modda test et
python verify_pillar3.py --mock   # mock test (her zaman çalışır)

# Sadece code agent gerçek mod (GitHub token ile)
python -c "
import os; os.environ['GITHUB_TOKEN']='ghp_...'
from agents.analysis.code_improvement_agent import analyze_autonomous_code
analyze_autonomous_code(mock=False)
"
```

---

## 6. Güvenlik Notları

> ⚠️ **ASLA şunları GitHub'a commit etme:**
> - `credentials/token.json`
> - `credentials/credentials.json`
> - `.env`
> - `credentials/service-account-key.json`

Bunlar `.gitignore` tarafından engelleniyor ama dikkatli ol.
