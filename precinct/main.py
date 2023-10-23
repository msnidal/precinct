import os
import configparser
import pyperclip
import psycopg2
import sqlparse
import openai
import click
import yaml
import instructor
from pydantic import BaseModel
from typing import List, Dict, Union, Set

# Support openai function calling with pydantic base model
instructor.patch()


class ExplainQueryOutput(BaseModel):
    structure: str
    goal: str


class OptimizeQueryOutput(BaseModel):
    query: str
    explanation: str


def load_prompts(file_path="prompts.yml"):
    with open(file_path, "r") as prompts_file:
        return yaml.safe_load(prompts_file)


def is_valid_query(conn, query: str) -> bool:
    parsed = sqlparse.parse(query)
    if not parsed:
        return False

    with conn.cursor() as cursor:
        try:
            cursor.execute(
                psycopg2.sql.SQL("PREPARE stmt AS {0}").format(psycopg2.sql.SQL(query))
            )
        except psycopg2.Error:
            return False
        finally:
            cursor.execute("DEALLOCATE stmt")
    return True


def extract_tables(query: str) -> Set[str]:
    parsed = sqlparse.parse(query)
    table_names = set()

    for statement in parsed:
        from_seen = False
        for token in statement.tokens:
            if from_seen:
                if token.ttype is None:
                    table_names.add(token.get_real_name())
                if token.value.upper() == "JOIN":
                    table_names.update(
                        token.get_real_name()
                        for join_token in token.tokens
                        if join_token.ttype is None
                    )
            from_seen = token.value.upper() == "FROM"

    return table_names


def fetch_indices(conn, table_names: Set[str]) -> List[Dict[str, Union[str, int]]]:
    query = """
    SELECT
        indexname AS index_name,
        indexdef AS index_definition
    FROM pg_indexes
    WHERE tablename = %s;
    """
    indices = []
    with conn.cursor() as cursor:
        for table in table_names:
            cursor.execute(query, (table,))
            indices.extend(
                {
                    "table": table,
                    "index_name": index[0],
                    "index_definition": index[1],
                }
                for index in cursor.fetchall()
            )
    return indices


def execute_query_analysis(conn, query: str) -> List[str]:
    with conn.cursor() as cursor:
        cursor.execute(f"EXPLAIN ANALYZE {query}")
        return [plan[0] for plan in cursor.fetchall()]


def run_ai_prompt(prompts: Dict[str, str], query: str, model: BaseModel) -> BaseModel:
    return openai.ChatCompletion.create(
        model="gpt-4",
        response_model=model,
        messages=[
            {"role": "system", "content": prompts["explain"]},
            {"role": "user", "content": query},
        ],
    )


def get_optimization_query(
    query: str, indices: List[Dict[str, Union[str, int]]], plan: List[str]
) -> str:
    pass


@click.group()
def main():
    pass


@main.command()
@click.argument("input_file", type=click.File("r"))
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
def file(input_file, service_name, copy):
    query = input_file.read()
    process_query(query, service_name, input_file=input_file, copy=copy)


@main.command()
@click.argument("input_query", type=str)
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
def query(input_query, service_name, copy):
    query = input_query
    process_query(query, service_name, copy=copy)


def process_query(
    query: str,
    service_name: str,
    output_file: str = None,
    copy_to_clipboard: bool = False,
):
    service_file_path = os.getenv(
        "PGSERVICEFILE", os.path.expanduser("~/.pg_service.conf")
    )
    config = configparser.ConfigParser()
    config.read(service_file_path)

    if service_name not in config.sections():
        print("Invalid service name.")
        return

    conn = (
        psycopg2.connect(service=service_name) if service_name else psycopg2.connect()
    )
    if not is_valid_query(conn, query):
        print("Invalid query.")
        return

    prompts = load_prompts()

    ## First step: think through the query step by step and explain the goal of the query and the main steps
    # This will be offered back to the user to confirm and then included as context in the optimization step
    explanation = run_ai_prompt(prompts, query, ExplainQueryOutput)
    # TODO: Revise thee goal
    print(f"Query: {query}")
    print(f"Explanation: {explanation.goal}")
    confirm = input("Do you want to proceed? (y/n): ")
    if confirm.lower() != "y":
        print("Operation cancelled.")
        return

    ## Second step: check for relevant tables, indices, and run EXPLAIN ANALYZE
    # Check for relevant tables, indices, and run EXPLAIN ANALYZE
    tables = extract_tables(query)
    indices = fetch_indices(conn, tables)
    original_plan = execute_query_analysis(conn, query)

    ## Third step: synthesize query, indices, and plan into a query to get the diff
    # Synthesize query, indices, and plan into a query to get the diff
    # TODO: loop here? also validate the output query
    optimization_query = get_optimization_query(
        query, indices, original_plan, explanation
    )

    optimization = run_ai_prompt(prompts, optimization_query, OptimizeQueryOutput)
    revised_plan = execute_query_analysis(conn, optimization.query)

    action_prompt = "What would you like to do? (execute/cancel)"
    if output_file:
        action_prompt = "What would you like to do? (overwrite/execute/cancel)"

    action = input(action_prompt + ": ")

    if action == "overwrite" and output_file:
        with open(output_file, "w") as f:
            f.write(optimization.query)
    elif action == "execute":
        with conn.cursor() as cursor:
            cursor.execute(optimization.query)
    elif action == "cancel":
        print("Operation cancelled.")

    if copy_to_clipboard:
        pyperclip.copy(optimization.query)


if __name__ == "__main__":
    main()
