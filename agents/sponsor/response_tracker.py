import os
import datetime
try:
    from google.cloud import firestore
except ImportError:
    firestore = None
from agents.sponsor.meeting_scheduler import schedule_meeting

FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "formula-student-autonomus")

def get_gmail_service():
    """Builds and returns the Gmail API service."""
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
    # Real logic would use service.users().messages().list(q="is:unread")
    # Then parse the thread, extract company info, and classify
    
    # Mock data to simulate API response processing
    responses = [] 
    
    db = firestore.Client(project=FIRESTORE_PROJECT)
    
    for resp in responses:
        company = resp["company"]
        text = resp["text"]
        classification = classify_response(text)
        
        # Update Firestore
        try:
            doc_ref = db.collection("sponsor_pipeline").document(company.replace(" ", "_").lower())
            doc_ref.set({
                "response_type": classification,
                "response_text": text,
                "responded_at": datetime.datetime.now().isoformat(),
                "stage": "responded" if classification != "negative" else "closed_lost"
            }, merge=True)
        except Exception as e:
            print(f"Failed to log response for {company}: {e}")
            
        if classification == "positive":
            schedule_meeting(company, resp["contact"], resp["email"], mock=False)

if __name__ == "__main__":
    check_responses(mock=True)
