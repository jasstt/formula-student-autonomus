import sys
import json
from unittest.mock import patch, MagicMock

print("--- TESTING Analysis Agent ---")
try:
    from agents.analysis.main import AnalysisAgent
    
    agent = AnalysisAgent()
    
    # Test arxiv data
    arxiv_data = {"title": "New Path Planning Algo FSAE"}
    res_arxiv = agent.analyze_arxiv_data(arxiv_data, 0.9)
    print(f"arXiv Test Result: {res_arxiv}")
    
    # Test telemetry anomaly
    tel_data = {"sensor_id": "fuel_cell_temp_c"}
    res_tel = agent.analyze_telemetry_anomaly(tel_data, 9.5)
    print(f"Telemetry Test Result: {res_tel}")
    
    print("Analysis Agent SUCCESS")
except Exception as e:
    print(f"Analysis Agent FAILED: {e}")

print("\n--- TESTING Digital Twin Vehicle Model ---")
try:
    from digital_twin.vehicle_model import DigitalTwinVehicle
    
    twin = DigitalTwinVehicle()
    mock_config = {
        "max_speed_kph": 110.0,
        "power_limit_kw": 75.0
    }
    
    res = twin.simulate_lap(1000.0, mock_config)
    print(f"Simulate Lap Result: {res}")
    print("Digital Twin SUCCESS")
except Exception as e:
    print(f"Digital Twin FAILED: {e}")

print("\n--- TESTING Fuel Cell Manager ---")
try:
    from autonomous.control.fuel_cell_manager import FuelCellManager
    
    manager = FuelCellManager()
    res = manager.compute_power_distribution(torque_demand_kw=20.0, dt_seconds=1.0)
    print(f"Power Distribution Result: {res}")
    print("Fuel Cell Manager SUCCESS")
except Exception as e:
    print(f"Fuel Cell Manager FAILED: {e}")
