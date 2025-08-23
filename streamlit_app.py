
import sqlite3
from contextlib import closing
from datetime import datetime, date, timedelta
import random
import string
import pandas as pd
import streamlit as st

DB_PATH = "flight_booking.db"
SCHEMA_FILE = "flight_booking_schema.sql"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(conn):
    with closing(conn.cursor()) as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flights';")
        exists = cur.fetchone()
    if not exists:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            script = f.read()
        conn.executescript(script)
        conn.commit()

def random_booking_ref(n=6):
    alphabet = string.ascii_uppercase + string.digits
    return "FBX" + "".join(random.choices(alphabet, k=n))

def money(x):
    return f"₹{x:,.0f}"

@st.cache_data(ttl=60)
def get_reference_data():
    with get_conn() as conn:
        airports = pd.read_sql_query("SELECT airport_id, code || ' - ' || city AS label FROM airports ORDER BY city;", conn)
        airlines = pd.read_sql_query("SELECT airline_id, name FROM airlines ORDER BY name;", conn)
    return airports, airlines

def search_flights(src_id, dst_id, travel_date):
    date_str = travel_date.strftime("%Y-%m-%d")
    q = """
        SELECT f.flight_id, a.name AS airline, f.flight_no,
               src.code AS from_code, dst.code AS to_code,
               f.departure_time, f.arrival_time,
               f.base_fare, f.seats_available, f.status
        FROM flights f
        JOIN airlines a ON f.airline_id = a.airline_id
        JOIN airports src ON f.source_airport_id = src.airport_id
        JOIN airports dst ON f.dest_airport_id = dst.airport_id
        WHERE date(f.departure_time) = ?
          AND f.source_airport_id = ?
          AND f.dest_airport_id = ?
          AND f.status = 'SCHEDULED'
        ORDER BY f.departure_time;
    """
    with get_conn() as conn:
        df = pd.read_sql_query(q, conn, params=[date_str, src_id, dst_id])
    return df

def create_or_get_customer(first, last, email, phone):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT customer_id FROM customers WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO customers (first_name, last_name, email, phone) VALUES (?, ?, ?, ?)",
            (first, last, email, phone),
        )
        conn.commit()
        return cur.lastrowid

def book_flight(customer_id, flight_id, pax_names, payment_method):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT base_fare, seats_available FROM flights WHERE flight_id = ?", (flight_id,))
        rec = cur.fetchone()
        if not rec:
            raise ValueError("Flight not found.")
        base_fare, seats_avail = rec
        if seats_avail < len(pax_names):
            raise ValueError("Not enough seats available.")

        total_amount = base_fare * len(pax_names)
        bkref = random_booking_ref()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        cur.execute(
            "INSERT INTO bookings (booking_ref, customer_id, flight_id, booking_time, status, total_amount) VALUES (?, ?, ?, ?, 'CONFIRMED', ?)",
            (bkref, customer_id, flight_id, now, total_amount),
        )
        booking_id = cur.lastrowid

        for name in pax_names:
            seat_label = f"{random.randint(1, 30)}{random.choice(list('ABCDEF'))}"
            cur.execute(
                "INSERT INTO tickets (booking_id, passenger_name, seat_no) VALUES (?, ?, ?)",
                (booking_id, name.strip(), seat_label),
            )

        cur.execute(
            "INSERT INTO payments (booking_id, amount, method, status, payment_time) VALUES (?, ?, ?, 'PAID', ?)",
            (booking_id, total_amount, payment_method, now),
        )

        cur.execute(
            "UPDATE flights SET seats_available = seats_available - ? WHERE flight_id = ?",
            (len(pax_names), flight_id),
        )
        conn.commit()
        return bkref, total_amount

def cancel_booking(booking_ref):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT booking_id, flight_id, status FROM bookings WHERE booking_ref = ?", (booking_ref,))
        rec = cur.fetchone()
        if not rec:
            raise ValueError("Booking not found.")
        booking_id, flight_id, status = rec
        if status == "CANCELLED":
            return False, "Already cancelled."

        cur.execute("SELECT COUNT(*) FROM tickets WHERE booking_id = ?", (booking_id,))
        (pax_count,) = cur.fetchone()

        cur.execute("UPDATE bookings SET status='CANCELLED' WHERE booking_id = ?", (booking_id,))

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute(
            "INSERT INTO payments (booking_id, amount, method, status, payment_time) VALUES (?, (SELECT total_amount FROM bookings WHERE booking_id=?), 'REFUND', 'REFUNDED', ?)",
            (booking_id, booking_id, now),
        )

        cur.execute("UPDATE flights SET seats_available = seats_available + ? WHERE flight_id = ?", (pax_count, flight_id))
        conn.commit()
        return True, f"Cancelled {booking_ref}. Seats released: {pax_count}."

def get_customer_bookings(email):
    q = """
        SELECT b.booking_ref, b.status, a.name AS airline, f.flight_no,
               src.code AS from_code, dst.code AS to_code,
               f.departure_time, f.arrival_time, b.total_amount
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        JOIN flights f ON b.flight_id = f.flight_id
        JOIN airlines a ON f.airline_id = a.airline_id
        JOIN airports src ON f.source_airport_id = src.airport_id
        JOIN airports dst ON f.dest_airport_id = dst.airport_id
        WHERE c.email = ?
        ORDER BY b.booking_time DESC;
    """
    with get_conn() as conn:
        return pd.read_sql_query(q, conn, params=[email])

def admin_add_flight(airline_id, aircraft_id, flight_no, src_id, dst_id, dep_dt, arr_dt, fare):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT capacity FROM aircraft WHERE aircraft_id = ?", (aircraft_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Aircraft not found")
        cap = row[0]
        cur.execute(
            """INSERT INTO flights
               (airline_id, aircraft_id, flight_no, source_airport_id, dest_airport_id,
                departure_time, arrival_time, base_fare, seats_total, seats_available, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SCHEDULED')""",
            (airline_id, aircraft_id, flight_no, src_id, dst_id, dep_dt, arr_dt, fare, cap, cap),
        )
        conn.commit()

def main():
    st.set_page_config(page_title="Flight Booking System (Streamlit + SQLite)", layout="wide")
    st.title("✈️ Flight Booking System")
    st.caption("Demo app: RDBMS (SQLite) + DDL/DML + Python + Streamlit")

    with get_conn() as conn:
        init_db(conn)

    tab_search, tab_my, tab_admin = st.tabs(["🔎 Search & Book", "🧾 My Bookings", "🛠️ Admin"])

    airports_df, airlines_df = get_reference_data()

    with tab_search:
        st.subheader("Search flights")
        col1, col2, col3 = st.columns(3)
        with col1:
            src_label = st.selectbox("From (airport)", airports_df["label"], index=0)
            src_id = int(airports_df.loc[airports_df["label"] == src_label, "airport_id"].iloc[0])
        with col2:
            dst_label = st.selectbox("To (airport)", airports_df["label"], index=1)
            dst_id = int(airports_df.loc[airports_df["label"] == dst_label, "airport_id"].iloc[0])
        with col3:
            travel_date = st.date_input("Departure date", value=date.today() + timedelta(days=1), min_value=date.today())

        if src_id == dst_id:
            st.warning("Source and destination must be different.")
        else:
            if st.button("Search"):
                results = search_flights(src_id, dst_id, travel_date)
                if results.empty:
                    st.info("No flights found for selected route/date.")
                else:
                    results_display = results.copy()
                    results_display["base_fare"] = results_display["base_fare"].apply(money)
                    st.dataframe(results_display.drop(columns=["flight_id"]), use_container_width=True)

                    flight_map = {f"{r.flight_no} {r.from_code}->{r.to_code} at {r.departure_time} (Avail: {r.seats_available})": int(r.flight_id) for _, r in results.iterrows()}
                    selected = st.selectbox("Choose a flight to book", list(flight_map.keys()))
                    flight_id = flight_map[selected]

                    with st.form("booking_form"):
                        st.write("**Passenger & Contact**")
                        c1, c2 = st.columns(2)
                        with c1:
                            first = st.text_input("First name", value="Daksh")
                            email = st.text_input("Email", value="daksh@example.com")
                            phone = st.text_input("Phone", value="+91-9000000000")
                        with c2:
                            last = st.text_input("Last name", value="Garg")
                            pax_input = st.text_area("Passenger names (one per line)", value="Daksh Garg")
                        pay_method = st.selectbox("Payment method", ["UPI", "CARD", "CASH"])
                        submitted = st.form_submit_button("Confirm Booking")
                        if submitted:
                            pax_names = [p.strip() for p in pax_input.split("\n") if p.strip()]
                            try:
                                cust_id = create_or_get_customer(first, last, email, phone)
                                ref, total = book_flight(cust_id, flight_id, pax_names, pay_method)
                                st.success(f"Booking confirmed! Reference: {ref} | Total {money(total)}")
                            except Exception as e:
                                st.error(str(e))

    with tab_my:
        st.subheader("Find my bookings")
        email_q = st.text_input("Email used for booking", value="daksh@example.com")
        if st.button("Show Bookings"):
            dfb = get_customer_bookings(email_q)
            if dfb.empty:
                st.info("No bookings found.")
            else:
                dfb["total_amount"] = dfb["total_amount"].apply(money)
                st.dataframe(dfb, use_container_width=True)

        st.divider()
        st.subheader("Cancel a booking")
        ref_in = st.text_input("Booking reference (e.g., FBX12AB)")
        if st.button("Cancel Booking"):
            try:
                ok, msg = cancel_booking(ref_in.strip())
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)
            except Exception as e:
                st.error(str(e))

    with tab_admin:
        st.warning("Admin demo: no authentication. For classroom use only.")
        st.subheader("Add flight")
        with get_conn() as conn:
            aircraft_df = pd.read_sql_query("SELECT aircraft_id, model FROM aircraft ORDER BY model;", conn)
        c1, c2 = st.columns(2)
        with c1:
            airline_label = st.selectbox("Airline", airlines_df["name"])
            airline_id = int(airlines_df.loc[airlines_df['name'] == airline_label, 'airline_id'].iloc[0])
            aircraft_label = st.selectbox("Aircraft", aircraft_df["model"])
            aircraft_id = int(aircraft_df.loc[aircraft_df["model"] == aircraft_label, "aircraft_id"].iloc[0])
            flight_no = st.text_input("Flight No (e.g., AI-123)")
            fare = st.number_input("Base fare (₹)", min_value=0, value=5000, step=100)
        with c2:
            src_label2 = st.selectbox("From", airports_df["label"], key="admin_src")
            dst_label2 = st.selectbox("To", airports_df["label"], key="admin_dst", index=1)
            src_id2 = int(airports_df.loc[airports_df["label"] == src_label2, "airport_id"].iloc[0])
            dst_id2 = int(airports_df.loc[airports_df["label"] == dst_label2, "airport_id"].iloc[0])
            dep_dt = st.text_input("Departure (YYYY-MM-DD HH:MM)", value=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 09:00"))
            arr_dt = st.text_input("Arrival (YYYY-MM-DD HH:MM)", value=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 11:00"))

        if st.button("Add Flight"):
            try:
                if src_id2 == dst_id2:
                    st.error("Source and destination cannot be the same.")
                elif not flight_no.strip():
                    st.error("Flight number is required.")
                else:
                    admin_add_flight(airline_id, aircraft_id, flight_no.strip(), src_id2, dst_id2, dep_dt.strip(), arr_dt.strip(), float(fare))
                    st.success("Flight added successfully.")
                    get_reference_data.clear()
            except Exception as e:
                st.error(str(e))

if __name__ == "__main__":
    main()
