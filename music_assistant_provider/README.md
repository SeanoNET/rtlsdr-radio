# RTL-SDR Radio Provider for Music Assistant

This is a custom Music Assistant provider that integrates RTL-SDR Radio stations into Music Assistant.

## Features

- Browse and play saved RTL-SDR Radio station presets
- Automatic tuning when selecting a station
- MP3 audio streaming via internal Docker networking

## Installation

This provider is distributed as a custom Music Assistant Docker image that includes the provider pre-installed.

### Using Docker Compose (Recommended)

The provider is included in the main `docker-compose.prod.yml`:

```bash
docker compose -f docker-compose.prod.yml up -d music-assistant
```

### Manual Docker Run

```bash
docker run -d \
  --name music-assistant \
  -v music-assistant-data:/data \
  -p 8095:8095 \
  --network traefik \
  ghcr.io/seanonet/rtlsdr-music-assistant:latest
```

## Configuration

After starting Music Assistant, add the RTL-SDR Radio provider:

1. Open Music Assistant UI (e.g., `https://ma.local.seanonet.dev`)
2. Go to **Settings** → **Providers**
3. Click **Add Provider**
4. Select **RTL-SDR Radio**
5. Configure the connection:
   - **Host**: `rtlsdr-backend` (default, for Docker networking)
   - **API Port**: `9080`
   - **Stream Port**: `8089`

## Home Assistant Integration

To use Music Assistant with Home Assistant:

1. Install the "Music Assistant" integration from HACS
2. Point it to your Music Assistant server URL
3. RTL-SDR Radio stations will appear as radio sources in HA

## How It Works

```
┌─────────────────────┐     ┌──────────────────────┐
│  Music Assistant    │     │  RTL-SDR Radio       │
│                     │     │  Backend             │
│  ┌───────────────┐  │     │                      │
│  │ rtlsdr_radio  │──┼────▶│  GET /api/stations   │
│  │ provider      │  │     │  POST /api/playback  │
│  └───────────────┘  │     │  GET :8089/stream    │
└─────────────────────┘     └──────────────────────┘
```

1. Provider fetches station list from RTL-SDR Radio API
2. Stations appear as radio items in Music Assistant library
3. When you play a station, provider tells backend to tune the RTL-SDR
4. Audio streams from the backend's stream server (port 8089)
5. Music Assistant plays the stream on your selected output device

## Automatic Updates

The custom Docker image is automatically rebuilt when:

- Provider code changes (push to main)
- Weekly check for new Music Assistant releases
- Manual workflow trigger

Images are tagged with:
- `latest` - Most recent build
- `ma-{version}` - Specific Music Assistant version
- `{sha}` - Git commit SHA

## Development

To build locally:

```bash
cd music_assistant_provider
docker build -t rtlsdr-music-assistant:dev .
```

To test with local development:

```bash
docker compose -f docker-compose.dev.yml up -d
```

## Troubleshooting

### Provider not appearing

Check that the provider files are in the correct location inside the container:

```bash
docker exec music-assistant ls -la /app/music_assistant/providers/rtlsdr_radio/
```

### Cannot connect to RTL-SDR Radio

Ensure both containers are on the same Docker network:

```bash
docker network inspect traefik
```

Verify the backend is accessible:

```bash
docker exec music-assistant curl http://rtlsdr-backend:9080/api/health
```

### No audio

Check that the RTL-SDR device is connected and the backend is running:

```bash
docker logs rtlsdr-backend
```
