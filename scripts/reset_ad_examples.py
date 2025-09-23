#!/usr/bin/env python3
"""
Admin tool to reset learning examples for ad prompts.

It can preview (dry-run) and then archive+delete rows from learning_feedback_log
that match your filters (conversation_type and/or regenerated-only).

Usage (PowerShell):
  python scripts/reset_ad_examples.py --db-url $env:DATABASE_URL --type vegan --dry-run
  python scripts/reset_ad_examples.py --db-url $env:DATABASE_URL --type facebook_ad_response --only-regenerated --apply

Filters:
  --type values:
     - vegan                      (legacy ad few-shots)
     - facebook_ad_response       (new ad prompt key)
  --only-regenerated  only rows where user_notes ILIKE '%regenerated%'

Safe behavior:
  - Creates backup table learning_feedback_log_backup if not exists
  - Copies matched rows into backup before deleting
"""

from typing import Optional, Tuple, List
import argparse
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def ensure_backup(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_feedback_log_backup AS
        SELECT * FROM learning_feedback_log WITH NO DATA
        """
    )


def build_where(conversation_type: Optional[str], only_regen: bool) -> Tuple[str, List]:
    clauses = []
    params: list = []
    if conversation_type:
        clauses.append("conversation_type = %s")
        params.append(conversation_type)
    if only_regen:
        # inline literal so no param added
        clauses.append("COALESCE(user_notes, '') ILIKE '%regenerated%'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", required=True)
    p.add_argument(
        "--type", choices=["vegan", "facebook_ad_response"], help="Filter by conversation_type")
    p.add_argument("--only-regenerated", action="store_true",
                   help="Only match rows with user_notes containing 'regenerated'")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    if not (args.dry_run or args.apply):
        print("Specify --dry-run to preview or --apply to execute.")
        sys.exit(1)

    with psycopg2.connect(args.db_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where, params = build_where(args.type, args.only_regenerated)

            sql = "SELECT COUNT(*) AS cnt FROM learning_feedback_log " + where
            cur.execute(sql, params)
            total = (cur.fetchone() or {}).get("cnt", 0)
            print(f"Matched rows: {total}")

            if args.dry_run or total == 0:
                return

            # Backup then delete
            ensure_backup(cur)
            cur.execute(
                "INSERT INTO learning_feedback_log_backup SELECT * FROM learning_feedback_log " + where, params)
            cur.execute("DELETE FROM learning_feedback_log " + where, params)
            conn.commit()
            print(f"Archived and deleted {total} rows.")


if __name__ == "__main__":
    main()
