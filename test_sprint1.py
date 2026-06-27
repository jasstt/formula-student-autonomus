import sys
import json
from unittest.mock import patch, MagicMock

print("--- TESTING arxiv_scanner.py ---")
try:
    from agents.surveillance.sources import arxiv_scanner
    
    # Mock arXiv response
    mock_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Test Autonomous Driving</title>
            <summary>A summary.</summary>
            <published>2026-06-27T00:00:00Z</published>
            <id>http://arxiv.org/abs/1234.5678</id>
        </entry>
    </feed>
    """
    
    with patch('urllib.request.urlopen') as mock_urlopen, \
         patch('google.cloud.pubsub_v1.PublisherClient') as mock_pub:
        
        mock_response = MagicMock()
        mock_response.read.return_value = mock_xml
        mock_urlopen.return_value = mock_response
        
        mock_publisher_instance = MagicMock()
        mock_publisher_instance.publish.return_value.result.return_value = "msg-12345"
        mock_pub.return_value = mock_publisher_instance
        
        # Sadece bir anahtar kelime ile test edelim süreyi kısaltmak için
        arxiv_scanner.KEYWORDS = ["test keyword"]
        arxiv_scanner.scan_arxiv()
        print("arxiv_scanner.py SUCCESS")
except Exception as e:
    print(f"arxiv_scanner.py FAILED: {e}")

print("\n--- TESTING telemetry_stream.py ---")
try:
    from agents.surveillance.sources import telemetry_stream
    
    # Mock message
    mock_message = MagicMock()
    mock_message.data = json.dumps({
        "sensor_id": "fuel_cell_temp_c",
        "value": 100.0, # Anomaly (mean 65, std 5)
        "vehicle_id": "FSAE-1"
    }).encode("utf-8")
    
    with patch('google.cloud.pubsub_v1.PublisherClient') as mock_pub:
        mock_publisher_instance = MagicMock()
        mock_publisher_instance.publish.return_value = None
        mock_pub.return_value = mock_publisher_instance
        
        telemetry_stream.process_telemetry_message(mock_message)
        mock_message.ack.assert_called_once()
        print("telemetry_stream.py SUCCESS")
except Exception as e:
    print(f"telemetry_stream.py FAILED: {e}")

print("\n--- TESTING cone_detector.py ---")
try:
    from autonomous.perception.cone_detector import ConeDetector
    import numpy as np
    
    # We mock YOLO to avoid downloading the model or raising errors if ultralytics is missing
    with patch('autonomous.perception.cone_detector.YOLO') as mock_yolo:
        mock_model_instance = MagicMock()
        
        # Mock result
        mock_result = MagicMock()
        mock_box = MagicMock()
        # [x1, y1, x2, y2]
        mock_box.xyxy = [[100, 100, 200, 300]]
        mock_box.conf = [0.85]
        mock_box.cls = [1] # yellow_cone
        mock_result.boxes = [mock_box]
        
        mock_model_instance.return_value = [mock_result]
        mock_yolo.return_value = mock_model_instance
        
        detector = ConeDetector()
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cones = detector.process_frame(dummy_frame)
        print(f"Detected cones: {json.dumps(cones, indent=2)}")
        print("cone_detector.py SUCCESS")
except ImportError as ie:
    print(f"cone_detector.py FAILED (ImportError): {ie}. Make sure 'ultralytics' and 'opencv-python' are installed.")
except Exception as e:
    print(f"cone_detector.py FAILED: {e}")
