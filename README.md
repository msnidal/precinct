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

For developers, you can install locally in edit mode with optional extras:

```bash
pip install -e .[dev]
```

## Usage

To analyze a query from a file:

```bash
python precinct.py "path/to/your/file.sql"
```

To analyze a plaintext query:

```bash
python precinct.py "SELECT * FROM table;"
```

### Specify intent

Precinct will then analyze your query and extract an intent, which you can either accept or clarify. For example:

```bash
Query: select * from businesses
Intent: The intent of the query is simply to retrieve all data from all columns in the 'businesses' table.
Issue clarification to intent (y) to proceed, or (q) to quit (y/q/[intent]): y
```

To specify another intent, just type it in and press enter:

```bash
Issue clarification to intent (y) to proceed, or (q) to quit (y/q/[intent]): I want to find all businesses in the 'restaurants' category.
```

### Optimize

Precinct will then analyze your query and provide feedback on how to optimize it. For example:

```bash
Optimized query: select * from businesses

Explanation: The original query is as optimized as it can be since it is a simple SELECT ALL command. All records and all columns from the table 'businesses' are selected. Considering the structure and scope of the query, there are no specific joins, conditions, aggregations, or sorting criteria that we could modify to improve performance. Therefore, the original query remains unchanged. However, be careful with using 'SELECT *' as this query will become slower as the number of columns or rows in the 'businesses' table grows.
What would you like to do? (run/copy/cancel): c
```

From here, you can 


## Authentication

For database authentication, Precinct supports the following methods:

- [Connection Service File](#connection-service-file)
- [Connection URI](#connection-uri)
- [Environment Variables](#environment-variables)

### Connection Service File

PostgreSQL's Connection Service File is the recommended method. It allows for secure and easily configurable database connections. To use it, create a `.pg_service.conf` file in your home directory or specify its location using the `PGSERVICEFILE` environment variable or via the `--service-file` command line argument.

In this file, you can define your database connection parameters like so:

```ini
[my_service]
dbname=mydb
user=myuser
password=mypassword
host=localhost
port=5432
```

You can then connect to the database using the service name:

```bash
precinct --service my_service "SELECT * FROM table;"
```

### Connection URI

You can also connect using a connection URI. This is a commonly used method among database clients. To connect using a URI, use the `--uri` command line argument:

```bash
precinct --uri "postgresql://myuser:mypassword@localhost:5432/mydb" "SELECT * FROM table;"
```

### Environment Variables

Finally, you can connect using environment variables. To connect using environment variables, just set them and Precinct will default if a service file or URI is not available.

```bash
precinct "SELECT * FROM table;"
```

## License

GPL-3.0-or-later
