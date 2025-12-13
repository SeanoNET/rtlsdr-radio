# RTL-SDR Chromecast Radio

Stream FM radio from an RTL-SDR dongle to Chromecast or Logitech Media Server (Squeezebox) speakers via a web interface.

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────┐     ┌────────────┐
│   Web Frontend  │────▶│        FastAPI Backend          │────▶│ Chromecast │
│     (React)     │     │                                 │     └────────────┘
└─────────────────┘     │  ┌───────────┐  ┌────────────┐  │     ┌────────────┐
                        │  │  rtl_fm   │─▶│  ffmpeg    │  │────▶│    LMS     │
                        │  │  process  │  │  transcoder│  │     │ Squeezebox │
                        │  └───────────┘  └────────────┘  │     └────────────┘
                        └─────────────────────────────────┘
```

## Quick Start (Docker)

```bash
# Clone and run with Docker
docker-compose up -d

# Frontend: http://localhost (port 80)
# Backend API: http://localhost:8000
```

See [Docker Deployment](#docker-deployment) for details.

## Supported Playback Targets

- **Chromecast** - Audio/video Chromecast devices, Google Home speakers
- **LMS/Squeezebox** - Logitech Media Server players (piCorePlayer, Squeezelite, hardware Squeezeboxes)
- **Home Assistant** - Custom integration with full media player support

## Prerequisites

### System Dependencies (Arch Linux)

```bash
# RTL-SDR tools
sudo pacman -S rtl-sdr

# FFmpeg for transcoding
sudo pacman -S ffmpeg

# Python 3.11+
sudo pacman -S python python-pip
```

### Verify RTL-SDR

```bash
# Check device is detected
rtl_test -t

# Test FM reception (Ctrl+C to stop)
rtl_fm -f 101.1M -M wbfm -s 200000 -r 48000 | aplay -r 48000 -f S16_LE
```

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server (default: LMS on localhost:9000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or with custom LMS server location
LMS_HOST=192.168.1.100 LMS_PORT=9000 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. 
API docs at `http://localhost:8000/docs`.

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend will be available at `http://localhost:5173`.

## Home Assistant Integration

RTL-SDR Radio includes a custom Home Assistant integration that provides a full media player entity.

### Features

- **Media Player Entity**: Full media player controls in Home Assistant
- **Play/Pause/Stop**: Control playback from HA or automations
- **Source Selection**: Station presets appear as selectable sources
- **Volume Control**: Adjust volume through Home Assistant
- **State Sync**: Real-time state updates (playing, paused, idle)
- **Attributes**: Frequency, modulation, device info exposed as attributes

### Installation via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add this repository URL: `https://github.com/YOUR_USERNAME/rtlsdr-radio`
4. Select category: **Integration**
5. Click **Add**
6. Search for "RTL-SDR Radio" and install
7. Restart Home Assistant
8. Go to **Settings → Devices & Services → Add Integration**
9. Search for "RTL-SDR Radio"
10. Enter your RTL-SDR Radio server host and port (default: 8000)

### Manual Installation

1. Copy the `custom_components/rtlsdr_radio` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for "RTL-SDR Radio"
5. Enter your RTL-SDR Radio server host and port

### Configuration

When adding the integration, you'll be prompted for:

| Field | Description |
|-------|-------------|
| Host | IP or hostname of the RTL-SDR Radio server |
| Port | API port (default: 8000) |

### Home Assistant Automations

Example automation to play a station:

```yaml
automation:
  - alias: "Play morning radio"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: media_player.select_source
        target:
          entity_id: media_player.rtlsdr_radio
        data:
          source: "Triple J"
```

Example automation to stop radio when leaving:

```yaml
automation:
  - alias: "Stop radio when leaving"
    trigger:
      - platform: state
        entity_id: person.you
        to: "not_home"
    action:
      - service: media_player.media_stop
        target:
          entity_id: media_player.rtlsdr_radio
```

### Entity Attributes

The media player entity exposes these attributes:

| Attribute | Description |
|-----------|-------------|
| `frequency` | Current FM frequency (MHz) |
| `modulation` | Modulation type (wfm) |
| `device_id` | Active speaker ID |
| `device_name` | Active speaker name |
| `device_type` | Speaker type (chromecast/lms) |
| `available_speakers` | List of available speakers |

### Music Assistant

Once the media player is in Home Assistant, it will also be accessible in Music Assistant as a playback target.

## API Reference

### Speakers (Unified)

The unified speakers API combines Chromecast and LMS players. Speaker IDs are prefixed with their type (e.g., `chromecast:abc123` or `lms:00:11:22:33:44:55`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/speakers` | GET | List all speakers (Chromecast + LMS) |
| `/api/speakers/refresh` | POST | Refresh all speaker sources |
| `/api/speakers/{id}` | GET | Get speaker details |
| `/api/speakers/{id}/volume` | GET | Get volume (0.0-1.0) |
| `/api/speakers/{id}/volume` | PUT | Set volume |
| `/api/speakers/{id}/mute` | POST | Toggle mute |
| `/api/speakers/{id}/power` | POST | Power on/off (LMS only) |

### Devices (Chromecast only - legacy)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices` | GET | List all Chromecast devices |
| `/api/devices/refresh` | POST | Refresh device discovery |
| `/api/devices/{id}` | GET | Get device details |
| `/api/devices/{id}/volume` | GET | Get volume (0.0-1.0) |
| `/api/devices/{id}/volume` | PUT | Set volume |
| `/api/devices/{id}/mute` | POST | Toggle mute |

### Stations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stations` | GET | List all station presets |
| `/api/stations` | POST | Create a new station |
| `/api/stations/{id}` | GET | Get station details |
| `/api/stations/{id}` | PUT | Update a station |
| `/api/stations/{id}` | DELETE | Delete a station |

### Tuner

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tuner/status` | GET | Get current tuner status |
| `/api/tuner/tune` | POST | Tune to frequency |
| `/api/tuner/stop` | POST | Stop the tuner |

### Playback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/playback/status` | GET | Get playback status |
| `/api/playback/start` | POST | Start playback to device |
| `/api/playback/stop` | POST | Stop playback |
| `/api/playback/pause` | POST | Pause playback |
| `/api/playback/resume` | POST | Resume playback |
| `/api/playback/tune` | POST | Change frequency while playing |

### Stream

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stream` | GET | Raw MP3 audio stream |

## Example API Usage

### List all speakers

```bash
curl http://localhost:8000/api/speakers
```

### Start playing on Chromecast

```bash
curl -X POST http://localhost:8000/api/playback/start \
  -H "Content-Type: application/json" \
  -d '{"device_id": "chromecast:abc123", "frequency": 101.1, "modulation": "wfm"}'
```

### Start playing on LMS/Squeezebox

```bash
curl -X POST http://localhost:8000/api/playback/start \
  -H "Content-Type: application/json" \
  -d '{"device_id": "lms:00:11:22:33:44:55", "station_id": "xyz789"}'
```

### Control volume

```bash
# Set volume to 50%
curl -X PUT http://localhost:8000/api/speakers/lms:00:11:22:33:44:55/volume \
  -H "Content-Type: application/json" \
  -d '{"volume": 0.5}'
```

### Power on LMS player

```bash
curl -X POST "http://localhost:8000/api/speakers/lms:00:11:22:33:44:55/power?power=true"
```

### Add a station preset

```bash
curl -X POST http://localhost:8000/api/stations \
  -H "Content-Type: application/json" \
  -d '{"name": "My Station", "frequency": 98.7, "modulation": "wfm"}'
```

## Docker Deployment

### Prerequisites

Ensure your RTL-SDR dongle is accessible without root:

```bash
# 1. Find your RTL-SDR's vendor and product ID
lsusb | grep -i rtl
# Example output: Bus 001 Device 004: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838UHIDIR
#                                        ^^^^:^^^^ <- these are your vendor:product IDs

# 2. Create udev rule (replace 0bda and 2838 with your IDs from step 1)
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"' | sudo tee /etc/udev/rules.d/99-rtlsdr.rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# 3. Verify device is detected (may need to unplug/replug dongle)
rtl_test -t
```

### Running with Docker Compose

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Configuration

Environment variables can be set in a `.env` file or passed directly:

| Variable | Default | Description |
|----------|---------|-------------|
| `LMS_HOST` | `localhost` | Logitech Media Server hostname |
| `LMS_PORT` | `9000` | LMS JSON-RPC port |
| `LMS_HTTPS` | `false` | Use HTTPS for LMS connection |
| `EXTERNAL_STREAM_URL` | _(none)_ | HTTPS URL for Chromecast streaming (required for Chromecast) |

Example `.env` file:
```
LMS_HOST=192.168.1.100
LMS_PORT=9000
LMS_HTTPS=false
EXTERNAL_STREAM_URL=https://radio-stream.example.com/stream.mp3
```

### Chromecast HTTPS Requirement

Chromecast devices require HTTPS URLs for media playback. To use Chromecast:

1. Set up a reverse proxy (Traefik, nginx, etc.) with SSL to proxy port 8089
2. Set `EXTERNAL_STREAM_URL` to the HTTPS URL of your stream endpoint

### Ports

The Docker setup uses host networking for Chromecast mDNS discovery:

| Port | Service |
|------|---------|
| 80 | Frontend (nginx) |
| 8000 | Backend API |
| 8089 | Audio stream |

### Rebuilding

After code changes:
```bash
docker-compose build
docker-compose up -d
```

## Running as a Service (systemd)

Create `/etc/systemd/system/rtlsdr-radio.service`:

```ini
[Unit]
Description=RTL-SDR Chromecast Radio
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/rtlsdr-radio/backend
Environment="LMS_HOST=localhost"
Environment="LMS_PORT=9000"
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable rtlsdr-radio
sudo systemctl start rtlsdr-radio
```

## Troubleshooting

### RTL-SDR not detected
- Check USB connection
- Try `sudo rtl_test -t`
- Blacklist DVB drivers: `echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl.conf`

### No audio / choppy audio
- Ensure ffmpeg is installed
- Check that rtl_fm process starts (see logs)
- Verify network connectivity to Chromecast/LMS

### Chromecast not found
- Ensure devices are on the same network/VLAN
- Check firewall allows mDNS (port 5353 UDP)
- Try manual refresh via API

### LMS players not found
- Verify LMS server is running and accessible
- Check `LMS_HOST` and `LMS_PORT` environment variables
- Test LMS API directly: `curl http://your-lms:9000/jsonrpc.js`
- Ensure players are connected to LMS (check LMS web UI)

### LMS playback not working
- Verify the RTL-SDR Radio server is reachable from LMS player network
- Check firewall allows port 8089 (stream server)
- Test stream URL directly: `curl http://your-server:8089/stream.mp3`

### Home Assistant integration not connecting
- Verify the RTL-SDR Radio server is reachable from Home Assistant
- Check that port 8000 is accessible
- Test the health endpoint: `curl http://your-server:8000/api/health`

## License

MIT
