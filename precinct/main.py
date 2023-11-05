import pyperclip
import click
import json

from precinct.models import PrecinctQuery, GPTModel
from precinct.connection import get_connection
from precinct.logging import get_logger
logger = get_logger()



@click.command(
    help=(
        "\nPrecinct: A SQL query LLM copilot for analyzing queries, suggesting indices, "
        "and providing optimizations. Currently supports PostgreSQL.\n\n"
        "Examples:\n\n"
        '    precinct --query "SELECT * FROM table;"\n\n'
        "    precinct --file path/to/your/file.sql\n\n"
    )
)
@click.option("--query", help="SQL query string.")
@click.option("--file", type=click.Path(exists=True), help="File path to SQL query.")
@click.option(
    "--service",
    "service",
    type=str,
    help="PostgreSQL service name located in ~/.pg_service.conf or at PGSERVICEFILE.",
)
@click.option(
    "--connection-string",
    "connection_string",
    type=str,
    help="PostgreSQL standard connection string, ie. 'postgresql://username:password@host:port/database'",
)
@click.option(
    "--model",
    type=click.Choice([GPTModel.GPT_4, GPTModel.GPT_3_5_TURBO]),
    default=GPTModel.GPT_4,
    help="Model to use.",
)
@click.option(
    "--json", "json_io", is_flag=True, help="Enable VSCode optimized JSON I/O mode."
)
def main(query, file, service, connection_string, model, json_io):
    if service and connection_string:
        raise click.BadParameter("Cannot use both --service and --connection-string.")
    conn = get_connection(service, connection_string)

    # Special input mode for VSCode extension
    if json_io:
        # Switch to JSON I/O mode for interaction with VSCode
        precinct_query = PrecinctQuery(query, conn, model)
        explanation = precinct_query.get_query_summary()
        # Output initial explanation in JSON
        print(json.dumps({"query": query, "goal": explanation.goal}))

        # Wait for JSON input from VSCode
        input_json = json.loads(input())
        user_modified_goal = input_json.get("goal")

        # Perform optimization based on the modified goal
        new_query, explanation = precinct_query.get_optimized_query(user_modified_goal)
        print(
            json.dumps(
                {"optimized_query": new_query.query_str, "explanation": explanation}
            )
        )
        return

    # Get query
    if query:
        pass
    elif file:
        with open(file, "r") as input_file:
            query = input_file.read()
    else:
        click.secho(
            "Either --query, --file or --interactive must be provided.", fg="red"
        )
        return

    # Extract tables, indices, column properties, and analysis
    try:
        precinct_query = PrecinctQuery(query, conn, model)
    except ValueError:
        print("Invalid query.")
        return

    # Gather any clarifications on query goal
    do_proceed = False
    clarification = None
    while not do_proceed:
        explanation = precinct_query.get_query_summary(clarification)
        print(f"Query: {query}")
        print(f"Goal: {explanation.goal}")
        confirm = input(
            "Issue clarification to goal (y) to proceed, or (q) to quit (y/q/[goal]): "
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

    print(f"Optimized query: {new_query.query_str}\n\nExplanation: {explanation}")
    action_prompt = "What would you like to do? (run/copy/cancel)"
    action = input(action_prompt + ": ")

    if action == "run":
        with conn.cursor() as cursor:
            cursor.execute(new_query.query_str)
    elif action == "copy":
        pyperclip.copy(new_query.query_str)
    elif action == "cancel":
        print("Operation cancelled.")


if __name__ == "__main__":
    main()
