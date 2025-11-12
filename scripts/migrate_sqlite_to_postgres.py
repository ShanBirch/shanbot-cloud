#!/usr/bin/env python3
"""
Migrate core data from local SQLite to Postgres.

Tables:
 - users (subset of columns)
 - messages (new schema columns if present; falls back to legacy columns)
 - pending_reviews (optional, if exists in SQLite and in PG)

Usage (PowerShell on Windows):
  python scripts/migrate_sqlite_to_postgres.py --sqlite app/analytics_data_good.sqlite --pg $env:DATABASE_URL
"""

import argparse
import json
import sqlite3
import psycopg2
from psycopg2 import errors
from psycopg2.extras import execute_batch


def ensure_pg_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                ig_username TEXT PRIMARY KEY,
                subscriber_id TEXT,
                first_name TEXT,
                last_name TEXT,
                client_status TEXT,
                journey_stage TEXT,
                is_onboarding BOOLEAN,
                is_in_checkin_flow_mon BOOLEAN,
                is_in_checkin_flow_wed BOOLEAN,
                last_interaction_timestamp TEXT,
                metrics_json TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                ig_username TEXT NOT NULL,
                subscriber_id TEXT,
                timestamp TEXT,
                message_type TEXT,
                message_text TEXT
            );
            """
        )
        # Add missing columns on pre-existing tables
        try:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name='users'
                """
            )
            existing = {r[0] for r in cur.fetchall() or []}
            required = {
                'subscriber_id': 'TEXT',
                'first_name': 'TEXT',
                'last_name': 'TEXT',
                'client_status': 'TEXT',
                'journey_stage': 'TEXT',
                'is_onboarding': 'BOOLEAN',
                'is_in_checkin_flow_mon': 'BOOLEAN',
                'is_in_checkin_flow_wed': 'BOOLEAN',
                'last_interaction_timestamp': 'TEXT',
                'metrics_json': 'TEXT',
            }
            for col, coltype in required.items():
                if col not in existing:
                    cur.execute(
                        f"ALTER TABLE users ADD COLUMN {col} {coltype}")
        except Exception:
            pass
    conn.commit()


def migrate_users(sqlite_path: str, pg_conn):
    sconn = sqlite3.connect(sqlite_path)
    sconn.row_factory = sqlite3.Row
    scur = sconn.cursor()
    scur.execute(
        """
        SELECT ig_username, subscriber_id, first_name, last_name, client_status,
               journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
               last_interaction_timestamp, metrics_json
        FROM users
        WHERE ig_username IS NOT NULL AND ig_username != ''
        """
    )
    rows = scur.fetchall() or []

    # Normalize types for Postgres
    payloads = []
    for r in rows:
        d = dict(r)
        # Normalize empty strings to NULL for unique-constrained fields
        if not (d.get("subscriber_id") or "").strip():
            d["subscriber_id"] = None

        def as_bool(val):
            if val is None:
                return False
            if isinstance(val, (int, float)):
                return bool(val)
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("true", "t", "1", "yes", "y"):
                    return True
                if v in ("false", "f", "0", "no", "n", ""):
                    return False
            return bool(val)
        d["is_onboarding"] = as_bool(d.get("is_onboarding"))
        d["is_in_checkin_flow_mon"] = as_bool(d.get("is_in_checkin_flow_mon"))
        d["is_in_checkin_flow_wed"] = as_bool(d.get("is_in_checkin_flow_wed"))
        # Ensure JSON-like fields are strings
        for k in ("metrics_json", "journey_stage"):
            v = d.get(k)
            if isinstance(v, dict):
                d[k] = json.dumps(v)
            else:
                d[k] = v
        payloads.append(d)

    with pg_conn.cursor() as cur:
        insert_sql = (
            """
            INSERT INTO users (
                ig_username, subscriber_id, first_name, last_name, client_status,
                journey_stage, is_onboarding, is_in_checkin_flow_mon, is_in_checkin_flow_wed,
                last_interaction_timestamp, metrics_json
            ) VALUES (
                %(ig_username)s, %(subscriber_id)s, %(first_name)s, %(last_name)s, %(client_status)s,
                %(journey_stage)s, %(is_onboarding)s, %(is_in_checkin_flow_mon)s, %(is_in_checkin_flow_wed)s,
                %(last_interaction_timestamp)s, %(metrics_json)s
            )
            ON CONFLICT (ig_username) DO UPDATE SET
                subscriber_id = EXCLUDED.subscriber_id,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                client_status = EXCLUDED.client_status,
                journey_stage = EXCLUDED.journey_stage,
                is_onboarding = EXCLUDED.is_onboarding,
                is_in_checkin_flow_mon = EXCLUDED.is_in_checkin_flow_mon,
                is_in_checkin_flow_wed = EXCLUDED.is_in_checkin_flow_wed,
                last_interaction_timestamp = EXCLUDED.last_interaction_timestamp,
                metrics_json = EXCLUDED.metrics_json
            ;
            """
        )
        update_by_sub_sql = (
            """
            UPDATE users SET
                ig_username = %(ig_username)s,
                first_name = %(first_name)s,
                last_name = %(last_name)s,
                client_status = %(client_status)s,
                journey_stage = %(journey_stage)s,
                is_onboarding = %(is_onboarding)s,
                is_in_checkin_flow_mon = %(is_in_checkin_flow_mon)s,
                is_in_checkin_flow_wed = %(is_in_checkin_flow_wed)s,
                last_interaction_timestamp = %(last_interaction_timestamp)s,
                metrics_json = %(metrics_json)s
            WHERE subscriber_id = %(subscriber_id)s
            """
        )

        for p in payloads:
            try:
                cur.execute(insert_sql, p)
            except errors.UniqueViolation as e:
                pg_conn.rollback()
                # If duplicate on subscriber_id, update that row to latest fields;
                # otherwise, try to attach subscriber_id to the existing ig_username row.
                if p.get("subscriber_id"):
                    try:
                        cur.execute(update_by_sub_sql, p)
                    except Exception:
                        # Fallback: update the ig_username row directly
                        cur.execute(
                            """
                            UPDATE users SET
                                subscriber_id = COALESCE(subscriber_id, %(subscriber_id)s),
                                first_name = %(first_name)s,
                                last_name = %(last_name)s,
                                client_status = %(client_status)s,
                                journey_stage = %(journey_stage)s,
                                is_onboarding = %(is_onboarding)s,
                                is_in_checkin_flow_mon = %(is_in_checkin_flow_mon)s,
                                is_in_checkin_flow_wed = %(is_in_checkin_flow_wed)s,
                                last_interaction_timestamp = %(last_interaction_timestamp)s,
                                metrics_json = %(metrics_json)s
                            WHERE ig_username = %(ig_username)s
                            """,
                            p,
                        )
                else:
                    # No subscriber_id to reconcile; update ig_username row
                    cur.execute(
                        """
                        UPDATE users SET
                            first_name = %(first_name)s,
                            last_name = %(last_name)s,
                            client_status = %(client_status)s,
                            journey_stage = %(journey_stage)s,
                            is_onboarding = %(is_onboarding)s,
                            is_in_checkin_flow_mon = %(is_in_checkin_flow_mon)s,
                            is_in_checkin_flow_wed = %(is_in_checkin_flow_wed)s,
                            last_interaction_timestamp = %(last_interaction_timestamp)s,
                            metrics_json = %(metrics_json)s
                        WHERE ig_username = %(ig_username)s
                        """,
                        p,
                    )
    pg_conn.commit()
    sconn.close()
    return len(rows)


def migrate_messages(sqlite_path: str, pg_conn):
    sconn = sqlite3.connect(sqlite_path)
    sconn.row_factory = sqlite3.Row
    scur = sconn.cursor()

    # Prefer new schema columns; fall back to legacy
    try:
        scur.execute(
            """
            SELECT ig_username, subscriber_id, timestamp, message_type, message_text
            FROM messages
            WHERE ig_username IS NOT NULL AND ig_username != ''
            ORDER BY timestamp ASC
            """
        )
        rows = scur.fetchall() or []
        to_insert = [dict(r) for r in rows]
    except Exception:
        scur.execute(
            """
            SELECT ig_username, subscriber_id, timestamp, sender AS message_type, message AS message_text
            FROM messages
            WHERE ig_username IS NOT NULL AND ig_username != ''
            ORDER BY timestamp ASC
            """
        )
        rows = scur.fetchall() or []
        to_insert = [dict(r) for r in rows]

    with pg_conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO messages (ig_username, subscriber_id, timestamp, message_type, message_text)
            VALUES (%(ig_username)s, %(subscriber_id)s, %(timestamp)s, %(message_type)s, %(message_text)s)
            ON CONFLICT DO NOTHING
            """,
            to_insert,
            page_size=1000,
        )
    pg_conn.commit()
    sconn.close()
    return len(to_insert)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", required=True,
                    help="Path to local SQLite DB (e.g., app/analytics_data_good.sqlite)")
    ap.add_argument("--pg", required=True, help="Postgres DATABASE_URL")
    args = ap.parse_args()

    with psycopg2.connect(args.pg) as pg_conn:
        ensure_pg_tables(pg_conn)
        u = migrate_users(args.sqlite, pg_conn)
        m = migrate_messages(args.sqlite, pg_conn)
        print(f"Migrated users: {u}, messages: {m}")


if __name__ == "__main__":
    main()
