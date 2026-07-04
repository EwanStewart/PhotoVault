/**
 * Slideshow queue ordering.
 *
 * Photos synced in the last week get a weighted boost so they appear
 * early in the shuffle, and photos that arrive mid-session are inserted
 * right after the one on screen instead of waiting a full cycle.
 */

const RECENT_WINDOW_SECONDS = 7 * 24 * 60 * 60;
const RECENT_WEIGHT = 4;

/**
 * Weight for one photo: recent photos count more in the shuffle.
 *
 * @param photo Photo object with a modified timestamp in seconds
 * @param nowSeconds Current time in seconds
 * @returns Sampling weight for the photo
 */
function photoWeight(photo, nowSeconds) {
    const ageSeconds = nowSeconds - (photo.modified || 0);
    let weight = 1;
    if (ageSeconds < RECENT_WINDOW_SECONDS) {
        weight = RECENT_WEIGHT;
    }

    return weight;
}

/**
 * Shuffle photos with a bias towards recently modified ones.
 *
 * Uses weighted sampling without replacement (Efraimidis-Spirakis):
 * each photo draws a key of rng() ** (1 / weight) and the result sorts
 * by key descending, so heavier photos tend to land earlier.
 *
 * @param photos Photos to shuffle
 * @param nowSeconds Current time in seconds
 * @param rng Random source returning [0, 1), injectable for tests
 * @returns New array with all photos in weighted-shuffled order
 */
function weightedShuffle(photos, nowSeconds, rng = Math.random) {
    const keyed = photos.map(photo => ({
        photo,
        key: Math.pow(rng(), 1 / photoWeight(photo, nowSeconds))
    }));
    keyed.sort((a, b) => b.key - a.key);

    return keyed.map(entry => entry.photo);
}

/**
 * Shuffle an array in place using Fisher-Yates.
 *
 * @param array Array to shuffle
 * @param rng Random source returning [0, 1)
 * @returns The shuffled array
 */
function shuffleInPlace(array, rng) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }

    return array;
}

/**
 * Fold a fresh /photos response into the current slideshow queue.
 *
 * Surviving photos keep their queue order, deleted photos drop out,
 * and new photos slot in immediately after the one on screen so they
 * show on the next few slides.
 *
 * @param queue Photos in current slideshow order
 * @param incoming Photos from the latest /photos response
 * @param currentIndex Index of the photo on screen
 * @param rng Random source returning [0, 1), injectable for tests
 * @returns Object with the new photos array and adjusted currentIndex
 */
function insertNewPhotos(queue, incoming, currentIndex, rng = Math.random) {
    const incomingNames = new Set(incoming.map(p => p.filename));
    const queueNames = new Set(queue.map(p => p.filename));

    const surviving = queue.filter(p => incomingNames.has(p.filename));
    const survivorsBeforeCurrent = queue
        .slice(0, currentIndex)
        .filter(p => incomingNames.has(p.filename))
        .length;

    const fresh = shuffleInPlace(
        incoming.filter(p => !queueNames.has(p.filename)),
        rng
    );

    const insertAfter = Math.min(survivorsBeforeCurrent, Math.max(surviving.length - 1, 0));
    const photos = surviving
        .slice(0, insertAfter + 1)
        .concat(fresh, surviving.slice(insertAfter + 1));

    return {
        photos,
        currentIndex: Math.min(insertAfter, Math.max(photos.length - 1, 0))
    };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { weightedShuffle, insertNewPhotos };
}
