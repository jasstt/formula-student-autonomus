import datetime
import json
import os
import urllib.request
import pytz
from agents.social_media.content_generator import generate_technical_post
from agents.social_media.linkedin_agent import post_to_linkedin
from agents.social_media.instagram_agent import post_to_instagram

GITHUB_REPO = os.getenv("GITHUB_REPO", "jasstt/formula-student-autonomus")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
STATE_PATH = os.path.join("data", "social_media", "github_milestone_state.json")

def schedule_weekly_content(mock: bool = True, force: bool = False):
    """
    Checks if it's Friday 18:00 (Turkey Time) and generates/posts weekly update.
    Use force=True to bypass the time check for testing.
    """
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.datetime.now(tz)
    
    # Check if it's Friday (weekday == 4) and hour is around 18
    if mock:
        print(f"========== MOCK WEEKLY SCHEDULER ==========")
        print(f"Current TR Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("Simulating that it is Friday 18:00...")
        
        content = generate_technical_post("weekly_update", {"week": now.isocalendar()[1]}, mock=True)
        if content:
            post_to_linkedin(content.get("linkedin_text"), mock=True)
            post_to_instagram(content.get("instagram_caption"), "mock_image_path.jpg", mock=True)
            
        print("===========================================")
        return True

    # Real logic: run only if it's actually Friday 18:00 (or force=True for testing)
    if force or (now.weekday() == 4 and now.hour == 18):
        print(f"[REAL] Triggering weekly social media post (TR Time: {now.strftime('%Y-%m-%d %H:%M:%S')})...")
        content = generate_technical_post("weekly_update", {"week": now.isocalendar()[1]}, mock=False)
        if content:
            post_to_linkedin(content.get("linkedin_text"), mock=False)
            post_to_instagram(content.get("instagram_caption"), "generated_image_path.jpg", mock=False)
        return True
        
    print(f"[SKIP] Not Friday 18:00 — current: {now.strftime('%A %H:%M')} (use force=True to override)")
    return False

def check_github_for_milestone(mock: bool = True):
    """
    Checks GitHub API for new commits to main branch.
    If found, generates a technical milestone post.
    """
    if mock:
        print(f"========== MOCK GITHUB CHECK ==========")
        print("Simulating a new commit on main branch...")
        content = generate_technical_post("technical_milestone", {"commit_message": "Integrated Ouster LiDAR with ROS2"}, mock=True)
        if content:
            post_to_linkedin(content.get("linkedin_text"), mock=True)
            post_to_instagram(content.get("instagram_caption"), "mock_image_path.jpg", mock=True)
        print("=======================================")
        return True

    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AGU-FCEV-Agent",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            commit = json.loads(resp.read())
    except Exception as e:
        print(f"[GITHUB] Commit kontrolu basarisiz: {e}")
        return False

    sha = commit.get("sha", "")
    message = commit.get("commit", {}).get("message", "")
    if not sha:
        print("[GITHUB] Commit SHA donmedi.")
        return False

    state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

    if state.get("last_main_sha") == sha:
        print(f"[GITHUB] Yeni milestone yok. main zaten {sha[:7]}.")
        return False

    print(f"[GITHUB] Yeni main commit algilandi: {sha[:7]} — {message[:120]}")
    content = generate_technical_post("technical_milestone", {"commit_message": message, "sha": sha[:7]}, mock=False)
    posted = False
    if content:
        linkedin_id = post_to_linkedin(content.get("linkedin_text", ""), mock=False)
        image_url = os.getenv("INSTAGRAM_IMAGE_URL", "")
        instagram_id = None
        if image_url:
            instagram_id = post_to_instagram(content.get("instagram_caption", ""), image_url, mock=False)
        else:
            print("[INSTAGRAM] INSTAGRAM_IMAGE_URL yok; milestone Instagram'a gonderilmedi.")
        posted = bool(linkedin_id or instagram_id)

    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "last_main_sha": sha,
            "last_message": message,
            "last_checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "posted": posted,
        }, f, ensure_ascii=False, indent=2)

    return posted
