import csv
import os
import json

class VehicleParams:
    def __init__(self, compute, sensors, powertrain, safety):
        self.compute = compute
        self.sensors = sensors
        self.powertrain = powertrain
        self.safety = safety

def load_vehicle_params() -> VehicleParams:
    """
    Reads from data/blueprint/parts.csv and returns structured VehicleParams.
    """
    csv_path = os.path.join("data", "blueprint", "parts.csv")
    
    # Defaults according to requirements
    params = {
        "compute": {
            "onboard_computer": "NVIDIA Jetson AGX Xavier",
            "compute_power_w": 30
        },
        "sensors": {
            "lidar": "Ouster OS0-128",
            "lidar_range_m": 50,
            "camera": "ZED 2i",
            "imu": "ADIS16480BMLZ"
        },
        "powertrain": {
            "fc_max_power_w": 5000,
            "battery_capacity_wh": 2000,
            "motor_peak_power_w": 20000,
            "dc_dc_efficiency": 0.94
        },
        "safety": {
            "h2_alarm_threshold_pct_lfl": 0.1,
            "h2_shutdown_threshold_pct_lfl": 0.25,
            "hv_isolation_threshold_ohm_per_v": 500
        }
    }

    try:
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("Name", "")
                    prod_name = row.get("Product Name", "")
                    
                    if name == "Autonomous Onboard Computer":
                        params["compute"]["onboard_computer"] = prod_name
                    elif name == "LiDAR Unit":
                        params["sensors"]["lidar"] = prod_name.replace(" Sensor", "")
                    elif name == "Front Stereo Camera":
                        params["sensors"]["camera"] = prod_name.replace("StereoLabs ", "").replace(" Stereo Camera", "")
                    elif name == "High-Frequency IMU":
                        params["sensors"]["imu"] = prod_name.replace("Analog Devices ", "")
    except Exception as e:
        print(f"Error reading blueprint: {e}")
        
    return VehicleParams(
        compute=params["compute"],
        sensors=params["sensors"],
        powertrain=params["powertrain"],
        safety=params["safety"]
    )

if __name__ == "__main__":
    p = load_vehicle_params()
    print(f"Compute: {p.compute}")
    print(f"Sensors: {p.sensors}")
    print(f"Powertrain: {p.powertrain}")
    print(f"Safety: {p.safety}")
