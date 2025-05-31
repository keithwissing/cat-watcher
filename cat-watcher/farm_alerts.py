import asyncio
import configparser
import logging
import os
import time
from hashlib import md5

import aiomqtt
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from telegram import Bot

def load_config():
    load_dotenv()
    settings = os.getenv('SETTINGS', 'settings.ini')
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), settings))

    photo_sender_config = {
        'bot_token': config.get('telegram', 'bot_token'),
        'send_to_telegram': os.getenv('SEND_MESSAGES', 'false').lower() == 'true',
        'photo_send_interval': config.getint('telegram', 'photo_send_interval', fallback=2),
    }
    mqtt_listener_config = {
        'broker': config.get('mqtt', 'broker', fallback='127.0.0.1'),
        'port': config.getint('mqtt', 'port', fallback=1883),
        'username': config.get('mqtt', 'username', fallback='mqtt'),
        'password': config.get('mqtt', 'password', fallback='mqtt'),
        'topics': [topic.strip().strip("'\"") for topic in config.get('mqtt', 'topics').split(',')],
        'suppressed_cameras': [camera.strip().strip("'\"") for camera in config.get('mqtt', 'suppressed_cameras').split(',')],
        'use_channel': config.getint('telegram', 'channel'),
    }

    return photo_sender_config, mqtt_listener_config

async def photo_sender(photo_queue, config):
    bot = Bot(token=config['bot_token'])
    send_to_telegram = config['send_to_telegram']
    photo_send_interval = config['photo_send_interval']

    logging.info(f'Starting photo sender, with {send_to_telegram=}, {photo_send_interval=}')

    async with bot:
        last_sent = 0
        while True:
            item = await photo_queue.get()
            channel, payload, caption = item
            now = time.monotonic()
            await asyncio.sleep(max(0, photo_send_interval - (now - last_sent)))
            try:
                logging.info(f'Sending photo to {channel} {caption}')
                if send_to_telegram:
                    message = await bot.send_photo(channel, payload, caption=caption)
                    # logging.info(message)
                    logging.info(f'Sent message id {message.message_id} caption: {message.caption}')
            except Exception as ex:
                logging.error(f"Error sending photo: {ex}")
            last_sent = time.monotonic()
            photo_queue.task_done()

async def mqtt_listener(photo_queue, config):
    logging.info('Starting MQTT listener')

    broker = config['broker']
    port = config['port']
    username = config['username']
    password = config['password']
    topics = config['topics']
    suppressed_cameras = config['suppressed_cameras']
    use_channel = config['use_channel']

    memory = {}
    max_reconnect_attempts = 5
    reconnect_attempts = 0
    base_interval = 5  # Starting interval in seconds

    logging.info(f'Connecting to {broker}:{port}')
    while True:
        try:
            mqtt_client = aiomqtt.Client(broker, username=username, password=password)
            async with mqtt_client:
                if reconnect_attempts > 0:
                    logging.info("Successfully reconnected to MQTT broker")
                reconnect_attempts = 0  # Reset on successful connect
                logging.info(f'Subscribing to {len(topics)} topics, {topics}')
                for topic in topics:
                    await mqtt_client.subscribe(topic)
                async for message in mqtt_client.messages:
                    image_hash = md5(message.payload).hexdigest()
                    logging.info(f'{str(message.topic):<34} :  {message.payload[6:10]} {image_hash}')
                    if message.topic in memory and image_hash != memory[message.topic]:
                        camera, detected = str(message.topic).split('/')[1:3]
                        caption = f'{detected} {camera}'
                        if camera not in suppressed_cameras:
                            await photo_queue.put((use_channel, message.payload, caption))
                        else:
                            logging.info(f'Suppressed camera {camera}')
                    else:
                        logging.info(f'No change in {message.topic}')
                    memory[message.topic] = image_hash
        except aiomqtt.MqttError:
            reconnect_attempts += 1
            if reconnect_attempts > max_reconnect_attempts:
                logging.error("Max reconnect attempts exceeded. Exiting.")
                break

            interval = min(base_interval * (1.5 ** (reconnect_attempts - 1)), 60)
            logging.error(f"Connection lost; Reconnecting in {interval} seconds ... (attempt {reconnect_attempts}/{max_reconnect_attempts})")
            await asyncio.sleep(interval)

async def run_all():
    photo_queue = asyncio.Queue()

    photo_sender_config, mqtt_listener_config = load_config()

    sender_task = asyncio.create_task(photo_sender(photo_queue, photo_sender_config))
    listener_task = asyncio.create_task(mqtt_listener(photo_queue, mqtt_listener_config))
    await asyncio.gather(sender_task, listener_task)

def main():
    console = Console(width=150)
    logging.basicConfig(level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler(console=console)])
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logging.info('Exiting on keyboard interrupt')

if __name__ == '__main__':
    main()
