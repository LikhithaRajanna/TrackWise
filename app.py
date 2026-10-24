from flask import Flask, jsonify, request, render_template
from database import (
    create_table,
    save_event,
    save_event_error,
    save_event_attempt,
    get_connection,
    execute_query
)
import sqlite3
import psycopg
import time

app = Flask(__name__)


def save_event_with_retry(
    user_id,
    event_name,
    product_id,
    client_event_id,
    max_attempts=3
):
    for attempt in range(1, max_attempts + 1):
        try:
            return save_event(
                user_id,
                event_name,
                product_id,
                client_event_id
            )

        except (sqlite3.OperationalError, psycopg.Error) as error:
            error_message = str(error).lower()

            is_temporary_error = (
                "locked" in error_message
                or "busy" in error_message
                or "deadlock" in error_message
                or "serialization failure" in error_message
                or "could not obtain lock" in error_message
            )

            if not is_temporary_error:
                raise

            if attempt == max_attempts:
                raise

            delay = 0.2 * (2 ** (attempt - 1))

            app.logger.warning(
                "Temporary database error. Retrying attempt %s of %s.",
                attempt + 1,
                max_attempts
            )

            time.sleep(delay)


@app.route("/api/health", methods=["GET"])
def health_check():
    connection = None

    try:
        connection = get_connection()
        connection.execute("SELECT 1")

        return jsonify({
            "status": "healthy",
            "application": "TrackWise API",
            "database": "connected"
        }), 200

    except Exception:
        app.logger.exception("Health check failed")

        return jsonify({
            "status": "unhealthy",
            "application": "TrackWise API",
            "database": "unavailable"
        }), 503

    finally:
        if connection is not None:
            connection.close()


# Create the database table when the application starts
create_table()
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("index.html")

@app.route("/customer-demo", methods=["GET"])
def customer_demo():
    return render_template("customer_demo.html")

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Welcome to TrackWise API",
        "project": "Customer Event Integration and Monitoring Platform",
        "status": "running"
    })


@app.route("/api/events", methods=["POST"])
def receive_event():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        message = "Request body must be valid JSON."

        try:
            save_event_error(None, None, message)
            save_event_attempt(
                None, None, None, "rejected", 400, message
            )
        except Exception:
            app.logger.exception("Failed to record invalid request")

        return jsonify({"error": message}), 400

    required_fields = ["user_id", "event_name", "product_id"]

    for field in required_fields:
        if (
            not isinstance(data.get(field), str)
            or not data[field].strip()
        ):
            message = f"Missing or invalid required field: {field}"

            user_id = (
                data.get("user_id")
                if isinstance(data.get("user_id"), str)
                else None
            )
            event_name = (
                data.get("event_name")
                if isinstance(data.get("event_name"), str)
                else None
            )
            product_id = (
                data.get("product_id")
                if isinstance(data.get("product_id"), str)
                else None
            )

            try:
                save_event_error(user_id, event_name, message)
                save_event_attempt(
                    user_id,
                    event_name,
                    product_id,
                    "rejected",
                    400,
                    message
                )
            except Exception:
                app.logger.exception("Failed to record invalid event")

            return jsonify({"error": message}), 400

    user_id = data["user_id"].strip()
    event_name = data["event_name"].strip()
    product_id = data["product_id"].strip()

    try:
        client_event_id = data.get("client_event_id")

        if client_event_id is not None:
            if (
                not isinstance(client_event_id, str)
                or not client_event_id.strip()
            ):
                return jsonify({
                    "error": "client_event_id must be a non-empty string."
                }), 400

            client_event_id = client_event_id.strip()

        result = save_event_with_retry(
            user_id,
            event_name,
            product_id,
            client_event_id
        )
        event_id = result["event_id"]
        is_duplicate = result["duplicate"]

        if is_duplicate:
            outcome = "duplicate"
            status_code = 200
            message = "Duplicate event detected."
        else:
            outcome = "accepted"
            status_code = 201
            message = "Event received and stored successfully."

        save_event_attempt(
            user_id,
            event_name,
            product_id,
            outcome,
            status_code,
            message
        )

    except Exception:
        app.logger.exception("Failed to process event")

        try:
            save_event_error(
                user_id,
                event_name,
                "Database error while processing event."
            )
        except Exception:
            app.logger.exception("Failed to record processing error")

        return jsonify({
            "error": "Unable to process the event."
        }), 500

    if is_duplicate:
        return jsonify({
            "message": message,
            "event_id": event_id,
            "event": {
                "user_id": user_id,
                "event_name": event_name,
                "product_id": product_id
            },
            "status": "duplicate"
        }), 200

    return jsonify({
        "message": message,
        "event_id": event_id,
        "event": {
            "user_id": user_id,
            "event_name": event_name,
            "product_id": product_id
        },
        "status": "accepted"
    }), 201




@app.route("/api/events", methods=["GET"])
def get_events():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT id, user_id, event_name, product_id, created_at
            FROM events
            WHERE 1 = 1
        """

        parameters = []

        user_id = request.args.get("user_id")
        event_name = request.args.get("event_name")

        if user_id:
            query += " AND user_id = ?"
            parameters.append(user_id)

        if event_name:
            query += " AND event_name = ?"
            parameters.append(event_name)

        query += " ORDER BY id DESC"

        execute_query(cursor, query, parameters)

        rows = cursor.fetchall()
        events = [dict(row) for row in rows]

        return jsonify({
            "count": len(events),
            "events": events
        }), 200

    finally:
        connection.close()

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Count product views and purchase events
        cursor.execute("""
            SELECT
                COUNT(CASE
                    WHEN event_name = 'product_viewed' THEN 1
                END) AS total_views,
                COUNT(CASE
                    WHEN event_name = 'purchase' THEN 1
                END) AS total_purchases
            FROM events
        """)

        summary = dict(cursor.fetchone())

        # Find the most-viewed product
        cursor.execute("""
            SELECT product_id, COUNT(*) AS view_count
            FROM events
            WHERE event_name = 'product_viewed'
            GROUP BY product_id
            ORDER BY view_count DESC, product_id ASC
            LIMIT 1
        """)

        most_viewed = cursor.fetchone()

        # Count views and purchases for each product
        cursor.execute("""
            SELECT
                product_id,
                COUNT(CASE
                    WHEN event_name = 'product_viewed' THEN 1
                END) AS views,
                COUNT(CASE
                    WHEN event_name = 'purchase' THEN 1
                END) AS purchases
            FROM events
            GROUP BY product_id
            ORDER BY views DESC, purchases DESC, product_id ASC
        """)

        products = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "summary": summary,
            "most_viewed_product": (
                dict(most_viewed) if most_viewed else None
            ),
            "products": products
        }), 200

    finally:
        connection.close()

@app.route("/api/monitoring", methods=["GET"])
def get_monitoring():
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_attempts,
                SUM(CASE
                    WHEN outcome = 'accepted' THEN 1
                    ELSE 0
                END) AS accepted,
                SUM(CASE
                    WHEN outcome = 'duplicate' THEN 1
                    ELSE 0
                END) AS duplicates,
                SUM(CASE
                    WHEN outcome = 'rejected' THEN 1
                    ELSE 0
                END) AS rejected,
                SUM(CASE
                    WHEN outcome = 'error' THEN 1
                    ELSE 0
                END) AS errors
            FROM event_attempts
        """)

        row = dict(cursor.fetchone())

        # SQLite returns NULL for SUM when the table is empty.
        for key in ("accepted", "duplicates", "rejected", "errors"):
            row[key] = row[key] or 0

        total_attempts = row["total_attempts"]

        if total_attempts:
            acceptance_rate = round(
                row["accepted"] / total_attempts * 100, 2
            )
        else:
            acceptance_rate = 0

        return jsonify({
            "total_attempts": total_attempts,
            "accepted": row["accepted"],
            "duplicates": row["duplicates"],
            "rejected": row["rejected"],
            "errors": row["errors"],
            "acceptance_rate_percent": acceptance_rate
        }), 200

    finally:
        connection.close()


@app.route("/api/attempts", methods=["GET"])
def get_event_attempts():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                id,
                user_id,
                event_name,
                product_id,
                outcome,
                status_code,
                message,
                created_at
            FROM event_attempts
            WHERE 1 = 1
        """

        parameters = []

        outcome = request.args.get("outcome")
        event_name = request.args.get("event_name")

        if outcome:
            query += " AND outcome = ?"
            parameters.append(outcome)

        if event_name:
            query += " AND event_name = ?"
            parameters.append(event_name)

        query += " ORDER BY id DESC"
        execute_query(cursor, query, parameters)
        attempts = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "count": len(attempts),
            "attempts": attempts
        }), 200

    finally:
        connection.close()


@app.route("/api/errors", methods=["GET"])
def get_event_errors():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id, user_id, event_name, error_message, created_at
            FROM event_errors
            ORDER BY id DESC
        """)

        errors = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "total_errors": len(errors),
            "errors": errors
        }), 200

    finally:
        connection.close()


if __name__ == "__main__":
    app.run(debug=True)
