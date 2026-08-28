import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from database import list_activity_logs, get_settings, list_campaigns

print("=== 1. SETTINGS EN BASE DE DATOS ===")
settings = get_settings()
for k, v in settings.items():
    if "token" in k or "key" in k:
        print(f"  {k}: {v[:10]}... (len {len(v)})" if v else f"  {k}: [VACIO]")
    else:
        print(f"  {k}: {v}")

print("\n=== 2. CAMPAÑAS ACTIVAS ===")
campaigns = list_campaigns()
for c in campaigns:
    print(f"  ID: {c['id']}, Nombre: {c['name']}, Activa: {c['is_active']}, Keywords: {c['keywords']}")

print("\n=== 3. ÚLTIMOS 15 LOGS REGISTRADOS ===")
logs = list_activity_logs(limit=15)
for l in logs:
    print(f"  [{l['created_at']}] [{l['event_type']}] {l['details']}")
