# ubot/__init__.py

import asyncio
import logging
import os
import re
import signal
from os import execvp
from sys import executable

from aiohttp import ClientSession
from pyrogram import *
from pyrogram.enums import *
from pyrogram.handlers import *
from pyrogram.types import *
from pyromod import listen
from pytgcalls import PyTgCalls

from ubot.config import *
from ubot.core.database import *
from ubot.core.function import *
from ubot.core.helpers import *
from ubot.core.plugins import *

# ----------------------------
# Shared aiohttp session (lazy)
# ----------------------------
_aiosession: ClientSession | None = None

async def get_aiosession() -> ClientSession:
    """
    Return a shared aiohttp ClientSession.
    Create it only when a running event loop exists.
    """
    global _aiosession
    if _aiosession is None or _aiosession.closed:
        _aiosession = ClientSession()
    return _aiosession

async def close_aiosession() -> None:
    """
    Close the shared aiohttp session. Call this during graceful shutdown.
    """
    global _aiosession
    if _aiosession and not _aiosession.closed:
        await _aiosession.close()
    _aiosession = None


# ----------------------------
# Process restart helper
# ----------------------------
def gas():
    execvp(executable, [executable, "-m", "ubot"])


# ----------------------------
# Logging setup
# ----------------------------
class ConnectionHandler(logging.Handler):
    def emit(self, record):
        for X in ["OSError"]:
            if X in record.getMessage():
                gas()

logger = logging.getLogger()
logger.setLevel(logging.ERROR)

formatter = logging.Formatter("[%(levelname)s] - %(name)s - %(message)s", "%d-%b %H:%M")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

connection_handler = ConnectionHandler()

logger.addHandler(stream_handler)
logger.addHandler(connection_handler)

LOGS = logging.getLogger(__name__)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ----------------------------
# Ubot client
# ----------------------------
class Ubot(Client):
    __module__ = "pyrogram.client"
    _ubot = []
    _prefix = {}
    _get_my_id = []
    _translate = {}
    _get_my_peer = {}

    def __init__(self, api_id, api_hash, device_model="Ichigo-Userbot", **kwargs):
        super().__init__(**kwargs)
        self.api_id = api_id
        self.api_hash = api_hash
        self.device_model = device_model
        self.call_py = PyTgCalls(self)

    def on_message(self, filters=None, group=0):
        def decorator(func):
            for ub in self._ubot:
                ub.add_handler(MessageHandler(func, filters))
            return func
        return decorator

    def set_prefix(self, user_id, prefix):
        self._prefix[self.me.id] = prefix

    async def start(self):
        # Ensure session can be created by any code that needs it later:
        # await get_aiosession()  # uncomment if you want to create it eagerly
        await super().start()
        await self.call_py.start()
        handler = await get_pref(self.me.id)
        if handler:
            self._prefix[self.me.id] = handler
        else:
            self._prefix[self.me.id] = ["."]
        self._ubot.append(self)
        self._get_my_id.append(self.me.id)
        self._translate[self.me.id] = {"negara": "id"}
        print(f"Starting Userbot ({self.me.id}|{self.me.first_name}{self.me.last_name})")


async def get_prefix(user_id):
    return ubot._prefix.get(user_id, ".")


def anjay(cmd):
    command_re = re.compile(r"([\"'])(.*?)(?<!\\)\1|(\S+)")

    async def func(_, client, message):
        if message.text and message.from_user:
            text = message.text.strip()
            username = client.me.username or ""
            prefixes = await get_prefix(client.me.id)

            if not text:
                return False

            for prefix in prefixes:
                if not text.startswith(prefix):
                    continue

                without_prefix = text[len(prefix):]

                for command in cmd.split("|"):
                    if not re.match(
                        rf"^(?:{command}(?:@?{username})?)(?:\s|$)",
                        without_prefix,
                        flags=re.IGNORECASE | re.UNICODE,
                    ):
                        continue

                    without_command = re.sub(
                        rf"{command}(?:@?{username})?\s?",
                        "",
                        without_prefix,
                        count=1,
                        flags=re.IGNORECASE | re.UNICODE,
                    )
                    message.command = [command] + [
                        re.sub(r"\\([\"'])", r"\1", m.group(2) or m.group(3) or "")
                        for m in command_re.finditer(without_command)
                    ]

                    return True

        return False

    return filters.create(func)


# Create clients (not started yet)
ubot = Ubot(name="ubot", api_id=API_ID, api_hash=API_HASH, device_model="Himi-Ubot")


class Bot(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, device_model="V1HimiUbot")

    def on_message(self, filters=None, group=-1):
        def decorator(func):
            self.add_handler(MessageHandler(func, filters), group)
            return func
        return decorator

    def on_callback_query(self, filters=None, group=-1):
        def decorator(func):
            self.add_handler(CallbackQueryHandler(func, filters), group)
            return func
        return decorator

    async def start(self):
        # await get_aiosession()  # uncomment if you want to create it eagerly
        await super().start()


bot = Bot(
    name="bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ----------------------------
# Optional: graceful shutdown hooks
# (Only used if your entrypoint imports this module and registers signals here)
# ----------------------------
def _install_signal_handlers():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _stop():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            # Windows on Python <3.8 or non-main thread
            pass

    return stop_event

# If you prefer handling shutdown in your __main__, you can ignore _install_signal_handlers()
# and simply call `await close_aiosession()` when stopping your app.
