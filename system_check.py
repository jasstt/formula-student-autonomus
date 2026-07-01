import sys, os
sys.stdout.reconfigure(encoding='utf-8')

results = {}

print('=' * 55)
print('AGU FCEV MULTI-AGENT SISTEM KONTROLU')
print('=' * 55)

# 1. EVENT BUS
print('\n[1] EVENT BUS')
try:
    from agents.event_bus.event_definitions import FCEVEvent, EventPayload
    from agents.event_bus.event_router import route_event
    print(f'  FCEVEvent: {len(FCEVEvent)} event tanimli OK')
    results['event_bus'] = True
except Exception as e:
    print(f'  HATA: {e}')
    results['event_bus'] = False

# 2. LSTM
print('\n[2] LSTM ANOMALY DETECTOR')
try:
    from agents.ml.lstm_anomaly_detector import SensorLSTM, SponsorResponseLSTM
    s = SensorLSTM()
    loaded = s.load_model()
    status_str = 'YUKLU' if loaded else 'MODEL YOK (fallback aktif)'
    print(f'  SensorLSTM model: {status_str}')
    pred = s.mock_predict(1)[0]
    print(f'  Mock tahmin: score={pred["anomaly_score"]:.3f}, type={pred["anomaly_type"]}')
    results['lstm'] = True
except Exception as e:
    print(f'  HATA: {e}')
    results['lstm'] = False

# 3. CHIEF ENGINEER
print('\n[3] CHIEF ENGINEER AGENT')
try:
    from agents.chief_engineer.main import ChiefEngineerAgent
    agent = ChiefEngineerAgent()
    agent.update_state(fc_temperature_c=78, battery_soc=0.35, motor_demanded_power_w=15000)
    dec = agent._rule_based_fallback()
    print(f'  ChiefEngineer OK | fc_ratio={dec["fc_power_ratio"]} | conf={dec["confidence"]}')
    results['chief'] = True
except Exception as e:
    print(f'  HATA: {e}')
    results['chief'] = False

# 4. TECHNICAL AGENTS
print('\n[4] TECHNICAL AGENTS')
try:
    from agents.technical.structural_analysis_agent import analyze_weight_distribution
    r = analyze_weight_distribution(mock=True)
    print(f'  Structural: kute={r["total_mass_kg"]}kg, CoG_Z={r["cog_z_mm"]}mm OK')
    results['structural'] = True
except Exception as e:
    print(f'  Structural HATA: {e}')
    results['structural'] = False

try:
    from agents.technical.electrical_safety_agent import check_hv_compliance
    r = check_hv_compliance(mock=True)
    print(f'  Electrical: uyumlu={r["compliant"]} OK')
    results['electrical'] = True
except Exception as e:
    print(f'  Electrical HATA: {e}')
    results['electrical'] = False

try:
    from agents.technical.hydrogen_safety_agent import monitor_hydrogen_system
    r = monitor_hydrogen_system(mock=True)
    print(f'  H2 Safety: seviye={r["overall_level"]} OK')
    results['h2'] = True
except Exception as e:
    print(f'  H2 HATA: {e}')
    results['h2'] = False

try:
    from agents.technical.performance_optimizer import optimize_race_strategy
    r = optimize_race_strategy(mock=True)
    print(f'  PerfOpt: fc_ratio={r["optimal_fc_power_ratio"]} OK')
    results['perf'] = True
except Exception as e:
    print(f'  PerfOpt HATA: {e}')
    results['perf'] = False

# 5. 3-PILLAR
print('\n[5] 3-PILLAR SISTEM')
try:
    from agents.sponsor.outreach_agent import batch_outreach
    print('  Pillar 1 (Sponsor): OK')
    results['pillar1'] = True
except Exception as e:
    print(f'  Pillar 1 HATA: {e}')
    results['pillar1'] = False

try:
    from agents.social_media.scheduler import schedule_weekly_content
    print('  Pillar 2 (Social): OK')
    results['pillar2'] = True
except Exception as e:
    print(f'  Pillar 2 HATA: {e}')
    results['pillar2'] = False

try:
    from agents.analysis.code_improvement_agent import analyze_autonomous_code
    print('  Pillar 3 (Code): OK')
    results['pillar3'] = True
except Exception as e:
    print(f'  Pillar 3 HATA: {e}')
    results['pillar3'] = False

# 6. DOSYALAR
print('\n[6] SPRINT 3 DOSYALARI')
files = [
    'agents/event_bus/__init__.py',
    'agents/event_bus/event_definitions.py',
    'agents/event_bus/event_router.py',
    'agents/ml/__init__.py',
    'agents/ml/lstm_anomaly_detector.py',
    'agents/ml/lstm_trainer.py',
    'agents/chief_engineer/__init__.py',
    'agents/chief_engineer/main.py',
    'agents/chief_engineer/system_monitor.py',
    'agents/chief_engineer/report_generator.py',
    'agents/technical/__init__.py',
    'agents/technical/structural_analysis_agent.py',
    'agents/technical/electrical_safety_agent.py',
    'agents/technical/hydrogen_safety_agent.py',
    'agents/technical/performance_optimizer.py',
    'models/sensor_lstm.pt',
    'data/training/sensor_sequences.csv',
    'test_motor_scenario.py',
]
ok_count = sum(1 for f in files if os.path.exists(f))
print(f'  {ok_count}/{len(files)} dosya mevcut')
for f in files:
    if not os.path.exists(f):
        print(f'  [EKSIK] {f}')
    else:
        sz = os.path.getsize(f)
        print(f'  [OK] {f} ({sz} bytes)')

# OZET
print('\n' + '=' * 55)
total_ok = sum(results.values())
print(f'SISTEM OZETI: {total_ok}/{len(results)} modul aktif')
ok_mods = [k for k, v in results.items() if v]
fail_mods = [k for k, v in results.items() if not v]
if ok_mods:
    print(f'  AKTIF  : {", ".join(ok_mods)}')
if fail_mods:
    print(f'  HATA   : {", ".join(fail_mods)}')
print('=' * 55)
