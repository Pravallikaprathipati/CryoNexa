import unittest
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from app.generate import REFERENCE_TIME, SCHEMA_PATH, START, export, new_records, validate


class GeneratorTests(unittest.TestCase):
    def test_seeded_generation_is_reproducible(self):
        first = new_records(shipments_count=8, seed=20261022)
        second = new_records(shipments_count=8, seed=20261022)
        self.assertEqual(first, second)

    def test_relations_and_injected_scenarios_validate(self):
        records = new_records(shipments_count=20, seed=20261022)
        result = validate(records)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["record_counts"]["shipment"], 20)
        self.assertTrue(any(row["issue_type"] == "reading_outside_physical_range" for row in records["ground_truth"]))
        self.assertTrue(any(row["issue_type"] == "missing_interval" for row in records["ground_truth"]))
        self.assertTrue(any(row["issue_type"] == "delivery_before_departure" for row in records["ground_truth"]))
        self.assertTrue(any(row["issue_type"] == "threshold_applied_to_wrong_product" for row in records["ground_truth"]))
        self.assertTrue(any(row["issue_type"] == "excursion_duration_undercounted" for row in records["ground_truth"]))
        self.assertGreater(result["record_counts"]["sensor_reading"], 20 * 500)
        self.assertEqual(result["coverage"]["excursions_by_duration_scenario"], {"brief": 5, "prolonged": 7})
        self.assertGreater(result["coverage"]["excursions_by_metric"]["humidity"], 0)
        self.assertGreater(result["coverage"]["delayed_route_stops"], 0)

    def test_different_seeds_change_measurements_not_identifiers(self):
        first = new_records(shipments_count=4, seed=10)
        second = new_records(shipments_count=4, seed=11)
        self.assertEqual([row["id"] for row in first["shipment"]], [row["id"] for row in second["shipment"]])
        self.assertNotEqual(first["sensor_reading"][0]["temperature_c"], second["sensor_reading"][0]["temperature_c"])

    def test_shipments_fit_a_bounded_simulation_window(self):
        records = new_records(shipments_count=20, seed=20261022)
        departures = [datetime.fromisoformat(row["departed_at"].replace("Z", "+00:00")) for row in records["shipment"]]
        latest_reading = max(datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00")) for row in records["sensor_reading"])

        self.assertLessEqual(max(departures) - min(departures), timedelta(days=1))
        self.assertEqual(min(departures), START)
        self.assertLessEqual(latest_reading, REFERENCE_TIME)
        self.assertTrue(any(row["status"] == "in_transit" for row in records["shipment"]))

    def test_exports_are_byte_reproducible_and_ground_truth_is_separate(self):
        records = new_records(shipments_count=4, seed=20261022)
        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first"
            second = Path(temporary_directory) / "second"
            first_validation = export(records, first, 20261022)
            second_validation = export(new_records(shipments_count=4, seed=20261022), second, 20261022)
            self.assertEqual(first_validation["record_counts"], second_validation["record_counts"])
            self.assertEqual(
                json.loads((first / "checksums.json").read_text()),
                json.loads((second / "checksums.json").read_text()),
            )
            connection = sqlite3.connect(first / "cryo.db")
            try:
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertNotIn("ground_truth", table_names)
            finally:
                connection.close()
            seed_connection = sqlite3.connect(Path(temporary_directory) / "seeded.db")
            try:
                seed_connection.executescript(SCHEMA_PATH.read_text())
                seed_connection.executescript((first / "seed.sql").read_text())
                self.assertEqual(seed_connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(seed_connection.execute("SELECT COUNT(*) FROM shipment").fetchone()[0], 4)
                self.assertNotIn(
                    "ground_truth",
                    {row[0] for row in seed_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                )
            finally:
                seed_connection.close()


if __name__ == "__main__":
    unittest.main()
