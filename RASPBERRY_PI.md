# Hackflix on Raspberry Pi 5 — Deployment Manual

A practical guide for running Hackflix as a set-top-box-style app on a Pi 5: auto-start on boot, render reliably to a TV, and set up the data directory.

Assumes Raspberry Pi OS Bookworm (64-bit) with the desktop environment installed. The default user is `pi`; substitute your username everywhere if different.

---

## 1. Make the Pi Render to the TV

The Pi 5 has **two micro-HDMI ports**. Use **HDMI0** — the one **closest to the USB-C power port**. HDMI1 is secondary and is not used by the kernel framebuffer at boot.

### Common failure modes

- **Black screen if the TV is off when the Pi boots.** The Pi reads EDID at boot; if no display is connected, it falls back to a tiny default mode (or no output at all), and many TVs won't sync when the cable is plugged in later.
- **Wrong resolution / overscan / cropped UI.** TV reports an EDID mode the kernel picks badly.
- **No sound over HDMI.** HDMI is configured in DVI mode rather than HDMI mode.

### Fix: `/boot/firmware/config.txt`

On Bookworm the boot config lives in **`/boot/firmware/config.txt`** (not `/boot/config.txt`). Edit it:

```bash
sudo nano /boot/firmware/config.txt
```

Add (or uncomment) under the `[all]` section:

```ini
# Always output HDMI even if no display is detected at boot
hdmi_force_hotplug:0=1

# Force HDMI (audio) mode rather than DVI
hdmi_drive:0=2

# Force a known-good mode if EDID negotiation is unreliable.
# 1080p60 — uncomment if the TV picks the wrong mode on its own.
# hdmi_group:0=1
# hdmi_mode:0=16

# Disable overscan if the image is cropped
disable_overscan=1
```

The `:0` suffix targets HDMI0. Reboot after editing.

If the TV is 4K or has an unusual native mode, plug in via SSH and run `kmsprint` or `tvservice -m CEA` to list supported modes, then pin one with `hdmi_mode:0=<n>`.

### Confirm the desktop session actually started

Hackflix is a Qt GUI app — it needs a running graphical session.

```bash
# Auto-login to desktop so a session always exists at boot
sudo raspi-config
# → System Options → Boot / Auto Login → Desktop Autologin
```

Pi OS Bookworm uses **Wayland (labwc / Wayfire)** by default. PyQt6 + VLC work on Wayland via XWayland. If you hit rendering glitches, switch the session to X11 in `raspi-config → Advanced Options → Wayland → X11`.

### TV always on first

If the TV/AVR is powered off at Pi boot, even with `hdmi_force_hotplug` set the desktop compositor may still come up with no monitor attached. Easiest fix: **leave the TV on** and let it stay in standby — HDMI hotplug from standby is reliable.

---

## 2. Set Up the Data Directory

Hackflix downloads media to `MEDIA_LIBRARY_PATH` (default `/mnt/usb_storage/hackflix-library`). Movies are large — **use an external USB SSD/HDD**, not the SD card.

### Mount the USB drive at boot

Plug in the drive and identify it:

```bash
lsblk -f
```

Note the partition (e.g. `sda1`) and its UUID. Format as ext4 if it's not already (this **erases the drive**):

```bash
sudo mkfs.ext4 -L hackflix /dev/sda1
```

Create the mount point and add it to `/etc/fstab` so it mounts on boot:

```bash
sudo mkdir -p /mnt/usb_storage
sudo blkid /dev/sda1   # copy the UUID
sudo nano /etc/fstab
```

Append (replace `<UUID>`):

```
UUID=<UUID>  /mnt/usb_storage  ext4  defaults,nofail,x-systemd.device-timeout=10  0  2
```

`nofail` is important — without it, the Pi refuses to boot if the drive is missing.

```bash
sudo mount -a
sudo mkdir -p /mnt/usb_storage/hackflix-library
sudo chown -R pi:pi /mnt/usb_storage/hackflix-library
```

### Project directory

Clone the project somewhere stable in the user's home:

```bash
cd ~
git clone <repo-url> hackflix
cd hackflix
```

### System dependencies

```bash
sudo apt update
sudo apt install -y vlc ffmpeg python3-libtorrent
```

Install `uv` (the project uses it for dependencies):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# re-open shell or: source ~/.bashrc
```

Then in the project directory:

```bash
uv sync
```

### Environment variables — `.env`

Create `~/hackflix/.env` (loaded automatically by `python-dotenv`):

```ini
CATALOG_URL=https://example.com/content.json
GEMINI_API_KEY=...
OPENSUBTITLES_API_KEY=...

# Optional — defaults shown
MEDIA_LIBRARY_PATH=/mnt/usb_storage/hackflix-library
CONFIG_DIR=/home/pi/.config/hackflix
```

Lock down the file so other users can't read your API keys:

```bash
chmod 600 ~/hackflix/.env
```

Smoke-test before wiring up auto-start:

```bash
cd ~/hackflix
uv run python src/main.py
```

The app should come up fullscreen on the TV. If it doesn't, fix that **before** moving on — a broken auto-start service is much harder to debug than a broken interactive launch.

---

## 3. Auto-Start on Boot

The cleanest approach is a **systemd user service** that starts after the graphical session is up. This keeps the app tied to the desktop session (so it has a display, audio, and `XDG_RUNTIME_DIR`) while still being managed by systemd.

### Enable lingering (so user services start at boot, not at login)

```bash
sudo loginctl enable-linger pi
```

### Create the service file

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/hackflix.service
```

Paste:

```ini
[Unit]
Description=Hackflix
After=graphical-session.target network-online.target
Wants=graphical-session.target network-online.target

[Service]
Type=simple
WorkingDirectory=%h/hackflix
ExecStart=%h/.local/bin/uv run python src/main.py
Restart=on-failure
RestartSec=5
# Keep stdout/stderr in the journal; the app also logs to ~/.config/hackflix/logs/app.log
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

`%h` expands to the user's home directory. `default.target` for a user manager corresponds to the active graphical session, so the service starts once the desktop is up.

### Enable and start

```bash
systemctl --user daemon-reload
systemctl --user enable hackflix.service
systemctl --user start hackflix.service
```

### Check it

```bash
systemctl --user status hackflix.service
journalctl --user -u hackflix.service -f
```

Reboot to verify it really comes up on its own:

```bash
sudo reboot
```

### If the app starts but can't open a window

That means the user service ran before the Wayland/X11 session was ready, or the session env vars (`WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR`) weren't inherited. As a fallback, use the desktop's own autostart instead of systemd:

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/hackflix.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=Hackflix
Exec=/home/pi/.local/bin/uv run --directory /home/pi/hackflix python src/main.py
X-GNOME-Autostart-enabled=true
```

This is launched by the desktop session itself, so display env vars are guaranteed to be set. The trade-off: no systemd-style restart-on-failure.

---

## 4. Updating the App

```bash
cd ~/hackflix
git pull
uv sync
systemctl --user restart hackflix.service
```

## 5. Quick Diagnostics

| Symptom | First thing to check |
|---|---|
| Black screen at boot | TV powered on before Pi? `hdmi_force_hotplug:0=1` in `/boot/firmware/config.txt`? |
| Desktop loads but Hackflix doesn't | `journalctl --user -u hackflix.service -n 100` |
| App says missing env vars | `.env` in `~/hackflix/`, readable by `pi`, `WorkingDirectory` in service is correct |
| Downloads fail with permission error | `chown -R pi:pi /mnt/usb_storage/hackflix-library`, drive actually mounted (`mount \| grep usb_storage`) |
| No HDMI audio | `hdmi_drive:0=2` in config.txt; in VLC select the HDMI audio device |
| App crashes after a while | `~/.config/hackflix/logs/app.log` — daily-rotated, 7 days retained |
