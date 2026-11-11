# CryoNexa data dictionary

All timestamps are UTC ISO-8601 strings ending in `Z`; generated identifiers are immutable. CSVs mirror the operational tables unless noted. `ground_truth.csv/json` is a separate evaluation sidecar and is never imported into the operational database or exposed by the API.

## Entities

| Entity | Field | Type / required | Unit / allowed values | Uniqueness and validation |
|---|---|---|---|---|
| Product | `id` | string, required | `PRD-` plus six digits | Primary key; immutable |
| Product | `name` | string, required | Human-readable | Unique, non-empty |
| Product | `category` | string, required | `biologic`, `vaccine`, `reagent`, `pharmaceutical`, `diagnostic` | Non-empty |
| Product | `created_at` | timestamp, required | UTC | Must parse as UTC |
| Shipment | `id` | string, required | `SHP-2026-` plus six digits | Primary key; immutable |
| Shipment | `product_id` | string, required | Product FK | Must reference Product |
| Shipment | `origin`, `destination` | string, required | Synthetic locations | Non-empty |
| Shipment | `status` | enum, required | `planned`, `in_transit`, `delivered`, `exception` | Must follow status-event history |
| Shipment | `departed_at`, `eta` | timestamp, required | UTC | ETA must not precede departure |
| Shipment | `delivered_at` | timestamp, optional | UTC | Required when delivered except explicitly labelled injected anomalies |
| Shipment | `created_at` | timestamp, required | UTC | Must not follow departure |
| Shipment | `issue_type` | string, optional | Known anomaly label | Set only for intentional edge cases |
| Container | `id` | string, required | `CNT-` plus six digits | Primary key; immutable |
| Container | `container_type` | string, required | `active_refrigerated` | Non-empty |
| Container | `capacity_liters` | integer, required | Liters | Positive |
| Container | `lifecycle_state` | enum, required | `available`, `in_transit`, `maintenance` | Must match assignment state |
| Container | `created_at` | timestamp, required | UTC | Must parse as UTC |
| Sensor | `id` | string, required | `SNS-CNT-xxxxxx-TEMP` | Primary key; immutable |
| Sensor | `container_id` | string, required | Container FK | Must reference Container |
| Sensor | `sensor_type` | enum, required | `TEMP_HUMIDITY` | Supported sensor type |
| Sensor | `calibration_status` | enum, required | `calibrated`, `expired`, `failed` | Calibration dates determine expiry |
| Sensor | `calibrated_at`, `calibration_due_at` | timestamp, required | UTC | Due date must not precede calibration |
| Sensor | `serial_number` | string, required | Calibration serial | Unique, non-empty |
| SensorReading | `id` | string, required | `RDG-<sensor-id>-<YYYYMMDDThhmmssZ>` | Primary key; unique per sensor/time |
| SensorReading | `sensor_id`, `shipment_id` | string, required | Sensor and Shipment FKs | Both parents must exist and assignment must be effective |
| SensorReading | `route_stop_id` | string, required | RouteStop FK | Must belong to the same shipment |
| SensorReading | `recorded_at` | timestamp, required | UTC; five-minute cadence | Unique with sensor; out-of-order values are invalid |
| SensorReading | `temperature_c` | number, required | °C; physical range -80 to 85 | Outside range only with explicit anomaly label |
| SensorReading | `humidity_pct` | number, required | %RH; 0 to 100 | Inclusive bounds |
| SensorReading | `threshold_policy_id` | string, required | ThresholdPolicy FK | Must match shipment product except labelled mismatch |
| SensorReading | `quality_status` | enum, required | `valid`, `calibration_warning`, `out_of_physical_range` | Must agree with sensor calibration and physical checks |
| SensorReading | `issue_type` | string, optional | Known anomaly label | Only injected edge cases |
| RouteStop | `id` | string, required | `STP-<shipment-sequence>-<stop-sequence>` | Primary key |
| RouteStop | `shipment_id` | string, required | Shipment FK | Must reference Shipment |
| RouteStop | `sequence_number` | integer, required | Positive ordinal | Unique per shipment; route sequence must increase |
| RouteStop | `location` | string, required | Synthetic location | Non-empty |
| RouteStop | `planned_at` | timestamp, required | UTC | Ordered within the route |
| RouteStop | `actual_at` | timestamp, optional | UTC | Must be null when planned, otherwise not before departure |
| RouteStop | `status` | enum, required | `planned`, `completed`, `delayed` | Must agree with actual time and delay |
| ThresholdPolicy | `id` | string, required | `POL-<product>-V1` | Primary key |
| ThresholdPolicy | `product_id` | string, required | Product FK | Product-specific policy |
| ThresholdPolicy | `min_temperature_c`, `max_temperature_c` | number, required | °C | Minimum must be less than maximum |
| ThresholdPolicy | `min_humidity_pct`, `max_humidity_pct` | number, required | %RH | Values in 0–100; minimum <= maximum |
| ThresholdPolicy | `permissible_excursion_minutes` | integer, required | Minutes | Non-negative; determines excursion severity |
| ThresholdPolicy | `effective_from` | timestamp, required | UTC | Policy active at reading time |
| ThresholdPolicy | `effective_to` | timestamp, optional | UTC | Must be later than `effective_from`; null means current |
| Excursion | `id` | string, required | `EXC-2026-` plus six digits | Primary key; immutable |
| Excursion | `shipment_id`, `sensor_id`, `threshold_policy_id` | string, required | Shipment, Sensor, ThresholdPolicy FKs | Must be valid for the affected shipment |
| Excursion | `started_at`, `ended_at` | timestamp, required | UTC | End >= start |
| Excursion | `duration_minutes` | integer, required | Minutes from readings | Derived from interval boundaries, never independently randomized |
| Excursion | `reported_duration_minutes` | integer, optional | Minutes | External/source-reported duration; may differ only when labelled |
| Excursion | `metric`, `unit` | enum, required | `temperature` / `°C`; `humidity` / `%RH` | Metric and unit must match the policy measure |
| Excursion | `severity` | enum, required | `low`, `medium`, `high`, `critical` | Derived from duration vs product policy |
| Excursion | `status` | enum, required | `open`, `investigating`, `resolved`, `accepted` | Must be tracked through corrective-action history |
| Excursion | `min_value`, `max_value` | number, required | Unit from `unit` | Derived from the selected metric's readings in the excursion window |
| Excursion | `issue_type` | string, optional | Known anomaly label | Only injected edge cases |
| CustodyEvent | `id` | string, required | `CUS-<shipment>-<sequence>` | Primary key |
| CustodyEvent | `shipment_id` | string, required | Shipment FK | Must reference Shipment |
| CustodyEvent | `route_stop_id` | string, optional | RouteStop FK | If present, must belong to Shipment |
| CustodyEvent | `event_type` | enum, required | `handoff`, `checkpoint`, `delivery`, `notification` | Supported event |
| CustodyEvent | `actor`, `location` | string, required | Role / location | Non-empty |
| CustodyEvent | `occurred_at` | timestamp, required | UTC | Timeline ordered per shipment |
| CustodyEvent | `notes` | string, optional | Free text | No personal data |
| CorrectiveAction | `id` | string, required | `ACT-<shipment>-<sequence>` | Primary key |
| CorrectiveAction | `excursion_id` | string, required | Excursion FK | Must reference Excursion |
| CorrectiveAction | `owner` | string, required | Operational role | Non-empty |
| CorrectiveAction | `description` | string, required | Action details | Non-empty |
| CorrectiveAction | `status` | enum, required | `open`, `in_progress`, `completed` | Completion timestamp required only when completed |
| CorrectiveAction | `created_at`, `due_at` | timestamp, required | UTC | Due date >= created date |
| CorrectiveAction | `completed_at` | timestamp, optional | UTC | Must not precede creation |

## Relationships and lifecycle

- Product 1:N ThresholdPolicy and Product 1:N Shipment. Policies may be versioned; only one policy per product is effective at a given instant.
- Shipment N:M Container through `shipment_container`; each assignment has an effective start and optional release timestamp. A shipment can have multiple containers and a container is reusable after release.
- Sensor N:M Shipment through `sensor_assignment`; assignments are time-bounded. Each sensor belongs to one Container (Container 1:N Sensor).
- Shipment 1:N RouteStop, SensorReading, Excursion, CustodyEvent, and ShipmentStatusEvent.
- Sensor 1:N SensorReading and Excursion. ThresholdPolicy 1:N SensorReading and Excursion.
- Excursion 1:N CorrectiveAction and 1:N Notification. Notifications may also reference Shipment without an excursion.
- CorrectiveAction 1:N `corrective_action_status_event`; every transition is appended with previous/new status, timestamp, actor, and optional note.
- RouteStop 1:N SensorReading and 0:N CustodyEvent. Each reading references one shipment, one sensor, one route stop, and one effective policy.
- Status changes are append-only in `shipment_status_event`; readings, custody, notifications, and actions are append-only event records. Corrective-action status has explicit timestamps rather than overwriting event history.
- The intentional delivery-before-departure, wrong-policy, out-of-range reading, dropout, and reported-duration-under-count scenarios are documented in the separate ground-truth sidecar and carry an `issue_type` on the affected source record where applicable.
