# TrackWise — Customer Event Integration and Monitoring Platform

TrackWise is a Flask-based event integration and monitoring platform designed to demonstrate how customer activity events can be collected, validated, stored, and analyzed through REST APIs.

The project simulates a customer engagement integration workflow, with features for event tracking, duplicate-event prevention, error monitoring, analytics, and database retry handling.

**Live Demo:** https://trackwise-q7kb.onrender.com  
**GitHub Repository:** https://github.com/LikhithaRajanna/TrackWise

## Key Features

- **REST API Integration:** Accepts customer activity events through HTTP endpoints.
- **Event Validation:** Checks required fields and rejects invalid event payloads.
- **Duplicate Event Prevention:** Uses a client event ID to identify repeated submissions and avoid duplicate records.
- **Database Integration:** Supports SQLite for local development and PostgreSQL for deployment.
- **Retry Handling:** Retries selected temporary database errors with increasing delays.
- **Event Monitoring:** Records request attempts, rejected events, and processing errors.
- **Analytics Dashboard:** Summarizes product views and purchases.
- **Event Filtering:** Retrieves events using supported filters such as user ID and event name.
- **Automated Testing:** Includes tests for application behavior, validation, and retry handling.

## Technology Stack

- **Backend:** Python, Flask
- **API:** REST, HTTP, JSON
- **Database:** SQLite, PostgreSQL
- **Testing:** pytest
- **Deployment:** Render
- **Version Control:** Git, GitHub

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Displays the API welcome response |
| GET | `/api/health` | Checks application health |
| POST | `/api/events` | Submits a customer activity event |
| GET | `/api/events` | Retrieves events, with supported filters |
| GET | `/api/analytics` | Returns product activity analytics |
| GET | `/api/monitoring` | Displays event processing metrics |
| GET | `/api/attempts` | Retrieves recorded request attempts |
| GET | `/api/errors` | Retrieves recorded errors |
| GET | `/customer-demo` | Demonstrates customer activity tracking |
| GET | `/dashboard` | Displays the monitoring dashboard |

## Example Event Request

**POST** `/api/events`

```json
{
  "user_id": "user_101",
  "event_name": "product_viewed",
  "product_id": "P101",
  "client_event_id": "event_001"
}
```

The API validates the payload, stores valid events, and records the request outcome. A newly accepted event returns HTTP `201`; a recognized duplicate returns HTTP `200`; an invalid payload returns HTTP `400`.

## Database and Reliability

TrackWise stores event records and monitoring information in a relational database. It uses client event IDs for duplicate detection and retries selected temporary database errors, such as database-lock errors.

Request attempts and errors are recorded to help investigate failed integrations and understand event-processing behavior.

## Testing

The project uses pytest to verify application behavior, including event validation, duplicate handling, and database retry scenarios.

**Latest test result:** 12 tests passed.

## Deployment

The application is deployed on Render and uses PostgreSQL through a deployment environment variable. Local development supports SQLite.

Sensitive database credentials are configured through environment variables rather than being included in the source code.

## What I Learned

- Building and testing REST APIs using Flask
- Validating JSON request payloads
- Working with relational databases and SQL
- Handling duplicate event submissions
- Implementing retry logic for temporary database errors
- Recording errors and monitoring request outcomes
- Testing backend functionality with pytest
- Deploying a Python application with a PostgreSQL database

## Future Improvements

- Add authentication and API-key management
- Introduce configurable event schemas
- Add configurable retry policies and dead-letter handling
- Improve monitoring with time-based metrics and charts
- Add automated integration testing and continuous deployment

---

*TrackWise is a portfolio project built to explore customer event integration, API reliability, and monitoring workflows.*
