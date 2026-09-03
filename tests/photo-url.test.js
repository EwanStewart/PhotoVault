const test = require('node:test');
const assert = require('node:assert');

const { photoUrl, liveVideoUrl, thumbUrl, managePhotoUrl } = require('../src/photovault/static/photo-url.js');

test('photoUrl encodes each segment but keeps folder slashes', () => {
    assert.strictEqual(
        photoUrl('Fife, Scotland/IMG_1.HEIC'),
        '/photos/Fife%2C%20Scotland/IMG_1.HEIC'
    );
});

test('photoUrl handles photos at the root', () => {
    assert.strictEqual(photoUrl('IMG_1.HEIC'), '/photos/IMG_1.HEIC');
});

test('liveVideoUrl uses the video route with the same encoding', () => {
    assert.strictEqual(
        liveVideoUrl('Fife, Scotland/clip.mov'),
        '/photos/video/Fife%2C%20Scotland/clip.mov'
    );
});

test('thumbUrl points at the preview route', () => {
    assert.strictEqual(thumbUrl('Fife, Scotland/IMG_1.HEIC'),
        '/photos/thumb/Fife%2C%20Scotland/IMG_1.HEIC');
});

test('managePhotoUrl points at the manage route for one photo', () => {
    assert.strictEqual(managePhotoUrl('Fife, Scotland/IMG_1.HEIC'),
        '/api/manage/photos/Fife%2C%20Scotland/IMG_1.HEIC');
});
