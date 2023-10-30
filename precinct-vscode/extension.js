const { exec, spawn } = require('child_process');
const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const diff = require('diff');

let venvCreated = false;  // flag to track if the virtual environment was created

function activate(context) {
	let disposable = vscode.commands.registerCommand('precinct-sql.optimizeSQL', function () {
		let editor = vscode.window.activeTextEditor;
		let originalQuery = editor.document.getText();
		let originalUri = editor.document.uri;

		// Check precinct install
		exec('pip show precinct', (err, stdout, stderr) => {
			if (err || !stdout.includes('Name: precinct')) {
				venvCreated = true;
				exec('python -m venv myenv && source myenv/bin/activate && pip install precinct', (err, stdout, stderr) => {
					if (err) {
						vscode.window.showErrorMessage('Error: ' + stderr);
						return;
					}
					executePrecinct('myenv/bin/python -m precinct args');
				});
			} else {
				executePrecinct('precinct args');
			}
		});

		// Refactored precinct execution into a separate function for clarity and reusability
		function executePrecinct(command) {
			const precinctProcess = spawn(command, { shell: true, stdio: ['pipe', 'pipe', 'pipe'] });

			let initialOutput = '';
			precinctProcess.stdout.on('data', (data) => {
				initialOutput += data.toString();
			});

			precinctProcess.stdout.on('close', async () => {
				const userModifiedGoal = await vscode.window.showInputBox({ prompt: 'Modify the goal as needed', value: initialOutput });
				precinctProcess.stdin.write(userModifiedGoal + '\n');

				let proposedQuery = '';
				precinctProcess.stdout.on('data', (data) => {
					proposedQuery += data.toString();
				});

				precinctProcess.stdout.on('close', () => {
					const changes = diff.diffLines(originalQuery, proposedQuery);
					const formattedDiff = changes.map(change => {
						return (change.added ? '+ ' : '- ') + change.value;
					}).join('\n');
					const diffUri = vscode.Uri.file(path.join(__dirname, 'diff.sql'));
					fs.writeFileSync(diffUri.fsPath, formattedDiff);
					vscode.commands.executeCommand('vscode.diff', originalUri, diffUri, 'Original ↔ Proposed');
				});
			});
		}
	});
	context.subscriptions.push(disposable);
}
exports.activate = activate;

function deactivate() {
	if (venvCreated) {
		// If the virtual environment was created, remove it
		let venvPath = path.join(__dirname, 'myenv');
		fs.rmdirSync(venvPath, { recursive: true, force: true }, (err) => {
			if (err) {
				console.error('Failed to remove virtual environment:', err);
			}
		});
	}
}

module.exports = {
	activate,
	deactivate
}
