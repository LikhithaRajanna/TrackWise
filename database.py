
import sqlite3
import os
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL")

DATABASE_NAME = os.environ.get(
    "TRACKWISE_DATABASE",
    "trackwise.db"
)

DUPLICATE_WINDOW_SECONDS = 60


def get_connection():
    if DATABASE_URL:
        return psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            connect_timeout=5
        )

    connection = sqlite3.connect(
        DATABASE_NAME,
        timeout=5
    )
    connection.row_factory = sqlite3.Row
    return connection

def execute_query(cursor, query, parameters=()):
    if DATABASE_URL:
        query = query.replace("?", "%s")

    cursor.execute(query, parameters)


def create_table():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        if DATABASE_URL:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    product_id TEXT,
                    created_at TEXT,
                    client_event_id TEXT
                )
            """)

            cursor.execute("""
                ALTER TABLE events
                ADD COLUMN IF NOT EXISTS client_event_id TEXT
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_events_user_client_event_id
                ON events(user_id, client_event_id)
                WHERE client_event_id IS NOT NULL
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_errors (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT,
                    event_name TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT,
                    event_name TEXT,
                    product_id TEXT,
                    outcome TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    product_id TEXT,
                    created_at TEXT
                )
            """)

            cursor.execute("PRAGMA table_info(events)")
            columns = [
                column[1] for column in cursor.fetchall()
            ]

            if "created_at" not in columns:
                cursor.execute(
                    "ALTER TABLE events ADD COLUMN created_at TEXT"
                )

            if "client_event_id" not in columns:
                cursor.execute(
                    "ALTER TABLE events ADD COLUMN client_event_id TEXT"
                )

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_events_user_client_event_id
                ON events(user_id, client_event_id)
                WHERE client_event_id IS NOT NULL
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    event_name TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    event_name TEXT,
                    product_id TEXT,
                    outcome TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

        execute_query(
            cursor,
            """
            UPDATE events
            SET created_at = ?
            WHERE created_at IS NULL
            """,
            (datetime.now().isoformat(timespec="seconds"),)
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_event(
    user_id,
    event_name,
    product_id,
    client_event_id=None
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        if not DATABASE_URL:
            cursor.execute("BEGIN IMMEDIATE")

        if client_event_id:
            execute_query(
                cursor,
                """
                SELECT id
                FROM events
                WHERE user_id = ?
                  AND client_event_id = ?
                LIMIT 1
                """,
                (user_id, client_event_id)
            )

            existing_event = cursor.fetchone()

            if existing_event:
                connection.rollback()

                event_id = (
                    existing_event["id"]
                    if isinstance(existing_event, dict)
                    else existing_event[0]
                )

                return {
                    "event_id": event_id,
                    "duplicate": True
                }

        else:
            now = datetime.now()
            cutoff = now - timedelta(
                seconds=DUPLICATE_WINDOW_SECONDS
            )

            execute_query(
                cursor,
                """
                SELECT id
                FROM events
                WHERE user_id = ?
                  AND event_name = ?
                  AND product_id = ?
                  AND created_at >= ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    user_id,
                    event_name,
                    product_id,
                    cutoff.isoformat(timespec="seconds")
                )
            )

            existing_event = cursor.fetchone()

            if existing_event:
                connection.rollback()

                return {
                    "event_id": existing_event["id"] if isinstance(existing_event, dict) else existing_event[0],
                    "duplicate": True
                }

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        insert_query = """
            INSERT INTO events (
                user_id,
                event_name,
                product_id,
                created_at,
                client_event_id
            )
            VALUES (?, ?, ?, ?, ?)
        """

        if DATABASE_URL:
            insert_query += " RETURNING id"

        execute_query(
            cursor,
            insert_query,
            (
                user_id,
                event_name,
                product_id,
                created_at,
                client_event_id
            )
        )

        if DATABASE_URL:
            event_id = cursor.fetchone()["id"]
        else:
            event_id = cursor.lastrowid

        connection.commit()

        return {
            "event_id": event_id,
            "duplicate": False
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_event_error(user_id, event_name, error_message):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        execute_query(
            cursor,
            """
            INSERT INTO event_errors (
                user_id,
                event_name,
                error_message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, event_name, error_message, created_at)
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_event_attempt(
    user_id,
    event_name,
    product_id,
    outcome,
    status_code,
    message
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        execute_query(
            cursor,
            """
            INSERT INTO event_attempts (
                user_id,
                event_name,
                product_id,
                outcome,
                status_code,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                event_name,
                product_id,
                outcome,
                status_code,
                message,
                created_at
            )
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
