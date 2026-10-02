import sys
sys.path.insert(0, ".")

from backend.sop_engine import load_sops, match_sops

sops = load_sops()
print(f"Loaded {len(sops)} SOPs\n")

weather = {
    "wind_speed_10m": 50, "temperature_2m": 30, "precipitation": 0,
    "uv_index": 5, "current_hour": 14, "wind_gusts_10m": 60,
    "precipitation_probability": 10, "visibility": 10000,
}
matched = match_sops(weather, ["cycling", "bike"], sops)
print("=== Test 1: High wind + cycling ===")
for m in matched:
    print(f"  {m['sop_id']} ({m['severity']}): {m['title']}")
assert any(m["sop_id"] == "SOP-002" for m in matched), "SOP-002 should match!"
print("  PASS\n")

weather2 = {
    "temperature_2m": 38, "wind_speed_10m": 8, "precipitation": 0,
    "uv_index": 6, "current_hour": 15, "wind_gusts_10m": 12,
    "precipitation_probability": 5, "visibility": 12000,
}
matched2 = match_sops(weather2, ["child", "children", "park"], sops)
print("=== Test 2: Heat + children ===")
for m in matched2:
    print(f"  {m['sop_id']} ({m['severity']}): {m['title']}")
assert any(m["sop_id"] == "SOP-008" for m in matched2), "SOP-008 should match!"
print("  PASS\n")

weather3 = {
    "temperature_2m": 30, "wind_speed_10m": 8, "precipitation": 0,
    "uv_index": 3, "current_hour": 10, "wind_gusts_10m": 12,
    "precipitation_probability": 10, "visibility": 20000,
}
matched3 = match_sops(weather3, ["indoor", "swimming"], sops)
print("=== Test 3: Indoor swimming (benign weather) ===")
print(f"  Matched: {len(matched3)} SOPs")
assert len(matched3) == 0, "No SOP should match for indoor swimming in benign weather!"
print("  PASS\n")

weather4 = {
    "temperature_2m": 25, "wind_speed_10m": 40, "precipitation": 20,
    "uv_index": 2, "current_hour": 14, "wind_gusts_10m": 55,
    "precipitation_probability": 90, "visibility": 3000,
}
matched4 = match_sops(weather4, ["walk", "walking"], sops)
print("=== Test 4: Severe weather (precip=20mm, wind=40km/h) ===")
for m in matched4:
    print(f"  {m['sop_id']} ({m['severity']}): {m['title']}")
assert any(m["sop_id"] == "SOP-012" for m in matched4), "SOP-012 (severe override) should match!"
assert matched4[0]["severity"] == "critical", "Critical SOP should be first!"
print("  PASS\n")

print("All SOP matching tests passed!")
