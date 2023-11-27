import pytest
from unittest.mock import patch, MagicMock
from unittest import TestCase
import psycopg2

from precinct import main, connection
from precinct.models import (
    PrecinctQuery,
    GPTModel,
    ExplainQueryOutput,
    OptimizeQueryOutput,
)


def test_argument_parsing_exclusive_options():
    """Test that the --uri and --service options are mutually exclusive."""
    with pytest.raises(
        SystemExit
    ):  # click.UsageError will trigger a SystemExit in testing
        main.main(["--uri", "postgresql://user@host/db", "--service", "my_service"])


def test_query_input_from_file(tmp_path):
    """Test that a query can be read from a file."""
    query_file = tmp_path / "query.sql"
    query_file.write_text("SELECT * FROM table;")
    assert main.get_query_string(str(query_file)) == "SELECT * FROM table;"


def test_query_input_as_string():
    """Test that a query can be read from a string."""
    assert main.get_query_string("SELECT * FROM table;") == "SELECT * FROM table;"


@pytest.fixture
def mock_db_connection():
    conn = MagicMock(spec=psycopg2.extensions.connection)
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [("mock_plan",)]
    return conn


@patch("precinct.connection.get_connection")
def test_database_connection(mock_get_connection, mock_db_connection):
    """Verify that a database connection is returned."""
    mock_get_connection.return_value = mock_db_connection
    connection.get_connection("service_name", "connection_string")
    mock_get_connection.assert_called_with("service_name", "connection_string")
    assert mock_get_connection.return_value == mock_db_connection


class TestPrecinctQuery(TestCase):
    def setUp(self):
        # Setup a mock database connection
        self.mock_conn = MagicMock(spec=psycopg2.extensions.connection)
        self.mock_cursor = self.mock_conn.cursor.return_value
        self.mock_cursor.fetchall.return_value = [("Mocked Analysis Output",)]

        # Mock responses for the OpenAI API
        self.mock_explain_response = ExplainQueryOutput(
            structure="Mocked Structure", intent="Mocked Intent"
        )
        self.mock_optimize_response = OptimizeQueryOutput(
            query="SELECT * FROM optimized_table", explanation="Mocked Explanation"
        )

    @patch("openai.ChatCompletion.create")
    def test_get_optimized_query(self, mock_openai_call):
        # Configure the mock to return a specific response
        mock_openai_call.side_effect = [
            self.mock_explain_response,
            self.mock_optimize_response,
        ]

        # Initialize PrecinctQuery with the mock connection
        pq = PrecinctQuery(
            "SELECT * FROM table", conn=self.mock_conn, model=GPTModel.GPT_4
        )

        # Call the method under test
        optimized_query, explanation = pq.get_optimized_query()

        # Assert that the optimized query and explanation are as expected
        self.assertEqual(optimized_query.query_str, "SELECT * FROM optimized_table")
        self.assertEqual(explanation, "Mocked Explanation")
