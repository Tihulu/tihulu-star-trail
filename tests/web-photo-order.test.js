const assert = require("node:assert/strict");
const {reorderEntries} = require("../docs/photo-order.js");

const files = ["01.jpg", "02.jpg", "03.jpg", "04.jpg"];
const scores = [0.1, 0.2, 0.3, 0.4];
const keyFor = (file) => file;

const single = reorderEntries(files, scores, ["01.jpg"], 3, true, keyFor);
assert.equal(single.changed, true);
assert.deepEqual(single.files, ["02.jpg", "03.jpg", "04.jpg", "01.jpg"]);
assert.deepEqual(single.scores, [0.2, 0.3, 0.4, 0.1]);

const block = reorderEntries(files, scores, ["02.jpg", "03.jpg"], 0, false, keyFor);
assert.equal(block.changed, true);
assert.deepEqual(block.files, ["02.jpg", "03.jpg", "01.jpg", "04.jpg"]);
assert.deepEqual(block.scores, [0.2, 0.3, 0.1, 0.4]);

const selectedTarget = reorderEntries(files, scores, ["02.jpg", "03.jpg"], 2, true, keyFor);
assert.equal(selectedTarget.changed, false);
assert.deepEqual(selectedTarget.files, files);

const unchanged = reorderEntries(files, scores, ["01.jpg"], 1, false, keyFor);
assert.equal(unchanged.changed, false);
assert.deepEqual(unchanged.files, files);

console.log("web photo order tests passed");
