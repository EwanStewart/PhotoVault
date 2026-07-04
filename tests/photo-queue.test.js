const test = require('node:test');
const assert = require('node:assert');

const { weightedShuffle, insertNewPhotos } = require('../src/photovault/static/photo-queue.js');

const DAY_SECONDS = 24 * 60 * 60;
const NOW = 1780000000;

function photo(filename, ageDays) {
    return { filename, modified: NOW - ageDays * DAY_SECONDS };
}

test('weightedShuffle returns a permutation of the input', () => {
    const photos = [photo('a.jpg', 1), photo('b.jpg', 30), photo('c.jpg', 100)];

    const shuffled = weightedShuffle(photos, NOW);

    assert.deepStrictEqual(
        shuffled.map(p => p.filename).sort(),
        ['a.jpg', 'b.jpg', 'c.jpg']
    );
});

test('weightedShuffle ranks recent photos first when rng is constant', () => {
    const photos = [
        photo('old1.jpg', 60),
        photo('new1.jpg', 1),
        photo('old2.jpg', 90),
        photo('new2.jpg', 3)
    ];

    const shuffled = weightedShuffle(photos, NOW, () => 0.5);

    assert.deepStrictEqual(
        shuffled.map(p => p.filename),
        ['new1.jpg', 'new2.jpg', 'old1.jpg', 'old2.jpg']
    );
});

test('weightedShuffle does not mutate the input array', () => {
    const photos = [photo('a.jpg', 1), photo('b.jpg', 30)];
    const original = photos.slice();

    weightedShuffle(photos, NOW, () => 0.5);

    assert.deepStrictEqual(photos, original);
});

test('insertNewPhotos places fresh photos right after the current one', () => {
    const queue = [photo('a.jpg', 30), photo('b.jpg', 30), photo('c.jpg', 30)];
    const incoming = queue.concat([photo('d.jpg', 0)]);

    const update = insertNewPhotos(queue, incoming, 0, () => 0);

    assert.deepStrictEqual(
        update.photos.map(p => p.filename),
        ['a.jpg', 'd.jpg', 'b.jpg', 'c.jpg']
    );
    assert.strictEqual(update.currentIndex, 0);
});

test('insertNewPhotos drops removed photos and keeps the index on the current photo', () => {
    const queue = [photo('a.jpg', 30), photo('b.jpg', 30), photo('c.jpg', 30)];
    const incoming = [photo('b.jpg', 30), photo('c.jpg', 30)];

    const update = insertNewPhotos(queue, incoming, 2, () => 0);

    assert.deepStrictEqual(update.photos.map(p => p.filename), ['b.jpg', 'c.jpg']);
    assert.strictEqual(update.currentIndex, 1);
    assert.strictEqual(update.photos[update.currentIndex].filename, 'c.jpg');
});

test('insertNewPhotos shuffles fresh photos with the provided rng', () => {
    const queue = [photo('a.jpg', 30)];
    const incoming = queue.concat([photo('d.jpg', 0), photo('e.jpg', 0)]);

    const update = insertNewPhotos(queue, incoming, 0, () => 0);

    assert.deepStrictEqual(
        update.photos.map(p => p.filename),
        ['a.jpg', 'e.jpg', 'd.jpg']
    );
});

test('insertNewPhotos clamps the index when every old photo was removed', () => {
    const queue = [photo('a.jpg', 30)];
    const incoming = [photo('b.jpg', 0)];

    const update = insertNewPhotos(queue, incoming, 0, () => 0);

    assert.deepStrictEqual(update.photos.map(p => p.filename), ['b.jpg']);
    assert.strictEqual(update.currentIndex, 0);
});

test('insertNewPhotos does not mutate its inputs', () => {
    const queue = [photo('a.jpg', 30)];
    const incoming = [photo('a.jpg', 30), photo('b.jpg', 0)];
    const queueCopy = queue.slice();
    const incomingCopy = incoming.map(p => Object.assign({}, p));

    insertNewPhotos(queue, incoming, 0, () => 0);

    assert.deepStrictEqual(queue, queueCopy);
    assert.deepStrictEqual(incoming, incomingCopy);
});
