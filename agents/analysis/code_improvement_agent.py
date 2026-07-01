import os
import ast
import datetime
import json
import urllib.request
import urllib.error
from agents.integrations.github_client import create_issue, github_get
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client
try:
    from google.cloud import firestore, pubsub_v1
except ImportError:
    firestore = None
    pubsub_v1 = None
try:
    import google.generativeai as genai
except ImportError:
    genai = None

FIRESTORE_PROJECT = GCP_PROJECT
GITHUB_REPO       = os.getenv("GITHUB_REPO", "jasstt/formula-student-autonomus")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")

# ─────────────────────────────────────────────────────────────
# Yardimci: GitHub API istegi
# ─────────────────────────────────────────────────────────────
def _github_get(path: str) -> dict | None:
    result = github_get(path)
    return result if isinstance(result, dict) else result

# ─────────────────────────────────────────────────────────────
# Yardimci: Yerel Python dosyalarini analiz et (AST)
# ─────────────────────────────────────────────────────────────
def _analyze_local_files(root: str = ".") -> list[dict]:
    findings = []
    py_dirs = ["agents", "autonomous", "digital_twin", "dashboard"]

    for dir_name in py_dirs:
        dir_path = os.path.join(root, dir_name)
        if not os.path.isdir(dir_path):
            continue
        for dirpath, _, filenames in os.walk(dir_path):
            for fname in filenames:
                if not fname.endswith(".py") or "__pycache__" in dirpath:
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=fpath)
                    rel = os.path.relpath(fpath, root)

                    for node in ast.walk(tree):
                        # Eksik docstring kontrolu
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not (node.body and isinstance(node.body[0], ast.Expr)
                                    and isinstance(node.body[0].value, ast.Constant)):
                                findings.append({
                                    "file": rel,
                                    "line": node.lineno,
                                    "type": "missing_docstring",
                                    "detail": f"'{node.name}' fonksiyonunda docstring yok",
                                    "severity": "low",
                                })

                    # TODO/FIXME/HACK yorumlari
                    for i, line in enumerate(source.splitlines(), 1):
                        stripped = line.strip()
                        for marker in ("# TODO", "# FIXME", "# HACK", "# XXX", "pass  #"):
                            if stripped.startswith(marker):
                                findings.append({
                                    "file": rel,
                                    "line": i,
                                    "type": "todo_comment",
                                    "detail": stripped[:100],
                                    "severity": "medium",
                                })

                except SyntaxError as e:
                    findings.append({
                        "file": os.path.relpath(fpath, root),
                        "line": getattr(e, "lineno", 0),
                        "type": "syntax_error",
                        "detail": str(e),
                        "severity": "critical",
                    })
                except Exception:
                    pass

    return findings

# ─────────────────────────────────────────────────────────────
# Yardimci: Gemini ile bulgu ozeti uret
# ─────────────────────────────────────────────────────────────
def _summarize_with_gemini(findings: list[dict]) -> str:
    if not GEMINI_API_KEY or not genai or not findings:
        return ""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""Sen bir kod kalite uzmanisın. 
Asagidaki bulgular bir Formula Student FCEV otonom arac projesinden AST analizi ile elde edildi.
Kisa, teknik ve oncelik sirali bir Turkce ozet yaz (max 200 kelime):

{json.dumps(findings[:20], ensure_ascii=False, indent=2)}
"""
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        return f"Gemini ozet alinamadi: {e}"

# ─────────────────────────────────────────────────────────────
# Yardimci: GitHub Issue ac
# ─────────────────────────────────────────────────────────────
def _create_github_issue(title: str, body: str) -> str | None:
    return create_issue(title, body, labels=["code-quality", "automated"])

# ─────────────────────────────────────────────────────────────
# Yardimci: Pub/Sub'a yayinla
# ─────────────────────────────────────────────────────────────
def _publish_to_pubsub(message: dict):
    if not pubsub_v1 or not FIRESTORE_PROJECT:
        return
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(FIRESTORE_PROJECT, "code-review-topic")
        data = json.dumps(message).encode("utf-8")
        future = publisher.publish(topic_path, data)
        print(f"[PUBSUB] Mesaj yayinlandi: {future.result()}")
    except Exception as e:
        print(f"[PUBSUB] Yayinlanamadi: {e}")

# ─────────────────────────────────────────────────────────────
# ANA FONKSİYON
# ─────────────────────────────────────────────────────────────
def analyze_autonomous_code(mock: bool = True):
    """
    Kod kalitesi analizi yapar:
    (a) AST ile yerel dosyalari tarar
    (b) GitHub son commit'i getirir
    (c) Gemini ile ozet olusturur
    (d) Kritik bulgu varsa GitHub Issue acar
    (e) Pub/Sub'a rapor yayinlar
    (f) Firestore'a loglar
    """
    if mock:
        print("========== MOCK CODE IMPROVEMENT ANALYSIS ==========")
        print("Analyzing repo via GitHub MCP...")

        report_content = """# Code Improvement Report

## Findings
1. **Hardcoded Values**: `vehicle_model.py` had hardcoded `battery_capacity=1000`. Fixed with `blueprint_reader.py`.
2. **Error Handling**: `telemetry_stream.py` is missing a try-catch block around the Pub/Sub publish method.
3. **Missing Docstrings**: `cone_detector.py` -> `process_frame` is missing a docstring.
4. **TODOs**: Found `# TODO: implement real sensor fusion` in `perception_sim.py`.

## Action Taken
- Auto-generated this report.
- Created GitHub Issue #42 automatically (Mocked).
"""
        with open("improvement_report.md", "w", encoding="utf-8") as f:
            f.write(report_content)
        print("Created improvement_report.md")
        print("Mocked GitHub Issue creation.")
        print("Published to code-review-topic (Mocked)")
        print("====================================================")
        return True

    # ── REAL MODE ─────────────────────────────────────────────
    print("[CODE AGENT] Kod analizi basliyor...")

    # 1. GitHub son commit bilgisi
    commits = _github_get("/commits?per_page=3&sha=main")
    last_commit = commits[0] if commits else {}
    last_sha  = last_commit.get("sha", "unknown")[:7]
    last_msg  = last_commit.get("commit", {}).get("message", "")[:80]
    print(f"[GITHUB] Son commit: {last_sha} — {last_msg}")

    # 2. Yerel AST analizi
    findings = _analyze_local_files()
    critical = [f for f in findings if f["severity"] == "critical"]
    medium   = [f for f in findings if f["severity"] == "medium"]
    low      = [f for f in findings if f["severity"] == "low"]
    print(f"[AST] {len(findings)} bulgu: {len(critical)} kritik, {len(medium)} orta, {len(low)} dusuk")

    # 3. Gemini ozeti
    gemini_summary = _summarize_with_gemini(findings)

    # 4. Rapor yaz
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report_lines = [
        f"# Code Improvement Report — {now_str}",
        f"",
        f"**Son Commit:** `{last_sha}` — {last_msg}",
        f"**Toplam Bulgu:** {len(findings)} ({len(critical)} kritik, {len(medium)} orta, {len(low)} dusuk)",
        f"",
    ]
    if gemini_summary:
        report_lines += [f"## Gemini Ozeti", f"", gemini_summary, f""]

    for sev in ("critical", "medium", "low"):
        group = [f for f in findings if f["severity"] == sev]
        if group:
            report_lines.append(f"## {sev.capitalize()} Bulgular ({len(group)})")
            for item in group[:20]:
                report_lines.append(f"- `{item['file']}:{item['line']}` — {item['detail']}")
            report_lines.append("")

    report_content = "\n".join(report_lines)
    with open("improvement_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"[CODE AGENT] improvement_report.md olusturuldu")

    # 5. Kritik bulgu varsa GitHub Issue ac
    issue_url = None
    if critical:
        title = f"[Auto] {len(critical)} kritik kod sorunu tespit edildi — {now_str}"
        issue_url = _create_github_issue(title, report_content[:8000])
        if issue_url:
            print(f"[GITHUB] Issue acildi: {issue_url}")

    # 6. Pub/Sub'a yayinla
    _publish_to_pubsub({
        "timestamp": now_str,
        "commit_sha": last_sha,
        "total_findings": len(findings),
        "critical": len(critical),
        "issue_url": issue_url,
    })

    # 7. Firestore log
    if firestore and FIRESTORE_PROJECT:
        try:
            db = get_firestore_client()
            db.collection("code_reports").add({
                "timestamp": datetime.datetime.now().isoformat(),
                "commit_sha": last_sha,
                "findings": len(findings),
                "critical": len(critical),
                "issue_url": issue_url,
            })
            print("[FIRESTORE] Rapor loglandiA")
        except Exception as e:
            print(f"[FIRESTORE] Log hatasi: {e}")

    return True

if __name__ == "__main__":
    analyze_autonomous_code(mock=True)

if __name__ == "__main__":
    analyze_autonomous_code(mock=True)
