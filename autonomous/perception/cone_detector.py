import cv2
import numpy as np
from ultralytics import YOLO
import json

# YOLOv8 nano modeli - hafif ve gerçek zamanlı işlem için
# Not: Eğitimli bir 'best.pt' modeli kullanılmalıdır (koni renkleri için).
# Burada temsili olarak yolov8n yükleniyor.
MODEL_PATH = "yolov8n.pt"

class ConeDetector:
    def __init__(self, model_path=MODEL_PATH, conf_threshold=0.7):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        
        # Sınıf eşleşmeleri (Varsayılan olarak modelin nasıl eğitildiğine bağlıdır)
        self.class_names = {
            0: "blue_cone",
            1: "yellow_cone",
            2: "orange_cone",
            3: "large_orange_cone"
        }
        
    def estimate_distance(self, bbox, img_width, img_height):
        """
        Kamera matrisine ve bounding box boyutlarına göre deterministik mesafe tahmini.
        Fiziksel koni boyutu (yaklaşık): Genişlik 228mm, Yükseklik 325mm (FS standart)
        """
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        
        # Basit pinhole kamera modeli (temsili odak uzaklığı f = 800)
        focal_length = 800
        real_cone_height_m = 0.325
        
        # Eğer bounding box geçersizse
        if h <= 0:
            return -1.0
            
        distance_m = (real_cone_height_m * focal_length) / h
        
        return round(distance_m, 2)

    def process_frame(self, frame):
        """
        Gelen görüntüyü işler ve koni konumlarını döner.
        """
        img_h, img_w = frame.shape[:2]
        
        # YOLOv8 inference
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        
        detected_cones = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Koordinatlar
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # İsimlendirme (Eğer sınıf dışındaysa unknown ata)
                color = self.class_names.get(cls_id, "unknown")
                
                # Mesafe tahmini
                dist = self.estimate_distance((x1, y1, x2, y2), img_w, img_h)
                
                # Aracın merkezine göre x,y tahmini (Basit 2D projeksiyon)
                # Kamera ekseninde x=ileri, y=sağ/sol gibi düşünülürse
                # Piksel merkezine göre sapma:
                cx = (x1 + x2) / 2
                dx = (cx - img_w/2) / (img_w/2) # -1 (sol) to 1 (sağ)
                
                lateral_offset = dx * dist * 0.5 # Temsili yanal uzaklık hesabı
                
                detected_cones.append({
                    "color": color,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "position_3d": {
                        "x": dist, # ileri mesafe
                        "y": lateral_offset, # yanal mesafe
                        "z": 0.0 # yer düzlemi
                    }
                })
                
        return detected_cones

if __name__ == "__main__":
    # Test bloğu
    print("Cone Detector başlatılıyor...")
    detector = ConeDetector()
    
    # Dummy frame oluştur (640x480 siyah ekran)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Rastgele bounding box oluşturup model simülasyonu yapamayız (YOLO çalışır)
    # Çıktı formatını göstermek için çalıştır
    res = detector.process_frame(dummy_frame)
    print(f"Bulunan koniler: {json.dumps(res, indent=2)}")
