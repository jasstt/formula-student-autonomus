import os
import datetime
import json
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client
import requests

FIRESTORE_PROJECT = GCP_PROJECT

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
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        author_urn = os.getenv("LINKEDIN_AUTHOR_URN")
        if not access_token:
            print("[LINKEDIN] LINKEDIN_ACCESS_TOKEN bulunamadi.")
            return None
        if not author_urn:
            print("[LINKEDIN] LINKEDIN_AUTHOR_URN bulunamadi. Ornek: urn:li:person:<id> veya urn:li:organization:<id>")
            return None

        if image_path:
            print("[LINKEDIN] Uyari: Resimli post icin asset upload akisi gerekir; su an text-only post atiliyor.")

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        try:
            response = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                data=json.dumps(payload),
                timeout=20,
            )
            if response.status_code not in (200, 201):
                print(f"[LINKEDIN] Post basarisiz: {response.status_code} {response.text[:500]}")
                return None
            post_id = response.headers.get("x-restli-id") or response.json().get("id")
            print(f"[LINKEDIN] Post yayinlandi: {post_id}")
        except Exception as e:
            print(f"[LINKEDIN] API hatasi: {e}")
            return None

    # Log to Firestore
    try:
        if not mock:
            db = get_firestore_client()
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
