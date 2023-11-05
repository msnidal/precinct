import os
import click
import configparser
import psycopg2
import psycopg2.extensions
from typing import Optional
from pydantic import BaseModel

from precinct.logging import get_logger
logger = get_logger()


class PostgresConnection(BaseModel):
    """A PostgreSQL connection object.

    Attributes:
        host (str): The host of the PostgreSQL database.
        port (int): The port of the PostgreSQL database.
        db_name (str): The name of the PostgreSQL database.
        user (str): The user of the PostgreSQL database.
        password (str): The password of the PostgreSQL database.
    """

    host: str
    port: int
    db_name: str
    user: str
    password: str

    def get_connection(self) -> psycopg2.extensions.connection:
        """Get and return a connection to a PostgreSQL database using the attributes of this object.

        Returns:
            psycopg2.extensions.connection: A connection to a PostgreSQL database.
        """
        conn_str = f"dbname='{self.db_name}' user='{self.user}' host='{self.host}' port='{self.port}' password='{self.password}'"
        conn = psycopg2.connect(conn_str)
        return conn

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "PostgresConnection":
        """Create a PostgresConnection object from a connection string.

        Args:
            conn_str (str): A connection string to use.
        Returns:
            PostgresConnection: A PostgresConnection object.
        Raises:
            ValueError: If the connection string is invalid.
        """
        try:
            _, uri = conn_str.split("://")
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
        """Create a PostgresConnection object from environment variables.

        Returns:
            PostgresConnection: A PostgresConnection object.
        Raises:
            ValueError: If any of the required environment variables are missing.
        """
        host = os.getenv("PGHOST")
        port = os.getenv("PGPORT")
        db_name = os.getenv("PGDATABASE")
        user = os.getenv("PGUSER")
        password = os.getenv("PGPASSWORD")

        if not host or not port or not db_name or not user or not password:
            missing_vars = [
                "PGHOST" if not host else None,
                "PGPORT" if not port else None,
                "PGDATABASE" if not db_name else None,
                "PGUSER" if not user else None,
                "PGPASSWORD" if not password else None,
            ]

            raise ValueError(
                f"Missing environment variables for connection: {[var for var in missing_vars if var]}"
            )

        return cls(
            host=host, port=int(port), db_name=db_name, user=user, password=password
        )


def get_connection(service_name, connection_string) -> psycopg2.extensions.connection:
    """Get and return a connection to a PostgreSQL database.

    Args:
        service_name (str): The name of the service to use.
        connection_string (str): A connection string to use.
    Returns:
        psycopg2.extensions.connection: A connection to a PostgreSQL database.
    Raises:
        ValueError: If both service_name and connection_string are provided.
        click.BadParameter: If neither service_name nor connection_string are provided.
    """
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
    """Checks for and parses a connection from PostgreSQL's service file specification

    Args:
        service_name (str): The name of the service to use.
    Returns:
        psycopg2.extensions.connection: A connection to a PostgreSQL database.
    Raises:
        FileNotFoundError: If the service file is not found.
        ValueError: If the service name is invalid.
    """
    service_file_path = os.getenv(
        "PGSERVICEFILE", os.path.expanduser("~/.pg_service.conf")
    )

    # Check if service file exists
    if not os.path.exists(service_file_path):
        logger.error(f"Service file not found: {service_file_path}")
        raise FileNotFoundError(f"Service file not found: {service_file_path}")

    config = configparser.ConfigParser()
    config.read(service_file_path)

    # Use the first service name if none is provided
    if not service_name:
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
