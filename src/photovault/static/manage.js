/**
 * Manage page wiring.
 *
 * Signs in with the PIN, lists the library as a grid of previews, and
 * lets each photo be switched in or out of the slideshow or deleted from
 * Google Drive. Pure list handling lives in manage-library.js.
 */

const grid = document.getElementById('photo-grid');
const summary = document.getElementById('library-summary');
const status = document.getElementById('library-status');
const toast = document.getElementById('toast');
const signin = document.getElementById('signin');
const library = document.getElementById('library');
const signinForm = document.getElementById('signin-form');
const signinError = document.getElementById('signin-error');
const pinInput = document.getElementById('pin-input');

const TOAST_MILLISECONDS = 2600;

let photos = [];
let toastTimer = null;

/**
 * Show a short message at the foot of the screen.
 *
 * @param message Text to show
 * @param isError True to style the message as a failure
 */
function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle('error', isError);
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), TOAST_MILLISECONDS);
}

/**
 * Send a JSON request and raise on any error the server reports.
 *
 * @param url Endpoint to call
 * @param options Fetch options
 * @returns The parsed response body
 */
async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    let body = {};
    try {
        body = await response.json();
    } catch (e) {
        body = {};
    }
    if (!response.ok) {
        throw new Error(body.error || `Request failed (${response.status})`);
    }

    return body;
}

/**
 * Build the card for one photo.
 *
 * @param photo A photo from the manage listing
 * @returns The card element
 */
function buildCard(photo) {
    const card = document.createElement('div');
    card.className = 'photo-card';
    card.dataset.filename = photo.filename;
    card.classList.toggle('disabled', !photo.enabled);

    const image = document.createElement('img');
    image.loading = 'lazy';
    image.decoding = 'async';
    image.alt = describePhoto(photo);
    image.src = thumbUrl(photo.filename);
    card.appendChild(image);

    if (photo.isLivePhoto) {
        const badge = document.createElement('span');
        badge.className = 'live-badge';
        badge.textContent = 'Live';
        badge.title = 'Has its Live Photo clip';
        card.appendChild(badge);
    }

    const caption = document.createElement('div');
    caption.className = 'caption';
    caption.textContent = describePhoto(photo);
    card.appendChild(caption);

    const actions = document.createElement('div');
    actions.className = 'card-actions';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'toggle-btn';
    toggle.textContent = photo.enabled ? 'On' : 'Off';
    toggle.setAttribute('aria-pressed', photo.enabled ? 'true' : 'false');
    toggle.addEventListener('click', () => setEnabled(photo.filename, !photo.enabled));
    actions.appendChild(toggle);

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'delete-btn';
    remove.textContent = 'Delete';
    remove.addEventListener('click', () => confirmDelete(photo));
    actions.appendChild(remove);

    card.appendChild(actions);

    return card;
}

/**
 * Redraw the grid and the counts from the current list.
 */
function render() {
    const counts = summarise(photos);
    summary.textContent = `${counts.enabled} of ${counts.total} playing, ${counts.live} Live`;
    grid.replaceChildren(...photos.map(buildCard));
    status.textContent = counts.total ? '' : 'No photos yet.';
}

/**
 * Fetch the library and redraw.
 */
async function loadLibrary() {
    status.textContent = 'Loading library';
    try {
        photos = await requestJson('/api/manage/photos');
        render();
    } catch (e) {
        status.textContent = '';
        showToast(e.message, true);
    }
}

/**
 * Switch one photo in or out of the slideshow.
 *
 * @param filename Photos-relative path of the photo
 * @param enabled True to let the slideshow show it
 */
async function setEnabled(filename, enabled) {
    try {
        await requestJson(`${managePhotoUrl(filename)}/enabled`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        photos = applyEnabled(photos, filename, enabled);
        render();
    } catch (e) {
        showToast(e.message, true);
    }
}

/**
 * Apply one flag to the whole library, one request per photo that changes.
 *
 * @param enabled Flag to apply to every photo
 */
async function setAll(enabled) {
    const changing = setAllEnabled(photos, enabled);
    if (!changing.length) {
        showToast('Nothing to change');
    } else {
        status.textContent = `Updating ${changing.length} photos`;
        for (const filename of changing) {
            await setEnabled(filename, enabled);
        }
        status.textContent = '';
        showToast(`${changing.length} photos updated`);
    }
}

/**
 * Ask before deleting, then delete from Drive and from the Pi.
 *
 * @param photo The photo to delete
 */
async function confirmDelete(photo) {
    const name = (photo.filename || '').split('/').pop();
    const clip = photo.isLivePhoto ? ' and its Live Photo clip' : '';
    const message = `Delete ${name}${clip} from Google Drive? This cannot be undone.`;
    if (window.confirm(message)) {
        try {
            const result = await requestJson(managePhotoUrl(photo.filename), { method: 'DELETE' });
            photos = removePhoto(photos, photo.filename);
            render();
            showToast(`Deleted ${result.deleted.length} file(s)`);
        } catch (e) {
            showToast(e.message, true);
        }
    }
}

/**
 * Exchange the PIN for a session and reveal the library.
 *
 * @param event The form submit event
 */
async function signIn(event) {
    event.preventDefault();
    signinError.textContent = '';
    try {
        await requestJson('/api/manage/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pinInput.value })
        });
        pinInput.value = '';
        signin.classList.add('hidden');
        library.classList.remove('hidden');
        loadLibrary();
    } catch (e) {
        signinError.textContent = e.message;
    }
}

signinForm.addEventListener('submit', signIn);
document.getElementById('refresh-btn').addEventListener('click', loadLibrary);
document.getElementById('select-all-btn').addEventListener('click', () => setAll(true));
document.getElementById('select-none-btn').addEventListener('click', () => setAll(false));

if (document.body.dataset.signedIn === 'yes') {
    loadLibrary();
}
