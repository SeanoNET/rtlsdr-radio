# Custom Music Assistant Server with RTL-SDR Radio Provider
# This image extends the official MA server and adds our custom provider

ARG MA_VERSION=latest
FROM ghcr.io/music-assistant/server:${MA_VERSION}

# Copy the RTL-SDR Radio provider to the actual providers location
# MA loads providers from the venv site-packages directory
COPY rtlsdr_radio /app/venv/lib/python3.13/site-packages/music_assistant/providers/rtlsdr_radio

# Ensure proper permissions
RUN chmod -R 755 /app/venv/lib/python3.13/site-packages/music_assistant/providers/rtlsdr_radio

# The base image already sets the entrypoint and command
