import json
import os
import subprocess
import urllib.error
import urllib.request

GITHUB_REPO = os.getenv("GITHUB_REPO", "jasstt/formula-student-autonomus")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def _repo_api_url(path: str) -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}{path}"


def github_get(path: str) -> dict | list | None:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AGU-FCEV-Agent",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        req = urllib.request.Request(_repo_api_url(path), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        print(f"[GITHUB] GET {path} basarisiz: {exc}")
        return None


def create_issue(title: str, body: str, labels: list[str] | None = None) -> str | None:
    labels = labels or []

    if GITHUB_TOKEN:
        payload = json.dumps({"title": title, "body": body, "labels": labels}).encode()
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AGU-FCEV-Agent",
            "Content-Type": "application/json",
        }
        try:
            req = urllib.request.Request(
                _repo_api_url("/issues"),
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                issue = json.loads(resp.read())
                return issue.get("html_url")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            print(f"[GITHUB] Issue acilamadi: HTTP {exc.code} {detail}")
            return None
        except Exception as exc:
            print(f"[GITHUB] Issue acilamadi: {exc}")
            return None

    cmd = ["gh", "issue", "create", "--repo", GITHUB_REPO, "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0:
            print(f"[GITHUB] gh issue create basarisiz: {result.stderr.strip()}")
            return None
        return result.stdout.strip().splitlines()[-1]
    except FileNotFoundError:
        print("[GITHUB] GITHUB_TOKEN yok ve gh CLI bulunamadi.")
        return None
    except Exception as exc:
        print(f"[GITHUB] gh issue create hatasi: {exc}")
        return None
