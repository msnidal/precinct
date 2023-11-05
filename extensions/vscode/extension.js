const { exec, spawn } = require('child_process');
const vscode = require('vscode');
const fs = require('fs').promises; // use promise-based fs module
const path = require('path');
const diff = require('diff');
const os = require('os');

function activate(context) {
	console.log('Precinct SQL extension activating...');
	let disposable = vscode.commands.registerCommand('precinct-sql.optimizeSQL', async function () {
		let editor = vscode.window.activeTextEditor;
		if (!editor) {
			vscode.window.showWarningMessage("No active text editor found");
			return;
		}

		let originalUri = editor.document.uri;
		const filePath = originalUri.fsPath;
		const precinctModel = vscode.workspace.getConfiguration('precinct-sql').get('model');
		const connectionString = vscode.workspace.getConfiguration('precinct-sql').get('connectionString');
		if (!connectionString) {
			vscode.window.showErrorMessage("PostgreSQL connection string is not set in settings");
			vscode.commands.executeCommand('workbench.action.openSettings', 'precinct-sql.connectionString');
			return;
		}
		const customPath = vscode.workspace.getConfiguration('precinct-sql').get('cliPath');
		const precinctCommand = customPath || 'precinct';

		try {
			await executePrecinct(filePath, precinctModel, connectionString, editor, precinctCommand);
		} catch (error) {
			if (error.message.includes('command not found') && !customPath) {
				offerToInstallPrecinct();
			} else {
				vscode.window.showErrorMessage("Error optimizing SQL: " + error.message);
			}
		}
	});
	context.subscriptions.push(disposable);
}

async function executePrecinct(filePath, precinctModel, connectionString, editor, precinctCommand) {
	const command = `${precinctCommand} --file "${filePath}" --model ${precinctModel} --connection-string "${connectionString}" --json`;
	const precinctProcess = spawn(command, { shell: true, stdio: ['pipe', 'pipe', 'pipe'] });

	precinctProcess.stderr.on('data', (data) => {
		console.error(`stderr: ${data}`); // This will log to the VS Code's debug console, not to the output channel
	});

	for await (const data of precinctProcess.stdout) {
		try {
			let output = JSON.parse(data.toString());
			if (output.goal) {
				let userInput = await vscode.window.showInputBox({ prompt: 'Modify the goal as needed', value: output.goal });
				precinctProcess.stdin.write(JSON.stringify({ goal: userInput }) + "\n"); // Make sure to add newline to signify input end
			} else if (output.optimized_query) {
				await showDiff(editor.document, output.optimized_query);
			}
		} catch (error) {
			vscode.window.showErrorMessage('Failed to parse output from Precinct.');
			precinctProcess.kill(); // terminate the process if there's an error
			break; // exit the loop if an error occurs
		}
	}
}

function offerToInstallPrecinct() {
	// Use the integrated terminal to offer the installation of Precinct
	const installMessage = 'Precinct is not installed. Would you like to install it now?';
	vscode.window.showInformationMessage(installMessage, 'Yes', 'No').then(selection => {
		if (selection === 'Yes') {
			const terminal = vscode.window.createTerminal({ name: 'Install Precinct' });
			terminal.sendText('pip install precinct');
			terminal.show();
		}
	});
}

async function showDiff(document, proposedQuery) {
	const originalQuery = document.getText();
	const changes = diff.diffLines(originalQuery, proposedQuery);
	const formattedDiff = changes.map(change => {
		return (change.added ? '+ ' : change.removed ? '- ' : '  ') + change.value;
	}).join('\n');

	// Use os.tmpdir() to get a platform-independent temporary directory
	const tempDir = os.tmpdir();
	const tempDiffFile = path.join(tempDir, 'precinct-diff.sql');

	await fs.writeFile(tempDiffFile, formattedDiff);

	// Generate a Uri for the temporary file
	const diffUri = vscode.Uri.file(tempDiffFile);

	vscode.commands.executeCommand('vscode.diff', document.uri, diffUri, 'Original ↔ Proposed');
}

module.exports = {
	activate,
};