import csv
import datetime
import os
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

FIRESTORE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "formula-student-autonomus")

VALID_STAGES = ["contacted", "responded", "meeting", "negotiating", "agreed", "closed"]

def update_pipeline(company: str, stage: str, mock: bool = True):
    """
    Updates the stage of a sponsor in the pipeline.
    Reads/writes to data/sponsors/sponsor_tracker.csv, syncs to Firestore,
    and triggers social media if agreed.
    """
    if stage not in VALID_STAGES:
        print(f"Invalid stage: {stage}")
        return False
        
    csv_path = os.path.join("data", "sponsors", "sponsor_tracker.csv")
    updated_rows = []
    found = False
    
    try:
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row["company_name"].lower() == company.lower():
                        row["stage"] = stage
                        row["last_updated"] = datetime.datetime.now().date().isoformat()
                        found = True
                    updated_rows.append(row)
        else:
            fieldnames = ["company_name", "stage", "last_updated"]
            
        if not found:
            updated_rows.append({
                "company_name": company,
                "stage": stage,
                "last_updated": datetime.datetime.now().date().isoformat()
            })
            
        if not mock:
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(updated_rows)
    except Exception as e:
        print(f"Failed to update CSV tracker: {e}")
        
    if mock:
        print(f"========== MOCK PIPELINE UPDATE ==========")
        print(f"Company: {company}")
        print(f"New Stage: {stage}")
        print("==========================================")
    else:
        try:
            db = firestore.Client(project=FIRESTORE_PROJECT)
            doc_ref = db.collection("sponsor_pipeline").document(company.replace(" ", "_").lower())
            doc_ref.set({
                "stage": stage,
                "last_updated": datetime.datetime.now().isoformat()
            }, merge=True)
        except Exception as e:
            print(f"Failed to update Firestore: {e}")
            
    if stage == "agreed":
        print(f"Sponsor {company} agreed! Triggering social media announcement...")
        try:
            # We will import social_media_agent dynamically to avoid circular dependencies
            from agents.social_media.content_generator import generate_technical_post
            from agents.social_media.linkedin_agent import post_to_linkedin
            
            content = generate_technical_post("sponsor_joined", {"company": company}, mock=mock)
            
            if content and not mock:
                post_to_linkedin(content["linkedin_text"])
                
        except ImportError:
            print("Social media agents not yet implemented or available.")

if __name__ == "__main__":
    update_pipeline("Global Logistics", "agreed", mock=True)
