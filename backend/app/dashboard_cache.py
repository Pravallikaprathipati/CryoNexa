"""Precomputed dashboard aggregates for generated cold-chain datasets."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any


def build_dashboard_snapshot(connection: sqlite3.Connection) -> tuple[str | None, dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    latest_reading_at = connection.execute(
        "SELECT MAX(recorded_at) FROM sensor_reading"
    ).fetchone()[0]

    counts = connection.execute(
        """SELECT
            (SELECT COUNT(*) FROM shipment WHERE status = 'in_transit') AS active_shipments,
            (SELECT COUNT(DISTINCT container_id) FROM shipment_container sc
                JOIN shipment s ON s.id = sc.shipment_id WHERE s.status = 'in_transit') AS monitored_containers,
            (SELECT COUNT(*) FROM excursion WHERE status IN ('open', 'investigating')) AS open_excursions,
            (SELECT COUNT(*) FROM sensor_reading) AS total_readings"""
    ).fetchone()
    reading_metrics = {
        row["product_id"]: dict(row)
        for row in connection.execute(
            """SELECT s.product_id, COUNT(*) AS reading_count,
                    SUM(CASE WHEN r.quality_status != 'valid' THEN 1 ELSE 0 END) AS flagged_readings,
                    SUM(CASE WHEN r.temperature_c BETWEEN p.min_temperature_c AND p.max_temperature_c
                                  AND r.humidity_pct BETWEEN p.min_humidity_pct AND p.max_humidity_pct
                                  AND p.product_id = s.product_id
                                  AND r.quality_status = 'valid'
                             THEN 1 ELSE 0 END) AS compliant_readings
               FROM sensor_reading r
               JOIN shipment s ON s.id = r.shipment_id
               JOIN threshold_policy p ON p.id = r.threshold_policy_id
               GROUP BY s.product_id"""
        ).fetchall()
    }
    shipment_counts = {
        row["product_id"]: row["shipment_count"]
        for row in connection.execute(
            "SELECT product_id, COUNT(*) AS shipment_count FROM shipment GROUP BY product_id"
        ).fetchall()
    }
    excursion_counts = {
        row["product_id"]: row["excursion_count"]
        for row in connection.execute(
            """SELECT s.product_id, COUNT(*) AS excursion_count
               FROM excursion e JOIN shipment s ON s.id = e.shipment_id
               GROUP BY s.product_id"""
        ).fetchall()
    }
    product_ids = set(reading_metrics) | set(shipment_counts) | set(excursion_counts)
    compliance_by_product = {
        product_id: {
            "shipment_count": shipment_counts.get(product_id, 0),
            "reading_count": reading_metrics.get(product_id, {}).get("reading_count", 0),
            "flagged_readings": reading_metrics.get(product_id, {}).get("flagged_readings", 0),
            "excursion_count": excursion_counts.get(product_id, 0),
        }
        for product_id in sorted(product_ids)
    }
    total_readings_for_compliance = sum(
        row["reading_count"] for row in reading_metrics.values()
    )
    compliant_readings = sum(
        row["compliant_readings"] for row in reading_metrics.values()
    )
    compliance = (
        100.0 * compliant_readings / total_readings_for_compliance
        if total_readings_for_compliance
        else None
    )
    gaps = connection.execute(
        """WITH ordered AS (
            SELECT shipment_id, sensor_id, recorded_at,
                LAG(recorded_at) OVER (
                    PARTITION BY shipment_id, sensor_id ORDER BY recorded_at
                ) AS previous_at
            FROM sensor_reading
        )
        SELECT COUNT(*) FROM ordered
        WHERE previous_at IS NOT NULL
          AND (julianday(recorded_at) - julianday(previous_at)) * 1440 > 10"""
    ).fetchone()[0]
    severity = [
        dict(row) for row in connection.execute(
            """SELECT severity, COUNT(*) AS count FROM excursion
               WHERE status IN ('open', 'investigating')
               GROUP BY severity ORDER BY CASE severity
                 WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"""
        ).fetchall()
    ]

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
        hourly = connection.execute(
            """SELECT strftime('%Y-%m-%dT%H:00:00Z', recorded_at) AS hour,
                    ROUND(AVG(temperature_c), 2) AS temperature,
                    ROUND(AVG(humidity_pct), 2) AS humidity,
                    COUNT(*) AS reading_count
               FROM sensor_reading
               WHERE recorded_at >= ? AND recorded_at <= ?
               GROUP BY hour ORDER BY hour""",
            (window_start, latest_reading_at),
        ).fetchall()
        hourly_by_bucket = {row["hour"]: row for row in hourly}
        trend = []
        bucket = window_start_datetime.replace(minute=0, second=0, microsecond=0)
        last_bucket = latest_datetime.replace(minute=0, second=0, microsecond=0)
        while bucket <= last_bucket:
            hour = bucket.strftime("%Y-%m-%dT%H:00:00Z")
            row = hourly_by_bucket.get(hour)
            trend.append({
                "hour": hour,
                "temperature": row["temperature"] if row else None,
                "humidity": row["humidity"] if row else None,
                "reading_count": row["reading_count"] if row else 0,
            })
            bucket += timedelta(hours=1)
        recent_excursions = connection.execute(
            "SELECT COUNT(*) FROM excursion WHERE started_at >= ? AND started_at <= ?",
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
        }
    else:
        trend = []
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
        }

    snapshot = {
        "metrics": {
            "active_shipments": counts["active_shipments"],
            "monitored_containers": counts["monitored_containers"],
            "open_excursions": counts["open_excursions"],
            "compliance_rate": round(compliance or 0, 2),
            "total_readings": counts["total_readings"],
            "flagged_gaps": gaps,
        },
        "recent_24h": recent_24h,
        "trend": trend,
        "severity_breakdown": severity,
        "compliance_by_product": compliance_by_product,
    }
    return latest_reading_at, snapshot


def refresh_dashboard_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    latest_reading_at, snapshot = build_dashboard_snapshot(connection)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS dashboard_snapshot (
            id TEXT PRIMARY KEY CHECK (id = 'overview'),
            source_latest_reading_at TEXT,
            payload TEXT NOT NULL
        )"""
    )
    connection.execute(
        """INSERT OR REPLACE INTO dashboard_snapshot
           (id, source_latest_reading_at, payload) VALUES ('overview', ?, ?)""",
        (latest_reading_at, json.dumps(snapshot, separators=(",", ":"))),
    )
    connection.commit()
    return snapshot


def get_dashboard_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    latest_reading_at = connection.execute(
        "SELECT MAX(recorded_at) FROM sensor_reading"
    ).fetchone()[0]
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dashboard_snapshot'"
    ).fetchone()
    if table_exists:
        cached = connection.execute(
            "SELECT source_latest_reading_at, payload FROM dashboard_snapshot WHERE id = 'overview'"
        ).fetchone()
        if cached and cached["source_latest_reading_at"] == latest_reading_at:
            snapshot = json.loads(cached["payload"])
            if "compliance_by_product" in snapshot:
                return snapshot
    return refresh_dashboard_snapshot(connection)
