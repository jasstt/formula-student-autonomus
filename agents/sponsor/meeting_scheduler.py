import datetime
import os
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.integrations.gcp_clients import GCP_PROJECT, get_firestore_client

FIRESTORE_PROJECT = GCP_PROJECT
ALLOW_SPONSOR_MEETING_SCHEDULE = os.getenv("ALLOW_SPONSOR_MEETING_SCHEDULE", "").lower() in {"1", "true", "yes"}
BUSINESS_TZ = "Europe/Istanbul"
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 17

def _next_business_slot(service, days_ahead: int = 10) -> tuple[datetime.datetime, datetime.datetime] | None:
    now = datetime.datetime.now(datetime.timezone.utc)
    time_min = now.isoformat()
    time_max = (now + datetime.timedelta(days=days_ahead)).isoformat()

    freebusy = service.freebusy().query(body={
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": BUSINESS_TZ,
        "items": [{"id": "primary"}],
    }).execute()
    busy = [
        (
            datetime.datetime.fromisoformat(item["start"].replace("Z", "+00:00")),
            datetime.datetime.fromisoformat(item["end"].replace("Z", "+00:00")),
        )
        for item in freebusy.get("calendars", {}).get("primary", {}).get("busy", [])
    ]

    candidate = now + datetime.timedelta(hours=2)
    candidate = candidate.replace(minute=0, second=0, microsecond=0)
    for _ in range(days_ahead * 24 * 2):
        local = candidate.astimezone(datetime.timezone(datetime.timedelta(hours=3)))
        if local.weekday() < 5 and BUSINESS_START_HOUR <= local.hour < BUSINESS_END_HOUR:
            end = candidate + datetime.timedelta(minutes=30)
            overlaps = any(candidate < busy_end and end > busy_start for busy_start, busy_end in busy)
            if not overlaps:
                return candidate, end
        candidate += datetime.timedelta(minutes=30)
    return None

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

    if not ALLOW_SPONSOR_MEETING_SCHEDULE:
        print("[SAFETY] ALLOW_SPONSOR_MEETING_SCHEDULE=1 degil; Calendar daveti olusturulmadi.")
        return False

    service = get_calendar_service()
    if not service:
        print("[CALENDAR] Servis hazir degil; toplanti olusturulmadi.")
        return False
    
    slot = _next_business_slot(service)
    if not slot:
        print("[CALENDAR] Uygun 30 dakikalik slot bulunamadi.")
        return False
    start_time, end_time = slot
    
    event = {
        'summary': f'AGÜ Formula Student - {company} Sponsorluk Görüşmesi',
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': BUSINESS_TZ,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': BUSINESS_TZ,
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
        db = get_firestore_client()
        doc_ref = db.collection("sponsor_pipeline").document(company.replace(" ", "_").lower())
        doc_ref.set({
            "status": "meeting_scheduled",
            "stage": "meeting"
        }, merge=True)
        print(f"Updated Firestore for {company} meeting")
    except Exception as e:
        print(f"Failed to update Firestore: {e}")
        
    return True
