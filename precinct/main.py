import pyperclip
import click
import json
import os
import openai

from precinct.models import PrecinctQuery, GPTModel
from precinct.connection import get_connection
from precinct.logging import get_logger

logger = get_logger()


def get_query_string(query_input: str):
    """Determine if query_input is a query string or file path."""
    if os.path.isfile(query_input):
        with open(query_input, "r") as file:
            return file.read()
    return query_input


@click.command(
    help=(
        "\nPrecinct: A SQL query LLM copilot for analyzing queries, suggesting indices, "
        "and providing optimizations. Currently supports PostgreSQL.\n\n"
        "Examples:\n\n"
        '    precinct "SELECT * FROM table;"\n\n'
        '    precinct "path/to/your/file.sql"\n\n'
    )
)
@click.argument("query", type=str, required=True, nargs=1)
@click.option(
    "--uri",
    type=str,
    help="PostgreSQL connection URI, ie. 'postgresql://username:password@host:port/database'. Mutually exclusive with --service.",
)
@click.option(
    "--service",
    type=str,
    help="PostgreSQL service name as located in ~/.pg_service.conf or at specified path. Mutually exclusive with --uri.",
)
@click.option(
    "--service-file",
    type=click.Path(exists=True),
    default=os.path.expanduser("~/.pg_service.conf"),
    help="Path to PGSERVICEFILE. Optionally provide in conjunction with --service.",
    show_default="~/.pg_service.conf",
)
@click.option(
    "--openai-api-key",
    type=str,
    default=os.environ.get("OPENAI_API_KEY", ""),
    help="OpenAI API key for authentication.",
    show_default="from environment variable OPENAI_API_KEY",
)
@click.option(
    "--model",
    type=click.Choice([GPTModel.GPT_4, GPTModel.GPT_3_5_TURBO]),
    default=GPTModel.GPT_4,
    help="Model to use.",
)
@click.option(
    "--rows",
    type=int,
    default=10,
    help="Number of rows to return from query at most. Typically used for previewing query results.",
)
@click.option(
    "--json", "json_io", is_flag=True, help="Enable VSCode optimized JSON I/O mode."
)
def main(query, uri, service, service_file, openai_api_key, model, rows, json_io):
    if service and uri:
        raise click.UsageError("Options --service and --uri are mutually exclusive.")

    query = get_query_string(query)

    if openai_api_key:
        openai.api_key = openai_api_key

    if service_file:
        os.environ["PGSERVICEFILE"] = service_file

    conn = get_connection(service, uri)

    # Special input mode for VSCode extension
    if json_io:
        # Switch to JSON I/O mode for interaction with VSCode
        precinct_query = PrecinctQuery(query, conn, model)
        explanation = precinct_query.get_query_summary()
        # Output initial explanation in JSON
        print(json.dumps({"query": query, "intent": explanation.intent}))

        # Wait for JSON input from VSCode
        input_json = json.loads(input())
        user_modified_intent = input_json.get("intent")

        # Perform optimization based on the modified intent
        new_query, explanation = precinct_query.get_optimized_query(
            user_modified_intent
        )
        print(
            json.dumps(
                {"optimized_query": new_query.query_str, "explanation": explanation}
            )
        )
        return

    # Extract tables, indices, column properties, and analysis
    try:
        precinct_query = PrecinctQuery(query, conn, model)
    except ValueError:
        print("Invalid query.")
        return

    # Gather any clarifications on query intent
    do_proceed = False
    clarification = None
    while not do_proceed:
        explanation = precinct_query.get_query_summary(clarification)
        print(f"Query: {query}")
        print(f"Intent: {explanation.intent}")
        confirm = input(
            "Accept intent with `y`, quit with `q` or type out clarification to intent (y/q/[intent]): "
        )
        if confirm.lower() == "y":
            do_proceed = True
        if confirm.lower() == "q":
            return
        else:
            clarification = confirm

    # Synthesize query, indices, and plan into a query to get the diff
    attempts = 0
    while attempts < 3:
        try:
            new_query, explanation = precinct_query.get_optimized_query()
            break
        except Exception:
            attempts += 1
            logger.warn("Failed to optimize query. Retrying...")
    else:
        logger.error("Unable to optimize query. Exiting")
        return

    print(f"\nOptimized query: {new_query.query_str}\nExplanation: {explanation}")
    action = input(
        "Run query now with `r`, copy to clipboard with `c`, or cancel with `q` (r/c/q): "
    )

    if action.lower() == "r":
        with conn.cursor() as cursor:
            cursor.execute(new_query.query_str)
            print(cursor.fetchmany(rows))
    elif action.lower() == "c":
        pyperclip.copy(new_query.query_str)
    else:
        print("Operation cancelled.")


if __name__ == "__main__":
    main()
