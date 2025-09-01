# ACL API

ACL generator API build on [Aerleon](https://aerleon.readthedocs.io/en/latest/).

## Development environment

To provide type checking in your code editor a local venv is recommended. 

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