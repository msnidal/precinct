import os
import click
import configparser
import psycopg2
import psycopg2.extensions
import logging
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PostgresConnection(BaseModel):
    host: str
    port: int
    db_name: str
    user: str
    password: str

    def get_connection(self) -> psycopg2.extensions.connection:
        conn_str = f"dbname='{self.db_name}' user='{self.user}' host='{self.host}' port='{self.port}' password='{self.password}'"
        conn = psycopg2.connect(conn_str)
        return conn

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "PostgresConnection":
        try:
            protocol, uri = conn_str.split("://")
            credentials, hostinfo = uri.split("@")
            user, password = credentials.split(":")
            host, port_db = hostinfo.split("/")
            port, db_name = port_db.split(":")
            return cls(
                host=host, port=int(port), db_name=db_name, user=user, password=password
            )
        except ValueError:
            raise ValueError(
                "Invalid connection string format. Expected format: postgresql://username:password@host:port/database"
            )

    @classmethod
    def get_from_env(cls) -> "PostgresConnection":
        host = os.getenv("PGHOST")
        port = os.getenv("PGPORT")
        db_name = os.getenv("PGDATABASE")
        user = os.getenv("PGUSER")
        password = os.getenv("PGPASSWORD")

        missing_vars = []
        if not host:
            missing_vars.append("PGHOST")
        if not port:
            missing_vars.append("PGPORT")
        if not db_name:
            missing_vars.append("PGDATABASE")
        if not user:
            missing_vars.append("PGUSER")
        if not password:
            missing_vars.append("PGPASSWORD")
        if missing_vars:
            raise ValueError(
                f"Missing environment variables for connection: {missing_vars}"
            )

        return cls(host=host, port=port, db_name=db_name, user=user, password=password)


def get_connection(service_name, connection_string) -> psycopg2.extensions.connection:
    try:
        conn = get_service_connection(service_name)
        return conn
    except Exception:
        pass

    if connection_string:
        logger.info(f"Using connection string {connection_string}...")
        postgres_connection = PostgresConnection.from_connection_string(
            connection_string
        )
        return postgres_connection.get_connection()

    try:
        postgres_connection = PostgresConnection.get_from_env()
        logger.info("Using environment variables...")
        return postgres_connection.get_connection()
    except ValueError:
        raise click.BadParameter(
            "You must provide either --service, --connection-string, or set the appropriate environment variables."
        )


def get_service_connection(
    service_name: Optional[str] = None,
) -> psycopg2.extensions.connection:
    service_file_path = os.getenv(
        "PGSERVICEFILE", os.path.expanduser("~/.pg_service.conf")
    )

    # Check if service file exists
    if not os.path.exists(service_file_path):
        logger.error(f"Service file not found: {service_file_path}")
        raise FileNotFoundError(f"Service file not found: {service_file_path}")

    config = configparser.ConfigParser()
    config.read(service_file_path)

    if not service_name:
        # Use the first service name if none is provided
        if config.sections():
            service_name = config.sections()[0]
            logger.info(
                f"No service name provided. Using the first service: {service_name}"
            )
        else:
            logger.error("No service sections found in the service file.")
            raise ValueError("No service sections found in the service file.")

    if service_name not in config.sections():
        logger.error(f"Invalid service name: {service_name}")
        raise ValueError(f"Invalid service name: {service_name}")

    try:
        conn = psycopg2.connect(service=service_name)
        logger.info(f"Connection established using service: {service_name}")
        return conn
    except Exception as e:
        logger.error(f"Failed to establish connection: {str(e)}")
        raise
