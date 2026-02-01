// Configuration
const SLIDE_INTERVAL = 30000; // 30 seconds per photo
const POLL_INTERVAL = 5000;   // Poll Spotify every 5 seconds
const OVERLAY_TIMEOUT = 10000; // Hide overlay after 10 seconds
const SKIP_DEBOUNCE = 1000;   // Debounce skip button
const DOUBLE_TAP_DELAY = 300;
const SWIPE_THRESHOLD = 30;

// Gesture zone percentages
const LEFT_ZONE_PERCENT = 0.125;   // Left 12.5% for brightness
const RIGHT_ZONE_PERCENT = 0.125;  // Right 12.5% for volume

// State management
const state = {
    photos: [],
    currentIndex: 0,
    overlayVisible: false,
    isPlaying: false,
    isPaused: false,
    currentBrightness: 128,
    currentVolume: 50,
    displayOn: true,
    currentTrackId: null,
    isTrackSaved: false,
    showQueue: false,
    theme: {
        accent_color: '#1DB954',
        overlay_opacity: 0.8
    }
};

// Timers
let overlayTimer = null;
let slideshowInterval = null;
let indicatorTimers = new Map();
let lastSkipTime = 0;
let lastTapTime = 0;

// Touch tracking
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;
let activeGesture = null;
let gestureStartValue = 0;

// DOM elements
const photoCurrent = document.getElementById('photo-current');
const photoNext = document.getElementById('photo-next');
const photoLoading = document.getElementById('photo-loading');
const photoError = document.getElementById('photo-error');
const overlay = document.getElementById('overlay');
const albumArt = document.getElementById('album-art');
const trackName = document.getElementById('track-name');
const trackArtist = document.getElementById('track-artist');
const progressBar = document.getElementById('progress-bar');
const progressFill = document.getElementById('progress-fill');
const skipBtn = document.getElementById('skip-btn');
const pauseBtn = document.getElementById('pause-btn');
const likeBtn = document.getElementById('like-btn');
const queueBtn = document.getElementById('queue-btn');
const queuePanel = document.getElementById('queue-panel');
const queueList = document.getElementById('queue-list');
const authPrompt = document.getElementById('auth-prompt');
const brightnessIndicator = document.getElementById('brightness-indicator');
const volumeIndicator = document.getElementById('volume-indicator');
const syncStatus = document.getElementById('sync-status');

// === Photo Management ===

async function loadPhotos() {
    try {
        showPhotoLoading(true);
        const response = await fetch('/photos');
        const data = await response.json();

        // Handle new API format (array of objects with filename)
        state.photos = data.map(p => typeof p === 'string' ? p : p.filename);

        if (state.photos.length > 0) {
            showPhoto(0);
            startSlideshow();
        } else {
            showPhotoError('No photos found. Add photos to Google Drive.');
        }
    } catch (error) {
        console.error('Failed to load photos:', error);
        showPhotoError('Failed to load photos');
    } finally {
        showPhotoLoading(false);
    }
}

function showPhotoLoading(show) {
    if (photoLoading) {
        photoLoading.classList.toggle('visible', show);
    }
}

function showPhotoError(message) {
    if (photoError) {
        photoError.textContent = message;
        photoError.classList.add('visible');
    }
}

function hidePhotoError() {
    if (photoError) {
        photoError.classList.remove('visible');
    }
}

function showPhoto(index) {
    if (state.photos.length === 0) return;

    const nextImg = photoCurrent.classList.contains('active') ? photoNext : photoCurrent;
    const currentImg = photoCurrent.classList.contains('active') ? photoCurrent : photoNext;

    showPhotoLoading(true);
    hidePhotoError();

    const img = new Image();
    img.onload = () => {
        nextImg.src = img.src;
        nextImg.classList.add('active');
        currentImg.classList.remove('active');
        showPhotoLoading(false);
    };
    img.onerror = () => {
        console.error('Failed to load photo:', state.photos[index]);
        showPhotoLoading(false);
        // Try next photo
        state.currentIndex = (state.currentIndex + 1) % state.photos.length;
        if (state.photos.length > 1) {
            setTimeout(() => showPhoto(state.currentIndex), 100);
        } else {
            showPhotoError('Failed to load photo');
        }
    };
    img.src = `/photos/${encodeURIComponent(state.photos[index])}`;
}

function startSlideshow() {
    // Clear existing interval to prevent memory leaks
    if (slideshowInterval) {
        clearInterval(slideshowInterval);
    }

    slideshowInterval = setInterval(() => {
        state.currentIndex = (state.currentIndex + 1) % state.photos.length;
        showPhoto(state.currentIndex);
    }, SLIDE_INTERVAL);
}

function stopSlideshow() {
    if (slideshowInterval) {
        clearInterval(slideshowInterval);
        slideshowInterval = null;
    }
}

// === Spotify Integration ===

async function pollNowPlaying() {
    try {
        const response = await fetch('/api/now-playing');
        const data = await response.json();

        if (data.error === 'not_authenticated') {
            authPrompt.classList.remove('hidden');
            return;
        }

        authPrompt.classList.add('hidden');

        if (data.playing) {
            state.isPlaying = true;
            state.isPaused = !data.is_playing;
            state.currentTrackId = data.track_id;
            state.isTrackSaved = data.is_saved || false;

            trackName.textContent = data.name;
            trackArtist.textContent = data.artist;

            if (data.album_art) {
                albumArt.src = data.album_art;
                albumArt.style.display = 'block';
            } else {
                albumArt.style.display = 'none';
            }

            // Update progress bar
            updateProgressBar(data.progress_ms, data.duration_ms);

            // Update pause button state
            updatePauseButton();

            // Update like button state
            updateLikeButton();
        } else {
            state.isPlaying = false;
            state.isPaused = false;
            trackName.textContent = 'Not Playing';
            trackArtist.textContent = '';
            albumArt.style.display = 'none';
            updateProgressBar(0, 0);
        }
    } catch (error) {
        console.error('Failed to poll now playing:', error);
    }
}

function updateProgressBar(progress, duration) {
    if (!progressFill || !duration) {
        if (progressFill) progressFill.style.width = '0%';
        return;
    }

    const percent = (progress / duration) * 100;
    progressFill.style.width = `${percent}%`;
}

function updatePauseButton() {
    if (!pauseBtn) return;
    pauseBtn.innerHTML = state.isPaused ? '&#x25B6;' : '&#x23F8;';
    pauseBtn.title = state.isPaused ? 'Play' : 'Pause';
}

function updateLikeButton() {
    if (!likeBtn) return;
    likeBtn.classList.toggle('saved', state.isTrackSaved);
    likeBtn.innerHTML = state.isTrackSaved ? '&#x2764;' : '&#x2661;';
    likeBtn.title = state.isTrackSaved ? 'Remove from Library' : 'Save to Library';
}

// === Overlay Controls ===

function toggleOverlay() {
    state.overlayVisible = !state.overlayVisible;

    if (state.overlayVisible) {
        overlay.classList.remove('hidden');
        resetOverlayTimer();
    } else {
        overlay.classList.add('hidden');
        clearOverlayTimer();
        hideQueue();
    }
}

function showOverlayTemporarily() {
    overlay.classList.remove('hidden');
    state.overlayVisible = true;
    resetOverlayTimer();
}

function resetOverlayTimer() {
    clearOverlayTimer();
    overlayTimer = setTimeout(() => {
        overlay.classList.add('hidden');
        state.overlayVisible = false;
        hideQueue();
    }, OVERLAY_TIMEOUT);
}

function clearOverlayTimer() {
    if (overlayTimer) {
        clearTimeout(overlayTimer);
        overlayTimer = null;
    }
}

// === Playback Controls ===

async function skipTrack(e) {
    if (e) e.stopPropagation();

    // Debounce
    const now = Date.now();
    if (now - lastSkipTime < SKIP_DEBOUNCE) return;
    lastSkipTime = now;

    resetOverlayTimer();

    try {
        await fetch('/api/skip', { method: 'POST' });
        // Poll after delay to allow Spotify to update
        setTimeout(pollNowPlaying, 500);
    } catch (error) {
        console.error('Failed to skip:', error);
    }
}

async function togglePlayback(e) {
    if (e) e.stopPropagation();
    resetOverlayTimer();

    const endpoint = state.isPaused ? '/api/resume' : '/api/pause';

    try {
        const response = await fetch(endpoint, { method: 'POST' });
        if (response.ok) {
            state.isPaused = !state.isPaused;
            updatePauseButton();
        }
    } catch (error) {
        console.error('Failed to toggle playback:', error);
    }
}

async function toggleLike(e) {
    if (e) e.stopPropagation();
    resetOverlayTimer();

    try {
        const response = await fetch('/api/like', { method: 'POST' });
        if (response.ok) {
            state.isTrackSaved = !state.isTrackSaved;
            updateLikeButton();
        }
    } catch (error) {
        console.error('Failed to toggle like:', error);
    }
}

// === Queue Panel ===

async function toggleQueue(e) {
    if (e) e.stopPropagation();
    resetOverlayTimer();

    state.showQueue = !state.showQueue;

    if (state.showQueue) {
        await loadQueue();
        queuePanel.classList.add('visible');
    } else {
        hideQueue();
    }
}

function hideQueue() {
    state.showQueue = false;
    if (queuePanel) queuePanel.classList.remove('visible');
}

async function loadQueue() {
    if (!queueList) return;

    try {
        const response = await fetch('/api/queue');
        const data = await response.json();

        queueList.innerHTML = '';

        if (data.tracks && data.tracks.length > 0) {
            data.tracks.forEach(track => {
                const item = document.createElement('div');
                item.className = 'queue-item';
                item.innerHTML = `
                    <img class="queue-art" src="${track.album_art || ''}" alt="">
                    <div class="queue-info">
                        <div class="queue-name">${escapeHtml(track.name)}</div>
                        <div class="queue-artist">${escapeHtml(track.artist)}</div>
                    </div>
                `;
                queueList.appendChild(item);
            });
        } else {
            queueList.innerHTML = '<div class="queue-empty">No upcoming tracks</div>';
        }
    } catch (error) {
        console.error('Failed to load queue:', error);
        queueList.innerHTML = '<div class="queue-empty">Failed to load queue</div>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// === Hardware Controls ===

async function loadHardwareState() {
    try {
        const [brightnessRes, volumeRes, displayRes] = await Promise.all([
            fetch('/api/brightness'),
            fetch('/api/volume'),
            fetch('/api/display')
        ]);

        const brightnessData = await brightnessRes.json();
        const volumeData = await volumeRes.json();
        const displayData = await displayRes.json();

        if (brightnessData.level !== undefined) state.currentBrightness = brightnessData.level;
        if (volumeData.level !== undefined) state.currentVolume = volumeData.level;
        if (displayData.state !== undefined) state.displayOn = displayData.state === 'on';
    } catch (error) {
        console.error('Failed to load hardware state:', error);
    }
}

async function setBrightness(level) {
    level = Math.max(0, Math.min(255, Math.round(level)));
    state.currentBrightness = level;
    updateIndicator(brightnessIndicator, level / 255 * 100);

    try {
        await fetch('/api/brightness', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level })
        });
    } catch (error) {
        console.error('Failed to set brightness:', error);
    }
}

async function setVolume(level) {
    level = Math.max(0, Math.min(100, Math.round(level)));
    state.currentVolume = level;
    updateIndicator(volumeIndicator, level);

    try {
        await fetch('/api/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level })
        });
    } catch (error) {
        console.error('Failed to set volume:', error);
    }
}

async function toggleDisplay() {
    state.displayOn = !state.displayOn;
    const displayState = state.displayOn ? 'on' : 'off';

    try {
        await fetch('/api/display', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: displayState })
        });
    } catch (error) {
        console.error('Failed to toggle display:', error);
    }
}

// === Adaptive Brightness ===

async function checkAutoBrightness() {
    try {
        const response = await fetch('/api/brightness/auto');
        const data = await response.json();

        // Only auto-adjust if difference is significant (>30)
        if (Math.abs(state.currentBrightness - data.recommended) > 30) {
            await setBrightness(data.recommended);
        }
    } catch (error) {
        console.error('Failed to check auto brightness:', error);
    }
}

// === Sync Status ===

async function loadSyncStatus() {
    if (!syncStatus) return;

    try {
        const response = await fetch('/api/sync-status');
        const data = await response.json();

        if (data.last_sync) {
            const date = new Date(data.last_sync);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            syncStatus.textContent = `Synced: ${timeStr}`;
            syncStatus.classList.add('visible');
        }
    } catch (error) {
        console.error('Failed to load sync status:', error);
    }
}

// === Theme ===

async function loadTheme() {
    try {
        const response = await fetch('/api/theme');
        const theme = await response.json();
        state.theme = theme;
        applyTheme(theme);
    } catch (error) {
        console.error('Failed to load theme:', error);
    }
}

function applyTheme(theme) {
    const root = document.documentElement;
    if (theme.accent_color) {
        root.style.setProperty('--accent-color', theme.accent_color);
    }
    if (theme.overlay_opacity) {
        root.style.setProperty('--overlay-opacity', theme.overlay_opacity);
    }
}

// === Gesture Indicators ===

function updateIndicator(indicator, percent) {
    if (!indicator) return;
    const fill = indicator.querySelector('.indicator-fill');
    if (fill) fill.style.height = percent + '%';
}

function showIndicator(indicator, percent) {
    if (!indicator) return;
    indicator.classList.add('visible');
    updateIndicator(indicator, percent);
}

function hideIndicator(indicator) {
    if (!indicator) return;

    // Clear existing timer for this indicator
    const existingTimer = indicatorTimers.get(indicator);
    if (existingTimer) clearTimeout(existingTimer);

    const timer = setTimeout(() => {
        indicator.classList.remove('visible');
        indicatorTimers.delete(indicator);
    }, 1000);

    indicatorTimers.set(indicator, timer);
}

// === Gesture Detection ===

function getGestureZone(x) {
    const screenWidth = window.innerWidth;
    const leftBoundary = screenWidth * LEFT_ZONE_PERCENT;
    const rightBoundary = screenWidth * (1 - RIGHT_ZONE_PERCENT);

    if (x <= leftBoundary) return 'brightness';
    if (x >= rightBoundary) return 'volume';
    return 'center';
}

function handleTouchStart(e) {
    const touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();

    const zone = getGestureZone(touchStartX);

    if (zone === 'brightness') {
        activeGesture = 'brightness';
        gestureStartValue = state.currentBrightness;
        showIndicator(brightnessIndicator, state.currentBrightness / 255 * 100);
    } else if (zone === 'volume') {
        activeGesture = 'volume';
        gestureStartValue = state.currentVolume;
        showIndicator(volumeIndicator, state.currentVolume);
    } else {
        activeGesture = null;
    }
}

function handleTouchMove(e) {
    if (!activeGesture) return;

    const touch = e.touches[0];
    const deltaY = touchStartY - touch.clientY; // Positive = swipe up

    // Prevent default to avoid scrolling
    e.preventDefault();

    // Calculate change: 200px swipe = full range
    const sensitivity = 200;

    if (activeGesture === 'brightness') {
        const change = (deltaY / sensitivity) * 255;
        const newValue = gestureStartValue + change;
        setBrightness(newValue);
    } else if (activeGesture === 'volume') {
        const change = (deltaY / sensitivity) * 100;
        const newValue = gestureStartValue + change;
        setVolume(newValue);
    }
}

function handleTouchEnd(e) {
    const touchEndTime = Date.now();
    const touchDuration = touchEndTime - touchStartTime;

    // Check for double tap (only in center zone)
    if (!activeGesture && touchDuration < 300) {
        if (touchEndTime - lastTapTime < DOUBLE_TAP_DELAY) {
            // Double tap detected
            toggleDisplay();
            lastTapTime = 0;
            return;
        }
        lastTapTime = touchEndTime;

        // Single tap in center - toggle overlay (wait to rule out double-tap)
        setTimeout(() => {
            // Only toggle if this was a single tap (lastTapTime still equals touchEndTime)
            if (lastTapTime === touchEndTime) {
                toggleOverlay();
                lastTapTime = 0;
            }
        }, DOUBLE_TAP_DELAY + 50);
    }

    // Hide indicators
    if (activeGesture === 'brightness') {
        hideIndicator(brightnessIndicator);
    } else if (activeGesture === 'volume') {
        hideIndicator(volumeIndicator);
    }

    activeGesture = null;
}

// === Event Listeners ===

document.body.addEventListener('touchstart', handleTouchStart, { passive: false });
document.body.addEventListener('touchmove', handleTouchMove, { passive: false });
document.body.addEventListener('touchend', handleTouchEnd, { passive: false });

// Mouse click for non-touch (fallback)
document.body.addEventListener('click', (e) => {
    // Only handle clicks that aren't from touch
    if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;

    const zone = getGestureZone(e.clientX);
    if (zone === 'center') {
        toggleOverlay();
    }
});

// Button event listeners
if (skipBtn) skipBtn.addEventListener('click', skipTrack);
if (pauseBtn) pauseBtn.addEventListener('click', togglePlayback);
if (likeBtn) likeBtn.addEventListener('click', toggleLike);
if (queueBtn) queueBtn.addEventListener('click', toggleQueue);

// Prevent overlay clicks from toggling
if (overlay) {
    overlay.addEventListener('click', (e) => {
        e.stopPropagation();
        resetOverlayTimer();
    });

    overlay.addEventListener('touchend', (e) => {
        e.stopPropagation();
        resetOverlayTimer();
    });
}

// === Initialization ===

async function init() {
    await loadTheme();
    await loadPhotos();
    await loadHardwareState();
    await loadSyncStatus();

    pollNowPlaying();

    // Set up polling intervals
    setInterval(pollNowPlaying, POLL_INTERVAL);
    setInterval(loadPhotos, 300000);  // Refresh photos every 5 minutes
    setInterval(loadSyncStatus, 60000);  // Check sync status every minute

    // Check auto-brightness every hour
    setInterval(checkAutoBrightness, 3600000);
    // Initial check after 5 seconds
    setTimeout(checkAutoBrightness, 5000);
}

init();
