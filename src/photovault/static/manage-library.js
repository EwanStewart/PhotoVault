/**
 * Library state for the manage page.
 *
 * The page holds one list of photos fetched from /api/manage/photos.
 * These helpers summarise that list, label each photo for the grid, and
 * return updated copies as the user switches photos on and off, so the
 * rendering code never mutates the list it is drawing from.
 */

/**
 * Count the library, the photos left on, and the Live Photos.
 *
 * @param photos Photos from the manage listing
 * @returns Object holding the total, enabled and live counts
 */
function summarise(photos) {
    return {
        total: photos.length,
        enabled: photos.filter(photo => photo.enabled).length,
        live: photos.filter(photo => photo.isLivePhoto).length
    };
}

/**
 * Format a capture date the way the badge on the frame does.
 *
 * @param dateTaken Capture timestamp as sent by the server
 * @returns The date in day, month, year form, or an empty string
 */
function formatDate(dateTaken) {
    let text = '';
    const parsed = dateTaken ? new Date(dateTaken) : null;
    if (parsed && !Number.isNaN(parsed.getTime())) {
        text = parsed.toLocaleDateString('en-GB', {
            day: 'numeric', month: 'long', year: 'numeric'
        });
    }

    return text;
}

/**
 * Caption for one photo in the grid.
 *
 * @param photo A photo from the manage listing
 * @returns Location and date where known, else the bare filename
 */
function describePhoto(photo) {
    const parts = [photo.location, formatDate(photo.date_taken)].filter(Boolean);
    const fallback = (photo.filename || '').split('/').pop();

    return parts.length ? parts.join(' - ') : fallback;
}

/**
 * Copy of the list with one photo's flag changed.
 *
 * @param photos Photos from the manage listing
 * @param filename Photos-relative path of the photo to change
 * @param enabled New flag for that photo
 * @returns A new list holding the change
 */
function applyEnabled(photos, filename, enabled) {
    return photos.map(photo => (
        photo.filename === filename ? { ...photo, enabled } : photo
    ));
}

/**
 * Photos that would actually change if the whole library were set one way.
 *
 * @param photos Photos from the manage listing
 * @param enabled Flag to apply to every photo
 * @returns Filenames whose flag differs from the target
 */
function setAllEnabled(photos, enabled) {
    return photos
        .filter(photo => !!photo.enabled !== enabled)
        .map(photo => photo.filename);
}

/**
 * Copy of the list without one photo.
 *
 * @param photos Photos from the manage listing
 * @param filename Photos-relative path of the photo to drop
 * @returns A new list without that photo
 */
function removePhoto(photos, filename) {
    return photos.filter(photo => photo.filename !== filename);
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { summarise, describePhoto, applyEnabled, setAllEnabled, removePhoto };
}
