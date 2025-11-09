# ubot/__init__.py

import asyncio
import logging
import os
import re
from os import execvp
from sys import executable
from typing import Optional, Dict, List

from aiohttp import ClientSession
from pyrogram import Client
from pyrogram.enums import *
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import *
from pyromod import listen
from pytgcalls import PyTgCalls

from ubot.config import *

# ---------------------------
# aiohttp session management
# ---------------------------

_aiosession: Optional[ClientSession] = None
# Back-compat global (some modules might `from ubot import aiosession`)
aiosession: Optional[ClientSession] = None


async def get_aiosession() -> ClientSession:
    """Return a process-wide shared aiohttp session. Create it on first use."""
    global _aiosession
    if _aiosession is None or _aiosession.closed:
        _aiosession = ClientSession()
    return _aiosession


async def ensure_aiosession() -> ClientSession:
    """Create the session and also set the back-compat global `aiosession`."""
    global aiosession
    aiosession = await get_aiosession()
    return aiosession


async def close_aiosession() -> None:
    """Close the shared session on shutdown."""
    global _aiosession, aiosession
    if _aiosession and not _aiosession.closed:
        await _aiosession.close()
    _aiosession = None
    aiosession = None


# ---------------------------
# Restart helper + logging
# ---------------------------

def gas():
    """Gracefully restart the process with `python -m ubot`."""
    execvp(executable, [executable, "-m", "ubot"])


class ConnectionHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        # Auto-restart on certain network-related errors
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


# ---------------------------
# Ubot client
# ---------------------------

class Ubot(Client):
    __module__ = "pyrogram.client"
    _ubot: List["Ubot"] = []
    _prefix: Dict[int, List[str]] = {}
    _get_my_id: List[int] = []
    _translate: Dict[int, Dict[str, str]] = {}
    _get_my_peer: Dict[int, str] = {}

    def __init__(self, api_id, api_hash, device_model="Ichigo-Userbot", **kwargs):
        # Important: let pyrogram manage the loop; do not touch it here.
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
        # Make sure our shared HTTP session exists under a running loop
        await ensure_aiosession()

        await super().start()
        await self.call_py.start()

        # get_pref is expected to be provided by your db/helpers (imported below)
        handler = await get_pref(self.me.id)
        if handler:
            self._prefix[self.me.id] = handler
        else:
            self._prefix[self.me.id] = ["."]
        self._ubot.append(self)
        self._get_my_id.append(self.me.id)
        self._translate[self.me.id] = {"negara": "id"}

        print(f"Starting Userbot ({self.me.id}|{self.me.first_name}{self.last_name or ''})")


# ---------------------------
# Prefix utilities
# ---------------------------

async def get_prefix(user_id):
    return ubot._prefix.get(user_id, ".")


def anjay(cmd):
    command_re = re.compile(r"([\"'])(.*?)(?<!\\)\1|(\S+)")

    async def func(_, client: Client, message):
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

    from pyrogram import filters
    return filters.create(func)


# ---------------------------
# Instances
# ---------------------------

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
        # Ensure shared session exists for anything that might use it.
        await ensure_aiosession()
        await super().start()


bot = Bot(
    name="bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------------------------
# Downstream imports (use shared session via get_aiosession/aiosession)
# ---------------------------

from ubot.core.database import *
from ubot.core.function import *
from ubot.core.helpers import *
from ubot.core.plugins import *

__all__ = [
    "Ubot",
    "Bot",
    "ubot",
    "bot",
    "LOGGER",
    "anjay",
    "get_prefix",
    "get_aiosession",
    "ensure_aiosession",
    "close_aiosession",
    "aiosession",  # back-compat
]
