import datetime
import os
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "formula-student-autonomus")

def get_calendar_service():
    """
    Builds the Google Calendar API service.
    Loads credentials from credentials/token.json (same OAuth token as Gmail).
    """
    import os
    token_path = os.path.join(os.path.dirname(__file__), '..', '..', 'credentials', 'token.json')

    if not os.path.exists(token_path):
        print(f"[AUTH] token.json bulunamadi: {token_path}")
        print("[AUTH] 'python setup_credentials.py' calistirarak token olusturun.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as f:
                f.write(creds.to_json())

        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"[AUTH] Calendar servisi olusturulamadi: {e}")
        return None

def schedule_meeting(company: str, contact: str, email: str, mock: bool = True):
    """
    Finds the next available 30-min slot, creates a Google Calendar event,
    and invites the contact. Updates Firestore.
    """
    if mock:
        print(f"========== MOCK MEETING SCHEDULE ==========")
        print(f"Company: {company}")
        print(f"Contact: {contact} ({email})")
        print(f"Action: Scheduled next available 30-min slot")
        print("===========================================")
        return True

    service = get_calendar_service()
    
    # Fake logic for real calendar API:
    # 1. Fetch freebusy
    # 2. Find first 30 min gap during business hours
    # 3. Create event
    
    start_time = datetime.datetime.now() + datetime.timedelta(days=1)
    end_time = start_time + datetime.timedelta(minutes=30)
    
    event = {
        'summary': f'AGÜ Formula Student - {company} Sponsorluk Görüşmesi',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Europe/Istanbul',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Europe/Istanbul',
        },
        'attendees': [
            {'email': email},
        ],
    }
    
    try:
        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all'  # Katilimcilara davet maili gonder
        ).execute()
        print(f"[CALENDAR] Toplanti olusturuldu: {created_event.get('htmlLink')}")
    except Exception as e:
        print(f"Failed to create calendar event: {e}")
        return False

    # Update Firestore
    try:
        db = firestore.Client(project=FIRESTORE_PROJECT)
        doc_ref = db.collection("sponsor_pipeline").document(company.replace(" ", "_").lower())
        doc_ref.set({
            "status": "meeting_scheduled",
            "stage": "meeting"
        }, merge=True)
        print(f"Updated Firestore for {company} meeting")
    except Exception as e:
        print(f"Failed to update Firestore: {e}")
        
    return True
