import random
import math

class DigitalTwinVehicle:
    def __init__(self):
        # FS standartlarında temsili araç parametreleri
        self.mass_kg = 250.0
        self.drag_coefficient = 0.8
        self.frontal_area = 1.0
        self.air_density = 1.225
        
        # Güç sistemi
        self.battery_capacity_kwh = 6.0
        self.fuel_cell_max_power_kw = 8.5
        
    def simulate_lap(self, track_length_m, proposed_config):
        """
        Gelen konfigürasyona (Analysis Agent'tan) göre basit fiziksel formüller 
        ve stokastik gürültülerle bir turu simüle eder.
        """
        # Konfigürasyondan parametreleri al
        max_speed_kph = proposed_config.get("max_speed_kph", 100.0)
        power_limit_kw = proposed_config.get("power_limit_kw", 60.0)
        
        # Max hız m/s
        max_speed_ms = max_speed_kph / 3.6
        
        # Basit ortalama hız tahmini (Motor gücü ve hız limiti tabanlı)
        # Ne kadar agresif kısıtlanmışsa o kadar yavaş
        power_factor = min(power_limit_kw / 80.0, 1.0)
        avg_speed_ms = max_speed_ms * 0.65 * power_factor
        
        # Stokastik hava durumu/sürtünme varyansı (Track condition)
        track_friction_noise = random.uniform(0.95, 1.05)
        avg_speed_ms *= track_friction_noise
        
        # 0'a bölme hatasını önle
        avg_speed_ms = max(avg_speed_ms, 5.0) 
        
        lap_time_s = track_length_m / avg_speed_ms
        
        # Enerji tüketimi tahmini: E = Integral(F_drag * v * dt)
        # F_drag = 0.5 * rho * v^2 * Cd * A
        f_drag = 0.5 * self.air_density * (avg_speed_ms**2) * self.drag_coefficient * self.frontal_area
        energy_joules = f_drag * track_length_m
        energy_kwh = energy_joules / 3.6e6
        
        # Rastgele sensör gürültüsü ve isinma kayiplari
        thermal_loss = random.uniform(1.05, 1.15)
        total_energy_consumed_kwh = energy_kwh * thermal_loss
        
        return {
            "lap_time_s": round(lap_time_s, 2),
            "energy_consumed_kwh": round(total_energy_consumed_kwh, 3),
            "avg_speed_kph": round(avg_speed_ms * 3.6, 2),
            "success": True if total_energy_consumed_kwh < self.battery_capacity_kwh else False
        }

if __name__ == "__main__":
    twin = DigitalTwinVehicle()
    mock_config = {
        "max_speed_kph": 110.0,
        "power_limit_kw": 75.0
    }
    
    # 22km dayaniklilik pisti temsili (FS Endurance: 22000m)
    # Burada tek tur (yaklaşık 1km) testi
    result = twin.simulate_lap(1000.0, mock_config)
    print("Digital Twin Test Result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
