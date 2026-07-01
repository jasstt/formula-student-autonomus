import os
try:
    import google.generativeai as genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def generate_technical_post(event_type: str, data: dict, mock: bool = True) -> dict:
    """
    Uses Gemini API to generate bilingual (TR/EN) technical posts tailored for 
    LinkedIn and Instagram.
    """
    valid_events = ["sponsor_joined", "technical_milestone", "weekly_update", "competition_prep"]
    if event_type not in valid_events:
        raise ValueError(f"Invalid event_type. Must be one of {valid_events}")

    if mock:
        print(f"========== MOCK CONTENT GENERATION ==========")
        print(f"Event: {event_type}")
        print(f"Data: {data}")
        print("=============================================")
        
        # Return mock generated content
        company = data.get("company", "Tech Innovations")
        return {
            "linkedin_text": f"🚀 Exciting news! We are thrilled to announce that {company} has joined the AGÜ Formula Student FCEV project as a sponsor. Their support is crucial for our autonomous systems. #FormulaStudent #Autonomous #FCEV #AGU",
            "instagram_caption": f"🚀 {company} is now our sponsor! Thank you for supporting our autonomous journey. 🏎️💨 #FormulaStudent #FCEV",
            "hashtags": ["#FormulaStudent", "#Autonomous", "#FCEV", "#AGU"],
            "image_prompt": f"A high-tech futuristic Formula Student race car with {company} logo on it, glowing hydrogen fuel cell."
        }

    if not GEMINI_API_KEY:
        print("[GEMINI] GEMINI_API_KEY bulunamadi; gercek icerik uretilemedi.")
        return None
    if not genai:
        print("[GEMINI] google-generativeai paketi kurulu degil.")
        return None

    # Real Gemini Prompt
    prompt = f"""
    Sen AGÜ Formula Student FCEV (Otonom Hidrojen Yakıt Hücreli Araç) takımının sosyal medya yöneticisisin.
    Şu olay için içerik üret: {event_type}
    Veri: {data}
    
    Lütfen şu formatta JSON döndür:
    {{
        "linkedin_text": "Profesyonel, teknik detaylar içeren, 150-200 kelime arası, iki dilli (TR/EN) LinkedIn metni",
        "instagram_caption": "Daha kısa, görsel odaklı, emojili, iki dilli (TR/EN) Instagram metni",
        "hashtags": ["#etiket1", "#etiket2", "5-7 adet etiket"],
        "image_prompt": "Bu post için Midjourney/DALL-E'ye verilecek İngilizce resim üretme promptu"
    }}
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        # Parse JSON from response
        import json
        
        # Clean markdown codeblocks if Gemini added them
        text = response.text
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        result = json.loads(text.strip())
        return result
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None

if __name__ == "__main__":
    print(generate_technical_post("sponsor_joined", {"company": "Acme Corp"}, mock=True))
