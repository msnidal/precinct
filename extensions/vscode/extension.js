const { exec, spawn } = require('child_process');
const vscode = require('vscode');
const fs = require('fs')
const path = require('path');
const diff = require('diff');
const os = require('os');

function activate(context) {
	console.log('Precinct SQL extension activating...');

	async function setupConnectionWrapper() {
		const configuration = vscode.workspace.getConfiguration('precinct-sql');
		const secrets = context.secrets;

		const userChoice = await vscode.window.showQuickPick(
			['Use individual credentials', 'Use PGSERVICEFILE'],
			{ placeHolder: 'How would you like to provide PostgreSQL credentials?' }
		);
		const useServiceFileSetting = userChoice === 'Use PGSERVICEFILE';
		await configuration.update('useServiceFile', useServiceFileSetting, vscode.ConfigurationTarget.Global);

		if (useServiceFileSetting) {
			let serviceFilePath = configuration.get('serviceFilePath') || path.join(os.homedir(), '.pg_service.conf');
			serviceFilePath = await askForInput('PGSERVICEFILE path', serviceFilePath);
			await configuration.update('serviceFilePath', serviceFilePath, vscode.ConfigurationTarget.Global);

			// Check if the default or the entered service file path exists and is valid
			try {
				await fs.promises.access(serviceFilePath); // Throws if the file does not exist
				const serviceFileContent = await fs.promises.readFile(serviceFilePath, 'utf8');
				const serviceNames = serviceFileContent.match(/^\[(.*?)\]/gm);
				if (!serviceNames) {
					throw new Error('No service definitions found in the PGSERVICEFILE.');
				}
				const selectedService = await vscode.window.showQuickPick(
					serviceNames.map(name => name.replace(/[\[\]]/g, '')),
					{ placeHolder: 'Select a service definition' }
				);
				if (selectedService) {
					await configuration.update('serviceDefinition', selectedService, vscode.ConfigurationTarget.Global);
				} else {
					throw new Error('Service definition selection was cancelled.');
				}
			} catch (error) {
				if (error.code === 'ENOENT') {
					vscode.window.showErrorMessage(`The file ${serviceFilePath} does not exist.`);
					return; // Abort the flow if the file does not exist
				} else {
					vscode.window.showErrorMessage(`Error accessing the service file: ${error.message}`);
					return; // Abort the flow for any other error
				}
			}
		} else {
			try {
				const host = await askForInput('PostgreSQL Host');
				const port = await askForInput('PostgreSQL Port', '5432');
				const user = await askForInput('PostgreSQL Username');
				const password = await askForInput('PostgreSQL Password', '', true); // Mask input
				const database = await askForInput('PostgreSQL Database');
				// Construct the connection string using the provided credentials
				connectionString = `postgresql://${user}:${password}@${host}:${port}/${database}`;
				secrets.store('precinctSQLConnectionString', connectionString);
				vscode.window.showInformationMessage('PostgreSQL credentials saved securely.');
			} catch (error) {
				vscode.window.showErrorMessage(error.message);
				// If here, an input was cancelled, so we should exit the function.
				return;
			}
		}
	}
	let setupConnectionCommand = vscode.commands.registerCommand('precinct-sql.setupConnection', () => setupConnectionWrapper());

	let disposable = vscode.commands.registerCommand('precinct-sql.optimizeSQL', async function () {
		let editor = vscode.window.activeTextEditor;
		if (!editor) {
			vscode.window.showWarningMessage("No active text editor found");
			return;
		}

		let originalUri = editor.document.uri;
		const secrets = context.secrets;

		const filePath = originalUri.fsPath;
		const configuration = vscode.workspace.getConfiguration('precinct-sql');
		const precinctModel = configuration.get('model');
		const useServiceFileSetting = configuration.get('useServiceFile');
		const serviceFilePath = configuration.get('serviceFilePath') || path.join(os.homedir(), '.pg_service.conf');
		const serviceDefinition = configuration.get('serviceDefinition');
		const customPath = configuration.get('cliPath');

		// Prepare parameters based on settings
		let params = {};
		if (useServiceFileSetting) {
			params.serviceFilePath = serviceFilePath;
			params.service = serviceDefinition;
		} else {
			connectionString = await secrets.get('precinctSQLConnectionString'); // retrieve previously stored connection string
			if (!connectionString) {
				await setupConnectionWrapper(); // Ensure credentials are set up
				connectionString = await secrets.get('precinctSQLConnectionString');
			}
			params.connectionString = connectionString;
		}

		executePrecinct(filePath, precinctModel, params, editor, precinctCommand)
			.catch((error) => {
				if (error.message.includes('command not found')) {
					if (!customPath) {
						offerToInstallPrecinct();
					} else {
						vscode.window.showErrorMessage("Error: Precinct command not found at custom path.");
					}
				} else {
					vscode.window.showErrorMessage("Error optimizing SQL: " + error.message);
				}
			});
	});

	context.subscriptions.push(disposable);
	context.subscriptions.push(setupConnectionCommand);
}

async function executePrecinct(filePath, precinctModel, params, editor, customPath) {
	// Construct command arguments based on params passed
	const precinctCommand = customPath || 'precinct';
	let commandArgs = `--file "${filePath}" --model ${precinctModel}`;
	if (params.serviceFilePath && params.service) {
		commandArgs += ` --service ${params.service} --service-file-path "${params.serviceFilePath}"`;
	} else if (params.connectionString) {
		commandArgs += ` --connection-string "${params.connectionString}"`;
	}
	const command = `${precinctCommand} ${commandArgs} --json`;

	return new Promise((resolve, reject) => {
		const precinctProcess = spawn(command, { shell: true, stdio: ['pipe', 'pipe', 'pipe'] });

		precinctProcess.on('close', (code) => {
			if (code !== 0) {
				reject(new Error('Precinct command failed with exit code ' + code));
			} else {
				resolve();
			}
		});

		precinctProcess.stderr.on('data', (data) => {
			const dataStr = data.toString();
			console.error(`stderr: ${dataStr}`); // Log the error
			if (dataStr.includes('command not found')) {
				precinctProcess.kill(); // terminate the process
				reject(new Error('Precinct command not found. Please ensure that Precinct is installed and properly configured.'));
			}
		});

		for await (const data of precinctProcess.stdout) {
			try {
				let output = JSON.parse(data.toString());
				if (output.intent) {
					let userInput = await vscode.window.showInputBox({ prompt: 'Modify the intent as needed', value: output.intent });
					precinctProcess.stdin.write(JSON.stringify({ intent: userInput }) + "\n"); // Make sure to add newline to signify input end
				} else if (output.optimized_query) {
					await showDiff(editor.document, output.optimized_query);
				}
			} catch (error) {
				vscode.window.showErrorMessage('Failed to parse output from Precinct.');
				precinctProcess.kill(); // terminate the process if there's an error
				break; // exit the loop if an error occurs
			}
		}
	});
}

async function askForInput(prompt, defaultValue = '', isPassword = false) {
	const result = await vscode.window.showInputBox({
		prompt: prompt,
		value: defaultValue,
		password: isPassword,
		ignoreFocusOut: true
	});
	if (result === undefined) { // User pressed escape or closed the input box
		throw new Error('Input for ' + prompt + ' was cancelled by the user.');
	}
	return result;
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

	await fs.promises.writeFile(tempDiffFile, formattedDiff);

	// Generate a Uri for the temporary file
	const diffUri = vscode.Uri.file(tempDiffFile);

	vscode.commands.executeCommand('vscode.diff', document.uri, diffUri, 'Original ↔ Proposed');
}

module.exports = {
	activate,
};