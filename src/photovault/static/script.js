// Configuration
const SLIDE_INTERVAL = 30000; // 30 seconds per photo
const POLL_INTERVAL = 5000;   // Poll Spotify every 5 seconds
const OVERLAY_TIMEOUT = 10000; // Hide overlay after 10 seconds
const SKIP_DEBOUNCE = 1000;   // Debounce skip button
const DOUBLE_TAP_DELAY = 300;
const SWIPE_THRESHOLD = 30;
const HORIZONTAL_SWIPE_THRESHOLD = 50;  // Threshold to determine swipe direction

// Gesture zone percentages
const LEFT_ZONE_PERCENT = 0.125;   // Left 12.5% for brightness
const RIGHT_ZONE_PERCENT = 0.125;  // Right 12.5% for volume

// State management
const state = {
    photos: [],
    currentIndex: 0,
    currentPhoto: null,
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
    },
    bulbPanelVisible: false,
    bulbs: [],
    selectedBulbId: null,
    colourPresets: {}
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
let gestureDirectionDetermined = false;

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
const locationBadge = document.getElementById('location-badge');
const locationText = document.getElementById('location-text');
const locationFlag = document.getElementById('location-flag');
const dateBadge = document.getElementById('date-badge');
const liveIndicator = document.getElementById('live-indicator');
const liveVideo = document.getElementById('live-video');
const photoBg = document.getElementById('photo-bg');
const bulbPanel = document.getElementById('bulb-panel');
const bulbList = document.getElementById('bulb-list');
const bulbCloseBtn = document.getElementById('bulb-close-btn');
const bulbAllOnBtn = document.getElementById('bulb-all-on-btn');
const bulbAllOffBtn = document.getElementById('bulb-all-off-btn');
const colourPalette = document.getElementById('colour-palette');
const bulbTab = document.getElementById('bulb-tab');
const brightnessSlider = document.getElementById('brightness-slider');


// Preloaded image for next photo
let preloadedImage = null;

/**
 * Format EXIF date string to human-readable format.
 *
 * @param exifDate Date string in EXIF format (YYYY:MM:DD HH:MM:SS)
 * @returns Formatted date string or null if invalid
 */
function formatPhotoDate(exifDate) {
    let formattedDate = null;

    if (!exifDate) {
        return formattedDate;
    }

    try {
        // EXIF date format: "YYYY:MM:DD HH:MM:SS"
        const parts = exifDate.split(' ');
        const dateParts = parts[0].split(':');

        if (dateParts.length >= 3) {
            const year = parseInt(dateParts[0], 10);
            const month = parseInt(dateParts[1], 10) - 1;
            const day = parseInt(dateParts[2], 10);

            const date = new Date(year, month, day);

            // Format as "15 January 2024"
            formattedDate = date.toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'long',
                year: 'numeric'
            });
        }
    } catch (error) {
        console.error('Failed to parse date:', exifDate, error);
    }

    return formattedDate;
}

/**
 * Shuffle array in place using Fisher-Yates algorithm.
 *
 * @param array Array to shuffle
 * @returns The shuffled array
 */
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }

    return array;
}

/**
 * Preload the next photo in the slideshow.
 */
function preloadNextPhoto() {
    if (state.photos.length <= 1) {
        return;
    }

    const nextIndex = (state.currentIndex + 1) % state.photos.length;
    const nextPhoto = state.photos[nextIndex];
    const filename = typeof nextPhoto === 'string' ? nextPhoto : nextPhoto.filename;

    preloadedImage = new Image();
    preloadedImage.src = `/photos/${encodeURIComponent(filename)}`;
}

// Live Photo tracking
let longPressTimer = null;
let isLiveVideoPlaying = false;

// === Photo Management ===

async function loadPhotos() {
    try {
        showPhotoLoading(true);
        const response = await fetch('/photos');
        const data = await response.json();

        // Keep full photo objects with metadata
        state.photos = shuffleArray(data);

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
    if (state.photos.length === 0) {
        return;
    }

    const photo = state.photos[index];
    const filename = typeof photo === 'string' ? photo : photo.filename;
    const photoUrl = `/photos/${encodeURIComponent(filename)}`;

    const nextImg = photoCurrent.classList.contains('active') ? photoNext : photoCurrent;
    const currentImg = photoCurrent.classList.contains('active') ? photoCurrent : photoNext;

    showPhotoLoading(true);
    hidePhotoError();

    // Check if this image was preloaded
    let img;
    if (preloadedImage && preloadedImage.src.endsWith(encodeURIComponent(filename))) {
        img = preloadedImage;
        preloadedImage = null;
    } else {
        img = new Image();
        img.src = photoUrl;
    }

    img.onload = () => {
        nextImg.src = img.src;
        nextImg.classList.add('active');
        currentImg.classList.remove('active');
        showPhotoLoading(false);

        // Update blurred background
        if (photoBg) {
            photoBg.style.backgroundImage = `url('${img.src}')`;
        }

        // Update current photo and display info
        state.currentPhoto = photo;
        updatePhotoInfo(photo);

        // Preload next photo
        preloadNextPhoto();
    };

    img.onerror = () => {
        console.error('Failed to load photo:', filename);
        showPhotoLoading(false);
        // Try next photo
        state.currentIndex = (state.currentIndex + 1) % state.photos.length;
        if (state.photos.length > 1) {
            setTimeout(() => showPhoto(state.currentIndex), 100);
        } else {
            showPhotoError('Failed to load photo');
        }
    };

    // If we created a new image (not preloaded), we already set the src above
    // For preloaded images, if already loaded, onload may not fire, so check
    if (img.complete && img.naturalWidth > 0) {
        img.onload();
    }
}
function updatePhotoInfo(photo) {

    // Update location badge
    if (photo.location && locationBadge && locationText) {
        locationText.textContent = photo.location;
        if (locationFlag) {
            if (photo.country_code) {
                locationFlag.src = '/flags/' + photo.country_code + '.svg';
                locationFlag.classList.add('visible');
            } else {
                locationFlag.classList.remove('visible');
            }
        }
        locationBadge.classList.add('visible');
    } else if (locationBadge) {
        locationBadge.classList.remove('visible');
        if (locationFlag) {
            locationFlag.classList.remove('visible');
        }
    }


    // Update date badge
    if (photo.date_taken && dateBadge) {
        const dateStr = formatPhotoDate(photo.date_taken);
        if (dateStr) {
            dateBadge.textContent = dateStr;
            dateBadge.classList.add('visible');
        } else {
            dateBadge.classList.remove('visible');
        }
    } else if (dateBadge) {
        dateBadge.classList.remove('visible');
    }

    // Update Live Photo indicator
    if (liveIndicator) {
        liveIndicator.classList.toggle('visible', !!photo.isLivePhoto);
    }
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

            // Show overlay while music is playing
            overlay.classList.remove('hidden');
            state.overlayVisible = true;
            clearOverlayTimer();
        } else {
            state.isPlaying = false;
            state.isPaused = false;
            trackName.textContent = 'Not Playing';
            trackArtist.textContent = '';
            albumArt.style.display = 'none';
            updateProgressBar(0, 0);

            // Hide overlay when nothing is playing
            overlay.classList.add('hidden');
            state.overlayVisible = false;
            hideQueue();
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
    if (state.isPlaying) {
        // When playing, tap toggles queue instead of hiding the overlay
        toggleQueue();
        return;
    }

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

function resetOverlayTimer() {
    if (state.isPlaying) {
        return;
    }

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

// === Live Photo Playback ===

function playLiveVideo(photo) {
    if (!liveVideo || !photo.videoFilename) return;

    isLiveVideoPlaying = true;
    liveVideo.src = `/photos/video/${encodeURIComponent(photo.videoFilename)}`;
    liveVideo.currentTime = 0;
    liveVideo.play();
    liveVideo.classList.add('playing');

    // Stop when video ends
    liveVideo.onended = () => {
        stopLiveVideo();
    };
}

function stopLiveVideo() {
    if (!liveVideo) return;

    isLiveVideoPlaying = false;
    liveVideo.pause();
    liveVideo.classList.remove('playing');
    liveVideo.src = '';
}

function handleLivePhotoPress(photo) {
    if (!photo || !photo.isLivePhoto) return;

    longPressTimer = setTimeout(() => {
        playLiveVideo(photo);
    }, 500); // 500ms hold to trigger
}

function handleLivePhotoRelease() {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
    if (isLiveVideoPlaying) {
        stopLiveVideo();
    }
}

// === Bulb Panel ===

function openBulbPanel() {
    if (!bulbPanel) return;

    state.bulbPanelVisible = true;
    bulbPanel.classList.add('visible');
    if (bulbTab) bulbTab.classList.add('hidden');
    loadBulbStates();
}

function closeBulbPanel() {
    if (!bulbPanel) return;

    state.bulbPanelVisible = false;
    state.selectedBulbId = null;
    bulbPanel.classList.remove('visible');
    if (bulbTab) bulbTab.classList.remove('hidden');

    // Clear colour swatch selection
    const swatches = document.querySelectorAll('.colour-swatch');
    swatches.forEach(swatch => swatch.classList.remove('selected'));
}

async function loadBulbStates() {
    if (!bulbList) return;

    bulbList.classList.add('loading');
    bulbList.innerHTML = '';

    try {
        const response = await fetch('/api/bulbs');
        const data = await response.json();

        if (data.error) {
            bulbList.innerHTML = `<div class="bulb-error">${escapeHtml(data.error)}</div>`;
        } else {
            state.bulbs = data.bulbs || [];
            state.colourPresets = data.presets || {};
            renderBulbList();

            // Sync brightness slider to selected or first on bulb
            if (brightnessSlider) {
                const target = state.selectedBulbId
                    ? state.bulbs.find(b => b.id === state.selectedBulbId)
                    : state.bulbs.find(b => b.connected && b.is_on);
                if (target && target.brightness !== undefined) {
                    brightnessSlider.value = target.brightness;
                }
            }
        }
    } catch (error) {
        console.error('Failed to load bulb states:', error);
        bulbList.innerHTML = '<div class="bulb-error">Failed to load bulbs</div>';
    } finally {
        bulbList.classList.remove('loading');
    }
}

function renderBulbList() {
    if (!bulbList) return;

    bulbList.innerHTML = '';

    if (state.bulbs.length === 0) {
        bulbList.innerHTML = '<div class="bulb-empty">No bulbs configured</div>';
        return;
    }

    state.bulbs.forEach(bulb => {
        const card = createBulbCard(bulb);
        bulbList.appendChild(card);
    });
}

function createBulbCard(bulb) {
    const card = document.createElement('div');
    card.className = 'bulb-card';
    card.dataset.bulbId = bulb.id;

    if (!bulb.connected) {
        card.classList.add('disconnected');
    }

    if (state.selectedBulbId === bulb.id) {
        card.classList.add('selected');
    }

    const statusDotClass = bulb.connected ? 'connected' : 'disconnected';
    const statusText = bulb.connected ? (bulb.is_on ? 'On' : 'Off') : 'Disconnected';
    const toggleClass = bulb.is_on ? 'on' : '';
    const colourStyle = getColourStyle(bulb);

    let cardContent = `
        <div class="bulb-status-dot ${statusDotClass}"></div>
        <div class="bulb-info">
            <div class="bulb-name">${escapeHtml(bulb.name || 'Bulb ' + bulb.id)}</div>
            <div class="bulb-status-text">${statusText}</div>
        </div>
    `;

    if (bulb.connected) {
        cardContent += `
            <button class="bulb-colour-btn" style="${colourStyle}"
                    data-bulb-id="${bulb.id}"
                    title="Select for colour change"
                    aria-label="Select bulb for colour change"></button>
            <button class="bulb-toggle ${toggleClass}"
                    data-bulb-id="${bulb.id}"
                    aria-label="${bulb.is_on ? 'Turn off' : 'Turn on'}"></button>
        `;
    } else {
        cardContent += `
            <button class="bulb-retry-btn" data-bulb-id="${bulb.id}">Retry</button>
        `;
    }

    card.innerHTML = cardContent;

    // Add event listeners
    const toggle = card.querySelector('.bulb-toggle');
    if (toggle) {
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBulb(bulb.id, !bulb.is_on);
        });
    }

    const colourBtn = card.querySelector('.bulb-colour-btn');
    if (colourBtn) {
        colourBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            selectBulbForColour(bulb.id);
        });
    }

    const retryBtn = card.querySelector('.bulb-retry-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            reconnectBulb(bulb.id);
        });
    }

    return card;
}

function getColourStyle(bulb) {
    if (!bulb.connected || bulb.hue === undefined) {
        return 'background: #888;';
    }

    const hue = bulb.hue || 0;
    const saturation = bulb.saturation || 100;
    const lightness = Math.min(50 + (bulb.brightness || 100) / 4, 75);

    return `background: hsl(${hue}, ${saturation}%, ${lightness}%);`;
}

function selectBulbForColour(bulbId) {
    // Toggle selection
    if (state.selectedBulbId === bulbId) {
        state.selectedBulbId = null;
    } else {
        state.selectedBulbId = bulbId;
    }

    // Update card selection state
    const cards = document.querySelectorAll('.bulb-card');
    cards.forEach(card => {
        card.classList.toggle('selected', card.dataset.bulbId === state.selectedBulbId);
    });
}

async function toggleBulb(bulbId, powerOn) {
    // Optimistic update
    const bulb = state.bulbs.find(b => b.id === bulbId);
    if (bulb) {
        bulb.is_on = powerOn;
        renderBulbList();
    }

    try {
        const response = await fetch(`/api/bulbs/${bulbId}/power`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ power: powerOn })
        });

        const result = await response.json();

        if (!result.success) {
            // Revert on failure
            if (bulb) {
                bulb.is_on = !powerOn;
            }
            console.error('Failed to toggle bulb:', result.error);
        }

        // Refresh actual state
        await loadBulbStates();
    } catch (error) {
        console.error('Failed to toggle bulb:', error);
        // Revert on failure
        if (bulb) {
            bulb.is_on = !powerOn;
            renderBulbList();
        }
    }
}

async function setAllBulbsPower(powerOn) {
    // Disable buttons during operation
    if (bulbAllOnBtn) bulbAllOnBtn.disabled = true;
    if (bulbAllOffBtn) bulbAllOffBtn.disabled = true;

    try {
        const response = await fetch('/api/bulbs/all/power', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ power: powerOn })
        });

        const result = await response.json();

        if (result.success_count < result.total_count) {
            console.warn(`Bulk power: ${result.success_count}/${result.total_count} succeeded`);
        }

        // Refresh state
        await loadBulbStates();
    } catch (error) {
        console.error('Failed to set all bulbs power:', error);
    } finally {
        if (bulbAllOnBtn) bulbAllOnBtn.disabled = false;
        if (bulbAllOffBtn) bulbAllOffBtn.disabled = false;
    }
}

async function setBulbColour(presetName) {
    const targetBulbId = state.selectedBulbId;

    try {
        let url = '';

        if (targetBulbId) {
            // Set colour for selected bulb only
            url = `/api/bulbs/${targetBulbId}/colour`;
        } else {
            // Set colour for all bulbs
            url = '/api/bulbs/all/colour';
        }

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset: presetName })
        });

        const result = await response.json();

        if (!result.success && !result.success_count) {
            console.error('Failed to set colour:', result.error);
        }

        // Refresh state
        await loadBulbStates();
    } catch (error) {
        console.error('Failed to set bulb colour:', error);
    }
}

async function setBulbBrightness(brightness) {
    const targetBulbId = state.selectedBulbId;

    try {
        const url = targetBulbId
            ? `/api/bulbs/${targetBulbId}/brightness`
            : '/api/bulbs/all/brightness';

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brightness })
        });

        const result = await response.json();

        if (!result.success && !result.success_count) {
            console.error('Failed to set bulb brightness:', result.error);
        }

        await loadBulbStates();
    } catch (error) {
        console.error('Failed to set bulb brightness:', error);
    }
}

async function reconnectBulb(bulbId) {
    // Show loading state on the retry button
    const retryBtn = document.querySelector(`.bulb-retry-btn[data-bulb-id="${bulbId}"]`);
    if (retryBtn) {
        retryBtn.textContent = 'Connecting';
        retryBtn.disabled = true;
    }

    try {
        const response = await fetch(`/api/bulbs/${bulbId}/reconnect`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!result.success) {
            console.error(`Failed to reconnect bulb ${bulbId}:`, result.error);
        }

        // Refresh state
        await loadBulbStates();
    } catch (error) {
        console.error('Failed to reconnect bulb:', error);
        if (retryBtn) {
            retryBtn.textContent = 'Retry';
            retryBtn.disabled = false;
        }
    }
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
    gestureDirectionDetermined = false;

    const zone = getGestureZone(touchStartX);

    if (zone === 'brightness') {
        activeGesture = 'brightness';
        gestureStartValue = state.currentBrightness;
        showIndicator(brightnessIndicator, state.currentBrightness / 255 * 100);
    } else if (zone === 'volume') {
        // For right edge, we need to determine direction first
        // Start as potential volume gesture, may switch to panel swipe
        activeGesture = 'volume_or_panel';
        gestureStartValue = state.currentVolume;
    } else {
        activeGesture = null;
        // Start Live Photo long-press detection in center zone
        if (state.currentPhoto && state.currentPhoto.isLivePhoto) {
            handleLivePhotoPress(state.currentPhoto);
        }
    }
}

function handleTouchMove(e) {
    if (!activeGesture) return;

    const touch = e.touches[0];
    const deltaX = touchStartX - touch.clientX; // Positive = swipe left
    const deltaY = touchStartY - touch.clientY; // Positive = swipe up

    // Prevent default to avoid scrolling
    e.preventDefault();

    // For right edge, determine gesture direction after threshold
    if (activeGesture === 'volume_or_panel' && !gestureDirectionDetermined) {
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);

        if (absX >= HORIZONTAL_SWIPE_THRESHOLD || absY >= HORIZONTAL_SWIPE_THRESHOLD) {
            gestureDirectionDetermined = true;

            if (absX > absY && deltaX > 0) {
                // Horizontal swipe left from right edge - open bulb panel
                activeGesture = 'panel_swipe';
                openBulbPanel();
            } else {
                // Vertical swipe - volume control
                activeGesture = 'volume';
                showIndicator(volumeIndicator, state.currentVolume);
            }
        }
        return;
    }

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

    // Handle Live Photo release
    handleLivePhotoRelease();

    // Check for double tap (only in center zone)
    if (!activeGesture && touchDuration < 300 && !isLiveVideoPlaying) {
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
    } else if (activeGesture === 'volume_or_panel' && !gestureDirectionDetermined) {
        // Quick tap in right zone without direction determined
        hideIndicator(volumeIndicator);
    }

    activeGesture = null;
    gestureDirectionDetermined = false;
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

// Bulb tab event listener
if (bulbTab) {
    bulbTab.addEventListener('click', (e) => {
        e.stopPropagation();
        openBulbPanel();
    });

    bulbTab.addEventListener('touchend', (e) => {
        e.stopPropagation();
    });
}

// Bulb brightness slider event listener
if (brightnessSlider) {
    let bulbBrightnessTimeout = null;

    brightnessSlider.addEventListener('input', (e) => {
        e.stopPropagation();
        const brightness = parseInt(e.target.value, 10);

        if (bulbBrightnessTimeout) clearTimeout(bulbBrightnessTimeout);
        bulbBrightnessTimeout = setTimeout(() => {
            setBulbBrightness(brightness);
        }, 100);
    });

    brightnessSlider.addEventListener('touchstart', (e) => {
        e.stopPropagation();
    });

    brightnessSlider.addEventListener('touchmove', (e) => {
        e.stopPropagation();
    });
}

// Bulb panel event listeners
if (bulbCloseBtn) {
    bulbCloseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeBulbPanel();
    });
}

if (bulbAllOnBtn) {
    bulbAllOnBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setAllBulbsPower(true);
    });
}

if (bulbAllOffBtn) {
    bulbAllOffBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setAllBulbsPower(false);
    });
}

// Colour swatch event listeners
if (colourPalette) {
    const swatches = colourPalette.querySelectorAll('.colour-swatch');
    swatches.forEach(swatch => {
        swatch.addEventListener('click', (e) => {
            e.stopPropagation();
            const presetName = swatch.dataset.preset;
            if (presetName) {
                // Update selection visual
                swatches.forEach(s => s.classList.remove('selected'));
                swatch.classList.add('selected');
                setBulbColour(presetName);
            }
        });
    });
}

// Prevent bulb panel clicks from closing or propagating
if (bulbPanel) {
    bulbPanel.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    bulbPanel.addEventListener('touchend', (e) => {
        e.stopPropagation();
    });

    // Handle swipe right to close panel
    let panelTouchStartX = 0;
    bulbPanel.addEventListener('touchstart', (e) => {
        panelTouchStartX = e.touches[0].clientX;
    }, { passive: true });

    bulbPanel.addEventListener('touchend', (e) => {
        if (e.changedTouches && e.changedTouches[0]) {
            const deltaX = e.changedTouches[0].clientX - panelTouchStartX;
            // Swipe right to close
            if (deltaX > 50) {
                closeBulbPanel();
            }
        }
    }, { passive: true });
}

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

}

init();
