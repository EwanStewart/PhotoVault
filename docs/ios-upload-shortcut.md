# Uploading from an iPhone

PhotoVault takes photos straight from your phone and puts them on Google
Drive alongside the ones already there. The next sync mirrors them onto
the Pi, so the frame picks them up on its own.

Two pieces do the work:

- An iOS Shortcut sends a photo, and its Live Photo clip, from the share sheet.
- A web page at `http://<pi-address>:5000/manage` curates the library.

## Why a Shortcut rather than a file picker

Safari cannot hand a Live Photo's video to a web page. Choosing a Live
Photo in the iOS photo picker gives the still image only, because iOS
never exposes the motion component to web JavaScript. A Shortcut runs
inside iOS, so it can read both halves and send them together.

## Setting up the Pi

Set two variables in `.env` on the Pi, then restart the app.

```bash
PHOTOVAULT_BIND_HOST=0.0.0.0
PHOTOVAULT_PIN=your_pin_here
```

`PHOTOVAULT_BIND_HOST` puts the app on your home network instead of the
loopback address alone. `PHOTOVAULT_PIN` guards every write. Pick
something longer than four digits, because it protects your photo
library and your lights.

Requests from the Pi itself skip the PIN, so the kiosk keeps working
untouched. Every request from the network needs the PIN, including the
existing brightness, volume and bulb controls.

Find the Pi's address with `hostname -I` on the Pi.

## Building the Shortcut

Open the Shortcuts app and create a new shortcut.

1. Rename it "Send to PhotoVault".
2. Open the shortcut details. Turn on **Show in Share Sheet**.
3. Set the accepted input types to **Images and Media** only.
4. Add **Repeat with Each**, and pass it the Shortcut Input.

Everything below goes inside the repeat block.

5. Add **Encode Media**. Pass it the Repeat Item. This returns the
   motion clip when the item is a Live Photo.
6. Add **Get Contents of URL**. Point it at
   `http://<pi-address>:5000/api/upload`.
7. Set the method to **POST**.
8. Add a header. Key `X-PhotoVault-Pin`, value your PIN.
9. Set Request Body to **Form**.
10. Add a form field. Key `photo`, type **File**, value the Repeat Item.
11. Add a second form field. Key `video`, type **File**, value the
    Encode Media output.

Run it once from the share sheet to check it. Photos then appear in the
manage page and on the frame.

### If Encode Media gives you trouble

Some iOS versions label the conversion differently. Look for the action
that turns a Live Photo into a video and use that instead. A shortcut
that sends the `photo` field alone still works, and the photo will
simply not animate on the frame.

You can also send a clip on its own. PhotoVault stores it and pairs it
with its still by comparing capture times, which is how it already
handles clips exported through **Save as Video**.

## The manage page

Open `http://<pi-address>:5000/manage` on your phone and enter the PIN.
Add it to your home screen for quicker access.

The page shows every photo in the library as a grid of previews. Each
card carries two buttons:

- **On** and **Off** decide whether the slideshow shows that photo. A
  photo switched off stays on Drive and can be switched back on later.
- **Delete** removes the photo from Google Drive for good, along with
  its Live Photo clip. This cannot be undone.

"All on" and "All off" apply one setting to the whole library. A "Live"
badge marks a photo whose clip PhotoVault has found and paired.

The on and off flags live in `photo_prefs.json` on the Pi. They key on
each file's name rather than its path, so a flag survives the move into
a location folder that enrichment triggers.

## How an upload travels

1. The Shortcut posts the still, and the clip when there is one.
2. PhotoVault names the clip after the still, which makes the two halves
   pair without relying on capture times.
3. Both files go to Google Drive first. Only then does PhotoVault place
   them in the local photos directory.
4. The sync watcher sees the new files on Drive and keeps the local
   copies.

The Drive push comes first on purpose. The sync mirrors Drive onto the
Pi and deletes anything local that Drive does not hold, so a file placed
locally first would vanish on the next sync.
