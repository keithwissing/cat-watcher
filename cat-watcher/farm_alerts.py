import asyncio
import logging
from hashlib import md5
import os
import time
import configparser

import aiomqtt
import telegram
from rich.logging import RichHandler
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

settings = os.getenv('SETTINGS', 'settings.ini')
send_to_telegram = os.getenv('SEND_MESSAGES', 'false').lower() == 'true'

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), settings))

broker = config.get('mqtt', 'broker', fallback='127.0.0.1')
port = config.getint('mqtt', 'port', fallback=1883)
username = config.get('mqtt', 'username', fallback='mqtt')
password = config.get('mqtt', 'password', fallback='mqtt')
topics = [topic.strip().strip("'\"") for topic in config.get('mqtt', 'topics').split(',')]
supressed_cameras = [camera.strip().strip("'\"") for camera in config.get('mqtt', 'suppressed_cameras').split(',')]

bot_token = config.get('telegram', 'bot_token')
use_channel = config.getint('telegram', 'channel')

PHOTO_SEND_INTERVAL = 1  # seconds between photo sends

memory = {}
photo_queue = asyncio.Queue()

async def photo_sender(photo_queue):
    logging.info('Starting photo sender')
    bot = Bot(token=bot_token)
    async with bot:
        last_sent = 0
        while True:
            item = await photo_queue.get()
            channel, payload, caption = item
            now = time.monotonic()
            wait = max(0, PHOTO_SEND_INTERVAL - (now - last_sent))
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                logging.info(f'Sending photo to {channel} {caption}')
                if send_to_telegram:
                    await bot.sendPhoto(channel, payload, caption=caption)
            except telegram.error.TimedOut as ex:
                logging.error(ex)
            last_sent = time.monotonic()
            photo_queue.task_done()

async def mqtt_listener(photo_queue):
    logging.info('Starting MQTT listener')
    max_reconnect_attempts = 5
    reconnect_attempts = 0
    logging.info(f'Connecting to {broker}:{port}')
    mqtt_client = aiomqtt.Client(broker, username=username, password=password)
    while True:
        try:
            async with mqtt_client:
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
                        if camera not in supressed_cameras:
                            await photo_queue.put((use_channel, message.payload, caption))
                    memory[message.topic] = image_hash
        except aiomqtt.MqttError:
            reconnect_attempts += 1
            if reconnect_attempts > max_reconnect_attempts:
                logging.error("Max reconnect attempts exceeded. Exiting.")
                break
            interval = 5  # Seconds
            logging.error(f"Connection lost; Reconnecting in {interval} seconds ... (attempt {reconnect_attempts}/{max_reconnect_attempts})")
            await asyncio.sleep(interval)

async def run_all():
    sender_task = asyncio.create_task(photo_sender(photo_queue))
    listener_task = asyncio.create_task(mqtt_listener(photo_queue))
    await asyncio.gather(sender_task, listener_task)

def main():
    logging.basicConfig(level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logging.info('Exiting on keyboard interrupt')

if __name__ == '__main__':
    main()
