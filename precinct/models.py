import yaml
import psycopg2
import psycopg2.sql
import psycopg2.extensions
import sqlparse
import sqlparse.sql
import openai
import logging
import os
import instructor

from pydantic import BaseModel
from typing import List, Dict, Set, Optional, Tuple, Union
from cachetools import cached, LRUCache
from cachetools.keys import hashkey

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Support openai function calling with pydantic base model
instructor.patch()


def load_prompts(
    file_path: Optional[str] = None,
) -> Dict[str, Union[str, Dict[str, str]]]:
    if file_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, "prompts.yml")

    with open(file_path, "r") as prompts_file:
        return yaml.safe_load(prompts_file)


PROMPTS = load_prompts()


class ExplainQueryInput(BaseModel):
    query: str
    clarification: Optional[str]

    def __str__(self) -> str:
        base = f"<query>{self.query}</query>"
        if self.clarification:
            return base + f"\n<clarification>{self.clarification}</clarification>"
        return base


class ExplainQueryOutput(BaseModel):
    structure: str
    goal: str


class OptimizeQueryOutput(BaseModel):
    query: str
    explanation: str


class OptimizeQueryInput(BaseModel):
    query: str
    goal: str
    indices: Dict[str, Dict[str, str]]
    columns: Dict[str, Dict[str, str]]
    analyze: List[str]

    def __str__(self) -> str:
        return f"<query>{self.query}</query>\n<goal>{self.goal}</goal>\n<indices>{self.indices}</indices>\n<columns>{self.columns}</columns>\n<analyze>{self.analyze}</analyze>"


class PrecinctTable:
    """Represents a table referenced by a query and related information for the optimization process.

    Attributes:
        table_name: The name of the table.
        conn: The connection to the database.
        indices: The indices on the table.
        column_properties: The properties of the columns in the table.
    """

    def __init__(self, table_name: str, conn: psycopg2.extensions.connection) -> None:
        self.table_name = table_name
        self.conn = conn

        logger.info(f"Fetching indices for table {self.table_name}")
        self.indices = self.fetch_indices()

        logger.info(f"Fetching columns for table {self.table_name}")
        self.column_properties = self.fetch_columns()

    def fetch_indices(self) -> Dict[str, str]:
        query = """
        SELECT
            indexname AS index_name,
            indexdef AS index_definition
        FROM pg_indexes
        WHERE tablename = %s;
        """

        indices: Dict[str, str] = {}
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(query, (self.table_name,))
                for index in cursor.fetchall():
                    indices[index[0]] = index[1]
            except Exception as e:
                logger.error(f"Error fetching indices: {str(e)}")
                raise

        logger.debug(f"Indices: {indices}")
        return indices

    def fetch_columns(self) -> Dict[str, str]:
        """Fetch column names and types from database.

        Returns:
            A list of dictionaries keyed by column name whose values are the type.
        """
        query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = %s;
        """
        columns = {}
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(query, (self.table_name,))
                for col in cursor.fetchall():
                    columns[col[0]] = col[1]
            except Exception as e:
                logger.error(f"Error fetching columns: {str(e)}")
                raise

        logger.debug(f"Columns: {columns}")
        return columns


class PrecinctQuery:
    def __init__(self, query_str: str, conn: psycopg2.extensions.connection) -> None:
        """
        Initialize a PrecinctQuery instance.

        :param query_str: The SQL query string.
        :param conn: The database connection object.
        """
        self.query_str = query_str
        if not self.validate(conn):
            logger.error("Invalid query.")
            raise ValueError("Invalid query.")

        self.analysis = self.execute_query_analysis(conn)
        self.tables = self.get_tables(query_str, conn)

    def validate(self, conn: psycopg2.extensions.connection) -> bool:
        """
        Validate query by attempting to prepare it.

        :param conn: The database connection object.
        :return: True if the query is valid, False otherwise.
        """
        parsed = sqlparse.parse(self.query_str)
        if not parsed:
            logger.warning("Failed to parse query.")
            return False

        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    psycopg2.sql.SQL("PREPARE stmt AS {0}").format(
                        psycopg2.sql.SQL(self.query_str)
                    )
                )
                cursor.execute("DEALLOCATE stmt")
            except psycopg2.Error as e:
                logger.error(f"Failed to prepare statement: {str(e)}")
                return False
        return True

    def get_tables(
        self, query: str, conn: psycopg2.extensions.connection
    ) -> List[PrecinctTable]:
        """Parse SQL query and extract referenced table names."""
        table_names = self.extract_table_names(query)
        return [self.get_table(table_name, conn) for table_name in table_names]

    @cached(
        cache=LRUCache(maxsize=128),
        key=lambda self, table_name, conn: hashkey(table_name),
    )
    def get_table(
        self, table_name: str, conn: psycopg2.extensions.connection
    ) -> PrecinctTable:
        """Fetch table information from database.

        Caches the table information to avoid repeated queries.
        """
        return PrecinctTable(table_name, conn)

    def extract_table_names(self, query: str) -> Set[str]:
        """Parse SQL query and extract referenced table names."""
        table_names = set()

        parsed = sqlparse.parse(query)
        for statement in parsed:
            for token in statement.tokens:
                if isinstance(
                    token, (sqlparse.sql.Identifier, sqlparse.sql.IdentifierList)
                ):
                    if isinstance(token, sqlparse.sql.Identifier):
                        table_names.add(token.get_real_name())
                    else:  # token is IdentifierList
                        for identifier in token.get_identifiers():
                            table_names.add(identifier.get_real_name())

        logger.info(f"Extracted table names: {table_names}")
        return table_names

    def execute_query_analysis(self, conn: psycopg2.extensions.connection) -> List[str]:
        """
        Run an EXPLAIN ANALYZE on the query and return the output.

        :param conn: The database connection object.
        :return: A list of analysis output strings.
        """
        with conn.cursor() as cursor:
            try:
                cursor.execute(f"EXPLAIN ANALYZE {self.query_str}")
                return [plan[0] for plan in cursor.fetchall()]
            except psycopg2.Error as e:
                logger.error(f"Failed to execute query analysis: {str(e)}")
                return []

    def get_query_summary(self, clarification: Optional[str]) -> ExplainQueryOutput:
        """
        Get a natural language summary of the query and its goal.

        :return: An instance of ExplainQueryOutput or None in case of failure.
        """
        try:
            query_input = ExplainQueryInput(
                query=self.query_str, clarification=clarification
            )
            return openai.ChatCompletion.create(
                model="gpt-4",
                response_model=ExplainQueryOutput,
                messages=[
                    {"role": "system", "content": PROMPTS["explain"]},
                    {"role": "user", "content": str(query_input)},
                ],
            )
        except Exception as e:
            logger.error(f"Failed to get query summary: {str(e)}")
            raise e

    def get_optimized_query(
        self,
        conn: psycopg2.extensions.connection = None,
        prior_clarification: Optional[str] = None,
    ) -> Tuple["PrecinctQuery", str]:
        """
        Get an optimized query based on the original query and related information

        :return: An instance of PrecinctQuery and the optimized query string.
        """
        try:
            query_input = OptimizeQueryInput(
                query=self.query_str,
                goal=self.get_query_summary(prior_clarification).goal,
                indices={table.table_name: table.indices for table in self.tables},
                columns={
                    table.table_name: table.column_properties for table in self.tables
                },
                analyze=self.analysis,
            )

            optimized_query_out = openai.ChatCompletion.create(
                model="gpt-4",
                response_model=OptimizeQueryOutput,
                messages=[
                    {"role": "system", "content": PROMPTS["optimize"]},
                    {"role": "user", "content": str(query_input)},
                ],
            )

            optimized_query = PrecinctQuery(optimized_query_out.query, conn=conn)
            return optimized_query, optimized_query_out.explanation

        except Exception as e:
            logger.error(f"Failed to get query summary: {str(e)}")
            raise e
