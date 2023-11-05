const path = require('path');
const Mocha = require('mocha');
const {glob} = require("glob")

function run(callback) {
	const mocha = new Mocha({
		ui: 'tdd',
		color: true,
	});

	const testsRoot = path.resolve(__dirname, '..');

	// Use the callback version of glob here.
	glob('**/*.test.js', { cwd: testsRoot }, (err, files) => {
		if (err) {
			console.error('Error finding test files:', err);
			return callback(err);
		}

		files.forEach((file) => {
			mocha.addFile(path.resolve(testsRoot, file));
		});

		// Run the Mocha test suite and pass results to callback
		mocha.run((failures) => {
			if (failures > 0) {
				callback(new Error(`${failures} tests failed.`));
			} else {
				callback(null); // null is typically used to signify "no error" in callback patterns
			}
		});
	});
}

module.exports = {
	run
};
