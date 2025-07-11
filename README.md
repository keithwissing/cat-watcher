# Cat Watcher

A Dockerized application for watching MQTT topics for cat photos, potentually published by frigate, and sending them to Telegram.

### Settings Configuration

The application uses a `settings.ini` file for configuration. Here's an example configuration:

```ini
[mqtt]
broker = 127.0.0.1
port = 1883
username = mqtt
password = mqtt
topics = "frigate/+/dog/snapshot", "frigate/+/cat/snapshot"
suppressed_cameras = none

[telegram]
bot_token = <your_telegram_bot_token>
channel = <your_channel_id>
```

### Docker Compose

You can run the application using Docker Compose. Here's an example `docker-compose.yml`:

```yaml
services:
  cat_watcher:
    image: ghcr.io/keithwissing/cat-watcher:latest
    container_name: cat_watcher
    restart: always
    volumes:
      - ./settings.ini:/app/settings.ini
```

### Or run directly with Docker:

```bash
docker run -d \
  --name cat-watcher \
  -v $(pwd)/settings.ini:/app/settings.ini \
  ghcr.io/keithwissing/cat-watcher:latest
```
