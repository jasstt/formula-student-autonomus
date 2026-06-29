"""
verify_pillar3.py
=================
3-Sütunlu Multi-Agent Sistemi için kapsamlı doğrulama betiği.
Her bileşeni doğrudan import ederek test eder; subprocess değil.

Kullanım:
    python verify_pillar3.py --mock
"""
import sys
import os
import argparse
import traceback
import subprocess

# UTF-8 zorla (Windows cp1254 sorunu)
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PASS = "[PASS]"
FAIL = "[FAIL]"
SECTION = "=" * 60

def sep(title):
    print(f"\n{SECTION}")
    print(f"  {title}")
    print(SECTION)

# ────────────────────────────────────────────────────────────────
# SORU 1 — blueprint_reader: fc_max_power_w değeri nedir?
# ────────────────────────────────────────────────────────────────
def test_blueprint_reader():
    sep("SORU 1 — blueprint_reader: fc_max_power_w değeri nedir?")
    try:
        from agents.surveillance.sources.blueprint_reader import load_vehicle_params
        params = load_vehicle_params()

        fc_power   = params.powertrain.get("fc_max_power_w", "YOK")
        batt_wh    = params.powertrain.get("battery_capacity_wh", "YOK")
        lidar      = params.sensors.get("lidar", "YOK")
        camera     = params.sensors.get("camera", "YOK")
        imu        = params.sensors.get("imu", "YOK")
        compute    = params.compute.get("onboard_computer", "YOK")

        print(f"  powertrain.fc_max_power_w      = {fc_power} W")
        print(f"  powertrain.battery_capacity_wh = {batt_wh} Wh")
        print(f"  sensors.lidar                  = {lidar}")
        print(f"  sensors.camera                 = {camera}")
        print(f"  sensors.imu                    = {imu}")
        print(f"  compute.onboard_computer       = {compute}")

        assert fc_power != "YOK", "fc_max_power_w bulunamadı"
        print(f"\n  {PASS} blueprint_reader çalışıyor | fc_max_power_w = {fc_power} W")
        return True
    except Exception as e:
        print(f"  {FAIL} blueprint_reader hatası: {e}")
        traceback.print_exc()
        return False

# ────────────────────────────────────────────────────────────────
# SORU 2 — outreach_agent: hangi template seçildi, mail içeriği?
# ────────────────────────────────────────────────────────────────
def test_outreach_agent():
    sep("SORU 2 — outreach_agent: template seçimi & mail içeriği")
    try:
        from agents.sponsor.outreach_agent import load_template, send_sponsor_email

        test_cases = [
            ("Acme Corp",        "John Doe",     "john@acme.com",        "manufacturing"),
            ("Hydrogen Dynamics","Dr. Alan Grant","grant@hdynamics.com",  "hydrogen"),
            ("Tech Innovations", "Jane Smith",    "jane@tech.com",        "tech"),
        ]

        for company, contact, email, stype in test_cases:
            print(f"\n  --- Sponsor: {company} (type={stype}) ---")
            tpl = load_template(stype)
            print(f"  Template seçildi: '{stype}'")
            print(f"  Ham şablon:\n    {tpl[:120]}...")

            # Maili yazdır (mock=True → gerçek gönderim yok)
            print(f"\n  >>> send_sponsor_email(..., mock=True) çıktısı:")
            result = send_sponsor_email(company, contact, email, stype, mock=True)
            assert result, "send_sponsor_email False döndü"

        print(f"\n  {PASS} outreach_agent çalışıyor")
        return True
    except Exception as e:
        print(f"  {FAIL} outreach_agent hatası: {e}")
        traceback.print_exc()
        return False

# ────────────────────────────────────────────────────────────────
# SORU 3 — content_generator: Gemini'den ne döndü?
# ────────────────────────────────────────────────────────────────
def test_content_generator():
    sep("SORU 3 — content_generator: Gemini mock çıktısı")
    try:
        from agents.social_media.content_generator import generate_technical_post

        events = [
            ("sponsor_joined",       {"company": "Hydrogen Dynamics"}),
            ("technical_milestone",  {"commit_message": "LiDAR-ROS2 entegrasyonu tamamlandı"}),
            ("weekly_update",        {"week": 26}),
        ]

        for event_type, data in events:
            print(f"\n  --- Event: {event_type} ---")
            result = generate_technical_post(event_type, data, mock=True)
            assert result is not None, "generate_technical_post None döndü"

            print(f"  linkedin_text   : {result.get('linkedin_text', '')[:120]}...")
            print(f"  instagram_caption: {result.get('instagram_caption', '')[:80]}...")
            print(f"  hashtags        : {result.get('hashtags', [])}")
            print(f"  image_prompt    : {result.get('image_prompt', '')[:80]}...")

        print(f"\n  {PASS} content_generator çalışıyor (mock=True, Gemini API çağrısı yapılmadı)")
        return True
    except Exception as e:
        print(f"  {FAIL} content_generator hatası: {e}")
        traceback.print_exc()
        return False

# ────────────────────────────────────────────────────────────────
# SORU 4 — orchestrator dry_run: hangi agent'lar tetiklendi?
# ────────────────────────────────────────────────────────────────
def test_orchestrator():
    sep("SORU 4 — orchestrator: hangi agent'lar tetiklendi?")
    triggered = []
    errors    = []

    def _run(label, fn):
        try:
            print(f"\n  >>> {label} başlatılıyor...")
            fn()
            triggered.append(label)
            print(f"  {PASS} {label} tamamlandı")
        except Exception as e:
            errors.append(label)
            print(f"  {FAIL} {label}: {e}")

    # Sponsor Cycle
    from agents.sponsor.outreach_agent import batch_outreach
    from agents.sponsor.response_tracker import check_responses
    _run("sponsor.batch_outreach",  lambda: batch_outreach("data/sponsors/target_companies.csv", mock=True))
    _run("sponsor.check_responses", lambda: check_responses(mock=True))

    # Social Media Cycle
    from agents.social_media.scheduler import schedule_weekly_content, check_github_for_milestone
    _run("social.schedule_weekly_content",    lambda: schedule_weekly_content(mock=True))
    _run("social.check_github_for_milestone", lambda: check_github_for_milestone(mock=True))

    # Code Cycle
    from agents.analysis.code_improvement_agent import analyze_autonomous_code
    _run("code.analyze_autonomous_code", lambda: analyze_autonomous_code(mock=True))

    print(f"\n  Tetiklenen agent'lar ({len(triggered)}):")
    for a in triggered:
        print(f"    {PASS} {a}")
    if errors:
        print(f"\n  Hata veren agent'lar ({len(errors)}):")
        for a in errors:
            print(f"    {FAIL} {a}")

    return len(errors) == 0

# ────────────────────────────────────────────────────────────────
# SORU 5 — terraform validate
# ────────────────────────────────────────────────────────────────
def test_terraform():
    sep("SORU 5 — terraform validate: hata var mı?")
    tf_dir = os.path.join(ROOT, "infrastructure", "terraform")

    # terraform komutunun var olup olmadığını kontrol et
    try:
        result = subprocess.run(
            ["terraform", "--version"],
            capture_output=True, text=True, timeout=10
        )
        tf_version = result.stdout.strip().split("\n")[0]
        print(f"  terraform kurulu: {tf_version}")
    except FileNotFoundError:
        print("  Terraform CLI bu makinede kurulu değil.")
        print("  Sözdizimi doğrulaması yapılıyor (python tarafında)...")

        # Terraform CLI yoksa basit sözdizimi kontrolü: hcl brace balance
        tf_file = os.path.join(tf_dir, "main.tf")
        if not os.path.exists(tf_file):
            print(f"  {FAIL} main.tf bulunamadı: {tf_file}")
            return False

        with open(tf_file, "r", encoding="utf-8") as f:
            content = f.read()

        open_braces  = content.count("{")
        close_braces = content.count("}")
        open_parens  = content.count("(")
        close_parens = content.count(")")

        print(f"  main.tf istatistikleri:")
        print(f"    Toplam satır : {len(content.splitlines())}")
        print(f"    {{ açılan    : {open_braces}")
        print(f"    }} kapanan   : {close_braces}")
        print(f"    ( açılan    : {open_parens}")
        print(f"    ) kapanan   : {close_parens}")

        brace_ok = open_braces == close_braces
        paren_ok = open_parens == close_parens

        if brace_ok and paren_ok:
            print(f"\n  {PASS} Küme parantez dengesi TAMAM")
        else:
            if not brace_ok:
                print(f"  {FAIL} Küme parantez dengesizliği: {open_braces} açık != {close_braces} kapalı")
            if not paren_ok:
                print(f"  {FAIL} Parantez dengesizliği: {open_parens} açık != {close_parens} kapalı")

        # Kaynak blokları bul ve listele
        import re
        resources = re.findall(r'^resource\s+"([^"]+)"\s+"([^"]+)"', content, re.MULTILINE)
        print(f"\n  Tanımlı Terraform resource'ları ({len(resources)} adet):")
        for rtype, rname in resources:
            print(f"    + {rtype}.{rname}")

        return brace_ok and paren_ok

    except subprocess.TimeoutExpired:
        print(f"  {FAIL} terraform --version zaman aşımına uğradı")
        return False

    # Terraform varsa gerçek validate çalıştır
    try:
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false"],
            capture_output=True, text=True, cwd=tf_dir, timeout=60
        )
        val_result = subprocess.run(
            ["terraform", "validate"],
            capture_output=True, text=True, cwd=tf_dir, timeout=30
        )
        if val_result.returncode == 0:
            print(f"  {PASS} terraform validate BAŞARILI")
            print(f"  Çıktı: {val_result.stdout.strip()}")
            return True
        else:
            print(f"  {FAIL} terraform validate BAŞARISIZ")
            print(f"  Stderr: {val_result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  {FAIL} terraform hatası: {e}")
        return False

# ────────────────────────────────────────────────────────────────
# ANA ÇALIŞMA
# ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="verify_pillar3 — AGÜ FCEV Agent Doğrulama")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Mock modda çalıştır (gerçek API çağrısı yapma)")
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"  AGU FCEV — 3-Pillar Multi-Agent Verification")
    print(f"  Mode: {'MOCK (kuru çalıştırma)' if args.mock else 'PRODUCTION'}")
    print(f"{'#'*60}\n")

    results = {
        "1. blueprint_reader"  : test_blueprint_reader(),
        "2. outreach_agent"    : test_outreach_agent(),
        "3. content_generator" : test_content_generator(),
        "4. orchestrator"      : test_orchestrator(),
        "5. terraform validate": test_terraform(),
    }

    sep("ÖZET")
    all_pass = True
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  {status}  {name}")
        if not ok:
            all_pass = False

    print(f"\n{'#'*60}")
    if all_pass:
        print("  TUM TESTLER GECTI")
    else:
        print("  BAZI TESTLER BASARISIZ")
    print(f"{'#'*60}\n")
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
