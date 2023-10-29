import os
import configparser
import pyperclip
import psycopg2
import psycopg2.sql
import psycopg2.extensions
import click
import logging
from typing import Optional

from precinct.models import PrecinctQuery

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@click.command(
    help=(
        "\nPrecinct: A SQL query LLM copilot for analyzing queries, suggesting indices, "
        "and providing optimizations. Currently supports PostgreSQL.\n\n"
        "Example:\n\n"
        '    precinct "SELECT * FROM table;"\n\n'
        "    precinct --file path/to/your/file.sql\n\n"
    )
)
@click.argument("input", required=True)
@click.option(
    "--file",
    "is_file",
    is_flag=True,
    default=False,
    help="Indicate that the input is a file path.",
)
@click.option(
    "--service",
    "service_name",
    type=str,
    default=None,
    help="PostgreSQL service name for connection.",
)
@click.option(
    "--copy",
    "copy",
    is_flag=True,
    default=False,
    help="Copy optimized query to clipboard.",
)
@click.option(
    "--output-file",
    "output_file",
    type=str,
    default=None,
    help="Optional output file to write optimized query.",
)
def main(input, is_file, service_name, copy, output_file):
    if is_file:
        with open(input, "r") as input_file:
            query = input_file.read()
    else:
        query = input

    conn = get_connection(service_name)
    try:
        precinct_query = PrecinctQuery(query, conn)
    except ValueError:
        print("Invalid query.")
        return

    ## First step: think through the query step by step and explain the goal of the query and the main steps
    # This will be offered back to the user to confirm and then included as context in the optimization step
    do_proceed = False
    clarification = None
    while not do_proceed:
        explanation = precinct_query.get_query_summary(clarification)
        # TODO: Revise thee goal
        print(f"Query: {query}")
        print(f"Goal: {explanation.goal}")
        confirm = input(
            "Issue clarification to goal (y) to proceed, or (q) to quit (y/q/[goal]): "
        )
        if confirm.lower() != "y":
            do_proceed = True
        if confirm.lower() == "q":
            return
        else:
            clarification = confirm

    ## Third step: synthesize query, indices, and plan into a query to get the diff
    # Synthesize query, indices, and plan into a query to get the diff
    # TODO: loop here? also validate the output query
    new_query, explanation = precinct_query.get_optimized_query(conn)
    print(f"Optimized query: {new_query.query_str}\n\nExplanation: {explanation}")

    action_prompt = "What would you like to do? (execute/cancel)"
    if output_file:
        action_prompt = "What would you like to do? (overwrite/execute/cancel)"

    action = input(action_prompt + ": ")

    if action == "overwrite" and output_file:
        with open(output_file, "w") as f:
            f.write(new_query.query_str)
    elif action == "execute":
        with conn.cursor() as cursor:
            cursor.execute(new_query.query_str)
    elif action == "cancel":
        print("Operation cancelled.")

    if copy:
        pyperclip.copy(new_query.query_str)


def get_connection(
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


if __name__ == "__main__":
    main()
