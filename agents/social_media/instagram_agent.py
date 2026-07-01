import os
import datetime
from urllib.parse import urlparse
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client
import requests

FIRESTORE_PROJECT = GCP_PROJECT

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
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        ig_user_id = os.getenv("INSTAGRAM_USER_ID")
        if not access_token:
            print("[INSTAGRAM] INSTAGRAM_ACCESS_TOKEN bulunamadi.")
            return None
        if not ig_user_id:
            print("[INSTAGRAM] INSTAGRAM_USER_ID bulunamadi.")
            return None

        parsed = urlparse(image_path)
        image_url = image_path if parsed.scheme in ("http", "https") else os.getenv("INSTAGRAM_IMAGE_URL", "")
        if not image_url:
            print("[INSTAGRAM] Instagram Graph API public image_url ister. image_path URL degil ve INSTAGRAM_IMAGE_URL yok.")
            return None

        graph_version = os.getenv("INSTAGRAM_GRAPH_VERSION", "v20.0")
        try:
            create_resp = requests.post(
                f"https://graph.facebook.com/{graph_version}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": access_token,
                },
                timeout=30,
            )
            if create_resp.status_code not in (200, 201):
                print(f"[INSTAGRAM] Container olusturulamadi: {create_resp.status_code} {create_resp.text[:500]}")
                return None
            creation_id = create_resp.json().get("id")
            if not creation_id:
                print(f"[INSTAGRAM] Container id donmedi: {create_resp.text[:500]}")
                return None

            publish_resp = requests.post(
                f"https://graph.facebook.com/{graph_version}/{ig_user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": access_token},
                timeout=30,
            )
            if publish_resp.status_code not in (200, 201):
                print(f"[INSTAGRAM] Publish basarisiz: {publish_resp.status_code} {publish_resp.text[:500]}")
                return None
            media_id = publish_resp.json().get("id")
            print(f"[INSTAGRAM] Media yayinlandi: {media_id}")
        except Exception as e:
            print(f"[INSTAGRAM] API hatasi: {e}")
            return None

    # Log to Firestore
    try:
        if not mock:
            db = get_firestore_client()
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
