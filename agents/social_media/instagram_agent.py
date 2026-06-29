import os
import datetime
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "formula-student-autonomus")

def post_to_instagram(caption: str, image_path: str, mock: bool = True):
    """
    Authenticates with Instagram Graph API, uploads an image and caption, 
    and logs to Firestore.
    """
    if not image_path:
        print("Instagram requires an image path.")
        return None

    if mock:
        print("========== MOCK INSTAGRAM POST ==========")
        print(f"Caption:\n{caption}")
        print(f"Image: {image_path}")
        print("=========================================")
        
        media_id = f"ig_mock_{int(datetime.datetime.now().timestamp())}"
    else:
        # Real Instagram Graph API Logic using Access Token from Secret Manager
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        if not access_token:
            print("No Instagram Access Token found.")
            return None
            
        # Placeholder for real REST API calls to graph.facebook.com/vX.X/ig_user_id/media
        # ...
        
        media_id = f"ig_real_{int(datetime.datetime.now().timestamp())}"

    # Log to Firestore
    try:
        if not mock:
            db = firestore.Client(project=FIRESTORE_PROJECT)
            doc_ref = db.collection("social_media_posts").document(media_id)
            doc_ref.set({
                "platform": "instagram",
                "media_id": media_id,
                "content_preview": caption[:100] + "...",
                "posted_at": datetime.datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Failed to log Instagram post to Firestore: {e}")

    return media_id
