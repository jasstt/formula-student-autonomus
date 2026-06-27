import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import time
from datetime import datetime, timedelta
from google.cloud import pubsub_v1
import random

# Google Cloud Project Info
PROJECT_ID = "YOUR_PROJECT_ID"
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
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    
    # Sistemin stokastik karar alma mekanizması için güven/önem skoru ekle
    # (Örn: Makale başlığındaki özel terimlere göre veya rastgele ağırlıklarla)
    importance_score = round(random.uniform(0.4, 0.95), 2)
    
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
