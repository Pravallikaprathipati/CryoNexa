"""Deterministic cold-chain data generation, validation, and export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "database" / "schema.sql"
DEFAULT_OUTPUT = ROOT / "data" / "generated"
SEED = 20261022
INTERVAL_MINUTES = 5
START = datetime(2026, 11, 4, tzinfo=timezone.utc)
REFERENCE_TIME = START + timedelta(days=5)
PRODUCTS = [
    ("PRD-000001", "Cell Therapy", "biologic", 2.0, 8.0, 20.0, 70.0, 15),
    ("PRD-000002", "mRNA Vaccine", "vaccine", 2.0, 8.0, 20.0, 70.0, 15),
    ("PRD-000003", "Frozen Reagent", "reagent", -25.0, -15.0, 10.0, 60.0, 10),
    ("PRD-000004", "Insulin", "pharmaceutical", 2.0, 8.0, 20.0, 65.0, 30),
    ("PRD-000005", "Diagnostic Kit", "diagnostic", 15.0, 25.0, 25.0, 75.0, 45),
]
ROUTES = [
    ("Boston, MA", "New York, NY", "Worcester, MA", "Hartford, CT"),
    ("San Diego, CA", "Phoenix, AZ", "Tucson, AZ", "El Paso, TX"),
    ("Dublin, IE", "Cork, IE", "Limerick, IE", "Galway, IE"),
    ("Toronto, CA", "Ottawa, CA", "Montreal, CA", "Quebec City, CA"),
]


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def new_records(shipments_count: int = 36, containers_count: int | None = None, seed: int = SEED) -> dict[str, list[dict[str, Any]]]:
    if shipments_count < 1:
        raise ValueError("shipments_count must be at least 1")
    containers_count = containers_count or min(300, shipments_count)
    if containers_count < 1 or containers_count > 300:
        raise ValueError("containers_count must be between 1 and 300")

    rng = random.Random(seed)
    rows: dict[str, list[dict[str, Any]]] = {
        key: [] for key in (
            "product", "threshold_policy", "container", "sensor", "shipment",
            "shipment_container", "sensor_assignment", "route_stop", "sensor_reading",
            "excursion", "custody_event", "corrective_action", "corrective_action_status_event", "notification",
            "shipment_status_event", "ground_truth",
        )
    }

    for product_id, name, category, tmin, tmax, hmin, hmax, allowance in PRODUCTS:
        rows["product"].append({"id": product_id, "name": name, "category": category, "created_at": iso(START)})
        rows["threshold_policy"].append({
            "id": f"POL-{product_id[-6:]}-V1", "product_id": product_id,
            "min_temperature_c": tmin, "max_temperature_c": tmax,
            "min_humidity_pct": hmin, "max_humidity_pct": hmax,
            "permissible_excursion_minutes": allowance, "effective_from": iso(START),
            "effective_to": None,
        })

    for index in range(1, containers_count + 1):
        container_id = f"CNT-{index:06d}"
        rows["container"].append({
            "id": container_id, "container_type": "active_refrigerated",
            "capacity_liters": rng.choice([240, 320, 480, 600]),
            "lifecycle_state": "available", "created_at": iso(START),
        })
        rows["sensor"].append({
            "id": f"SNS-{container_id}-TEMP", "container_id": container_id,
            "sensor_type": "TEMP_HUMIDITY",
            "calibration_status": "expired" if index % 13 == 0 else "calibrated",
            "calibrated_at": iso(START - timedelta(days=180 if index % 13 == 0 else 20)),
            "calibration_due_at": iso(START - timedelta(days=1) if index % 13 == 0 else START + timedelta(days=160)),
            "serial_number": f"CAL-{index:08d}",
        })

    departure_span = timedelta(days=1)
    departure_intervals = max(1, shipments_count - 1)
    for index in range(1, shipments_count + 1):
        shipment_id = f"SHP-2026-{index:06d}"
        product = PRODUCTS[(index - 1) % len(PRODUCTS)]
        product_id, _, _, tmin, tmax, hmin, hmax, allowance = product
        policy_id = f"POL-{product_id[-6:]}-V1"
        container_index = (index - 1) % containers_count + 1
        container_id = f"CNT-{container_index:06d}"
        sensor_id = f"SNS-{container_id}-TEMP"
        sensor = rows["sensor"][container_index - 1]
        route_variant = index % len(ROUTES)
        route = ROUTES[route_variant]
        departed = START + departure_span * ((index - 1) / departure_intervals)
        trip_days = rng.randint(2, 5)
        planned_duration = timedelta(days=trip_days)
        route_delay = timedelta(hours=8) if index % 11 == 0 else timedelta(0)
        actual_duration = planned_duration + route_delay
        delivered = departed + actual_duration
        reference_time = REFERENCE_TIME
        issue_type = None
        if index == 5:
            issue_type = "delivery_before_departure"
            delivered = departed - timedelta(minutes=15)
        status = "delivered" if delivered <= reference_time else "in_transit"
        rows["shipment"].append({
            "id": shipment_id, "product_id": product_id, "origin": route[0],
            "destination": route[3], "status": status, "departed_at": iso(departed),
            "eta": iso(departed + planned_duration), "delivered_at": iso(delivered) if status == "delivered" else None,
            "created_at": iso(departed - timedelta(hours=12)), "issue_type": issue_type,
        })
        rows["shipment_container"].append({
            "shipment_id": shipment_id, "container_id": container_id,
            "assigned_at": iso(departed - timedelta(minutes=30)),
            "released_at": iso(delivered) if status == "delivered" and delivered >= departed else None,
        })
        rows["sensor_assignment"].append({
            "sensor_id": sensor_id, "shipment_id": shipment_id,
            "assigned_at": iso(departed - timedelta(minutes=20)),
            "unassigned_at": iso(delivered) if status == "delivered" and delivered >= departed else None,
        })
        rows["shipment_status_event"].append({
            "id": f"STE-{index:08d}-01", "shipment_id": shipment_id,
            "from_status": None, "to_status": "planned",
            "occurred_at": iso(departed - timedelta(hours=12)), "actor": "production_planner",
        })
        rows["shipment_status_event"].append({
            "id": f"STE-{index:08d}-02", "shipment_id": shipment_id,
            "from_status": "planned", "to_status": "in_transit",
            "occurred_at": iso(departed), "actor": "plant_operator",
        })
        if status == "delivered":
            rows["shipment_status_event"].append({
                "id": f"STE-{index:08d}-03", "shipment_id": shipment_id,
                "from_status": "in_transit", "to_status": "delivered",
                "occurred_at": iso(delivered), "actor": "plant_operator",
            })
        if issue_type:
            rows["ground_truth"].append({
                "entity_type": "shipment", "entity_id": shipment_id, "issue_type": issue_type,
                "expected_decision": "flag_invalid_delivery_timeline",
                "description": "Injected delivery timestamp precedes the shipment departure.",
            })

        stops = [departed, departed + actual_duration / 3, departed + actual_duration * 2 / 3, departed + actual_duration]
        stop_ids: list[str] = []
        for stop_index, (location, planned_at) in enumerate(zip(route, [departed, departed + planned_duration / 3, departed + planned_duration * 2 / 3, departed + planned_duration]), 1):
            actual_at = stops[stop_index - 1]
            stop_status = "delayed" if route_delay and stop_index == 4 and actual_at <= reference_time else ("completed" if actual_at <= reference_time else "planned")
            stop_id = f"STP-{index:06d}-{stop_index:02d}"
            stop_ids.append(stop_id)
            rows["route_stop"].append({
                "id": stop_id, "shipment_id": shipment_id, "sequence_number": stop_index,
                "location": location, "planned_at": iso(planned_at),
                "actual_at": iso(actual_at) if stop_status != "planned" else None,
                "status": stop_status,
            })
            if stop_status != "planned":
                rows["custody_event"].append({
                    "id": f"CUS-{index:06d}-{stop_index:02d}", "shipment_id": shipment_id,
                    "route_stop_id": stop_id, "event_type": "handoff" if stop_index in (1, 4) else "checkpoint",
                    "actor": ("plant_operator", "carrier", "carrier", "receiving_team")[stop_index - 1],
                    "location": location, "occurred_at": iso(actual_at),
                    "notes": "Route delay recorded." if stop_status == "delayed" else None,
                })

        t_cursor = departed
        total_minutes = int(actual_duration.total_seconds() // 60)
        trip_step_count = total_minutes // INTERVAL_MINUTES
        observation_end = min(departed + actual_duration, reference_time)
        observed_minutes = int((observation_end - departed).total_seconds() // 60)
        step_count = max(0, observed_minutes // INTERVAL_MINUTES)
        scenario = "humidity" if index % 8 == 0 else (
            "brief" if index % 4 == 2 else ("prolonged" if index % 4 == 3 else "normal")
        )
        excursion_start_step = max(10, step_count // 2)
        excursion_length = 2 if scenario == "brief" else (12 if scenario in ("prolonged", "humidity") else 0)
        excursion_metric = "humidity" if scenario == "humidity" else "temperature"
        excursion_values: list[float] = []
        readings: list[dict[str, Any]] = []
        for step in range(step_count + 1):
            recorded = t_cursor + timedelta(minutes=INTERVAL_MINUTES * step)
            if index % 17 == 0 and excursion_start_step + 24 <= step < excursion_start_step + 27:
                continue
            temperature = round((tmin + tmax) / 2 + rng.uniform(-0.7, 0.7), 2)
            humidity = round((hmin + hmax) / 2 + rng.uniform(-4, 4), 2)
            issue = None
            if excursion_length and excursion_start_step <= step < excursion_start_step + excursion_length:
                if excursion_metric == "humidity":
                    humidity = round(hmax + 1.0 + rng.uniform(0, 3), 2)
                else:
                    temperature = round(tmax + 1.0 + rng.uniform(0, 1), 2)
            if index == 1 and step == 20:
                temperature = 86.0
                issue = "reading_outside_physical_range"
                rows["ground_truth"].append({
                    "entity_type": "sensor_reading", "entity_id": f"RDG-{sensor_id}-{stamp(recorded)}",
                    "issue_type": issue, "expected_decision": "reject_as_physically_impossible",
                    "description": "Injected temperature outside the supported physical range (-80 to 85 C).",
                })
            if index == 2 and step == excursion_start_step:
                issue = "threshold_applied_to_wrong_product"
            policy_used = policy_id
            if index == 2 and step == excursion_start_step:
                policy_used = f"POL-{PRODUCTS[(index) % len(PRODUCTS)][0][-6:]}-V1"
            if index == 2 and step == excursion_start_step:
                rows["ground_truth"].append({
                    "entity_type": "sensor_reading", "entity_id": f"RDG-{sensor_id}-{stamp(recorded)}",
                    "issue_type": issue, "expected_decision": "flag_policy_product_mismatch",
                    "description": "Injected reading references a policy for a different product.",
                })
            if index == 3 and step == excursion_start_step:
                rows["ground_truth"].append({
                    "entity_type": "excursion", "entity_id": f"EXC-2026-{index:06d}",
                    "issue_type": "excursion_duration_undercounted", "expected_decision": "use_reading_derived_duration",
                    "description": "The reported duration is deliberately lower than the reading-derived duration.",
                })
            quality = "out_of_physical_range" if issue == "reading_outside_physical_range" else (
                "calibration_warning" if sensor["calibration_status"] != "calibrated" else "valid"
            )
            reading = {
                "id": f"RDG-{sensor_id}-{stamp(recorded)}", "sensor_id": sensor_id,
                "shipment_id": shipment_id,
                "route_stop_id": stop_ids[min(3, step * 4 // max(1, trip_step_count + 1))],
                "recorded_at": iso(recorded),
                "temperature_c": temperature, "humidity_pct": humidity,
                "threshold_policy_id": policy_used, "quality_status": quality, "issue_type": issue,
            }
            readings.append(reading)
            if step >= excursion_start_step and step < excursion_start_step + excursion_length:
                excursion_values.append(humidity if excursion_metric == "humidity" else temperature)
        rows["sensor_reading"].extend(readings)

        # A missing fixed-interval sample is a gap, never evidence of safe conditions.
        if index % 17 == 0:
            gap_at = t_cursor + timedelta(minutes=INTERVAL_MINUTES * (excursion_start_step + 24))
            rows["ground_truth"].append({
                "entity_type": "sensor_reading", "entity_id": f"{sensor_id}-{stamp(gap_at)}",
                "issue_type": "missing_interval", "expected_decision": "flag_data_gap",
                "description": "Three five-minute samples are absent due to a simulated sensor dropout.",
            })

        if excursion_length:
            started = t_cursor + timedelta(minutes=INTERVAL_MINUTES * excursion_start_step)
            ended = started + timedelta(minutes=INTERVAL_MINUTES * (excursion_length - 1))
            duration = max(0, int((ended - started).total_seconds() // 60) + INTERVAL_MINUTES)
            over_allowance = duration > allowance
            severity = "high" if over_allowance else "low"
            status_exc = "open" if over_allowance else "resolved"
            excursion_id = f"EXC-2026-{index:06d}"
            reported_duration = max(0, duration - 20) if index == 3 else duration
            exc_issue = "excursion_duration_undercounted" if index == 3 else None
            rows["excursion"].append({
                "id": excursion_id, "shipment_id": shipment_id, "sensor_id": sensor_id,
                "threshold_policy_id": policy_id, "started_at": iso(started), "ended_at": iso(ended),
                "duration_minutes": duration, "reported_duration_minutes": reported_duration,
                "metric": excursion_metric, "unit": "%RH" if excursion_metric == "humidity" else "°C",
                "severity": severity, "status": status_exc,
                "min_value": min(excursion_values), "max_value": max(excursion_values),
                "issue_type": exc_issue,
            })
            action_status = "open" if over_allowance else "completed"
            rows["corrective_action"].append({
                "id": f"ACT-{index:06d}-01", "excursion_id": excursion_id,
                "owner": "quality_engineer" if over_allowance else "plant_operator",
                "description": "Investigate product exposure and document disposition." if over_allowance
                else f"Review brief {excursion_metric} excursion and confirm product remained within allowance.",
                "status": action_status, "created_at": iso(ended),
                "due_at": iso(ended + timedelta(hours=4 if over_allowance else 24)),
                "completed_at": None if over_allowance else iso(ended + timedelta(hours=1)),
            })
            action = rows["corrective_action"][-1]
            rows["corrective_action_status_event"].append({
                "id": f"ACE-{index:06d}-01", "action_id": action["id"],
                "from_status": None, "to_status": action_status,
                "occurred_at": action["created_at"],
                "actor": action["owner"], "note": "Corrective action created from excursion decision.",
            })
            rows["notification"].append({
                "id": f"NTF-{index:06d}-01", "shipment_id": shipment_id,
                "excursion_id": excursion_id,
                "recipient_role": "quality_engineer" if over_allowance else "plant_operator",
                "message": f"{severity.title()} {excursion_metric} excursion detected for {shipment_id}.",
                "created_at": iso(started), "acknowledged_at": None if over_allowance else iso(ended),
            })

    latest_status_by_container: dict[str, str] = {}
    for shipment, assignment in zip(rows["shipment"], rows["shipment_container"]):
        latest_status_by_container[assignment["container_id"]] = shipment["status"]
    for container in rows["container"]:
        sensor = rows["sensor"][int(container["id"][-6:]) - 1]
        if latest_status_by_container.get(container["id"]) == "in_transit":
            container["lifecycle_state"] = "in_transit"
        elif sensor["calibration_status"] != "calibrated":
            container["lifecycle_state"] = "maintenance"

    return rows


def validate(records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    counts = {name: len(items) for name, items in records.items()}
    for table, rows in records.items():
        if table == "ground_truth":
            continue
        ids = [row["id"] for row in rows if "id" in row]
        duplicates = [key for key, count in Counter(ids).items() if count > 1]
        if duplicates:
            errors.append(f"{table}: duplicate primary keys ({duplicates[:3]})")

    products = {r["id"] for r in records["product"]}
    policies = {r["id"]: r for r in records["threshold_policy"]}
    shipments = {r["id"]: r for r in records["shipment"]}
    containers = {r["id"] for r in records["container"]}
    sensors = {r["id"]: r for r in records["sensor"]}
    stops = {r["id"]: r for r in records["route_stop"]}
    excursions = {r["id"] for r in records["excursion"]}
    shipment_container_pairs = {
        (row["shipment_id"], row["container_id"]) for row in records["shipment_container"]
    }
    sensor_assignment_pairs = {
        (row["sensor_id"], row["shipment_id"]) for row in records["sensor_assignment"]
    }
    for row in records["threshold_policy"]:
        if row["product_id"] not in products:
            errors.append(f"threshold policy {row['id']}: missing product")
        if row["effective_to"] is not None and row["effective_to"] <= row["effective_from"]:
            errors.append(f"threshold policy {row['id']}: invalid effective date range")
    for row in records["sensor"]:
        if row["calibration_due_at"] < row["calibrated_at"]:
            errors.append(f"sensor {row['id']}: calibration due date precedes calibration")
    for row in records["shipment"]:
        if row["product_id"] not in products:
            errors.append(f"shipment {row['id']}: missing product")
        if row["created_at"] > row["departed_at"]:
            errors.append(f"shipment {row['id']}: created after departure")
        if row["status"] != "delivered" and row["eta"] < row["departed_at"]:
            errors.append(f"shipment {row['id']}: ETA precedes departure")
        if row["status"] == "delivered" and row["delivered_at"] is None:
            errors.append(f"shipment {row['id']}: delivered status missing delivered_at")
        if row["status"] == "in_transit" and row["delivered_at"] is not None:
            errors.append(f"shipment {row['id']}: in-transit status has delivered_at")
        # The deliberately injected edge case is recorded as ground truth.
        if row["delivered_at"] is not None and row["delivered_at"] < row["departed_at"] and row["issue_type"] != "delivery_before_departure":
            errors.append(f"shipment {row['id']}: unexpected delivery before departure")
    for row in records["shipment_container"]:
        if row["shipment_id"] not in shipments or row["container_id"] not in containers:
            errors.append("shipment_container: invalid foreign key")
        elif row["released_at"] is not None and row["released_at"] < row["assigned_at"]:
            errors.append(f"shipment_container {row['shipment_id']}: release precedes assignment")
    for row in records["sensor_assignment"]:
        if row["sensor_id"] not in sensors or row["shipment_id"] not in shipments:
            errors.append("sensor_assignment: invalid foreign key")
        elif (row["shipment_id"], sensors[row["sensor_id"]]["container_id"]) not in shipment_container_pairs:
            errors.append(f"sensor assignment {row['sensor_id']}: sensor container is not assigned to shipment")
        elif row["unassigned_at"] is not None and row["unassigned_at"] < row["assigned_at"]:
            errors.append(f"sensor assignment {row['sensor_id']}: unassignment precedes assignment")

    route_groups: dict[str, list[dict[str, Any]]] = {}
    for row in records["route_stop"]:
        if row["shipment_id"] not in shipments:
            errors.append(f"route stop {row['id']}: missing shipment")
        route_groups.setdefault(row["shipment_id"], []).append(row)
    for shipment_id, route in route_groups.items():
        route.sort(key=lambda stop: stop["sequence_number"])
        if any(route[i]["planned_at"] > route[i + 1]["planned_at"] for i in range(len(route) - 1)):
            errors.append(f"shipment {shipment_id}: route plan is not chronological")
        for stop in route:
            if (stop["status"] == "planned") != (stop["actual_at"] is None):
                errors.append(f"route stop {stop['id']}: status and actual timestamp disagree")
            if stop["actual_at"] is not None and stop["actual_at"] < shipments[shipment_id]["departed_at"]:
                errors.append(f"route stop {stop['id']}: actual time precedes departure")

    reading_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in records["sensor_reading"]:
        if row["sensor_id"] not in sensors or row["shipment_id"] not in shipments or row["threshold_policy_id"] not in policies:
            errors.append(f"reading {row['id']}: invalid foreign key")
        else:
            if (row["sensor_id"], row["shipment_id"]) not in sensor_assignment_pairs:
                errors.append(f"reading {row['id']}: sensor is not assigned to shipment")
            if policies[row["threshold_policy_id"]]["product_id"] != shipments[row["shipment_id"]]["product_id"] and row["issue_type"] != "threshold_applied_to_wrong_product":
                errors.append(f"reading {row['id']}: threshold policy does not match product")
        if not -80 <= row["temperature_c"] <= 85 and row["issue_type"] != "reading_outside_physical_range":
            errors.append(f"reading {row['id']}: unexplained temperature outside physical range")
        if not 0 <= row["humidity_pct"] <= 100:
            errors.append(f"reading {row['id']}: humidity outside 0-100%")
        if row["route_stop_id"] not in stops:
            errors.append(f"reading {row['id']}: invalid route stop")
        elif stops[row["route_stop_id"]]["shipment_id"] != row["shipment_id"]:
            errors.append(f"reading {row['id']}: route stop belongs to a different shipment")
        policy = policies.get(row["threshold_policy_id"])
        if policy and row["recorded_at"] < policy["effective_from"]:
            errors.append(f"reading {row['id']}: threshold policy is not yet effective")
        if policy and policy["effective_to"] and row["recorded_at"] >= policy["effective_to"]:
            errors.append(f"reading {row['id']}: threshold policy has expired")
        reading_groups.setdefault((row["sensor_id"], row["shipment_id"]), []).append(row)
    gap_count = 0
    for (sensor_id, shipment_id), readings in reading_groups.items():
        readings.sort(key=lambda reading: reading["recorded_at"])
        for previous, current in zip(readings, readings[1:]):
            delta_minutes = int((parse_iso(current["recorded_at"]) - parse_iso(previous["recorded_at"])).total_seconds() // 60)
            if delta_minutes < INTERVAL_MINUTES:
                errors.append(f"sensor {sensor_id} shipment {shipment_id}: duplicate or out-of-order reading interval")
            elif delta_minutes > INTERVAL_MINUTES:
                gap_count += 1
    for row in records["excursion"]:
        if row["shipment_id"] not in shipments or row["sensor_id"] not in sensors or row["threshold_policy_id"] not in policies:
            errors.append(f"excursion {row['id']}: invalid foreign key")
        if row["ended_at"] < row["started_at"]:
            errors.append(f"excursion {row['id']}: end precedes start")
        policy = policies.get(row["threshold_policy_id"])
        if policy:
            low, high = (policy["min_humidity_pct"], policy["max_humidity_pct"]) if row["metric"] == "humidity" else (
                policy["min_temperature_c"], policy["max_temperature_c"]
            )
            if row["min_value"] >= low and row["max_value"] <= high:
                errors.append(f"excursion {row['id']}: evidence does not exceed its policy threshold")
            expected_severity = "high" if row["duration_minutes"] > policy["permissible_excursion_minutes"] else "low"
            if row["severity"] != expected_severity:
                errors.append(f"excursion {row['id']}: severity does not reconcile with policy allowance")
        expected = max(0, int((datetime.fromisoformat(row["ended_at"].replace("Z", "+00:00")) -
                               datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))).total_seconds() // 60) + INTERVAL_MINUTES)
        if row["duration_minutes"] != expected:
            errors.append(f"excursion {row['id']}: duration does not reconcile to timestamps")
    for row in records["custody_event"]:
        if row["shipment_id"] not in shipments or (row["route_stop_id"] and row["route_stop_id"] not in stops):
            errors.append(f"custody event {row['id']}: invalid foreign key")
        elif row["route_stop_id"] and stops[row["route_stop_id"]]["shipment_id"] != row["shipment_id"]:
            errors.append(f"custody event {row['id']}: route stop belongs to a different shipment")
    custody_groups: dict[str, list[dict[str, Any]]] = {}
    for row in records["custody_event"]:
        custody_groups.setdefault(row["shipment_id"], []).append(row)
    for shipment_id, events in custody_groups.items():
        if any(events[i]["occurred_at"] > events[i + 1]["occurred_at"] for i in range(len(events) - 1)):
            errors.append(f"shipment {shipment_id}: custody timeline is not ordered")
    for row in records["corrective_action"]:
        if row["excursion_id"] not in excursions:
            errors.append(f"action {row['id']}: missing excursion")
    action_ids = {row["id"] for row in records["corrective_action"]}
    if any(row["action_id"] not in action_ids for row in records["corrective_action_status_event"]):
        errors.append("corrective action event: invalid foreign key")

    known_anomalies = {row["entity_id"] for row in records["ground_truth"]}
    anomaly_rows = [r for r in records["sensor_reading"] if r["issue_type"]]
    anomaly_rows.extend(r for r in records["shipment"] if r["issue_type"])
    anomaly_rows.extend(r for r in records["excursion"] if r["issue_type"])
    if any(row["id"] not in known_anomalies for row in anomaly_rows):
        errors.append("An injected anomaly has no ground-truth record")
    valid_shipment_transitions = {(None, "planned"), ("planned", "in_transit"), ("in_transit", "delivered")}
    if any((row["from_status"], row["to_status"]) not in valid_shipment_transitions for row in records["shipment_status_event"]):
        errors.append("shipment status event: invalid lifecycle transition")
    valid_action_transitions = {(None, "open"), (None, "completed"), ("open", "in_progress"), ("in_progress", "completed")}
    if any((row["from_status"], row["to_status"]) not in valid_action_transitions for row in records["corrective_action_status_event"]):
        errors.append("corrective action event: invalid lifecycle transition")

    shipment_excursion_counts = Counter(row["shipment_id"] for row in records["excursion"])
    excursion_scenarios = Counter()
    for row in records["excursion"]:
        allowance = policies[row["threshold_policy_id"]]["permissible_excursion_minutes"]
        excursion_scenarios["brief" if row["duration_minutes"] <= allowance else "prolonged"] += 1
    coverage = {
        "shipments_by_status": dict(sorted(Counter(row["status"] for row in records["shipment"]).items())),
        "containers_by_lifecycle_state": dict(sorted(Counter(row["lifecycle_state"] for row in records["container"]).items())),
        "sensors_by_calibration_status": dict(sorted(Counter(row["calibration_status"] for row in records["sensor"]).items())),
        "readings_by_quality_status": dict(sorted(Counter(row["quality_status"] for row in records["sensor_reading"]).items())),
        "excursions_by_severity": dict(sorted(Counter(row["severity"] for row in records["excursion"]).items())),
        "excursions_by_metric": dict(sorted(Counter(row["metric"] for row in records["excursion"]).items())),
        "excursions_by_duration_scenario": dict(sorted(excursion_scenarios.items())),
        "shipments_without_excursions": sum(1 for row in records["shipment"] if not shipment_excursion_counts[row["id"]]),
        "delayed_route_stops": sum(1 for row in records["route_stop"] if row["status"] == "delayed"),
        "ground_truth_issue_types": dict(sorted(Counter(row["issue_type"] for row in records["ground_truth"]).items())),
    }

    return {
        "valid": not errors,
        "errors": errors,
        "record_counts": counts,
        "checks": {
            "primary_keys_unique": not any("duplicate primary keys" in e for e in errors),
            "foreign_keys_valid": not any("invalid foreign key" in e or "missing " in e for e in errors),
            "joins_match_parent_records": not any("does not match" in e or "belongs to a different shipment" in e or "not assigned" in e for e in errors),
            "date_and_duration_reconciliation": not any(
                marker in error for error in errors
                for marker in ("precedes", "after departure", "invalid effective date range", "duration does not reconcile")
            ),
            "lifecycle_transitions_valid": not any("invalid lifecycle transition" in e for e in errors),
            "custody_timelines_ordered": not any("custody timeline is not ordered" in e for e in errors),
            "reading_gaps_flagged": gap_count == sum(1 for row in records["ground_truth"] if row["issue_type"] == "missing_interval"),
            "anomalies_have_ground_truth": not any("no ground-truth" in e for e in errors),
        },
        "observed_reading_gaps": gap_count,
        "coverage": coverage,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def write_sql_seed(path: Path, records: dict[str, list[dict[str, Any]]]) -> None:
    insert_order = (
        "product", "threshold_policy", "container", "sensor", "shipment",
        "shipment_container", "sensor_assignment", "route_stop", "sensor_reading",
        "excursion", "custody_event", "corrective_action", "corrective_action_status_event",
        "notification", "shipment_status_event",
    )
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("-- Apply database/schema.sql before this generated operational seed.\n")
        file.write("PRAGMA foreign_keys = ON;\nBEGIN;\n")
        for table in insert_order:
            rows = records[table]
            if not rows:
                continue
            columns = list(rows[0])
            column_sql = ", ".join(f'"{column}"' for column in columns)
            prefix = f'INSERT INTO "{table}" ({column_sql}) VALUES '
            for row in rows:
                values = ", ".join(sql_value(row[column]) for column in columns)
                file.write(f"{prefix}({values});\n")
        file.write("COMMIT;\n")


def persist_sqlite(path: Path, records: dict[str, list[dict[str, Any]]]) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        insert_order = (
            "product", "threshold_policy", "container", "sensor", "shipment",
            "shipment_container", "sensor_assignment", "route_stop", "sensor_reading",
            "excursion", "custody_event", "corrective_action", "corrective_action_status_event", "notification",
            "shipment_status_event",
        )
        for table in insert_order:
            rows = records[table]
            if rows:
                columns = list(rows[0])
                query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
                connection.executemany(query, ([row[column] for column in columns] for row in rows))
        connection.commit()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError(f"SQLite foreign-key validation failed: {foreign_key_errors[:5]}")
    finally:
        connection.close()


def export(records: dict[str, list[dict[str, Any]]], output: Path, seed: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    validation = validate(records)
    if not validation["valid"]:
        raise ValueError("Generated dataset failed validation: " + "; ".join(validation["errors"][:10]))
    manifest = {
        "generator": "CryoNexa synthetic cold-chain generator",
        "generator_version": "1.0.0",
        "seed": seed,
        "anchor_utc": iso(START),
        "simulation_reference_utc": iso(REFERENCE_TIME),
        "interval_minutes": INTERVAL_MINUTES,
        "trip_duration_days": [2, 5],
        "shipment_count": len(records["shipment"]),
        "container_count": len(records["container"]),
        "provenance": "Entirely synthetic; no external or personal data used.",
        "ground_truth_separate": True,
        "exports": ["CSV", "JSON ground truth", "SQLite", "SQL seed"],
        "record_counts": validation["record_counts"],
    }
    file_hashes: dict[str, str] = {}
    for table, rows in records.items():
        if table == "ground_truth":
            continue
        if rows:
            write_csv(output / f"{table}.csv", rows)
    write_sql_seed(output / "seed.sql", records)
    write_csv(output / "ground_truth.csv", records["ground_truth"])
    (output / "ground_truth.json").write_text(json.dumps(records["ground_truth"], indent=2) + "\n", encoding="utf-8")
    (output / "validation_summary.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    (output / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    persist_sqlite(output / "cryo.db", records)
    for file in sorted(output.iterdir()):
        if file.is_file() and file.name != "checksums.json":
            file_hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    (output / "checksums.json").write_text(json.dumps(file_hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic CryoNexa synthetic cold-chain data.")
    parser.add_argument("--shipments", type=int, default=36, help="Number of shipments (full dataset: 1000).")
    parser.add_argument("--containers", type=int, help="Number of containers (default: min(300, shipments)).")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records = new_records(args.shipments, args.containers, args.seed)
    result = export(records, args.output, args.seed)
    print(json.dumps({"output": str(args.output.resolve()), **result}, indent=2))


if __name__ == "__main__":
    main()
