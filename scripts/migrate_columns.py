import sqlite3

def migrate():
    conn = sqlite3.connect('coordinator.db')
    cursor = conn.cursor()

    def add_col(table, col, col_type):
        cols = [x[1] for x in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            print(f"Adding {col} to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

    add_col('workers', 'cpu_count_logical', 'INTEGER DEFAULT 1')
    add_col('workers', 'cpu_count_physical', 'INTEGER DEFAULT 1')
    add_col('workers', 'disk_total_bytes', 'INTEGER DEFAULT 0')
    add_col('workers', 'disk_used_bytes', 'INTEGER DEFAULT 0')
    add_col('workers', 'disk_free_bytes', 'INTEGER DEFAULT 0')
    add_col('workers', 'disk_percent', 'REAL DEFAULT 0.0')
    add_col('workers', 'websync_available_ram_bytes', 'INTEGER DEFAULT 0')
    add_col('workers', 'configured_max_cpu_percent', 'REAL DEFAULT 90.0')
    add_col('workers', 'configured_min_available_ram_mb', 'INTEGER DEFAULT 512')

    add_col('jobs', 'parent_job_id', 'TEXT DEFAULT NULL')

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_jobs_parent_job_id ON jobs(parent_job_id)")

    conn.commit()
    conn.close()
    print("Database migration successfully applied.")

if __name__ == "__main__":
    migrate()
