# Precinct SQL: The SQL AI Copilot

Welcome to Precinct SQL - your artificial intelligence assistant for optimizing SQL queries within Visual Studio Code. Utilize advanced AI to streamline and improve your database queries directly from your editor.

## Features

- **SQL Query Optimization**: Improve your SQL with AI-powered suggestions.
- **Interactive Goal Setting**: Refine AI analysis goals through user interaction.
- **Diff View**: Compare and review optimization suggestions with your original query.
- **Streamlined VS Code Integration**: Experience a frictionless workflow within the editor's environment.

## Prerequisites

- [Node.js](https://nodejs.org/en/download/)
- [Python](https://www.python.org/downloads/)
- Precinct CLI: Must be installed globally or accessible through the extension's configuration.

## Extension Settings

Modify these settings to tailor the extension to your needs:

- `precinct-sql.model`: Select the AI model ('gpt-4' or 'gpt-3.5-turbo').
- `precinct-sql.connectionString`: Define the PostgreSQL connection string for analysis.
- `precinct-sql.cliPath`: Specify a custom path to the Precinct CLI.

## Quickstart Guide

1. Install the extension from the VS Code Marketplace.
2. Configure the necessary settings (`precinct-sql.model`, `precinct-sql.connectionString`).
3. Invoke the command `Precinct: Optimize SQL` for analysis.
4. Accept or adjust the optimization proposals as needed.
5. Experience enhanced SQL performance.

## Issues and Contributions

Encounter a glitch? Have suggestions? Contribute or report issues [here](https://github.com/msnidal/precinct).

## What's New in 0.1.0

- Initial launch with AI-powered optimization.
- New configuration options for enhanced control.

For detailed release notes, see the [changelog](CHANGELOG.md).

**Happy programming with your SQL query AI copilot!**
