/**
 * Estimate current track progress between Spotify polls.
 *
 * The overlay polls Spotify every few seconds; interpolating locally keeps
 * the progress bar moving smoothly instead of jumping on each poll.
 *
 * @param baseMs Progress reported by the last poll, in milliseconds
 * @param elapsedMs Time elapsed since that poll, in milliseconds
 * @param durationMs Total track duration, in milliseconds
 * @returns Estimated progress clamped to the range [0, durationMs]
 */
function interpolateTrackProgress(baseMs, elapsedMs, durationMs) {
    return Math.max(0, Math.min(baseMs + elapsedMs, durationMs));
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { interpolateTrackProgress };
}
