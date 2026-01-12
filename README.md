## Setup Instructions

### Prerequisites
* Docker
* Docker Compose
### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

### 3. Build and run the application

```bash
docker compose up --build
```

This will automatically:

* Start PostgreSQL
* Run database migrations (Alembic)
* Seed an admin user if admin env vars are set
* Import `sample_data.csv` **only if** the database is empty
* Start the FastAPI application
### 4. Access the API

* API base URL:
  [http://localhost:8000](http://localhost:8000)
* OpenAPI / Swagger UI:
  [http://localhost:8000/docs](http://localhost:8000/docs)
### 5. Stopping the application

```bash
docker compose down
```

### 6. Resetting the database (optional)

If you want a clean state:

```bash
docker compose down -v
docker compose up --build
```

This removes all persisted database data and re-imports the CSV on startup.

### Notes

* All endpoints (except `/register` and `/login`) require a JWT in the `Authorization` header:

  ```
  Authorization: Bearer <token>
  ```
* JWT tokens expire after 10 minutes by default (configurable via `JWT_EXPIRE_MINUTES`).

## Example requests for each endpoint

Register a normal user

``curl -i -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user1@example.com","password":"password123"}'

Login as normal user → store JWT
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user1@example.com","password":"password123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "USER TOKEN:"
echo "$TOKEN"

List conflict data (paginated by DISTINCT country)
curl -i "http://localhost:8000/conflictdata?page=1&per_page=20" \
  -H "Authorization: Bearer $TOKEN"

Get conflict data for Algeria
curl -i http://localhost:8000/conflictdata/algeria \
  -H "Authorization: Bearer $TOKEN"

Get Algeria risk score (first call → 202)
curl -i http://localhost:8000/conflictdata/algeria/riskscore \
  -H "Authorization: Bearer $TOKEN"

Submit feedback for Algeria / Algiers
curl -i -X POST http://localhost:8000/conflictdata/algiers/userfeedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"country":"algeria","feedback":"Hello again, friend of a friend"}'

Login as admin → store admin JWT
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"adminpass123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "ADMIN TOKEN:"
echo "$ADMIN_TOKEN"

Delete conflict data (admin-only)
curl -i -X DELETE http://localhost:8000/conflictdata \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"country":"algeria","admin1":"algiers"}'

## Notes: Decisions and Tradeoffs

**Time constraint:**  
This implementation was completed under a strict time budget. Design choices intentionally favored correctness, clarity, and reviewer runnability over infrastructure completeness.

- **Transactions (DELETE):**  
    DELETE uses a database transaction to atomically (1) remove `conflict_data` and (2) mark the country risk score cache as stale, preventing stale ready scores after deletions.
    
- **UPSERT for cache rows:**  
    Risk score cache rows are created using PostgreSQL UPSERT (`INSERT … ON CONFLICT DO NOTHING`) to ensure transaction safety and race safety without explicit locking or internal commits.
    
- **Background jobs:**  
    Risk score computation is implemented in-process using FastAPI background tasks to satisfy asynchronous computation requirements under time constraints.  
    _Tradeoff:_ this is not durable across restarts or horizontally scalable; a Redis/RQ-based worker model should be used for production.
    
- **Normalization:**  
    Normalized fields (`*_norm`) apply trim, collapsed internal whitespace, and lowercase for deterministic lookup and uniqueness, while raw fields preserve original dataset values.
    
- **Logging:**  
    Sensitive data (JWTs, feedback bodies) is intentionally excluded from logs. Only metadata (IDs, `country_norm`) is logged to balance observability and data sensitivity.
    
- **Ambiguity resolution:**  
    Where the exercise specification allowed multiple interpretations (e.g., country-level pagination semantics, admin1 uniqueness), the simplest defensible interpretation was chosen and made explicit in the implementation to avoid hidden or surprising behavior.
