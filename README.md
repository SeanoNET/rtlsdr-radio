# RTL-SDR Radio

Stream FM/AM radio from an RTL-SDR dongle to Chromecast speakers or Squeezelite players via Music Assistant.

![Radio Stations in Music Assistant](docs/radio.png)

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────┐     ┌────────────────┐
│   Web Frontend  │────▶│        FastAPI Backend          │────▶│   Chromecast   │
│     (React)     │     │                                 │     └────────────────┘
└─────────────────┘     │  ┌───────────┐  ┌────────────┐  │
                        │  │  rtl_fm   │─▶│  ffmpeg    │  │
                        │  │  process  │  │  transcoder│  │
                        │  └───────────┘  └────────────┘  │
                        └─────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────┐     ┌────────────────┐
                        │       Music Assistant           │────▶│  Squeezelite   │
                        │    (RTL-SDR Radio Provider)     │     │    Players     │
                        └─────────────────────────────────┘     └────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────┐
                        │        Home Assistant           │
                        │         (Automations)           │
                        └─────────────────────────────────┘
```

## Features

- **Web UI** - Browse and play station presets
- **Chromecast Support** - Stream directly to Chromecast/Google Home devices
- **Music Assistant Integration** - Custom provider exposes stations as radio items
- **Squeezelite Support** - Play to Squeezelite players via Music Assistant's Slimproto
- **Home Assistant Automations** - Control playback via HA automations through Music Assistant

## Quick Start (Docker)

```bash
# Clone the repository
git clone https://github.com/SeanoNET/rtlsdr-radio.git
cd rtlsdr-radio

# Start all services
docker-compose up -d

# Frontend: http://localhost
# Backend API: http://localhost:8000
# Music Assistant: http://localhost:8095
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 80 | React web UI |
| Backend | 8000 | FastAPI REST API |
| Music Assistant | 8095 | Music Assistant with RTL-SDR provider |

## Music Assistant Setup

1. Open Music Assistant at `http://localhost:8095`
2. Go to **Settings → Providers → Add Provider**
3. Select **RTL-SDR Radio**
4. Configure:
   - **Host**: `rtlsdr-backend` (or `localhost` if using host networking)
   - **Port**: `8000`
5. Click **Save**
6. Your stations will appear in **Radio** section

## Home Assistant Automations

Once Music Assistant is connected to Home Assistant, you can control radio playback via automations:

```yaml
# Play a station
service: mass.play_media
data:
  media_id: "Nova 93.7"
  entity_id: media_player.kitchen_speaker

# Play by station ID
service: mass.play_media
data:
  media_id: "rtlsdr_radio://station_id"
  entity_id: media_player.office_speaker
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXTERNAL_STREAM_URL` | _(none)_ | HTTPS URL for Chromecast streaming |

### Chromecast HTTPS Requirement

Chromecast devices require HTTPS URLs. Set up a reverse proxy with SSL and configure `EXTERNAL_STREAM_URL`.

## API Reference

### Stations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stations` | GET | List all station presets |
| `/api/stations` | POST | Create a new station |
| `/api/stations/{id}` | GET | Get station details |
| `/api/stations/{id}` | PUT | Update a station |
| `/api/stations/{id}` | DELETE | Delete a station |

### Speakers (Chromecast)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/speakers` | GET | List all Chromecast speakers |
| `/api/speakers/{id}/volume` | PUT | Set volume (0.0-1.0) |

### Playback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/playback/status` | GET | Get playback status |
| `/api/playback/start` | POST | Start playback |
| `/api/playback/stop` | POST | Stop playback |

### Stream

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stream` | GET | Raw MP3 audio stream |

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Troubleshooting

### RTL-SDR not detected

```bash
# Check USB connection
lsusb | grep -i rtl

# Create udev rule
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"' | sudo tee /etc/udev/rules.d/99-rtlsdr.rules
sudo udevadm control --reload-rules
```

### Stations not appearing in Music Assistant

1. Check provider is configured with correct host/port
2. Verify backend is reachable: `curl http://localhost:8000/api/stations`
3. Trigger a library sync in MA: **Settings → Providers → RTL-SDR Radio → Sync**

### Chromecast not found

- Ensure devices are on the same network
- Check firewall allows mDNS (port 5353 UDP)

## License

MIT
