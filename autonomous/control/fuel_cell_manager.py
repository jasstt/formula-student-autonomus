import random

class FuelCellManager:
    def __init__(self):
        # FS için standart parametreler (Örnek)
        self.fc_max_power_kw = 8.5       # Hidrojen Yakıt hücresi max gücü
        self.battery_capacity_kwh = 6.0  # Akümülatör kapasitesi
        
        # Anlık durum (State)
        self.current_soc_percent = 100.0 # Batarya doluluk oranı (%)
        self.fc_output_kw = 0.0          # Yakıt hücresinin anlık üretimi
        
    def compute_power_distribution(self, torque_demand_kw, dt_seconds):
        """
        Talep edilen gücü (motorların çektiği) karşılamak için
        Batarya ve Fuel Cell arasındaki enerji dengelemesini yapar (Low-level controller).
        
        Args:
            torque_demand_kw (float): Motorların talep ettiği toplam güç (kW). Negatif ise rejeneratif frenleme.
            dt_seconds (float): Zaman adımı.
        """
        # Stokastik sensör hataları (Gerçek araçta ölçümler hafif sapar)
        measured_soc = self.current_soc_percent + random.uniform(-0.5, 0.5)
        
        # Basit Kural (Rule-Based Control):
        # 1. SOC %80 altındaysa Fuel Cell maksimum kapasitede şarj etmeye çalışsın
        # 2. SOC %95 üzerindeyse Fuel Cell'i kıs (israfı önle)
        target_fc_output = 0.0
        
        if measured_soc < 80.0:
            target_fc_output = self.fc_max_power_kw
        elif measured_soc > 95.0:
            target_fc_output = self.fc_max_power_kw * 0.2 # Rölanti veya düşük güç
        else:
            # Orantısal (P-control) bir bölge
            # 80-95 arası, %80'de max, %95'te %20 güce düşecek şekilde lineer interpolasyon
            ratio = (95.0 - measured_soc) / (95.0 - 80.0)
            target_fc_output = self.fc_max_power_kw * (0.2 + 0.8 * ratio)
            
        # Dinamik sınır: Yakıt hücresi anında max güce çıkamaz (slew rate)
        # Burada basitçe bir step gecikmesi simüle ediyoruz
        if target_fc_output > self.fc_output_kw:
            self.fc_output_kw = min(self.fc_output_kw + 1.0, target_fc_output) # Yavaş artış
        else:
            self.fc_output_kw = max(self.fc_output_kw - 2.0, target_fc_output) # Daha hızlı düşüş
            
        # Enerji Bilançosu: Bataryadan çekilen veya bataryaya dolan enerji (kW)
        # Power_net = FuelCell_Power - TorqueDemand
        net_power_kw = self.fc_output_kw - torque_demand_kw
        
        # Eğer net güç pozitifse batarya şarj olur, negatifse deşarj olur
        energy_kwh = net_power_kw * (dt_seconds / 3600.0)
        
        # SOC Güncellemesi
        soc_change = (energy_kwh / self.battery_capacity_kwh) * 100.0
        self.current_soc_percent = max(0.0, min(100.0, self.current_soc_percent + soc_change))
        
        return {
            "demand_kw": torque_demand_kw,
            "fc_output_kw": round(self.fc_output_kw, 2),
            "battery_soc": round(self.current_soc_percent, 2),
            "net_power_kw": round(net_power_kw, 2)
        }

if __name__ == "__main__":
    manager = FuelCellManager()
    
    print("Fuel Cell Manager Basit Simülasyonu:")
    # Aracın hızlandığı (yüksek güç talebi) bir periyot (1 saniye)
    for i in range(5):
        res = manager.compute_power_distribution(torque_demand_kw=20.0, dt_seconds=1.0)
        print(f"Adım {i+1} [Hızlanma]: {res}")
        
    # Aracın yavaşladığı (rejeneratif fren) bir periyot (1 saniye)
    for i in range(5):
        res = manager.compute_power_distribution(torque_demand_kw=-5.0, dt_seconds=1.0)
        print(f"Adım {i+6} [Rejeneratif Fren]: {res}")
