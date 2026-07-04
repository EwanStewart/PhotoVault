const test = require('node:test');
const assert = require('node:assert');

const { mergePhotoMetadata } = require('../src/photovault/static/photo-metadata.js');

test('merges enriched fields into existing photos by filename', () => {
    const current = [
        { filename: 'b.jpg', modified: 2 },
        { filename: 'a.heic', modified: 1 }
    ];
    const incoming = [
        { filename: 'a.heic', modified: 1, location: 'Oban, Scotland', country_code: 'gb-sct' },
        { filename: 'b.jpg', modified: 2, date_taken: '2024:01:15 12:00:00' }
    ];

    const merged = mergePhotoMetadata(current, incoming);

    assert.deepStrictEqual(merged.map(p => p.filename), ['b.jpg', 'a.heic']);
    assert.strictEqual(merged[0].date_taken, '2024:01:15 12:00:00');
    assert.strictEqual(merged[1].location, 'Oban, Scotland');
    assert.strictEqual(merged[1].country_code, 'gb-sct');
});

test('keeps photos unchanged when incoming has no match', () => {
    const current = [{ filename: 'a.jpg', modified: 1, location: 'Kept' }];

    const merged = mergePhotoMetadata(current, []);

    assert.deepStrictEqual(merged, [{ filename: 'a.jpg', modified: 1, location: 'Kept' }]);
});

test('does not mutate the current photo objects', () => {
    const original = { filename: 'a.jpg', modified: 1 };

    mergePhotoMetadata([original], [{ filename: 'a.jpg', modified: 1, location: 'New' }]);

    assert.strictEqual(original.location, undefined);
});
