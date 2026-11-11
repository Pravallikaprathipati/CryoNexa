import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import main
from app.generate import export, new_records


class ContainerMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "cryo.db"
        export(new_records(shipments_count=6, containers_count=6, seed=20261022), Path(self.temporary_directory.name), 20261022)
        self.database_path = Path(self.temporary_directory.name) / "cryo.db"
        self.database_patch = patch.object(main, "DB_PATH", self.database_path)
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.temporary_directory.cleanup()

    def test_monitoring_returns_policy_aligned_history_and_excursions(self):
        result = main.container_monitoring("CNT-000002", limit=20, offset=0)

        self.assertEqual(result["container"]["id"], "CNT-000002")
        self.assertGreater(result["reading_count"], len(result["readings"]))
        self.assertEqual(len(result["readings"]), 20)
        self.assertEqual(result["reading_offset"], 0)
        self.assertEqual(result["reading_limit"], 20)
        self.assertEqual(
            result["readings"],
            sorted(result["readings"], key=lambda reading: reading["recorded_at"], reverse=True),
        )
        for reading in result["readings"]:
            self.assertTrue(reading["shipment_id"])
            self.assertTrue(reading["product_name"])
            self.assertIsNotNone(reading["min_temperature_c"])
            self.assertIsNotNone(reading["max_temperature_c"])
            self.assertIsNotNone(reading["min_humidity_pct"])
            self.assertIsNotNone(reading["max_humidity_pct"])
        self.assertTrue(result["excursions"])
        self.assertTrue(all(excursion["shipment_id"] for excursion in result["excursions"]))

    def test_monitoring_paginates_and_rejects_unknown_container(self):
        first_page = main.container_monitoring("CNT-000002", limit=10, offset=0)
        next_page = main.container_monitoring("CNT-000002", limit=10, offset=10)

        self.assertEqual(len(first_page["readings"]), 10)
        self.assertEqual(len(next_page["readings"]), 10)
        self.assertNotEqual(first_page["readings"][0]["id"], next_page["readings"][0]["id"])
        self.assertEqual(first_page["reading_count"], next_page["reading_count"])
        with self.assertRaises(HTTPException) as error:
            main.container_monitoring("CNT-DOES-NOT-EXIST", limit=10, offset=0)
        self.assertEqual(error.exception.status_code, 404)

    def test_dashboard_uses_latest_available_24_hour_window(self):
        dashboard = main.dashboard()
        recent = dashboard["recent_24h"]
        connection = sqlite3.connect(self.database_path)
        try:
            latest = connection.execute("SELECT MAX(recorded_at) FROM sensor_reading").fetchone()[0]
            expected_start = (
                datetime.fromisoformat(latest.replace("Z", "+00:00")) - timedelta(hours=24)
            ).isoformat(timespec="seconds").replace("+00:00", "Z")
            expected_count = connection.execute(
                "SELECT COUNT(*) FROM sensor_reading WHERE recorded_at >= ? AND recorded_at <= ?",
                (expected_start, latest),
            ).fetchone()[0]
            readings_by_sensor = {}
            for shipment_id, sensor_id, recorded_at in connection.execute(
                """SELECT shipment_id, sensor_id, recorded_at FROM sensor_reading
                   ORDER BY shipment_id, sensor_id, recorded_at"""
            ):
                readings_by_sensor.setdefault((shipment_id, sensor_id), []).append(recorded_at)
        finally:
            connection.close()
        start_datetime = datetime.fromisoformat(expected_start.replace("Z", "+00:00"))
        end_datetime = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        expected_gaps = 0
        for readings in readings_by_sensor.values():
            previous = None
            for reading in readings:
                current = datetime.fromisoformat(reading.replace("Z", "+00:00"))
                if (
                    previous is not None
                    and start_datetime <= current <= end_datetime
                    and (current - previous).total_seconds() > 600
                ):
                    expected_gaps += 1
                previous = current

        self.assertEqual(recent["readings"], expected_count)
        self.assertEqual(recent["readings"], sum(point["reading_count"] for point in dashboard["trend"]))
        self.assertGreater(len(dashboard["trend"]), 0)
        self.assertTrue(all(point["hour"].endswith(":00:00Z") for point in dashboard["trend"]))
        self.assertEqual(dashboard["trend"], sorted(dashboard["trend"], key=lambda point: point["hour"]))
        self.assertEqual(recent["window_start"], expected_start)
        self.assertEqual(recent["window_end"], latest)
        self.assertEqual(recent["data_gaps"], expected_gaps)
        expected_age = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(latest.replace("Z", "+00:00"))
        ).total_seconds()
        self.assertLessEqual(abs(recent["dataset_age_seconds"] - expected_age), 2)
        self.assertGreaterEqual(recent["window_end"], recent["window_start"])
        self.assertGreaterEqual(recent["readings"], 1)


if __name__ == "__main__":
    unittest.main()
