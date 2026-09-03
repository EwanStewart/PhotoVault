const test = require('node:test');
const assert = require('node:assert');

const {
    summarise, describePhoto, applyEnabled, setAllEnabled, removePhoto
} = require('../src/photovault/static/manage-library.js');

test('summarise counts the library, what is on, and the Live Photos', () => {
    const photos = [
        { filename: 'a.jpg', enabled: true },
        { filename: 'b.heic', enabled: false, isLivePhoto: true },
        { filename: 'c.heic', enabled: true, isLivePhoto: true }
    ];

    assert.deepStrictEqual(summarise(photos), { total: 3, enabled: 2, live: 2 });
});

test('describePhoto prefers the location and capture date', () => {
    const photo = {
        filename: 'a.heic',
        location: 'Angus, Scotland',
        date_taken: '2026-07-04T18:30:00'
    };

    assert.strictEqual(describePhoto(photo), 'Angus, Scotland - 4 July 2026');
});

test('describePhoto falls back to the filename when there is no metadata', () => {
    assert.strictEqual(describePhoto({ filename: 'sub/a.heic' }), 'a.heic');
});

test('describePhoto uses the date alone when the location is unknown', () => {
    const photo = { filename: 'a.heic', date_taken: '2026-01-09T08:00:00' };

    assert.strictEqual(describePhoto(photo), '9 January 2026');
});

test('applyEnabled updates one photo without touching the others', () => {
    const photos = [
        { filename: 'a.jpg', enabled: true },
        { filename: 'b.jpg', enabled: true }
    ];

    const updated = applyEnabled(photos, 'b.jpg', false);

    assert.deepStrictEqual(updated.map(p => p.enabled), [true, false]);
    assert.strictEqual(photos[1].enabled, true);
});

test('setAllEnabled returns only the photos that actually change', () => {
    const photos = [
        { filename: 'a.jpg', enabled: true },
        { filename: 'b.jpg', enabled: false }
    ];

    assert.deepStrictEqual(setAllEnabled(photos, true), ['b.jpg']);
    assert.deepStrictEqual(setAllEnabled(photos, false), ['a.jpg']);
});

test('removePhoto drops the photo from the list', () => {
    const photos = [{ filename: 'a.jpg' }, { filename: 'b.jpg' }];

    assert.deepStrictEqual(removePhoto(photos, 'a.jpg'), [{ filename: 'b.jpg' }]);
});
