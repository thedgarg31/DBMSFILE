
PRAGMA foreign_keys = ON;

-- Drop existing tables (for idempotent setup in demos)
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS flights;
DROP TABLE IF EXISTS aircraft;
DROP TABLE IF EXISTS airlines;
DROP TABLE IF EXISTS airports;

-- Core reference tables
CREATE TABLE airports (
    airport_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL UNIQUE,       -- IATA code like DEL, BOM
    name           TEXT NOT NULL,
    city           TEXT NOT NULL,
    country        TEXT NOT NULL
);

CREATE TABLE airlines (
    airline_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    iata           TEXT UNIQUE,                -- e.g., AI
    icao           TEXT UNIQUE                 -- e.g., AIC
);

CREATE TABLE aircraft (
    aircraft_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    model          TEXT NOT NULL,              -- e.g., A320, B737
    capacity       INTEGER NOT NULL CHECK (capacity > 0)
);

-- Flights table (each row = a scheduled flight occurrence)
CREATE TABLE flights (
    flight_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_id         INTEGER NOT NULL,
    aircraft_id        INTEGER NOT NULL,
    flight_no          TEXT NOT NULL,          -- e.g., AI-501
    source_airport_id  INTEGER NOT NULL,
    dest_airport_id    INTEGER NOT NULL,
    departure_time     TEXT NOT NULL,          -- ISO8601 'YYYY-MM-DD HH:MM'
    arrival_time       TEXT NOT NULL,
    base_fare          REAL NOT NULL CHECK (base_fare >= 0),
    seats_total        INTEGER NOT NULL CHECK (seats_total > 0),
    seats_available    INTEGER NOT NULL CHECK (seats_available >= 0),
    status             TEXT NOT NULL DEFAULT 'SCHEDULED', -- SCHEDULED/CANCELLED/DELAYED
    UNIQUE (flight_no, departure_time),
    FOREIGN KEY (airline_id)        REFERENCES airlines(airline_id) ON DELETE RESTRICT,
    FOREIGN KEY (aircraft_id)       REFERENCES aircraft(aircraft_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_airport_id) REFERENCES airports(airport_id) ON DELETE RESTRICT,
    FOREIGN KEY (dest_airport_id)   REFERENCES airports(airport_id) ON DELETE RESTRICT
);

-- Customers and bookings
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT
);

CREATE TABLE bookings (
    booking_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_ref   TEXT NOT NULL UNIQUE,    -- human reference like FBX1A2B
    customer_id   INTEGER NOT NULL,
    flight_id     INTEGER NOT NULL,
    booking_time  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'CONFIRMED', -- CONFIRMED/CANCELLED
    total_amount  REAL NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (flight_id)   REFERENCES flights(flight_id) ON DELETE CASCADE
);

CREATE TABLE tickets (
    ticket_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id    INTEGER NOT NULL,
    passenger_name TEXT NOT NULL,
    seat_no       TEXT,                    -- optional simple seat label, not enforcing layout
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

CREATE TABLE payments (
    payment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id    INTEGER NOT NULL,
    amount        REAL NOT NULL CHECK (amount >= 0),
    method        TEXT NOT NULL,          -- UPI/CARD/CASH/REFUND
    status        TEXT NOT NULL DEFAULT 'PAID', -- PAID/FAILED/REFUNDED
    payment_time  TEXT NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

-- Sample data (DML)
INSERT INTO airports (code, name, city, country) VALUES
 ('DEL', 'Indira Gandhi International Airport', 'New Delhi', 'India'),
 ('BOM', 'Chhatrapati Shivaji Maharaj International Airport', 'Mumbai', 'India'),
 ('BLR', 'Kempegowda International Airport', 'Bengaluru', 'India'),
 ('HYD', 'Rajiv Gandhi International Airport', 'Hyderabad', 'India'),
 ('MAA', 'Chennai International Airport', 'Chennai', 'India');

INSERT INTO airlines (name, iata, icao) VALUES
 ('Air India', 'AI', 'AIC'),
 ('IndiGo', '6E', 'IGO'),
 ('Vistara', 'UK', 'VTI');

INSERT INTO aircraft (model, capacity) VALUES
 ('Airbus A320', 180),
 ('Boeing 737-800', 186),
 ('Airbus A321', 220);

-- Create a few flights (IST timezone assumed in display)
INSERT INTO flights
 (airline_id, aircraft_id, flight_no, source_airport_id, dest_airport_id, departure_time, arrival_time, base_fare, seats_total, seats_available, status)
VALUES
 (1, 1, 'AI-201', 1, 2, '2025-08-24 08:30', '2025-08-24 10:30', 5500, 180, 180, 'SCHEDULED'),
 (2, 1, '6E-345', 2, 1, '2025-08-24 12:45', '2025-08-24 14:45', 5200, 180, 175, 'SCHEDULED'),
 (3, 3, 'UK-807', 3, 1, '2025-08-25 06:15', '2025-08-25 08:45', 4800, 220, 220, 'SCHEDULED'),
 (2, 2, '6E-912', 1, 3, '2025-08-26 18:00', '2025-08-26 20:15', 4500, 186, 180, 'SCHEDULED'),
 (1, 2, 'AI-450', 4, 5, '2025-08-27 09:20', '2025-08-27 11:05', 4300, 186, 160, 'SCHEDULED');

-- Optional demo customer
INSERT INTO customers (first_name, last_name, email, phone) VALUES
 ('Daksh', 'Garg', 'daksh@example.com', '+91-9000000000');
