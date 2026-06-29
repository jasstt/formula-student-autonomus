"""
setup_credentials.py
====================
AGU FCEV Multi-Agent Sistemi için credential kurulum scripti.
Sirayla Gmail, Calendar ve GitHub credential'larini ayarlar.

Kullanim:
    python setup_credentials.py
"""
import os
import sys
import json
import webbrowser

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
CREDS_DIR = os.path.join(ROOT, "credentials")
CREDS_JSON = os.path.join(CREDS_DIR, "credentials.json")
TOKEN_JSON = os.path.join(CREDS_DIR, "token.json")
ENV_FILE = os.path.join(ROOT, ".env")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
]

SEP = "=" * 60

def step(n, title):
    print(f"\n{SEP}")
    print(f"  ADIM {n}: {title}")
    print(SEP)

def check_mark(ok):
    return "[OK]" if ok else "[EKSIK]"

# ─────────────────────────────────────────────
# ADIM 0: Mevcut durum kontrol
# ─────────────────────────────────────────────
def check_status():
    step(0, "Mevcut Credential Durumu")
    items = {
        "credentials.json (Google OAuth)": os.path.exists(CREDS_JSON),
        "token.json (Google Auth Token)":  os.path.exists(TOKEN_JSON),
        "GITHUB_TOKEN env var":            bool(os.getenv("GITHUB_TOKEN")),
        "GEMINI_API_KEY env var":          bool(os.getenv("GEMINI_API_KEY")),
        "GOOGLE_CLOUD_PROJECT env var":    bool(os.getenv("GOOGLE_CLOUD_PROJECT")),
    }
    all_ok = True
    for name, ok in items.items():
        print(f"  {check_mark(ok)}  {name}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n  Tum credential'lar mevcut! Sistemi canliya alabilirsiniz.")
    return items

# ─────────────────────────────────────────────
# ADIM 1: Gmail + Calendar OAuth (credentials.json)
# ─────────────────────────────────────────────
def setup_google_oauth():
    step(1, "Gmail + Calendar OAuth — credentials.json")

    if os.path.exists(CREDS_JSON):
        print("  [OK] credentials.json zaten mevcut, atlaniyor.")
        return True

    print("""
  credentials.json olmadan Gmail ve Calendar API kullanilemiyor.
  Su adimlari izle:

  1. Tarayicida Google Cloud Console acilacak:
     https://console.cloud.google.com/apis/credentials

  2. Proje sec: formula-student-autonomus (veya mevcut projen)

  3. Ustte "+ CREATE CREDENTIALS" → "OAuth client ID" tikla

  4. Application type: "Desktop app" sec

  5. Name: "AGU FCEV Agent" yaz → CREATE

  6. Cikan pencerede "DOWNLOAD JSON" butonuna tikla

  7. Indirilen dosyayi sunuraya kaydet:
""")
    print(f"     {CREDS_JSON}")
    print("""
  Dosyayi kaydettikten sonra bu scripti tekrar calistir.
""")
    open_browser = input("  Tarayiciyi simdi acayim mi? (e/h): ").strip().lower()
    if open_browser == "e":
        webbrowser.open("https://console.cloud.google.com/apis/credentials")

    input("\n  credentials.json dosyasini kaydedince Enter'a bas...")

    if os.path.exists(CREDS_JSON):
        print("  [OK] credentials.json bulundu!")
        return True
    else:
        print("  [HATA] credentials.json hala bulunamadi. Dosyayi dogru konuma kaydettiginizden emin olun.")
        return False

# ─────────────────────────────────────────────
# ADIM 2: OAuth Token al (token.json)
# ─────────────────────────────────────────────
def setup_gmail_token():
    step(2, "Gmail + Calendar Token — token.json")

    if os.path.exists(TOKEN_JSON):
        print("  [OK] token.json zaten mevcut, atlaniyor.")
        return True

    if not os.path.exists(CREDS_JSON):
        print("  [HATA] Once credentials.json gerekli (Adim 1).")
        return False

    print("  Tarayicida Google hesabina giris yapmaniz istenecek.")
    print("  Gmail ve Calendar izinlerini onaylayin.\n")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_JSON, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_JSON, "w") as f:
            f.write(creds.to_json())
        print(f"\n  [OK] token.json kaydedildi: {TOKEN_JSON}")
        return True
    except ImportError:
        print("  [HATA] google-auth-oauthlib kurulu degil.")
        print("  Kurmak icin: pip install google-auth-oauthlib")
        return False
    except Exception as e:
        print(f"  [HATA] Token alinamadi: {e}")
        return False

# ─────────────────────────────────────────────
# ADIM 3: GitHub Personal Access Token
# ─────────────────────────────────────────────
def setup_github_token():
    step(3, "GitHub Personal Access Token")

    existing = os.getenv("GITHUB_TOKEN", "")
    if existing:
        print(f"  [OK] GITHUB_TOKEN zaten ayarli ({existing[:8]}...)")
        return existing

    print("""
  GitHub Personal Access Token olmadan code agent GitHub'a
  Issue acamaz ve commit okuyamaz.

  1. Su linke git:
     https://github.com/settings/tokens/new

  2. Note: "AGU FCEV Code Agent" yaz

  3. Expiration: 90 days sec

  4. Scopes:
     [x] repo         (commit, issue okuma/yazma)
     [x] read:org     (org repo erisimi icin)

  5. "Generate token" tikla → cikan tokeni kopyala (ghp_...)
""")
    open_browser = input("  Tarayiciyi simdi acayim mi? (e/h): ").strip().lower()
    if open_browser == "e":
        webbrowser.open("https://github.com/settings/tokens/new")

    token = input("\n  GitHub token'ini yapistir (ghp_...): ").strip()
    if token.startswith("ghp_") or token.startswith("github_pat_"):
        print(f"  [OK] Token alinidi ({token[:8]}...)")
        return token
    else:
        print("  [UYARI] Token 'ghp_' ile baslemiyor, devam edilecek ama hatali olabilir.")
        return token

# ─────────────────────────────────────────────
# ADIM 4: .env dosyasini guncelle
# ─────────────────────────────────────────────
def write_env_file(github_token, gemini_key="", gcp_project="formula-student-autonomus"):
    step(4, ".env dosyasi olusturuluyor")

    gemini_existing = os.getenv("GEMINI_API_KEY", gemini_key)

    env_content = f"""# AGU FCEV Multi-Agent System — Environment Variables
# Bu dosyayi asla Git'e commit etme!

# Google Cloud
GOOGLE_CLOUD_PROJECT={gcp_project}
GOOGLE_APPLICATION_CREDENTIALS=credentials/service-account-key.json

# Gemini API (AI Studio)
GEMINI_API_KEY={gemini_existing}

# GitHub
GITHUB_TOKEN={github_token}
GITHUB_REPO=jasstt/formula-student-autonomus

# Gmail gonderen adresi
GMAIL_SENDER=sponsorship@agu-fcev.com
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"  [OK] .env dosyasi olusturuldu: {ENV_FILE}")
    print("  [ONEMLI] .env dosyasini asla GitHub'a push etme!")
    print("  (credentials/.gitignore ve .gitignore bunu engelliyor)")

# ─────────────────────────────────────────────
# ADIM 5: Baglanti testi
# ─────────────────────────────────────────────
def test_connections():
    step(5, "Baglanti Testleri")

    results = {}

    # Gmail testi
    try:
        from agents.sponsor.outreach_agent import get_gmail_service
        svc = get_gmail_service()
        if svc:
            profile = svc.users().getProfile(userId="me").execute()
            print(f"  [OK] Gmail: {profile.get('emailAddress')}")
            results["Gmail"] = True
        else:
            print("  [EKSIK] Gmail: token.json bulunamadi")
            results["Gmail"] = False
    except Exception as e:
        print(f"  [HATA] Gmail: {e}")
        results["Gmail"] = False

    # GitHub testi
    try:
        import urllib.request
        token = os.getenv("GITHUB_TOKEN", "")
        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}", "User-Agent": "AGU-FCEV"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            user = json.loads(resp.read())
            print(f"  [OK] GitHub: @{user.get('login')}")
            results["GitHub"] = True
    except Exception as e:
        print(f"  [HATA] GitHub: {e}")
        results["GitHub"] = False

    # Gemini testi
    try:
        import urllib.request, urllib.error
        key = os.getenv("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"  [OK] Gemini API baglantisi basarili")
            results["Gemini"] = True
    except Exception as e:
        print(f"  [HATA] Gemini: {e}")
        results["Gemini"] = False

    return results

# ─────────────────────────────────────────────
# ANA AKIS
# ─────────────────────────────────────────────
def main():
    print(f"\n{'#'*60}")
    print("  AGU FCEV — Credential Kurulum Sihirbazi")
    print(f"{'#'*60}")

    status = check_status()

    # Adim 1: credentials.json
    if not status["credentials.json (Google OAuth)"]:
        ok = setup_google_oauth()
        if not ok:
            print("\n  Kurulum tamamlanamadi. credentials.json olmadan devam edilemiyor.")
            sys.exit(1)

    # Adim 2: token.json
    if not status["token.json (Google Auth Token)"]:
        setup_gmail_token()

    # Adim 3: GitHub token
    github_token = ""
    if not status["GITHUB_TOKEN env var"]:
        github_token = setup_github_token()
    else:
        github_token = os.getenv("GITHUB_TOKEN", "")

    # Adim 4: .env yaz
    write_env_file(github_token)

    # Adim 5: test
    results = test_connections()

    # Ozet
    print(f"\n{SEP}")
    print("  KURULUM OZETI")
    print(SEP)
    all_ok = all(results.values())
    for name, ok in results.items():
        print(f"  {check_mark(ok)}  {name}")

    if all_ok:
        print(f"\n  Tum baglantiler TAMAM!")
        print(f"  Sistemi gercek modda calistirmak icin:")
        print(f"  python verify_pillar3.py  (artik mock=False ile calisacak)")
    else:
        print(f"\n  Bazi baglantilarda sorun var. Yukaridaki hatalara bakin.")

if __name__ == "__main__":
    main()
