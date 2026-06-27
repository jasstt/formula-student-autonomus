import random

class PerceptionSimulator:
    def __init__(self):
        pass

    def apply_sensor_noise(self, distance_m, noise_level=0.05):
        """
        Dijital Twin simülasyonu için stokastik sensör gürültüsü.
        Sensör ölçümünü taklit etmek için gerçek mesafeye rastgele sapma ekler.
        """
        noise = random.uniform(-noise_level, noise_level)
        # Hata payını gerçek mesafeyle orantılı olarak da büyütebiliriz
        proportional_noise = distance_m * random.uniform(-0.02, 0.02)
        
        simulated_distance = distance_m + noise + proportional_noise
        return max(0.0, round(simulated_distance, 2))

    def process_ground_truth(self, ground_truth_cones):
        """
        Ground truth (gerçek) koni listesini alır, 
        sanki kameradan geçmiş gibi gürültü ekleyerek geri döner.
        """
        simulated_detections = []
        
        for cone in ground_truth_cones:
            # Bazen koni hiç tespit edilemeyebilir (False Negative)
            if random.random() < 0.05: # %5 ihtimalle koniyi kaçır
                continue
                
            dist_x = cone["position_3d"]["x"]
            dist_y = cone["position_3d"]["y"]
            
            simulated_dist_x = self.apply_sensor_noise(dist_x)
            simulated_dist_y = self.apply_sensor_noise(dist_y, noise_level=0.02)
            
            sim_cone = {
                "color": cone["color"],
                "confidence": round(random.uniform(0.70, 0.99), 2),
                "position_3d": {
                    "x": simulated_dist_x,
                    "y": simulated_dist_y,
                    "z": 0.0
                }
            }
            simulated_detections.append(sim_cone)
            
        return simulated_detections
