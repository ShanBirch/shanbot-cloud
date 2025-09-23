#!/usr/bin/env python3
"""
Find clients in Postgres by name or IG username and optionally update status.

Usage examples (PowerShell):
  python scripts/find_clients.py --db-url $env:DATABASE_URL --names linda sabrina kristy
  python scripts/find_clients.py --db-url $env:DATABASE_URL --names libby staci --set-paying
  python scripts/find_clients.py --db-url $env:DATABASE_URL --names shane --set-trial 2025-09-20
"""

import argparse
import json
from typing import List
import psycopg2
from psycopg2.extras import RealDictCursor


def find_users(conn, names: List[str]):
    ilikes = [f"%{n.lower()}%" for n in names]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT ig_username, subscriber_id, first_name, last_name, journey_stage
            FROM users
            WHERE (
                lower(ig_username) LIKE ANY(%s)
                OR lower(COALESCE(first_name, '')) LIKE ANY(%s)
                OR lower(COALESCE(last_name, '')) LIKE ANY(%s)
            )
            ORDER BY ig_username
            """,
            (ilikes, ilikes, ilikes),
        )
        return cur.fetchall() or []


def update_status(conn, ig_username: str, set_paying: bool = False, trial_start: str = None):
    with conn.cursor() as cur:
        # fetch current JSON
        cur.execute(
            "SELECT journey_stage FROM users WHERE ig_username=%s", (ig_username,))
        row = cur.fetchone()
        js = row[0] if row else None
        try:
            data = json.loads(js) if isinstance(js, str) and js.strip() else {}
        except Exception:
            data = {}
        if set_paying:
            data["is_paying_client"] = True
        if trial_start:
            data["trial_start_date"] = trial_start
        cur.execute(
            "UPDATE users SET journey_stage=%s WHERE ig_username=%s",
            (json.dumps(data), ig_username),
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", required=True, help="Postgres DATABASE_URL")
    p.add_argument("--names", nargs="+", required=True,
                   help="Names or IG usernames to search (case-insensitive substrings)")
    p.add_argument("--set-paying", action="store_true",
                   help="Mark matches as paying clients")
    p.add_argument("--set-trial", metavar="YYYY-MM-DD",
                   help="Set trial_start_date for matches")
    args = p.parse_args()

    with psycopg2.connect(args.db_url) as conn:
        results = find_users(conn, args.names)
        print(f"Found {len(results)} matches:")
        for r in results:
            print(
                f" - {r['ig_username']} | {r.get('first_name') or ''} {r.get('last_name') or ''} | journey_stage={r.get('journey_stage')}")

        if (args.set_paying or args.set_trial) and results:
            for r in results:
                update_status(
                    conn, r["ig_username"], set_paying=args.set_paying, trial_start=args.set_trial)
            conn.commit()
            print("Updated status for:")
            for r in results:
                print(f" - {r['ig_username']}")


if __name__ == "__main__":
    main()
