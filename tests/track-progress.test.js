const test = require('node:test');
const assert = require('node:assert');

const { interpolateTrackProgress } = require('../src/photovault/static/track-progress.js');

test('advances progress by elapsed time', () => {
    assert.strictEqual(interpolateTrackProgress(10000, 2500, 180000), 12500);
});

test('clamps progress at track duration', () => {
    assert.strictEqual(interpolateTrackProgress(179000, 5000, 180000), 180000);
});

test('returns zero for zero duration', () => {
    assert.strictEqual(interpolateTrackProgress(0, 5000, 0), 0);
});

test('never returns a negative value', () => {
    assert.strictEqual(interpolateTrackProgress(-100, 0, 180000), 0);
});
