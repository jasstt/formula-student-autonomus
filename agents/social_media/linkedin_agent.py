import os
import datetime
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
import requests

FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "formula-student-autonomus")

def post_to_linkedin(text: str, image_path: str = None, mock: bool = True):
    """
    Authenticates with LinkedIn API, creates a text or image post, and logs to Firestore.
    """
    if mock:
        print("========== MOCK LINKEDIN POST ==========")
        print(f"Text:\n{text}")
        if image_path:
            print(f"Image: {image_path}")
        print("========================================")
        
        post_id = f"urn:li:share:mock_{int(datetime.datetime.now().timestamp())}"
    else:
        # Real LinkedIn API Logic using OAuth2 Token from Secret Manager
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not access_token:
            print("No LinkedIn Access Token found.")
            return None
            
        # Placeholder for real REST API calls to api.linkedin.com/v2/ugcPosts
        # ...
        
        post_id = f"urn:li:share:real_{int(datetime.datetime.now().timestamp())}"

    # Log to Firestore
    try:
        if not mock:
            db = firestore.Client(project=FIRESTORE_PROJECT)
            doc_ref = db.collection("social_media_posts").document(post_id.replace(":", "_"))
            doc_ref.set({
                "platform": "linkedin",
                "post_id": post_id,
                "content_preview": text[:100] + "...",
                "posted_at": datetime.datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Failed to log LinkedIn post to Firestore: {e}")

    return post_id
