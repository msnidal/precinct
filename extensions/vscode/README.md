# Precinct SQL: Optimize Your Queries with GPT

Streamline your SQL development in Visual Studio Code with Precinct SQL. This extension applies OpenAI's GPT models to provide intelligent SQL optimization suggestions, integrating smoothly with your development workflow.

## Features

- **AI-Powered Optimization**: Leverage GPT-4 or GPT-3.5-turbo to enhance SQL query performance.
- **Secure Credential Storage**: Manage PostgreSQL credentials securely within VS Code.
- **Query Comparison**: Compare your SQL with AI-optimized alternatives using a clear diff view.
- **Flexible Tool Integration**: Directly integrate with the Precinct CLI using custom paths.

## Prerequisites

- [Python >=3.9](https://www.python.org/downloads/)

## Installation

1. Install the extension from the VS Code Marketplace.
2. Use the `Precinct: Setup PostgreSQL Connection` command to configure database connections.

## Setting Up Database Connections

Instead of modifying settings manually, run the setup command which guides you through the process:

1. **Start Setup**: Open the Command Palette (`Ctrl+Shift+P`) and type `Precinct: Setup PostgreSQL Connection`.
2. **Enter API Key**: Input your OpenAI API key when prompted.
3. **Provide Credentials**: Choose between using individual credentials or a PGSERVICEFILE.
   - If using **PGSERVICEFILE**, input the file path and select the service definition.
   - If using **individual credentials**, enter the host, port, username, password, and database name to construct the connection string.

Credentials are stored securely and used to connect to your PostgreSQL database when optimizing queries.

## Optimizing SQL Queries

To optimize a SQL query:

1. **Open a SQL File**: Ensure you have an active SQL file open in your editor.
2. **Invoke Optimization**: Use the `Precinct: Optimize SQL` command from the Command Palette.
3. **Authentication**: If not already authenticated, the extension will prompt you to run the setup command.
4. **Review Suggestions**: The extension processes your SQL query and provides a diff view showing the proposed optimizations.
5. **Apply or Adjust**: Decide to apply the AI's suggestions directly or adjust them according to your needs.

## Extension Settings

The extension manages most settings automatically after the initial setup. For advanced users, settings can be adjusted in the JSON configuration directly:

- `precinct-sql.model`: Choose between "gpt-4" or "gpt-3.5-turbo" for the optimization model.
- `precinct-sql.cliPath`: Specify a custom path or command to execute Precinct if it's not in your PATH.
- `precinct-sql.useServiceFile`: Use a PGSERVICEFILE to provide PostgreSQL connection details by setting this to true.
- `precinct-sql.serviceFilePath`: Specify the file path for PGSERVICEFILE, which stores connection profiles for PostgreSQL databases.
- `precinct-sql.serviceDefinition`: Define the service within PGSERVICEFILE to use for connections. It corresponds to a named profile in the PGSERVICEFILE.

These settings reflect preferences on how the Precinct SQL extension interacts with your SQL code, the connection to your database, and your preferred optimization model.

### Stored Secrets

- **OpenAI API Key**: Used to authenticate with OpenAI's services for query optimization, this key is only entered once by the user and then securely stored.
- **PostgreSQL Connection String**: If not using a service file, your database connection details, including host, port, username, password, and database name, are stored as a connection string.

The extension automatically prompts users for these details during the initial setup or connection configuration process and securely saves them in the VS Code local secrets storage.

## Issues and Contributions

Feedback and contributions are welcome. If you encounter any issues or wish to improve the extension, please [file an issue or submit a pull request](https://github.com/msnidal/precinct).

## What's New in 0.1.4

- Setup function for easy configuration.
- Optimized SQL queries with diff view comparison.

Thank you for choosing Precinct SQL for your query optimization needs!
