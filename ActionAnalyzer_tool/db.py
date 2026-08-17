"""
db.py — Database layer for Dolt / PyMySQL connectivity.

HOW TO CONFIGURE
────────────────
1.  Start your Dolt SQL server:
        dolt sql-server --host=127.0.0.1 --port=3306 --user=root

2.  Update DB_CONFIG below with your actual credentials.

3.  The module falls back to synthetic mock data automatically when
    USE_MOCK_DATA = True.  Set it to False once your server is running.

MOCK STATE
──────────
When USE_MOCK_DATA is True, all "writes" (manual commits, rollbacks,
parameter-sweep steps) are persisted to `db_mock_state.json` next to this
file, so the demo behaves like a real version-controlled DB across
Streamlit reruns. On a real Dolt server the equivalent actions are
UPDATE + DOLT_COMMIT / DOLT_REVERT and are executed as real SQL.
"""

import pymysql
import pandas as pd
import numpy as np
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, date
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
#  CELL / CELL-GROUP TOPOLOGY (mock)
# ══════════════════════════════════════════════════════════════════════

CELL_GROUPS: dict[str, list[str]] = {
    "Group-A · Urban Core": ["CELL_001", "CELL_002"],
    "Group-B · Suburban": ["CELL_003", "CELL_004"],
}
ALL_CELL_IDS: list[str] = [c for cells in CELL_GROUPS.values() for c in cells]


def cell_group_of(cell_id: str) -> str:
    for grp, cells in CELL_GROUPS.items():
        if cell_id in cells:
            return grp
    return "Ungrouped"


# ══════════════════════════════════════════════════════════════════════
#  TUNABLE PARAMETERS (mock)
# ══════════════════════════════════════════════════════════════════════

PARAMETER_CATALOG: dict[str, dict] = {
    "antenna_tilt_deg": {"table": "cell_config", "action_type": "Antenna Tilt", "default": 4.0, "step": 0.5},
    "tx_power_dbm": {"table": "cell_config", "action_type": "TX Power", "default": 43.0, "step": 0.5},
    "ca_band_combo": {"table": "rf_config", "action_type": "Carrier Aggregation", "default": "NULL", "step": None},
    "rach_root_seq": {"table": "rf_config", "action_type": "RACH Config", "default": 12, "step": 1},
    "ho_a3_offset": {"table": "handover_config", "action_type": "Handover Tuning", "default": 2.0, "step": 0.2},
    "sched_weight": {"table": "network_config", "action_type": "Scheduler Weight", "default": 1.0, "step": 0.1},
    "mimo_rank": {"table": "rf_config", "action_type": "MIMO Config", "default": 2, "step": 1},
    "qos_profile": {"table": "network_config", "action_type": "QoS Profile", "default": "standard", "step": None},
}

OPTIMIZER_TYPES = [
    "Manual (RF Engineer)",
    "Auto-Optimizer",
    "Parameter Sweep Engine",
    "Rollback Engine",
]

# ══════════════════════════════════════════════════════════════════════
#  MOCK STATE PERSISTENCE
# ══════════════════════════════════════════════════════════════════════

MOCK_STATE_PATH = Path(__file__).parent / "db_mock_state.json"


def _new_hash() -> str:
    return uuid.uuid4().hex[:16]


def _seed_commits() -> list[dict]:
    """Fabricated Dolt commit log with rich metadata, spread across cells."""
    base = datetime(2024, 5, 20, 9, 0, 0)

    seed = [
        dict(days=2, hours=0, minutes=12, committer="ali.hassan", email="ali@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_001", parameter="antenna_tilt_deg",
             from_val="4.0", to_val="6.5", msg="Adjust antenna tilt sector 3"),
        dict(days=2, hours=2, minutes=40, committer="ali.hassan", email="ali@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_001", parameter="tx_power_dbm",
             from_val="43.0", to_val="45.5", msg="Update TX power config sector 3"),
        dict(days=2, hours=4, minutes=5, committer="netops-robot", email="bot@carrier.net",
             optimizer="Auto-Optimizer", cell_id="CELL_002", parameter="ca_band_combo",
             from_val="NULL", to_val="3+7", msg="Enable CA band 3+7 cell 002"),
        dict(days=7, hours=1, minutes=20, committer="sara.farouk", email="sara@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_001", parameter="rach_root_seq",
             from_val="12", to_val="18", msg="RACH root sequence re-configuration"),
        dict(days=14, hours=0, minutes=0, committer="khaled.nasser", email="khaled@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_003", parameter="ho_a3_offset",
             from_val="2.0", to_val="3.0", msg="Handover parameter tuning batch A"),
        dict(days=14, hours=1, minutes=45, committer="khaled.nasser", email="khaled@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_004", parameter="ho_a3_offset",
             from_val="2.0", to_val="3.0", msg="Handover parameter tuning batch B"),
        dict(days=21, hours=3, minutes=10, committer="netops-robot", email="bot@carrier.net",
             optimizer="Auto-Optimizer", cell_id="CELL_002", parameter="sched_weight",
             from_val="1.0", to_val="1.3", msg="Scheduler weight optimization"),
        dict(days=21, hours=4, minutes=55, committer="ali.hassan", email="ali@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_001", parameter="mimo_rank",
             from_val="2", to_val="3", msg="Enable MIMO rank override"),
        dict(days=21, hours=5, minutes=30, committer="sara.farouk", email="sara@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_003", parameter="qos_profile",
             from_val="standard", to_val="volte-priority", msg="QoS profile update — VoLTE"),
        dict(days=28, hours=2, minutes=18, committer="khaled.nasser", email="khaled@carrier.net",
             optimizer="Manual (RF Engineer)", cell_id="CELL_004", parameter="ca_band_combo",
             from_val="NULL", to_val="1+3", msg="Neighbor cell relation audit"),
    ]

    commits = []
    for i, c in enumerate(seed):
        dt = base + timedelta(days=c["days"], hours=c["hours"], minutes=c["minutes"])
        action_type = PARAMETER_CATALOG.get(c["parameter"], {}).get("action_type", "Config Change")
        commits.append(
            {
                "commit_hash": f"a{i:02x}b{i * 3 + 7:02x}c{i * 7 + 1:04x}",
                "committer": c["committer"],
                "email": c["email"],
                "optimizer": c["optimizer"],
                "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "message": c["msg"],
                "cell_id": c["cell_id"],
                "cell_group": cell_group_of(c["cell_id"]),
                "action_type": action_type,
                "parameter": c["parameter"],
                "from_val": c["from_val"],
                "to_val": c["to_val"],
            }
        )
    return commits


def _seed_state() -> dict:
    commits = _seed_commits()
    param_values: dict[str, dict[str, str]] = {}
    for cell in ALL_CELL_IDS:
        param_values[cell] = {p: str(v["default"]) for p, v in PARAMETER_CATALOG.items()}
    for c in commits:
        param_values.setdefault(c["cell_id"], {})[c["parameter"]] = c["to_val"]
    return {"commits": commits, "param_values": param_values, "sweeps": []}


def _load_state() -> dict:
    if MOCK_STATE_PATH.exists():
        try:
            with open(MOCK_STATE_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    state = _seed_state()
    _save_state(state)
    return state


def _save_state(state: dict) -> None:
    with open(MOCK_STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, default=str)


def reset_mock_state() -> None:
    """Wipe all manual commits / rollbacks / sweeps back to the seed data."""
    _save_state(_seed_state())


# ══════════════════════════════════════════════════════════════════════
#  MOCK KPI DATA GENERATOR (multi-cell, commit-aware)
# ══════════════════════════════════════════════════════════════════════


def _cumulative_effect(commit_dates_signed: list[tuple[str, int]], as_of: date) -> float:
    """
    Sum of signed unit effects (+1 normal action, -1 rollback) for all
    commits on/before `as_of`, clipped to a sane [0, 4] range so the
    synthetic KPI curve stays realistic.
    """
    total = 0
    for d_str, sign in commit_dates_signed:
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        if d <= as_of:
            total += sign
    return float(max(0, min(4, total)))


def _mock_kpi_data_for_cell(
    start_date: str, end_date: str, cell_id: str, commit_dates_signed: list[tuple[str, int]]
) -> pd.DataFrame:
    rng = pd.date_range(start=start_date, end=end_date + " 23:45:00", freq="15min")
    n = len(rng)
    seed = int(hashlib.md5(cell_id.encode()).hexdigest(), 16) % (2**31)
    np.random.seed(seed)

    hour_pattern = np.array([rng[i].hour + rng[i].minute / 60 for i in range(n)])
    diurnal = 1 + 0.6 * np.sin(np.pi * (hour_pattern - 8) / 12) * (
        (hour_pattern >= 8) & (hour_pattern <= 20)
    )

    effect = np.array([_cumulative_effect(commit_dates_signed, ts.date()) for ts in rng])
    boost = effect / 4.0  # normalised 0..1 uplift factor

    df = pd.DataFrame({"timestamp": rng})
    df["cell_id"] = cell_id

    def noise(scale):
        return np.random.normal(0, scale, n)

    df["throughput_dl_mbps"] = np.clip(50 * diurnal + noise(5) + boost * 10, 5, 150)
    df["throughput_ul_mbps"] = np.clip(20 * diurnal + noise(2) + boost * 4, 2, 60)
    df["drop_rate_pct"] = np.clip(2.5 / diurnal + noise(0.3) - boost * 0.6, 0.0, 10.0)
    df["rach_success_rate_pct"] = np.clip(
        95 * diurnal / diurnal.mean() + noise(1.5) + boost * 1.6, 60.0, 100.0
    )
    df["avg_cqi"] = np.clip(9 * diurnal / diurnal.mean() + noise(0.8) + boost * 0.7, 1.0, 15.0)
    df["bler_dl_pct"] = np.clip(3 / diurnal + noise(0.4) - boost * 0.7, 0.0, 20.0)
    df["latency_ms"] = np.clip(25 / diurnal + noise(2) - boost * 3.2, 5.0, 120.0)
    df["prb_utilization_pct"] = np.clip(60 * diurnal / diurnal.mean() + noise(5), 5.0, 100.0)
    df["handover_success_rate_pct"] = np.clip(97 + noise(0.8) + boost * 0.8, 85.0, 100.0)
    df["sinr_db"] = 12 * diurnal / diurnal.mean() + noise(1.5) + boost * 1.0

    return df


def _mock_kpi_data(start_date: str, end_date: str) -> pd.DataFrame:
    """All cells concatenated, each driven by its own commit history."""
    state = _load_state()
    frames = []
    for cell in ALL_CELL_IDS:
        signed = [
            (c["date"][:10], -1 if c["action_type"] == "Rollback" else 1)
            for c in state["commits"]
            if c["cell_id"] == cell
        ]
        frames.append(_mock_kpi_data_for_cell(start_date, end_date, cell, signed))
    return pd.concat(frames, ignore_index=True)


# ══════════════════════════════════════════════════════════════════════
#  CONNECTION
# ══════════════════════════════════════════════════════════════════════


def get_connection():
    """Return a live PyMySQL connection or 'MOCK' sentinel."""
    if USE_MOCK_DATA:
        _load_state()  # ensure state file exists
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
        "tinyint", "smallint", "mediumint", "int", "bigint",
        "float", "double", "decimal", "numeric", "real",
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


def discover_cell_groups(conn) -> dict[str, list[str]]:
    """Return { cell_group_name: [cell_id, ...] }."""
    if conn == "MOCK":
        return CELL_GROUPS
    query = "SELECT DISTINCT cell_id, region FROM network_kpis"
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        groups: dict[str, list[str]] = {}
        for r in rows:
            groups.setdefault(r.get("region", "Ungrouped"), []).append(r["cell_id"])
        return groups
    except Exception as exc:
        warnings.warn(f"cell group discovery failed: {exc}")
        return {}


def discover_parameters(conn) -> dict[str, dict]:
    """Return the tunable-parameter catalog (name → {table, action_type, default, step})."""
    return PARAMETER_CATALOG


def get_current_param_value(conn, cell_id: str, parameter: str):
    if conn == "MOCK":
        state = _load_state()
        return state["param_values"].get(cell_id, {}).get(
            parameter, PARAMETER_CATALOG.get(parameter, {}).get("default")
        )
    return None  # real-DB lookup would SELECT the live config table


# ══════════════════════════════════════════════════════════════════════
#  DOLT LOG — ENHANCED WITH FULL METADATA (cell, action type, optimizer)
# ══════════════════════════════════════════════════════════════════════


def fetch_dolt_log(conn) -> pd.DataFrame:
    """
    Query dolt_log for all configuration commits.
    Returns: commit_hash, committer, email, optimizer, date, message,
             cell_id, cell_group, action_type, parameter, from_val, to_val.
    """
    if conn == "MOCK":
        state = _load_state()
        df = pd.DataFrame(state["commits"])
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    query = """
        SELECT
            commit_hash, committer, email, date, message
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


def fetch_dolt_diff(conn, commit_hash: str, parent_hash: str | None = None) -> list[dict]:
    """
    Retrieve the column-level diff for a single commit.
    Each returned dict has keys: table, column, from_val, to_val.
    """
    if conn == "MOCK":
        state = _load_state()
        match = next((c for c in state["commits"] if c["commit_hash"] == commit_hash), None)
        if not match:
            return [{"table": "—", "column": "No diff data available", "from_val": "—", "to_val": "—"}]
        table = PARAMETER_CATALOG.get(match["parameter"], {}).get("table", "network_config")
        return [
            {
                "table": table,
                "column": match["parameter"],
                "from_val": match["from_val"],
                "to_val": match["to_val"],
            }
        ]

    config_tables = ["cell_config", "rf_config", "network_config", "handover_config"]
    changes = []
    from_ref = parent_hash or (commit_hash + "~1")
    to_ref = commit_hash

    for table in config_tables:
        query = f"""
            SELECT '{table}' AS `table`, diff_type, from_col_value, to_col_value, column_name
            FROM dolt_diff_{table}
            WHERE to_commit = %s AND from_commit = %s
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
            pass

    if not changes:
        changes.append({"table": "—", "column": "No diff data available", "from_val": "—", "to_val": "—"})
    return changes


# ══════════════════════════════════════════════════════════════════════
#  ACTION COMMIT / ROLLBACK
# ══════════════════════════════════════════════════════════════════════


def commit_action(
    conn,
    cell_id: str,
    parameter: str,
    new_value,
    message: str,
    committer: str = "you",
    email: str = "you@carrier.net",
    optimizer: str = "Manual (RF Engineer)",
    action_type: str | None = None,
    when: datetime | None = None,
) -> dict:
    """
    Commit a parameter change for a cell.  On a real Dolt server this
    would run an UPDATE against the config table followed by
    `DOLT_COMMIT('-am', message)`.  In mock mode it appends to the
    persisted commit log and updates the live parameter-value table.
    """
    when = when or datetime.now()
    if conn == "MOCK":
        state = _load_state()
        from_val = str(
            state["param_values"].get(cell_id, {}).get(
                parameter, PARAMETER_CATALOG.get(parameter, {}).get("default", "—")
            )
        )
        commit = {
            "commit_hash": _new_hash(),
            "committer": committer,
            "email": email,
            "optimizer": optimizer,
            "date": when.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
            "cell_id": cell_id,
            "cell_group": cell_group_of(cell_id),
            "action_type": action_type or PARAMETER_CATALOG.get(parameter, {}).get("action_type", "Config Change"),
            "parameter": parameter,
            "from_val": from_val,
            "to_val": str(new_value),
        }
        state["commits"].append(commit)
        state["param_values"].setdefault(cell_id, {})[parameter] = str(new_value)
        _save_state(state)
        return commit

    # Real Dolt path (adapt table name via PARAMETER_CATALOG)
    table = PARAMETER_CATALOG.get(parameter, {}).get("table", "network_config")
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {table} SET {parameter} = %s WHERE cell_id = %s",
            (new_value, cell_id),
        )
        cur.execute("SELECT DOLT_COMMIT('-am', %s) AS hash", (message,))
        row = cur.fetchone()
    conn.commit()
    return {"commit_hash": row.get("hash", ""), "message": message, "cell_id": cell_id, "parameter": parameter}


def rollback_action(conn, commit_hash: str, committer: str = "you", email: str = "you@carrier.net") -> dict | None:
    """
    Roll back a single commit by creating a new commit that restores the
    parameter's `from_val`.  This mirrors `dolt_revert()` semantics
    without rewriting history.
    """
    if conn == "MOCK":
        state = _load_state()
        target = next((c for c in state["commits"] if c["commit_hash"] == commit_hash), None)
        if not target:
            return None
        return commit_action(
            conn,
            cell_id=target["cell_id"],
            parameter=target["parameter"],
            new_value=target["from_val"],
            message=f"Rollback of #{commit_hash[:8]} — {target['message']}",
            committer=committer,
            email=email,
            optimizer="Rollback Engine",
            action_type="Rollback",
        )

    with conn.cursor() as cur:
        cur.execute("SELECT DOLT_REVERT(%s) AS hash", (commit_hash,))
        row = cur.fetchone()
    conn.commit()
    return {"commit_hash": row.get("hash", ""), "message": f"Rollback of {commit_hash}"}


# ══════════════════════════════════════════════════════════════════════
#  GRADUAL PARAMETER SWEEP ENGINE
# ══════════════════════════════════════════════════════════════════════


def create_parameter_sweep(
    conn,
    cell_id: str,
    parameter: str,
    start_value: float,
    step_size: float,
    n_steps: int,
    interval_days: int,
    committer: str = "you",
    email: str = "you@carrier.net",
) -> dict:
    """
    Register a gradual parameter sweep: `parameter` is stepped from
    `start_value` in fixed `step_size` increments, one step every
    `interval_days`, each step auto-committed by `advance_due_sweeps`.
    """
    state = _load_state()
    today = date.today()
    steps = []
    for i in range(n_steps):
        steps.append(
            {
                "index": i,
                "value": round(start_value + i * step_size, 6),
                "scheduled_date": (today + timedelta(days=i * interval_days)).strftime("%Y-%m-%d"),
                "executed": False,
                "commit_hash": None,
                "executed_date": None,
                "kpi_score": None,
            }
        )
    sweep = {
        "id": uuid.uuid4().hex[:10],
        "cell_id": cell_id,
        "parameter": parameter,
        "start_value": start_value,
        "step_size": step_size,
        "n_steps": n_steps,
        "interval_days": interval_days,
        "committer": committer,
        "email": email,
        "created": today.strftime("%Y-%m-%d"),
        "status": "running",
        "steps": steps,
        "best_step_index": None,
        "best_value": None,
    }
    state["sweeps"].append(sweep)
    _save_state(state)
    return sweep


def _score_for_step(cell_id: str, parameter: str, value: float) -> float:
    """
    Synthetic 'goodness' score for a candidate parameter value — peaks
    near a per-(cell, parameter) pseudo-random optimum so a sweep has a
    discoverable best value. Higher is better.
    """
    seed = int(hashlib.md5(f"{cell_id}:{parameter}".encode()).hexdigest(), 16) % 1000
    rng = np.random.RandomState(seed)
    default = PARAMETER_CATALOG.get(parameter, {}).get("default", 0)
    try:
        default = float(default)
    except (TypeError, ValueError):
        default = 0.0
    ideal_value = default + (seed % 7 - 3) * 0.5
    noise = rng.normal(0, 0.15)
    return float(-abs(value - ideal_value) + noise)


def advance_due_sweeps(conn) -> list[dict]:
    """
    Execute (commit) any sweep step whose scheduled_date has arrived and
    hasn't been executed yet — one due step per sweep per call, so steps
    respect their interval even across many app reruns on the same day.
    Also finalises sweeps once all steps are done, selecting the
    best-scoring step. Returns the list of sweeps that changed.
    """
    if conn != "MOCK":
        return []

    state = _load_state()
    today = date.today()
    changed = []

    for sweep in state["sweeps"]:
        if sweep["status"] != "running":
            continue
        advanced_this_sweep = False
        for step in sweep["steps"]:
            if step["executed"]:
                continue
            sched = datetime.strptime(step["scheduled_date"], "%Y-%m-%d").date()
            if sched <= today:
                commit = commit_action(
                    conn,
                    cell_id=sweep["cell_id"],
                    parameter=sweep["parameter"],
                    new_value=step["value"],
                    message=f"Parameter sweep step {step['index'] + 1}/{sweep['n_steps']}: "
                    f"{sweep['parameter']} → {step['value']}",
                    committer=sweep["committer"],
                    email=sweep["email"],
                    optimizer="Parameter Sweep Engine",
                    action_type="Parameter Sweep Step",
                )
                step["executed"] = True
                step["commit_hash"] = commit["commit_hash"]
                step["executed_date"] = today.strftime("%Y-%m-%d")
                step["kpi_score"] = round(
                    _score_for_step(sweep["cell_id"], sweep["parameter"], step["value"]), 4
                )
                advanced_this_sweep = True
                break  # only one step per call, respecting the interval

        if advanced_this_sweep:
            changed.append(sweep)

        if all(s["executed"] for s in sweep["steps"]):
            scored = [s for s in sweep["steps"] if s["kpi_score"] is not None]
            if scored:
                best = max(scored, key=lambda s: s["kpi_score"])
                sweep["best_step_index"] = best["index"]
                sweep["best_value"] = best["value"]
            sweep["status"] = "completed"
            if sweep not in changed:
                changed.append(sweep)

    if changed:
        _save_state(state)
    return changed


def get_sweeps(conn) -> list[dict]:
    if conn != "MOCK":
        return []
    return _load_state()["sweeps"]


def finalize_sweep(conn, sweep_id: str) -> dict | None:
    """
    Auto-commit the best-performing value found by a completed sweep as
    the permanent setting ('automated commitment').
    """
    if conn != "MOCK":
        return None
    state = _load_state()
    sweep = next((s for s in state["sweeps"] if s["id"] == sweep_id), None)
    if not sweep or sweep["status"] != "completed" or sweep["best_value"] is None:
        return None

    commit = commit_action(
        conn,
        cell_id=sweep["cell_id"],
        parameter=sweep["parameter"],
        new_value=sweep["best_value"],
        message=f"Sweep finalize — best value {sweep['best_value']} "
        f"(step {sweep['best_step_index'] + 1}/{sweep['n_steps']}), auto-committed",
        committer=sweep["committer"],
        email=sweep["email"],
        optimizer="Parameter Sweep Engine",
        action_type="Sweep Finalize (Auto-Commit)",
    )
    sweep["status"] = "finalized"
    sweep["finalize_commit_hash"] = commit["commit_hash"]
    _save_state(state)
    return sweep


# ══════════════════════════════════════════════════════════════════════
#  KPI DATA QUERY
# ══════════════════════════════════════════════════════════════════════


def fetch_kpi_data(conn, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch all rows from `network_kpis` for DATE(timestamp) in
    [start_date, end_date] inclusive, across all cells.
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
        raise RuntimeError(f"Failed to fetch KPI data ({start_date} → {end_date}): {exc}") from exc
