const { exec, spawn } = require('child_process');
const vscode = require('vscode');
const fs = require('fs').promises; // use promise-based fs module
const path = require('path');
const diff = require('diff');

let venvPath = path.join(__dirname, 'myenv'); // constant for virtual env path

function activate(context) {
    ensurePrecinctInstalled()
        .then(() => {
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
                    return;
                }
                
                try {
                    await executePrecinct(filePath, precinctModel, connectionString);
                } catch (error) {
                    vscode.window.showErrorMessage("Error optimizing SQL: " + error.message);
                }
            });
            context.subscriptions.push(disposable);
        })
        .catch(error => {
            vscode.window.showErrorMessage("Precinct Installation Error: " + error.message);
        });
}

async function ensurePrecinctInstalled() {
    try {
        const { stdout } = await execAsync('pip show precinct');
        if (!stdout.includes('Name: precinct')) {
            throw new Error('Precinct is not installed');
        }
    } catch (error) {
        await createVirtualEnv();
    }
}

async function createVirtualEnv() {
    await execAsync('python -m venv myenv && source myenv/bin/activate && pip install precinct');
    // Set flag here if needed for cleanup later
}

async function execAsync(command) {
    return new Promise((resolve, reject) => {
        exec(command, (err, stdout, stderr) => {
            if (err) {
                reject({ message: stderr });
            } else {
                resolve({ stdout });
            }
        });
    });
}

async function executePrecinct(filePath, precinctModel, connectionString) {
    const command = `python ${venvPath}/bin/precinct --file "${filePath}" --model ${precinctModel} --connection-string "${connectionString}" --json`;
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

async function showDiff(document, proposedQuery) {
    const originalQuery = document.getText();
    const changes = diff.diffLines(originalQuery, proposedQuery);
    const formattedDiff = changes.map(change => {
        return (change.added ? '+ ' : '- ') + change.value;
    }).join('\n');
    const diffUri = vscode.Uri.file(path.join(venvPath, 'diff.sql'));
    await fs.writeFile(diffUri.fsPath, formattedDiff);
    vscode.commands.executeCommand('vscode.diff', document.uri, diffUri, 'Original ↔ Proposed');
}

function deactivate() {
    return fs.rmdir(venvPath, { recursive: true, force: true });
}

exports.activate = activate;
exports.deactivate = deactivate;
