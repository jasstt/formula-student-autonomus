import os
import datetime
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client
from agents.sponsor.meeting_scheduler import schedule_meeting

FIRESTORE_PROJECT = GCP_PROJECT

def get_gmail_service():
    """Builds the Gmail API service from credentials/token.json."""
    import os
    token_path = os.path.join(os.path.dirname(__file__), '..', '..', 'credentials', 'token.json')
    if not os.path.exists(token_path):
        print(f"[AUTH] token.json bulunamadi. 'python setup_credentials.py' calistirin.")
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.readonly',
        ]
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"[AUTH] Gmail servisi olusturulamadi: {e}")
        return None

def classify_response(text: str) -> str:
    text_lower = text.lower()
    
    positive_keywords = ["toplantı", "görüşelim", "ilgileniyoruz", "meeting", "interested"]
    negative_keywords = ["hayır", "ilgilenmiyoruz", "no", "not interested"]
    
    for kw in positive_keywords:
        if kw in text_lower:
            return "positive"
            
    for kw in negative_keywords:
        if kw in text_lower:
            return "negative"
            
    return "neutral"

def check_responses(mock: bool = True):
    """
    Scans inbox for replies to sent sponsor emails, classifies them,
    updates Firestore, and schedules meetings if positive.
    """
    if mock:
        print("========== MOCK INBOX SCAN ==========")
        # Mock an inbox scan finding a positive response
        mock_response = {
            "company": "Acme Corp",
            "contact": "John Doe",
            "email": "john@acme.com",
            "text": "Projeyle çok ilgileniyoruz, bir toplantı ayarlayabilir miyiz?"
        }
        
        classification = classify_response(mock_response["text"])
        print(f"Found response from {mock_response['company']}: '{mock_response['text']}' -> {classification}")
        
        if classification == "positive":
            print(f"Triggering meeting scheduler for {mock_response['company']}...")
            schedule_meeting(mock_response["company"], mock_response["contact"], mock_response["email"], mock=True)
            
        print("=====================================")
        return

    service = get_gmail_service()
    if not service:
        print("[RESPONSE TRACKER] Gmail servisi alinamadi, atlanıyor.")
        return

    # Gonderilen sponsorluk maillerine gelen cevaplari tara
    try:
        results = service.users().messages().list(
            userId='me',
            q='is:unread subject:"AGÜ Formula Student"',
            maxResults=20
        ).execute()
        messages = results.get('messages', [])
    except Exception as e:
        print(f"[GMAIL] Inbox taranamadi: {e}")
        return

    if not messages:
        print("[RESPONSE TRACKER] Yeni yanit bulunamadi.")
        return

    db = None
    if firestore and FIRESTORE_PROJECT:
        try:
            db = get_firestore_client()
        except Exception:
            pass

    for msg_ref in messages:
        try:
            msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='full'
            ).execute()

            headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
            sender  = headers.get('From', '')
            subject = headers.get('Subject', '')
            snippet = msg.get('snippet', '')

            classification = classify_response(snippet)
            print(f"[GMAIL] Yanit: {sender} -> {classification} | {snippet[:80]}")

            # Firestore'a logla
            if db:
                company_key = sender.split('@')[-1].split('.')[0]  # domain'den sirket adini tahmin et
                try:
                    db.collection('sponsor_pipeline').document(company_key).set({
                        'response_type': classification,
                        'response_text': snippet,
                        'responded_at': datetime.datetime.now().isoformat(),
                        'stage': 'responded' if classification != 'negative' else 'closed_lost'
                    }, merge=True)
                except Exception as e:
                    print(f"[FIRESTORE] Log hatasi: {e}")

            # Pozitif yanit -> toplanti planla
            if classification == 'positive':
                schedule_meeting(sender, sender, sender, mock=False)

            # Maili okundu olarak isaretle
            service.users().messages().modify(
                userId='me', id=msg_ref['id'],
                body={'removeLabelIds': ['UNREAD']}
            ).execute()

        except Exception as e:
            print(f"[GMAIL] Mesaj isleme hatasi: {e}")

if __name__ == "__main__":
    check_responses(mock=True)
