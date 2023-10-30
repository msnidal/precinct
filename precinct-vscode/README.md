# Precinct SQL: The SQL AI Copilot

Precinct SQL is your AI copilot for analyzing and optimizing SQL queries right within VS Code. Built as an extension, Precinct SQL operates on `.sql` files to provide actionable insights and automatic query optimizations.

## Features

* **SQL Analysis and Optimization**:
  * Run the Precinct command on your SQL file to get an analysis of your query.
  * Precinct will describe a goal based on the analysis which the user can correct and submit for further review.
  * Once the corrections are submitted, Precinct will propose an optimized query.
  * The proposal is presented as a diff against the original query, along with a textual description of the changes.

* **Integrated UX**:
  * Precinct SQL is designed to work seamlessly with VS Code's UI, providing a natural, intuitive experience.

* **Command Execution**:
  * Execute the Precinct command via a keyboard shortcut, a button in the editor toolbar, or from the command palette.

* **Result Presentation**:
  * Results are displayed inline, with options to accept or reject the proposed query optimizations.

![Precinct SQL in action](images/precinct-in-action.png)

## Requirements

* [Node.js](https://nodejs.org/)
* [Python](https://www.python.org/downloads/)
* The Precinct CLI tool (installed either globally or via the extension)

## Extension Settings

This extension contributes the following settings:

* `precinctSQL.enable`: Enable/disable this extension.
* `precinctSQL.cliPath`: Path to the Precinct CLI tool (if installed globally).

## Getting Started

1. Install Precinct SQL from the VS Code Marketplace.
2. Open a `.sql` file in VS Code.
3. Run the Precinct command via your preferred method (keyboard shortcut, editor toolbar button, or command palette).
4. Review the proposed query optimizations, accept or reject as needed.
5. Enjoy optimized SQL queries and a smoother development experience!

## Known Issues

Please report any issues or feature requests on the [GitHub repository](https://github.com/your-username/precinct-sql).

## Release Notes

### 1.0.0

Initial release of Precinct SQL.

### 1.0.1

Fixed issue #.

### 1.1.0

Added features X, Y, and Z.

---

## For more information

* [Visual Studio Code's Markdown Support](http://code.visualstudio.com/docs/languages/markdown)
* [Markdown Syntax Reference](https://help.github.com/articles/markdown-basics/)

**Enjoy!**
