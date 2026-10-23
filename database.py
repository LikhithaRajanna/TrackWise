
import sqlite3
import os
from datetime import datetime, timedelta

DATABASE_NAME = os.environ.get(
    "TRACKWISE_DATABASE",
    "trackwise.db"
)

DUPLICATE_WINDOW_SECONDS = 60


def create_table():
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                product_id TEXT,
                created_at TEXT
            )
        """)

        # Migrate older databases without deleting existing events.
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]

        if "created_at" not in columns:
            cursor.execute(
                "ALTER TABLE events ADD COLUMN created_at TEXT"
            )

        if "client_event_id" not in columns:
            cursor.execute(
                "ALTER TABLE events ADD COLUMN client_event_id TEXT"
            )

        cursor.execute("""
            UPDATE events
            SET created_at = ?
            WHERE created_at IS NULL
        """, (datetime.now().isoformat(timespec="seconds"),))

        # A client event ID must be unique for each user.
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

        connection.commit()

    finally:
        connection.close()


def save_event(
    user_id,
    event_name,
    product_id,
    client_event_id=None
):
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        cursor = connection.cursor()

        # Serialize the check-and-insert operation.
        cursor.execute("BEGIN IMMEDIATE")

        if client_event_id:
            # A matching client ID means the request is a retry.
            cursor.execute("""
                SELECT id
                FROM events
                WHERE user_id = ?
                  AND client_event_id = ?
                LIMIT 1
            """, (user_id, client_event_id))

            existing_event = cursor.fetchone()

            if existing_event:
                connection.rollback()
                return {
                    "event_id": existing_event[0],
                    "duplicate": True
                }

        else:
            # Preserve existing behavior for older clients that
            # do not send a client event ID.
            now = datetime.now()
            cutoff = now - timedelta(
                seconds=DUPLICATE_WINDOW_SECONDS
            )

            cursor.execute("""
                SELECT id
                FROM events
                WHERE user_id = ?
                  AND event_name = ?
                  AND product_id = ?
                  AND created_at >= ?
                ORDER BY id DESC
                LIMIT 1
            """, (
                user_id,
                event_name,
                product_id,
                cutoff.isoformat(timespec="seconds")
            ))

            existing_event = cursor.fetchone()

            if existing_event:
                connection.rollback()
                return {
                    "event_id": existing_event[0],
                    "duplicate": True
                }

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        cursor.execute("""
            INSERT INTO events (
                user_id,
                event_name,
                product_id,
                created_at,
                client_event_id
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            event_name,
            product_id,
            created_at,
            client_event_id
        ))

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
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        cursor = connection.cursor()
        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        cursor.execute("""
            INSERT INTO event_errors (
                user_id,
                event_name,
                error_message,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            event_name,
            error_message,
            created_at
        ))

        connection.commit()

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
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        cursor = connection.cursor()
        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        cursor.execute("""
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
        """, (
            user_id,
            event_name,
            product_id,
            outcome,
            status_code,
            message,
            created_at
        ))

        connection.commit()

    finally:
        connection.close()
