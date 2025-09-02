# ACL API

ACL generator API built on [Aerleon](https://aerleon.readthedocs.io/en/latest/).

## Development environment

To provide type checking in your code editor a local venv is recommended.

Default testing username is: admin, password: secret.

Add environment variables to src/.env.
Copy from src/.env.example
```bash 
# File: src/.env
# ------------- app settings -------------
REVISON_NEEDED_COVERAGE=0

# ------------- database -------------
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="postgres"
POSTGRES_SERVER="db" # default "localhost", if using docker compose you should use "db"
POSTGRES_PORT=5432
POSTGRES_DB="postgres"

# ------------- redis cache-------------
REDIS_CACHE_HOST="redis" # default "localhost", if using docker compose you should use "redis"
REDIS_CACHE_PORT=6379

# ------------- redis queue -------------
REDIS_QUEUE_HOST="redis" # default "localhost", if using docker compose you should use "redis"
REDIS_QUEUE_PORT=6379

# If using deployers and workers this needs to point to the API.
API_URL="http://127.0.0.1:8000/api/v1"
```

### Local
```bash
#Install poetry
python3 -m pip install poetry
# Create and activate a venv
python3 -m venv venv
source venv/bin/activate
# Install dependencies
poetry install
# Run API with hot reloading
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker
```bash
docker compose up -d
```