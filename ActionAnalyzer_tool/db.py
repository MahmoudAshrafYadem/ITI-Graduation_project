"""
db.py — Database layer for Dolt / PyMySQL connectivity.

HOW TO CONFIGURE
────────────────
1.  Start your Dolt SQL server:
        dolt sql-server --host=127.0.0.1 --port=3306 --user=root

2.  Update DB_CONFIG below with your actual credentials.

3.  The module falls back to synthetic mock data automatically when
    USE_MOCK_DATA = True.  Set it to False once your server is running.
"""

import pymysql
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings

# ══════════════════════════════════════════════════════════════════════
#  CONNECTION CONFIGURATION  ← plug your Dolt server details here
# ══════════════════════════════════════════════════════════════════════

DB_CONFIG: dict = {
    "host": "127.0.0.1",  # Dolt SQL server host
    "port": 3306,  # Default Dolt SQL-server port
    "user": "root",  # Dolt SQL-server user
    "password": "",  # Leave empty if no password is set
    "database": "network_db",  # Dolt database / repo name
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 5,
}

# ── Toggle mock data fallback ──────────────────────────────────────────
USE_MOCK_DATA: bool = True

# Non-KPI columns always excluded from schema discovery
NON_KPI_COLUMNS: set[str] = {
    "id",
    "timestamp",
    "cell_id",
    "node_id",
    "site_id",
    "sector_id",
    "enb_id",
    "gnb_id",
    "region",
    "vendor",
    "date",
    "hour",
    "created_at",
    "updated_at",
}


# ══════════════════════════════════════════════════════════════════════
#  MOCK DATA GENERATORS
# ══════════════════════════════════════════════════════════════════════


def _mock_kpi_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Synthetic KPI data at 15-minute granularity for [start_date, end_date].
    Injects a realistic post-optimisation uplift on dates ≥ action_date.
    """
    rng = pd.date_range(start=start_date, end=end_date + " 23:45:00", freq="15min")
    n = len(rng)
    np.random.seed(42)

    hour_pattern = np.array([rng[i].hour + rng[i].minute / 60 for i in range(n)])
    diurnal = 1 + 0.6 * np.sin(np.pi * (hour_pattern - 8) / 12) * (
        (hour_pattern >= 8) & (hour_pattern <= 20)
    )

    # All dates strictly after the start are treated as "post-action"
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    is_post = pd.Series(rng).dt.date > start_dt.date()

    df = pd.DataFrame({"timestamp": rng})
    df["cell_id"] = "CELL_001"

    def noise(scale):
        return np.random.normal(0, scale, n)

    df["throughput_dl_mbps"] = np.clip(
        50 * diurnal + noise(5) + is_post.values * 8, 5, 150
    )
    df["throughput_ul_mbps"] = np.clip(
        20 * diurnal + noise(2) + is_post.values * 3, 2, 60
    )
    df["drop_rate_pct"] = np.clip(
        2.5 / diurnal + noise(0.3) - is_post.values * 0.4, 0.0, 10.0
    )
    df["rach_success_rate_pct"] = np.clip(
        95 * diurnal / diurnal.mean() + noise(1.5) + is_post.values * 1.2, 60.0, 100.0
    )
    df["avg_cqi"] = np.clip(
        9 * diurnal / diurnal.mean() + noise(0.8) + is_post.values * 0.5, 1.0, 15.0
    )
    df["bler_dl_pct"] = np.clip(
        3 / diurnal + noise(0.4) - is_post.values * 0.5, 0.0, 20.0
    )
    df["latency_ms"] = np.clip(
        25 / diurnal + noise(2) - is_post.values * 2.5, 5.0, 120.0
    )
    df["prb_utilization_pct"] = np.clip(
        60 * diurnal / diurnal.mean() + noise(5), 5.0, 100.0
    )
    df["handover_success_rate_pct"] = np.clip(
        97 + noise(0.8) + is_post.values * 0.6, 85.0, 100.0
    )
    df["sinr_db"] = 12 * diurnal / diurnal.mean() + noise(1.5) + is_post.values * 0.8

    return df


def _mock_dolt_log() -> pd.DataFrame:
    """
    Fabricated Dolt commit log with rich metadata:
    commit_hash, committer, email, date, message.
    Five hunks across ~30 days.
    """
    base = datetime(2024, 5, 20, 9, 0, 0)

    commits = [
        # Hunk 1 — May 22
        {
            "days": 2,
            "hours": 0,
            "committer": "ali.hassan",
            "email": "ali@carrier.net",
            "msg": "Adjust antenna tilt sector 3",
        },
        {
            "days": 2,
            "hours": 2,
            "committer": "ali.hassan",
            "email": "ali@carrier.net",
            "msg": "Update TX power config sector 3",
        },
        {
            "days": 2,
            "hours": 4,
            "committer": "netops-robot",
            "email": "bot@carrier.net",
            "msg": "Enable CA band 3+7 cell 001",
        },
        # Hunk 2 — May 27
        {
            "days": 7,
            "hours": 1,
            "committer": "sara.farouk",
            "email": "sara@carrier.net",
            "msg": "RACH root sequence re-configuration",
        },
        # Hunk 3 — June 3
        {
            "days": 14,
            "hours": 0,
            "committer": "khaled.nasser",
            "email": "khaled@carrier.net",
            "msg": "Handover parameter tuning batch A",
        },
        {
            "days": 14,
            "hours": 1,
            "committer": "khaled.nasser",
            "email": "khaled@carrier.net",
            "msg": "Handover parameter tuning batch B",
        },
        # Hunk 4 — June 10
        {
            "days": 21,
            "hours": 3,
            "committer": "netops-robot",
            "email": "bot@carrier.net",
            "msg": "Scheduler weight optimization",
        },
        {
            "days": 21,
            "hours": 4,
            "committer": "ali.hassan",
            "email": "ali@carrier.net",
            "msg": "Enable MIMO rank override",
        },
        {
            "days": 21,
            "hours": 5,
            "committer": "sara.farouk",
            "email": "sara@carrier.net",
            "msg": "QoS profile update — VoLTE",
        },
        # Hunk 5 — June 17
        {
            "days": 28,
            "hours": 2,
            "committer": "khaled.nasser",
            "email": "khaled@carrier.net",
            "msg": "Neighbor cell relation audit",
        },
    ]

    rows = []
    for i, c in enumerate(commits):
        dt = base + timedelta(days=c["days"], hours=c["hours"])
        rows.append(
            {
                "commit_hash": f"a{i:02x}b{i * 3 + 7:02x}c{i * 7 + 1:04x}",
                "committer": c["committer"],
                "email": c["email"],
                "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "message": c["msg"],
            }
        )
    return pd.DataFrame(rows)


def _mock_dolt_diff(commit_hash: str) -> list[dict]:
    """
    Simulate dolt_diff output for a given commit hash.
    Returns a list of changed-field dicts.
    """
    # Map fake hashes to plausible config changes
    diff_catalog = {
        "a00b01c0001": [
            {
                "table": "cell_config",
                "column": "antenna_tilt_deg",
                "from_val": "4.0",
                "to_val": "6.5",
            },
            {
                "table": "cell_config",
                "column": "sector_id",
                "from_val": "S3",
                "to_val": "S3",
            },
        ],
        "a01b04c0022": [
            {
                "table": "cell_config",
                "column": "tx_power_dbm",
                "from_val": "43.0",
                "to_val": "45.5",
            },
        ],
        "a02b07c0043": [
            {
                "table": "rf_config",
                "column": "ca_band_enabled",
                "from_val": "false",
                "to_val": "true",
            },
            {
                "table": "rf_config",
                "column": "ca_band_combo",
                "from_val": "NULL",
                "to_val": "3+7",
            },
        ],
    }
    return diff_catalog.get(
        commit_hash,
        [
            {
                "table": "network_config",
                "column": "param_updated",
                "from_val": "—",
                "to_val": "✓",
            },
        ],
    )


# ══════════════════════════════════════════════════════════════════════
#  CONNECTION
# ══════════════════════════════════════════════════════════════════════


def get_connection():
    """Return a live PyMySQL connection or 'MOCK' sentinel."""
    if USE_MOCK_DATA:
        return "MOCK"
    try:
        return pymysql.connect(**DB_CONFIG)
    except pymysql.err.OperationalError as exc:
        raise ConnectionError(
            f"Cannot reach Dolt SQL server at "
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}. "
            f"Is `dolt sql-server` running?\n\nDetail: {exc}"
        ) from exc


# ══════════════════════════════════════════════════════════════════════
#  SCHEMA DISCOVERY
# ══════════════════════════════════════════════════════════════════════


def discover_kpi_columns(conn) -> list[str]:
    """Return numeric, non-metadata column names from `network_kpis`."""
    if conn == "MOCK":
        return [
            "throughput_dl_mbps",
            "throughput_ul_mbps",
            "drop_rate_pct",
            "rach_success_rate_pct",
            "avg_cqi",
            "bler_dl_pct",
            "latency_ms",
            "prb_utilization_pct",
            "handover_success_rate_pct",
            "sinr_db",
        ]

    numeric_types = {
        "tinyint",
        "smallint",
        "mediumint",
        "int",
        "bigint",
        "float",
        "double",
        "decimal",
        "numeric",
        "real",
    }
    query = """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'network_kpis'
        ORDER BY ORDINAL_POSITION
    """
    with conn.cursor() as cur:
        cur.execute(query, (DB_CONFIG["database"],))
        rows = cur.fetchall()

    return [
        r["COLUMN_NAME"]
        for r in rows
        if r["COLUMN_NAME"].lower() not in NON_KPI_COLUMNS
        and any(r["DATA_TYPE"].lower().startswith(t) for t in numeric_types)
    ]


# ══════════════════════════════════════════════════════════════════════
#  DOLT LOG — ENHANCED WITH FULL METADATA
# ══════════════════════════════════════════════════════════════════════


def fetch_dolt_log(conn) -> pd.DataFrame:
    """
    Query dolt_log for all configuration commits.
    Returns: commit_hash, committer, email, date (str), message.
    """
    if conn == "MOCK":
        return _mock_dolt_log()

    query = """
        SELECT
            commit_hash,
            committer,
            email,
            date,
            message
        FROM dolt_log
        WHERE message NOT LIKE 'Initialize%'
          AND message NOT LIKE 'Merge%'
        ORDER BY date ASC
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception as exc:
        warnings.warn(f"dolt_log query failed: {exc}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════
#  DOLT DIFF — CONFIG CHANGE DETAILS PER COMMIT
# ══════════════════════════════════════════════════════════════════════


def fetch_dolt_diff(
    conn, commit_hash: str, parent_hash: str | None = None
) -> list[dict]:
    """
    Retrieve the column-level diff for a single commit.

    For a real Dolt server this queries dolt_diff_<table> system views.
    Each returned dict has keys: table, column, from_val, to_val.

    Args:
        conn        : PyMySQL connection or 'MOCK'
        commit_hash : The commit to inspect
        parent_hash : Parent commit (used to bound the diff range)

    Returns:
        List of change dicts.
    """
    if conn == "MOCK":
        return _mock_dolt_diff(commit_hash)

    # ── Real Dolt path ────────────────────────────────────────────────
    # Dolt exposes per-table diff as dolt_diff_<tablename>.
    # We check the known config tables; adapt this list to your schema.
    config_tables = ["cell_config", "rf_config", "network_config", "handover_config"]
    changes = []

    from_ref = parent_hash or (commit_hash + "~1")
    to_ref = commit_hash

    for table in config_tables:
        query = f"""
            SELECT
                '{table}'        AS `table`,
                diff_type,
                from_col_value,
                to_col_value,
                column_name
            FROM dolt_diff_{table}
            WHERE to_commit   = %s
              AND from_commit = %s
            LIMIT 50
        """
        try:
            with conn.cursor() as cur:
                cur.execute(query, (to_ref, from_ref))
                rows = cur.fetchall()
            for r in rows:
                changes.append(
                    {
                        "table": r.get("table", table),
                        "column": r.get("column_name", "—"),
                        "from_val": str(r.get("from_col_value", "—")),
                        "to_val": str(r.get("to_col_value", "—")),
                    }
                )
        except Exception:
            # Table may not exist — skip silently
            pass

    if not changes:
        changes.append(
            {
                "table": "—",
                "column": "No diff data available",
                "from_val": "—",
                "to_val": "—",
            }
        )
    return changes


# ══════════════════════════════════════════════════════════════════════
#  KPI DATA QUERY
# ══════════════════════════════════════════════════════════════════════


def fetch_kpi_data(conn, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch all rows from `network_kpis` for DATE(timestamp) in
    [start_date, end_date] inclusive.
    """
    if conn == "MOCK":
        df = _mock_kpi_data(start_date, end_date)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    query = """
        SELECT * FROM network_kpis
        WHERE DATE(timestamp) BETWEEN %s AND %s
        ORDER BY timestamp ASC
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (start_date, end_date))
            rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch KPI data ({start_date} → {end_date}): {exc}"
        ) from exc
