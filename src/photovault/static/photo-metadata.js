/**
 * Merge freshly fetched photo metadata into the current photo list.
 *
 * The server enriches photos (EXIF date, location, Live Photo data) in the
 * background, so later fetches carry fields the first fetch lacked. This
 * overlays those fields by filename while preserving the current order.
 *
 * @param currentPhotos Photos currently in slideshow order
 * @param incomingPhotos Photos from the latest /photos response
 * @returns New array in the current order with merged metadata
 */
function mergePhotoMetadata(currentPhotos, incomingPhotos) {
    const incomingByName = new Map();
    incomingPhotos.forEach(photo => incomingByName.set(photo.filename, photo));

    const merged = currentPhotos.map(photo => {
        const incoming = incomingByName.get(photo.filename);
        return incoming ? Object.assign({}, photo, incoming) : photo;
    });

    return merged;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { mergePhotoMetadata };
}
