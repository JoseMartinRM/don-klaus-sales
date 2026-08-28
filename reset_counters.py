import sqlite3
from config import config

def reset_all_counters():
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads")
    cursor.execute("DELETE FROM activity_logs")
    cursor.execute("DELETE FROM conversations")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('leads', 'activity_logs', 'conversations')")
    conn.commit()
    conn.close()
    print("[OK] Tablas de leads, activity_logs y conversations reseteadas a 0.")

if __name__ == "__main__":
    reset_all_counters()
