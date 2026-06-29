import datetime
import pytz
from agents.social_media.content_generator import generate_technical_post
from agents.social_media.linkedin_agent import post_to_linkedin
from agents.social_media.instagram_agent import post_to_instagram

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
        
    # Real logic using GitHub API would go here
    # Check if last_commit_sha changed in Firestore
    # If yes -> generate post -> update Firestore
    
    return False
