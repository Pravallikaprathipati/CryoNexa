"""Read-only operational API for the CryoNexa dashboard."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("CRYONEXA_DB", ROOT / "data" / "generated" / "cryo.db"))

app = FastAPI(title="CryoNexa API", version="1.0.0", description="Cold-chain monitoring and excursion management API.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "PATCH"],
    allow_headers=["*"],
)


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Dataset is not initialized. Run the data generator first.")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, params).fetchall()]


class ActionTransition(BaseModel):
    status: Literal["in_progress", "completed"]
    actor: str = Field(default="quality_engineer", min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dataset": "ready" if DB_PATH.exists() else "missing"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    connection = connect()
    try:
        latest_reading_at = connection.execute(
            "SELECT MAX(recorded_at) FROM sensor_reading"
        ).fetchone()[0]
        if latest_reading_at:
            latest_datetime = datetime.fromisoformat(latest_reading_at.replace("Z", "+00:00"))
            window_start_datetime = latest_datetime - timedelta(hours=24)
            window_start = window_start_datetime.isoformat(timespec="seconds").replace("+00:00", "Z")
            recent = connection.execute(
                """SELECT COUNT(*) AS readings,
                        COUNT(DISTINCT r.sensor_id) AS sensors_reporting,
                        COUNT(DISTINCT r.shipment_id) AS shipments_monitored,
                        ROUND(AVG(r.temperature_c), 2) AS average_temperature_c,
                        ROUND(MIN(r.temperature_c), 2) AS minimum_temperature_c,
                        ROUND(MAX(r.temperature_c), 2) AS maximum_temperature_c,
                        ROUND(AVG(r.humidity_pct), 2) AS average_humidity_pct,
                        SUM(CASE WHEN r.quality_status != 'valid' THEN 1 ELSE 0 END) AS flagged_readings,
                        ROUND(100.0 * SUM(CASE WHEN r.quality_status = 'valid'
                            AND r.temperature_c BETWEEN tp.min_temperature_c AND tp.max_temperature_c
                            AND r.humidity_pct BETWEEN tp.min_humidity_pct AND tp.max_humidity_pct
                            AND tp.product_id = s.product_id THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)
                            AS compliance_rate
                   FROM sensor_reading r
                   JOIN shipment s ON s.id = r.shipment_id
                   JOIN threshold_policy tp ON tp.id = r.threshold_policy_id
                   WHERE r.recorded_at >= ? AND r.recorded_at <= ?""",
                (window_start, latest_reading_at),
            ).fetchone()
            hourly_trend = fetch_all(connection,
                """SELECT strftime('%Y-%m-%dT%H:00:00Z', r.recorded_at) AS hour,
                        ROUND(AVG(r.temperature_c), 2) AS temperature,
                        ROUND(AVG(r.humidity_pct), 2) AS humidity,
                        COUNT(*) AS reading_count
                   FROM sensor_reading r
                   WHERE r.recorded_at >= ? AND r.recorded_at <= ?
                   GROUP BY hour ORDER BY hour""",
                (window_start, latest_reading_at))
            hourly_by_bucket = {row["hour"]: row for row in hourly_trend}
            first_bucket = window_start_datetime.replace(minute=0, second=0, microsecond=0)
            last_bucket = latest_datetime.replace(minute=0, second=0, microsecond=0)
            hourly_trend = []
            while first_bucket <= last_bucket:
                hour = first_bucket.strftime("%Y-%m-%dT%H:00:00Z")
                row = hourly_by_bucket.get(hour)
                hourly_trend.append({
                    "hour": hour,
                    "temperature": row["temperature"] if row else None,
                    "humidity": row["humidity"] if row else None,
                    "reading_count": row["reading_count"] if row else 0,
                })
                first_bucket += timedelta(hours=1)
            recent_excursions = connection.execute(
                """SELECT COUNT(*) FROM excursion
                   WHERE started_at >= ? AND started_at <= ?""",
                (window_start, latest_reading_at),
            ).fetchone()[0]
            recent_gaps = connection.execute(
                """WITH window_readings AS (
                        SELECT shipment_id, sensor_id, recorded_at FROM sensor_reading
                        WHERE recorded_at >= ? AND recorded_at <= ?
                    ),
                    first_reading AS (
                        SELECT shipment_id, sensor_id, MIN(recorded_at) AS recorded_at
                        FROM window_readings GROUP BY shipment_id, sensor_id
                    ),
                    prior_readings AS (
                        SELECT r.shipment_id, r.sensor_id, r.recorded_at
                        FROM first_reading f
                        JOIN sensor_reading r
                          ON r.shipment_id = f.shipment_id AND r.sensor_id = f.sensor_id
                         AND r.recorded_at = (
                            SELECT MAX(previous.recorded_at) FROM sensor_reading previous
                            WHERE previous.shipment_id = f.shipment_id
                              AND previous.sensor_id = f.sensor_id
                              AND previous.recorded_at < f.recorded_at
                         )
                    ),
                    ordered_readings AS (
                        SELECT shipment_id, sensor_id, recorded_at FROM prior_readings
                        UNION ALL
                        SELECT shipment_id, sensor_id, recorded_at FROM window_readings
                    ),
                    intervals AS (
                        SELECT shipment_id, sensor_id, recorded_at,
                            LAG(recorded_at) OVER (
                                PARTITION BY shipment_id, sensor_id ORDER BY recorded_at
                            ) AS previous_at
                        FROM ordered_readings
                    )
                    SELECT COUNT(*) FROM intervals
                    WHERE previous_at IS NOT NULL AND recorded_at >= ?
                      AND (julianday(recorded_at) - julianday(previous_at)) * 1440 > 10""",
                (window_start, latest_reading_at, window_start),
            ).fetchone()[0]
            recent_24h = {
                **dict(recent),
                "window_start": window_start,
                "window_end": latest_reading_at,
                "excursions": recent_excursions,
                "data_gaps": recent_gaps,
                "dataset_age_seconds": round(
                    (datetime.now(timezone.utc) - latest_datetime).total_seconds()
                ),
            }
        else:
            hourly_trend = []
            recent_24h = {
                "readings": 0,
                "sensors_reporting": 0,
                "shipments_monitored": 0,
                "average_temperature_c": None,
                "minimum_temperature_c": None,
                "maximum_temperature_c": None,
                "average_humidity_pct": None,
                "flagged_readings": 0,
                "compliance_rate": None,
                "window_start": None,
                "window_end": None,
                "excursions": 0,
                "data_gaps": 0,
                "dataset_age_seconds": None,
            }
        counts = connection.execute(
            """SELECT
                (SELECT COUNT(*) FROM shipment WHERE status = 'in_transit') AS active_shipments,
                (SELECT COUNT(DISTINCT container_id) FROM shipment_container sc
                    JOIN shipment s ON s.id = sc.shipment_id WHERE s.status = 'in_transit') AS monitored_containers,
                (SELECT COUNT(*) FROM excursion WHERE status IN ('open', 'investigating')) AS open_excursions,
                (SELECT COUNT(*) FROM sensor_reading) AS total_readings
            """
        ).fetchone()
        compliance = connection.execute(
            """SELECT
                100.0 * SUM(CASE WHEN r.temperature_c BETWEEN p.min_temperature_c AND p.max_temperature_c
                                      AND r.humidity_pct BETWEEN p.min_humidity_pct AND p.max_humidity_pct
                                      AND p.product_id = s.product_id
                                      AND r.quality_status = 'valid'
                                 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)
               FROM sensor_reading r
               JOIN shipment s ON s.id = r.shipment_id
               JOIN threshold_policy p ON p.id = r.threshold_policy_id"""
        ).fetchone()[0]
        gaps = connection.execute(
            """WITH ordered AS (
                SELECT shipment_id, recorded_at,
                    LAG(recorded_at) OVER (PARTITION BY shipment_id ORDER BY recorded_at) AS previous_at
                FROM sensor_reading
            )
            SELECT COUNT(*) FROM ordered
            WHERE previous_at IS NOT NULL
              AND (julianday(recorded_at) - julianday(previous_at)) * 1440 > 10"""
        ).fetchone()[0]
        trend = hourly_trend
        severity = fetch_all(connection,
            """SELECT severity, COUNT(*) AS count FROM excursion
               WHERE status IN ('open', 'investigating')
               GROUP BY severity ORDER BY CASE severity
                 WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END""")
        excursions = fetch_all(connection,
            """SELECT e.id, e.shipment_id, p.name AS product_name, e.metric, e.unit,
                    COALESCE((SELECT rs.location FROM sensor_reading r
                        JOIN route_stop rs ON rs.id = r.route_stop_id
                        WHERE r.shipment_id = e.shipment_id AND r.recorded_at = e.started_at LIMIT 1), s.origin) AS location,
                    e.severity, e.status, e.started_at, e.duration_minutes AS duration_minutes,
                    ROUND((e.min_value + e.max_value) / 2.0, 2) AS measured_value,
                    CASE WHEN e.metric = 'temperature' THEN ROUND((e.min_value + e.max_value) / 2.0, 2) END AS temperature_c,
                    CASE WHEN e.metric = 'temperature' THEN tp.min_temperature_c END AS threshold_min_c,
                    CASE WHEN e.metric = 'temperature' THEN tp.max_temperature_c END AS threshold_max_c,
                    CASE WHEN e.metric = 'humidity' THEN tp.min_humidity_pct ELSE tp.min_temperature_c END AS threshold_min,
                    CASE WHEN e.metric = 'humidity' THEN tp.max_humidity_pct ELSE tp.max_temperature_c END AS threshold_max
               FROM excursion e
               JOIN shipment s ON s.id = e.shipment_id
               JOIN product p ON p.id = s.product_id
               JOIN threshold_policy tp ON tp.id = e.threshold_policy_id
               ORDER BY e.started_at DESC LIMIT 8""")
        shipments = fetch_all(connection,
            """SELECT s.id, p.name AS product_name, s.origin, s.destination, s.status,
                    s.departed_at, s.eta,
                    (SELECT sc.container_id FROM shipment_container sc
                        WHERE sc.shipment_id = s.id ORDER BY sc.assigned_at DESC LIMIT 1) AS container_id,
                    (SELECT r.temperature_c FROM sensor_reading r WHERE r.shipment_id = s.id
                        ORDER BY r.recorded_at DESC LIMIT 1) AS temperature_c,
                    (SELECT r.humidity_pct FROM sensor_reading r WHERE r.shipment_id = s.id
                        ORDER BY r.recorded_at DESC LIMIT 1) AS humidity_pct,
                    tp.min_temperature_c AS threshold_min_c,
                    tp.max_temperature_c AS threshold_max_c,
                    (SELECT COUNT(*) FROM excursion e WHERE e.shipment_id = s.id) AS excursion_count
               FROM shipment s JOIN product p ON p.id = s.product_id
               JOIN threshold_policy tp ON tp.product_id = s.product_id AND tp.effective_to IS NULL
               ORDER BY CASE s.status WHEN 'in_transit' THEN 0 ELSE 1 END, s.departed_at DESC LIMIT 8""")
        actions = fetch_all(connection,
            """SELECT id, excursion_id, owner, status, due_at, description
               FROM corrective_action ORDER BY CASE status WHEN 'open' THEN 0
                    WHEN 'in_progress' THEN 1 ELSE 2 END, due_at LIMIT 8""")
        return {
            "metrics": {
                "active_shipments": counts["active_shipments"],
                "monitored_containers": counts["monitored_containers"],
                "open_excursions": counts["open_excursions"],
                "compliance_rate": round(compliance or 0, 2),
                "total_readings": counts["total_readings"],
                "flagged_gaps": gaps,
            },
            "trend": trend,
            "recent_24h": recent_24h,
            "severity_breakdown": severity,
            "recent_excursions": excursions,
            "shipments": shipments,
            "actions": actions,
        }
    finally:
        connection.close()


@app.get("/api/shipments")
def shipments(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT s.id, p.name AS product_name, s.origin, s.destination, s.status,
                    s.departed_at, s.eta, s.delivered_at,
                    (SELECT container_id FROM shipment_container sc
                        WHERE sc.shipment_id = s.id ORDER BY assigned_at DESC LIMIT 1) AS container_id,
                    (SELECT temperature_c FROM sensor_reading r WHERE r.shipment_id = s.id
                        ORDER BY recorded_at DESC LIMIT 1) AS temperature_c,
                    (SELECT humidity_pct FROM sensor_reading r WHERE r.shipment_id = s.id
                        ORDER BY recorded_at DESC LIMIT 1) AS humidity_pct,
                    tp.min_temperature_c AS threshold_min_c,
                    tp.max_temperature_c AS threshold_max_c,
                    (SELECT COUNT(*) FROM excursion e WHERE e.shipment_id = s.id) AS excursion_count
               FROM shipment s JOIN product p ON p.id = s.product_id
               JOIN threshold_policy tp ON tp.product_id = s.product_id AND tp.effective_to IS NULL
               ORDER BY s.departed_at DESC LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM shipment").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.get("/api/containers")
def containers(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT c.id, c.container_type, c.capacity_liters, c.lifecycle_state, c.created_at,
                    (SELECT s.id FROM shipment_container sc JOIN shipment s ON s.id = sc.shipment_id
                        WHERE sc.container_id = c.id AND sc.released_at IS NULL
                        ORDER BY sc.assigned_at DESC LIMIT 1) AS shipment_id,
                    (SELECT se.id FROM sensor se WHERE se.container_id = c.id LIMIT 1) AS sensor_id
               FROM container c ORDER BY c.id LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM container").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.get("/api/containers/{container_id}/monitoring")
def container_monitoring(
    container_id: str,
    limit: int = Query(default=288, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    connection = connect()
    try:
        container = connection.execute(
            """SELECT c.id, c.container_type, c.capacity_liters, c.lifecycle_state,
                    se.id AS sensor_id, se.calibration_status, se.calibrated_at, se.calibration_due_at
               FROM container c
               LEFT JOIN sensor se ON se.container_id = c.id
               WHERE c.id = ?
               ORDER BY se.id
               LIMIT 1""",
            (container_id,),
        ).fetchone()
        if container is None:
            raise HTTPException(status_code=404, detail="Container not found.")

        readings = fetch_all(connection,
            """SELECT reading.* FROM (
                    SELECT r.id, r.sensor_id, r.shipment_id, r.route_stop_id, r.recorded_at,
                        r.temperature_c, r.humidity_pct, r.threshold_policy_id, r.quality_status,
                        r.issue_type, p.name AS product_name, rs.location,
                        tp.min_temperature_c, tp.max_temperature_c,
                        tp.min_humidity_pct, tp.max_humidity_pct,
                        tp.permissible_excursion_minutes
                    FROM sensor_reading r
                    JOIN sensor se ON se.id = r.sensor_id
                    JOIN shipment sh ON sh.id = r.shipment_id
                    JOIN product p ON p.id = sh.product_id
                    JOIN threshold_policy tp ON tp.id = r.threshold_policy_id
                    LEFT JOIN route_stop rs ON rs.id = r.route_stop_id
                    WHERE se.container_id = ?
                    ORDER BY r.recorded_at DESC, r.id DESC
                    LIMIT ? OFFSET ?
               ) AS reading
               ORDER BY reading.recorded_at DESC, reading.id DESC""",
            (container_id, limit, offset))
        reading_count = connection.execute(
            """SELECT COUNT(*) FROM sensor_reading r
               JOIN sensor se ON se.id = r.sensor_id WHERE se.container_id = ?""",
            (container_id,),
        ).fetchone()[0]

        excursions = fetch_all(connection,
            """SELECT e.id, e.shipment_id, p.name AS product_name, e.started_at, e.ended_at,
                    e.duration_minutes, e.reported_duration_minutes, e.metric, e.unit,
                    e.severity, e.status, e.min_value, e.max_value, e.issue_type,
                    e.threshold_policy_id, tp.min_temperature_c, tp.max_temperature_c,
                    tp.min_humidity_pct, tp.max_humidity_pct
               FROM excursion e
               JOIN sensor se ON se.id = e.sensor_id
               JOIN shipment sh ON sh.id = e.shipment_id
               JOIN product p ON p.id = sh.product_id
               JOIN threshold_policy tp ON tp.id = e.threshold_policy_id
               WHERE se.container_id = ?
               ORDER BY e.started_at DESC, e.id DESC""",
            (container_id,))
        return {
            "container": dict(container),
            "readings": readings,
            "reading_count": reading_count,
            "reading_limit": limit,
            "reading_offset": offset,
            "excursions": excursions,
        }
    finally:
        connection.close()


@app.get("/api/sensors")
def sensors(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT se.id, se.container_id, se.sensor_type, se.calibration_status,
                    se.calibrated_at, se.calibration_due_at, se.serial_number,
                    (SELECT sa.shipment_id FROM sensor_assignment sa
                        WHERE sa.sensor_id = se.id AND sa.unassigned_at IS NULL
                        ORDER BY sa.assigned_at DESC LIMIT 1) AS shipment_id,
                    (SELECT r.recorded_at FROM sensor_reading r WHERE r.sensor_id = se.id
                        ORDER BY r.recorded_at DESC LIMIT 1) AS last_reading_at
               FROM sensor se ORDER BY se.id LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM sensor").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.get("/api/compliance")
def compliance() -> dict[str, Any]:
    connection = connect()
    try:
        policies = fetch_all(connection,
            """SELECT p.id AS product_id, p.name AS product_name,
                    tp.id AS policy_id, tp.min_temperature_c, tp.max_temperature_c,
                    tp.min_humidity_pct, tp.max_humidity_pct,
                    tp.permissible_excursion_minutes, tp.effective_from, tp.effective_to,
                    (SELECT COUNT(*) FROM shipment s WHERE s.product_id = p.id) AS shipment_count,
                    (SELECT COUNT(*) FROM sensor_reading r
                        JOIN shipment s ON s.id = r.shipment_id
                        WHERE s.product_id = p.id) AS reading_count,
                    (SELECT COUNT(*) FROM sensor_reading r
                        JOIN shipment s ON s.id = r.shipment_id
                        WHERE s.product_id = p.id AND r.quality_status != 'valid') AS flagged_readings,
                    (SELECT COUNT(*) FROM excursion e
                        JOIN shipment s ON s.id = e.shipment_id
                        WHERE s.product_id = p.id) AS excursion_count
               FROM product p JOIN threshold_policy tp ON tp.product_id = p.id
               WHERE tp.effective_to IS NULL ORDER BY p.name""")
        summary = connection.execute(
            """SELECT
                (SELECT COUNT(*) FROM sensor WHERE calibration_status != 'calibrated') AS sensors_needing_calibration,
                (SELECT COUNT(*) FROM notification WHERE acknowledged_at IS NULL) AS unacknowledged_notifications"""
        ).fetchone()
        return {
            "items": policies,
            "count": len(policies),
            "sensors_needing_calibration": summary["sensors_needing_calibration"],
            "unacknowledged_notifications": summary["unacknowledged_notifications"],
        }
    finally:
        connection.close()


@app.get("/api/notifications")
def notifications(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT n.id, n.shipment_id, n.excursion_id, n.recipient_role, n.message,
                    n.created_at, n.acknowledged_at
               FROM notification n ORDER BY n.created_at DESC LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM notification").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.get("/api/excursions")
def excursions(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT e.id, e.shipment_id, p.name AS product_name, e.metric, e.unit,
                    COALESCE((SELECT rs.location FROM sensor_reading r
                        JOIN route_stop rs ON rs.id = r.route_stop_id
                        WHERE r.shipment_id = e.shipment_id AND r.recorded_at = e.started_at LIMIT 1), s.origin) AS location,
                    e.severity, e.status, e.started_at, e.ended_at, e.duration_minutes,
                    e.reported_duration_minutes, e.min_value, e.max_value,
                    ROUND((e.min_value + e.max_value) / 2.0, 2) AS measured_value,
                    CASE WHEN e.metric = 'temperature' THEN ROUND((e.min_value + e.max_value) / 2.0, 2) END AS temperature_c,
                    CASE WHEN e.metric = 'temperature' THEN tp.min_temperature_c END AS threshold_min_c,
                    CASE WHEN e.metric = 'temperature' THEN tp.max_temperature_c END AS threshold_max_c,
                    CASE WHEN e.metric = 'humidity' THEN tp.min_humidity_pct ELSE tp.min_temperature_c END AS threshold_min,
                    CASE WHEN e.metric = 'humidity' THEN tp.max_humidity_pct ELSE tp.max_temperature_c END AS threshold_max
               FROM excursion e
               JOIN shipment s ON s.id = e.shipment_id
               JOIN product p ON p.id = s.product_id
               JOIN threshold_policy tp ON tp.id = e.threshold_policy_id
               ORDER BY e.started_at DESC LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM excursion").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.get("/api/actions")
def actions(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    connection = connect()
    try:
        rows = fetch_all(connection,
            """SELECT a.id, a.excursion_id, a.owner, a.description, a.status, a.created_at,
                    a.due_at, a.completed_at, e.shipment_id, e.severity
               FROM corrective_action a JOIN excursion e ON e.id = a.excursion_id
               ORDER BY CASE a.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                    a.due_at LIMIT ? OFFSET ?""", (limit, offset))
        count = connection.execute("SELECT COUNT(*) FROM corrective_action").fetchone()[0]
        return {"items": rows, "count": count}
    finally:
        connection.close()


@app.patch("/api/actions/{action_id}")
def transition_action(action_id: str, transition: ActionTransition) -> dict[str, Any]:
    connection = connect()
    try:
        action = connection.execute(
            "SELECT status FROM corrective_action WHERE id = ?", (action_id,)
        ).fetchone()
        if action is None:
            raise HTTPException(status_code=404, detail="Corrective action not found.")
        current = action["status"]
        allowed = {"open": {"in_progress"}, "in_progress": {"completed"}, "completed": set()}
        if transition.status not in allowed[current]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition corrective action from {current} to {transition.status}.",
            )
        occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        next_event = connection.execute(
            "SELECT COUNT(*) + 1 FROM corrective_action_status_event WHERE action_id = ?",
            (action_id,),
        ).fetchone()[0]
        event_id = f"ACE-{action_id}-{next_event:02d}"
        connection.execute(
            """INSERT INTO corrective_action_status_event
               (id, action_id, from_status, to_status, occurred_at, actor, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, action_id, current, transition.status, occurred_at, transition.actor, transition.note),
        )
        completed_at = occurred_at if transition.status == "completed" else None
        connection.execute(
            """UPDATE corrective_action SET status = ?,
               completed_at = CASE WHEN ? = 'completed' THEN ? ELSE completed_at END
               WHERE id = ?""",
            (transition.status, transition.status, completed_at, action_id),
        )
        connection.commit()
        return {
            "id": action_id,
            "status": transition.status,
            "event_id": event_id,
            "occurred_at": occurred_at,
        }
    finally:
        connection.close()


@app.get("/api/actions/{action_id}/history")
def action_history(action_id: str) -> dict[str, Any]:
    connection = connect()
    try:
        if connection.execute(
            "SELECT 1 FROM corrective_action WHERE id = ?", (action_id,)
        ).fetchone() is None:
            raise HTTPException(status_code=404, detail="Corrective action not found.")
        events = fetch_all(connection,
            """SELECT id, from_status, to_status, occurred_at, actor, note
               FROM corrective_action_status_event WHERE action_id = ?
               ORDER BY occurred_at, id""", (action_id,))
        return {"action_id": action_id, "events": events}
    finally:
        connection.close()
