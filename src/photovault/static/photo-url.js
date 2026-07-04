/**
 * URL builders for photo and Live Photo clip routes.
 *
 * Photos live in per-location subfolders, so each path segment is
 * encoded separately to keep the folder slashes routable.
 */

/**
 * Encode a photos-relative path segment by segment.
 *
 * @param path Photos-relative file path
 * @returns Encoded path with literal slashes between segments
 */
function encodePhotoPath(path) {
    return path.split('/').map(encodeURIComponent).join('/');
}

/**
 * URL that serves a photo.
 *
 * @param filename Photos-relative file path
 * @returns Route for the photo
 */
function photoUrl(filename) {
    return `/photos/${encodePhotoPath(filename)}`;
}

/**
 * URL that serves a Live Photo clip.
 *
 * @param filename Photos-relative video path
 * @returns Route for the clip
 */
function liveVideoUrl(filename) {
    return `/photos/video/${encodePhotoPath(filename)}`;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { photoUrl, liveVideoUrl };
}
