# Precinct

## About

Precinct is a SQL query LLM copilot that helps analyze your queries, pick up indices and other optimizations and provide other actionable feedback. Currently only Postgres is supported.

## Features

- Input from a file or plain text.
- Checks for relevant tables.
- Retrieves table indices.
- Runs `EXPLAIN ANALYZE` for query diagnosis.
- Offers concise, actionable feedback.

## Requirements

- Python >=3.7
- PostgreSQL (More databases support coming soon)

## Installation

```bash
pip install precinct
```

To install from source:

```bash
pip install 
```

## Usage

To analyze a query from a file:

```bash
python precinct.py --file path/to/your/file.sql
```

To analyze a plaintext query:

```bash
python precinct.py --query "SELECT * FROM table;"
```

## Authentication

For database authentication, Precinct currently supports PostgreSQL's Connection Service File method. This method allows for secure and easily configurable database connections.

### Create a Connection Service File

Create a `.pg_service.conf` file in your home directory or specify its location using the `PGSERVICEFILE` environment variable.

In this file, you can define your database connection parameters like so:

```ini
[my_service]
dbname=mydb
user=myuser
password=mypassword
host=localhost
port=5432
```

### Use in Precinct

When you run Precinct, it will automatically use these settings if you've set up the service file correctly. To connect, Precinct utilizes the service name:

```python
conn = psycopg2.connect(service='my_service')
```

## License

GPL-3.0-or-later
