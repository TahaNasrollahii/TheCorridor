"""One-off helper to make the bot open the Mini App from its menu button.

Telegram shows a button next to the message box in every chat with the bot.
This points that button at the deployed Mini App so tapping it launches the
corridor's web UI inside Telegram.

Run locally once after the Mini App is deployed:

    # PowerShell
    $env:TOKEN="123:abc"; $env:WEBAPP_URL="https://your-project.vercel.app"; python set_menu_button.py

    # bash
    TOKEN=123:abc WEBAPP_URL=https://your-project.vercel.app python set_menu_button.py

Pass `reset` to restore the default ("commands") menu button:

    python set_menu_button.py reset

Note: the URL must be HTTPS — Telegram refuses to open a Mini App otherwise.
"""

import asyncio
import os
import sys

from aiogram import Bot
from aiogram.types import (
    MenuButtonCommands,
    MenuButtonWebApp,
    WebAppInfo,
)


async def main() -> None:
    token = os.environ["TOKEN"]
    bot = Bot(token=token)

    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        print("menu button reset to commands.")
    else:
        url = os.environ["WEBAPP_URL"]
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="the corridor",
                web_app=WebAppInfo(url=url),
            )
        )
        print(f"menu button now opens: {url}")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
