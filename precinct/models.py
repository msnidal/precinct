import yaml
import psycopg2
import psycopg2.sql
import psycopg2.extensions
import sqlparse
import sqlparse.sql
import openai
import os
import instructor

from enum import Enum
from typing import List, Dict, Set, Optional, Tuple, Union

from pydantic import BaseModel
from cachetools import cached, LRUCache
from cachetools.keys import hashkey

from precinct.logging import get_logger

logger = get_logger()

# Support openai function calling with pydantic base model
instructor.patch()


class GPTModel(str, Enum):
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"


def load_prompts(
    file_path: Optional[str] = None,
) -> Dict[str, Union[str, Dict[str, str]]]:
    """Load prompts from prompts.yml file.

    Args:
        file_path: The path to the prompts.yml file.
    Returns:
        Dict[str, Union[str, Dict[str, str]]]: The prompts.
    """
    if file_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, "prompts.yml")

    with open(file_path, "r") as prompts_file:
        return yaml.safe_load(prompts_file)


PROMPTS = load_prompts()


class ExplainQueryInput(BaseModel):
    """Input to the explain query prompt.

    Attributes:
        query: The SQL query as provided.
        clarification: Optional clarification on the nature or functionality of the query.
    """

    query: str
    clarification: Optional[str]

    def __str__(self) -> str:
        base = f"<query>{self.query}</query>"
        if self.clarification:
            return base + f"\n<clarification>{self.clarification}</clarification>"
        return base


class ExplainQueryOutput(BaseModel):
    """Output from the explain query prompt, in natural language.

    Attributes:
        structure: Comments on the structure of the query
        goal: The goal of the query explained succinctly
    """

    structure: str
    goal: str


class OptimizeQueryOutput(BaseModel):
    """Output from the optimize query prompt.

    Attributes:
        query: The optimized SQL query.
        explanation: Comments on the newly optimized query
    """

    query: str
    explanation: str


class OptimizeQueryInput(BaseModel):
    """Input to the optimize query prompt.

    Attributes:
        query: The SQL query as provided.
        goal: The goal of the query.
        indices: The indices on the tables referenced by the query.
        columns: The properties of the columns referenced by the query.
        analyze: The output of the EXPLAIN ANALYZE on the query.
    """

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
        """Fetch indices on the table from the database.

        Returns:
            A dictionary of index names and definitions.
        """
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
    """Represents a query and related information for the optimization process.

    Attributes:
        query_str: The SQL query string.
        analysis: The output of the EXPLAIN ANALYZE on the query.
        tables: The tables referenced by the query.
    """

    def __init__(
        self, query_str: str, conn: psycopg2.extensions.connection, model: GPTModel
    ) -> None:
        self.query_str = query_str
        self.conn = conn
        self.model = model

        if not self.validate():
            logger.error("Invalid query.")
            raise ValueError("Invalid query.")

        self.analysis = self.execute_query_analysis()
        self.tables = self.get_tables(query_str)

    def validate(self) -> bool:
        """
        Validate query by attempting to prepare it.

        Returns:
            True if query is valid, False otherwise.
        """
        parsed = sqlparse.parse(self.query_str)
        if not parsed:
            logger.warning("Failed to parse query.")
            return False

        with self.conn.cursor() as cursor:
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

    def get_tables(self, query: str) -> List[PrecinctTable]:
        """Parse SQL query and extract referenced table names.

        Args:
            query: The SQL query string.
        Returns:
            A list of PrecinctTable objects, representing the tables referenced by the query.
        """
        table_names = self.extract_table_names(query)
        return [self.get_table(table_name) for table_name in table_names]

    @cached(
        cache=LRUCache(maxsize=128),
        key=lambda self, table_name: hashkey(table_name),
    )
    def get_table(self, table_name: str) -> PrecinctTable:
        """Fetch table information from database.

        Caches the table information to avoid repeated queries.
        Args:
            table_name: The name of the table.
        Returns:
            A PrecinctTable object, representing the table referenced by the query.
        """
        return PrecinctTable(table_name, self.conn)

    def extract_table_names(self, query: str) -> Set[str]:
        """Parse SQL query and extract referenced table names.

        Args:
            query: The SQL query string.
        Returns:
            A set of table names referenced by the query.
        """
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

    def execute_query_analysis(self) -> List[str]:
        """
        Run an EXPLAIN ANALYZE on the query and return the output.

        Returns:
            A list of analysis output strings.
        """
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(f"EXPLAIN ANALYZE {self.query_str}")
                return [plan[0] for plan in cursor.fetchall()]
            except psycopg2.Error as e:
                logger.error(f"Failed to execute query analysis: {str(e)}")
                return []

    def get_query_summary(
        self, clarification: Optional[str] = None
    ) -> ExplainQueryOutput:
        """
        Get a natural language summary of the query and its goal.

        Args:
            clarification: Optional clarification on the nature or functionality of the query.
        Returns:
            An ExplainQueryOutput object.
        """
        try:
            query_input = ExplainQueryInput(
                query=self.query_str, clarification=clarification
            )
            query_out = openai.ChatCompletion.create(
                model=self.model,
                response_model=ExplainQueryOutput,
                messages=[
                    {"role": "system", "content": PROMPTS["explain"]},
                    {"role": "user", "content": str(query_input)},
                ],
            )

            if not isinstance(query_out, ExplainQueryOutput):
                raise ValueError("Failed to get query summary.")

            return query_out
        except Exception as e:
            logger.error(f"Failed to get query summary: {str(e)}")
            raise e

    def get_optimized_query(
        self,
        prior_clarification: Optional[str] = None,
    ) -> Tuple["PrecinctQuery", str]:
        """
        Get an optimized query based on the original query and related information

        Args:
            prior_clarification: Optional clarification on the nature or functionality of the query.
        Returns:
            A tuple of the optimized PrecinctQuery object and the explanation of the optimization.
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
                model=self.model,
                response_model=OptimizeQueryOutput,
                messages=[
                    {"role": "system", "content": PROMPTS["optimize"]},
                    {"role": "user", "content": str(query_input)},
                ],
            )
            if not isinstance(optimized_query_out, OptimizeQueryOutput):
                raise ValueError("Failed to optimize query.")

            optimized_query = PrecinctQuery(
                optimized_query_out.query, conn=self.conn, model=self.model
            )
            return optimized_query, optimized_query_out.explanation

        except Exception as e:
            logger.error(f"Failed to get query summary: {str(e)}")
            raise e
