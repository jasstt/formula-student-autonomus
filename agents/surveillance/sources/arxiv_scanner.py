import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import time
from datetime import datetime, timedelta
import os
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None
from agents.integrations.gcp_clients import GCP_PROJECT

# Google Cloud Project Info
PROJECT_ID = GCP_PROJECT
TOPIC_ID = "agent-results-topic"

# arXiv sorgu ayarları
KEYWORDS = [
    "autonomous vehicle", 
    "formula student", 
    "cone detection", 
    "path planning FSAE", 
    "fuel cell vehicle control", 
    "LiDAR perception"
]
ARXIV_API_URL = 'http://export.arxiv.org/api/query'
HIGH_VALUE_TERMS = {
    "fuel cell": 0.18,
    "formula student": 0.18,
    "fsae": 0.16,
    "autonomous": 0.12,
    "lidar": 0.12,
    "path planning": 0.12,
    "cone detection": 0.10,
    "hydrogen": 0.10,
}

def fetch_recent_papers(keyword, max_results=5):
    query = urllib.parse.quote(keyword)
    url = f"{ARXIV_API_URL}?search_query=all:{query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    
    try:
        response = urllib.request.urlopen(url)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        papers = []
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title = entry.find('{http://www.w3.org/2005/Atom}title').text.replace('\n', ' ')
            summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.replace('\n', ' ')
            published = entry.find('{http://www.w3.org/2005/Atom}published').text
            link = entry.find('{http://www.w3.org/2005/Atom}id').text
            
            papers.append({
                "title": title,
                "summary": summary,
                "published": published,
                "link": link,
                "keyword": keyword
            })
        return papers
    except Exception as e:
        print(f"arXiv'den veri çekerken hata: {e}")
        return []

def publish_to_pubsub(paper):
    if not pubsub_v1:
        print("[ARXIV] google-cloud-pubsub kurulu degil; yayin atlandi.")
        return False
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

    importance_score = score_paper_importance(paper)
    
    message_data = {
        "source": "arxiv",
        "type": "research_paper",
        "data": paper,
        "importance_score": importance_score,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    data_str = json.dumps(message_data).encode("utf-8")
    future = publisher.publish(topic_path, data_str)
    print(f"Yayınlandı: {paper['title'][:50]}... | Msg ID: {future.result()} | Skor: {importance_score}")
    return True

def score_paper_importance(paper: dict) -> float:
    text = f"{paper.get('title', '')} {paper.get('summary', '')} {paper.get('keyword', '')}".lower()
    score = 0.35
    for term, weight in HIGH_VALUE_TERMS.items():
        if term in text:
            score += weight
    try:
        published = datetime.fromisoformat(paper.get("published", "").replace("Z", "+00:00"))
        age_days = max(0, (datetime.now(published.tzinfo) - published).days)
        if age_days <= 14:
            score += 0.12
        elif age_days <= 60:
            score += 0.06
    except Exception:
        pass
    return round(min(score, 0.99), 2)

def scan_arxiv():
    print(f"[{datetime.now()}] arXiv taraması başlatılıyor...")
    all_papers = []
    
    for kw in KEYWORDS:
        print(f"Aranıyor: {kw}")
        papers = fetch_recent_papers(kw, max_results=3)
        all_papers.extend(papers)
        # arXiv API rate limit koruması
        time.sleep(3)
        
    for paper in all_papers:
        publish_to_pubsub(paper)
        
    print(f"[{datetime.now()}] Toplam {len(all_papers)} makale bulundu ve Pub/Sub'a iletildi.")

if __name__ == "__main__":
    scan_arxiv()
