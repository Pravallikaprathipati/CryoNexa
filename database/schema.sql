PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS product (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS threshold_policy (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES product(id),
    min_temperature_c REAL NOT NULL,
    max_temperature_c REAL NOT NULL,
    min_humidity_pct REAL NOT NULL CHECK (min_humidity_pct BETWEEN 0 AND 100),
    max_humidity_pct REAL NOT NULL CHECK (max_humidity_pct BETWEEN 0 AND 100),
    permissible_excursion_minutes INTEGER NOT NULL CHECK (permissible_excursion_minutes >= 0),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    CHECK (min_temperature_c < max_temperature_c),
    CHECK (min_humidity_pct <= max_humidity_pct)
);

CREATE TABLE IF NOT EXISTS container (
    id TEXT PRIMARY KEY,
    container_type TEXT NOT NULL,
    capacity_liters INTEGER NOT NULL CHECK (capacity_liters > 0),
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('available', 'in_transit', 'maintenance')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensor (
    id TEXT PRIMARY KEY,
    container_id TEXT NOT NULL REFERENCES container(id),
    sensor_type TEXT NOT NULL CHECK (sensor_type IN ('TEMP_HUMIDITY')),
    calibration_status TEXT NOT NULL CHECK (calibration_status IN ('calibrated', 'expired', 'failed')),
    calibrated_at TEXT NOT NULL,
    calibration_due_at TEXT NOT NULL,
    serial_number TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS shipment (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES product(id),
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'in_transit', 'delivered', 'exception')),
    departed_at TEXT NOT NULL,
    eta TEXT NOT NULL,
    delivered_at TEXT,
    created_at TEXT NOT NULL,
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS shipment_container (
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    container_id TEXT NOT NULL REFERENCES container(id),
    assigned_at TEXT NOT NULL,
    released_at TEXT,
    PRIMARY KEY (shipment_id, container_id)
);

CREATE TABLE IF NOT EXISTS sensor_assignment (
    sensor_id TEXT NOT NULL REFERENCES sensor(id),
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    assigned_at TEXT NOT NULL,
    unassigned_at TEXT,
    PRIMARY KEY (sensor_id, shipment_id)
);

CREATE TABLE IF NOT EXISTS route_stop (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    location TEXT NOT NULL,
    planned_at TEXT NOT NULL,
    actual_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('planned', 'completed', 'delayed')),
    UNIQUE (shipment_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS sensor_reading (
    id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL REFERENCES sensor(id),
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    route_stop_id TEXT REFERENCES route_stop(id),
    recorded_at TEXT NOT NULL,
    temperature_c REAL NOT NULL,
    humidity_pct REAL NOT NULL CHECK (humidity_pct BETWEEN 0 AND 100),
    threshold_policy_id TEXT NOT NULL REFERENCES threshold_policy(id),
    quality_status TEXT NOT NULL CHECK (quality_status IN ('valid', 'calibration_warning', 'out_of_physical_range')),
    issue_type TEXT,
    UNIQUE (sensor_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS excursion (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    sensor_id TEXT NOT NULL REFERENCES sensor(id),
    threshold_policy_id TEXT NOT NULL REFERENCES threshold_policy(id),
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 0),
    reported_duration_minutes INTEGER,
    metric TEXT NOT NULL CHECK (metric IN ('temperature', 'humidity')),
    unit TEXT NOT NULL CHECK (unit IN ('°C', '%RH')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL CHECK (status IN ('open', 'investigating', 'resolved', 'accepted')),
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    issue_type TEXT,
    CHECK (ended_at >= started_at)
);

CREATE TABLE IF NOT EXISTS custody_event (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    route_stop_id TEXT REFERENCES route_stop(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('handoff', 'checkpoint', 'delivery', 'notification')),
    actor TEXT NOT NULL,
    location TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS corrective_action (
    id TEXT PRIMARY KEY,
    excursion_id TEXT NOT NULL REFERENCES excursion(id),
    owner TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'completed')),
    created_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS corrective_action_status_event (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES corrective_action(id),
    from_status TEXT,
    to_status TEXT NOT NULL CHECK (to_status IN ('open', 'in_progress', 'completed')),
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS notification (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    excursion_id TEXT REFERENCES excursion(id),
    recipient_role TEXT NOT NULL CHECK (recipient_role IN ('plant_operator', 'quality_engineer', 'production_planner', 'ot_it_admin')),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT
);

CREATE TABLE IF NOT EXISTS shipment_status_event (
    id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipment(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reading_shipment_time ON sensor_reading(shipment_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_reading_recorded_at ON sensor_reading(recorded_at);
CREATE INDEX IF NOT EXISTS idx_excursion_status ON excursion(status, started_at);
CREATE INDEX IF NOT EXISTS idx_shipment_status ON shipment(status);
CREATE INDEX IF NOT EXISTS idx_custody_shipment_time ON custody_event(shipment_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_action_event_time ON corrective_action_status_event(action_id, occurred_at);
