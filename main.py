import asyncio
import logging
import os

from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError

from config import BOT_TOKEN, ADMIN_ID
from database import (
    init_db, close_db, save_message, get_history, create_pending,
    get_pending, resolve_pending, save_connection, get_stats, mark_disclosure_once,
)
from ai_service import generate_reply

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("javobbot")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


def approval_keyboard(pending_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash va yuborish", callback_data=f"approve:{pending_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{pending_id}"),
    ]])


@router.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user and message.from_user.id == ADMIN_ID:
        await message.answer(
            "Salom! JavobBot boshqaruv paneli ishga tushdi.\n\n"
            "/stats — statistika\n"
            "/pending — tasdiq kutayotgan javoblar"
        )
    else:
        await message.answer("Salom! Men JavobBot yordamchisiman. Akkaunt egasiga xabar yetkazishda yordam beraman.")


@router.message(Command("stats"))
async def stats_handler(message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    stats = await get_stats()
    await message.answer(
        f"📊 <b>JavobBot statistikasi</b>\n"
        f"Xabarlar: {stats['messages']}\n"
        f"Suhbatlar: {stats['chats']}\n"
        f"Tasdiq kutayotganlar: {stats['pending']}"
    )


@router.message(Command("pending"))
async def pending_handler(message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    from database import get_pool
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, original_text, suggested_reply, sender_name, sender_username,
                      sender_user_id, created_at
               FROM pending_replies WHERE status='pending'
               ORDER BY id DESC LIMIT 10"""
        )
    if not rows:
        await message.answer("Hozircha tasdiq kutayotgan javoblar yo'q.")
        return
    for row in rows:
        await message.answer(
            f"📝 <b>Tasdiq kutilmoqda #{row['id']}</b>\n"
            f"<b>Kimdan:</b> {escape_html(row['sender_name'] or 'Noma’lum')} "
            f"(@{escape_html(row['sender_username']) if row['sender_username'] else 'username yo‘q'})\n"
            f"<b>Telegram ID:</b> {row['sender_user_id'] or 'mavjud emas'}\n"
            f"<b>Kelgan xabar:</b> {escape_html(row['original_text'])}\n"
            f"<b>Taklif:</b> {escape_html(row['suggested_reply'])}",
            reply_markup=approval_keyboard(row["id"]),
        )


def escape_html(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


@router.business_connection()
async def business_connection_handler(event):
    connection = event
    rights = connection.rights
    can_reply = bool(getattr(rights, "can_reply", False)) if rights else bool(
        getattr(connection, "can_reply", False)
    )
    await save_connection(
        connection.id, connection.user.id, connection.is_enabled, can_reply
    )
    logger.info(
        "Business connection updated: owner=%s enabled=%s can_reply=%s",
        connection.user.id, connection.is_enabled, can_reply
    )
    if connection.user.id == ADMIN_ID:
        status = "ulandi" if connection.is_enabled else "uzildi"
        try:
            await bot.send_message(ADMIN_ID, f"Telegram Business ulanishi {status}.")
        except TelegramAPIError:
            logger.warning("Admin bot chatini hali ochmagan bo'lishi mumkin.")


@router.business_message(F.text)
async def business_text_handler(message: Message):
    connection_id = message.business_connection_id
    if not connection_id or not message.chat:
        return
    if message.chat.type != "private":
        return
    # Business akkaunt egasining o'zi yuborgan xabarlarni bot qayta ishlamasin.
    if message.from_user and message.from_user.id == ADMIN_ID:
        return
    if getattr(message, "sender_business_bot", None):
        return
    if message.chat.type != "private":
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    try:
        connection = await bot.get_business_connection(connection_id)
        # ADMIN_ID noto'g'ri sozlangan bo'lsa ham, akkaunt egasining o'z xabariga javob bermaymiz.
        if message.from_user and message.from_user.id == connection.user.id:
            logger.info("Business egasining o'z xabari o'tkazib yuborildi: chat=%s", message.chat.id)
            return
        rights = connection.rights
        can_reply = bool(getattr(rights, "can_reply", False)) if rights else bool(
            getattr(connection, "can_reply", False)
        )
        if not connection.is_enabled or not can_reply:
            logger.warning("Business connection has no reply permission")
            return

        # Incoming message is archived before AI processing; later deletion in Telegram
        # does not erase this server-side record.
        await save_message(connection_id, message.chat.id, "user", text)
        sender = message.from_user
        sender_name = (sender.full_name if sender else message.chat.full_name) or "Noma’lum"
        sender_username = sender.username if sender else None
        if await mark_disclosure_once(connection_id, message.chat.id):
            await bot.send_message(
                chat_id=message.chat.id,
                text="Salom! Men akkaunt egasining yordamchisiman. Xabaringizga imkon qadar tez javob beraman; egasining shaxsiy qarori yoki tasdig‘i kerak bo‘lsa, albatta yetkazaman.",
                business_connection_id=connection_id,
                parse_mode=None,
            )
        history = await get_history(connection_id, message.chat.id)
        # Joriy xabar history ichida bor; generate_reply uni takrorlamasligi uchun chiqaramiz.
        history = history[:-1]
        result = await generate_reply(history, text)

        if result["needs_approval"]:
            pending_id = await create_pending(
                connection_id,
                message.chat.id,
                sender.id if sender else None,
                sender_name,
                sender_username,
                text,
                result["reply"],
            )
            admin_text = (
                f"🔔 <b>Muhim xabar — tasdiq kerak</b>\\n"
                f"<b>Kimdan:</b> {escape_html(sender_name)} "
                f"(@{escape_html(sender_username) if sender_username else 'username yo‘q'})\\n"
                f"<b>Telegram ID:</b> {sender.id if sender else 'mavjud emas'}\\n"
                + (f"<b>Profil:</b> <a href=\\"tg://user?id={sender.id}\\">Telegram profilini ochish</a>\\n" if sender else "")
                + f"<b>Sabab:</b> {escape_html(result['reason'])}\\n"
                + f"<b>Xabar:</b> {escape_html(text)}\\n"
                + f"<b>AI taklifi:</b> {escape_html(result['reply'])}\\n\\n"
                + f"ID: #{pending_id}"
            )
            try:
                await bot.send_message(ADMIN_ID, admin_text, reply_markup=approval_keyboard(pending_id))
            except TelegramAPIError:
                logger.exception("Admin'ga tasdiq xabarini yuborib bo'lmadi")
            await bot.send_message(
                chat_id=message.chat.id,
                text="Xabaringizni muhim deb hisobladim. Uni Asomiddinga albatta yetkazib qo‘yaman. Bu masala bo‘yicha Asomiddin o‘zlari sizga javob beradilar.",
                business_connection_id=connection_id,
                parse_mode=None,
            )
            return

        await bot.send_message(
            chat_id=message.chat.id,
            text=result["reply"],
            business_connection_id=connection_id,
            parse_mode=None,
        )
        await save_message(connection_id, message.chat.id, "assistant", result["reply"])

    except TelegramAPIError:
        logger.exception("Telegram Business xabarini qayta ishlashda xato")
    except Exception:
        logger.exception("Xabarni qayta ishlashda kutilmagan xato")
        # Ichki texnik xatoni suhbatdoshga ko'rsatmaymiz; xabarni egasiga yetkazish va'dasini beramiz.
        try:
            sender = message.from_user
            sender_name = (sender.full_name if sender else message.chat.full_name) or "Noma'lum"
            sender_username = sender.username if sender else None
            safe_reply = (
                "Xabaringizni muhim deb hisobladim. Uni Asomiddinga albatta yetkazib qo‘yaman. "
                "Bu masala bo‘yicha Asomiddin o‘zlari sizga javob beradilar."
            )
            pending_id = await create_pending(
                connection_id, message.chat.id, sender.id if sender else None,
                sender_name, sender_username, text, safe_reply
            )
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>Javob tayyorlashda xatolik — qo‘lda ko‘rib chiqing</b>\n"
                    f"<b>Kimdan:</b> {escape_html(sender_name)}\n"
                    f"<b>Telegram ID:</b> {sender.id if sender else 'mavjud emas'}\n"
                    f"<b>Xabar:</b> {escape_html(text)}\n"
                    f"<b>Sabab:</b> Texnik xato. Render loglarini tekshiring.\n"
                    f"<b>ID:</b> #{pending_id}",
                    reply_markup=approval_keyboard(pending_id),
                )
            except TelegramAPIError:
                logger.exception("Admin'ga texnik xato bo'yicha xabar yuborilmadi")
            await bot.send_message(
                chat_id=message.chat.id,
                text=safe_reply,
                business_connection_id=connection_id,
                parse_mode=None,
            )
        except Exception:
            logger.exception("Xatolikdan keyingi xavfsiz javobni yuborib bo'lmadi")


@router.callback_query(F.data.startswith("approve:"))
async def approve_reply(callback: CallbackQuery):
    if not callback.from_user or callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    pending_id = int(callback.data.split(":", 1)[1])
    pending = await get_pending(pending_id)
    if not pending or pending["status"] != "pending":
        await callback.answer("Bu javob allaqachon ko'rib chiqilgan.")
        return
    try:
        connection = await bot.get_business_connection(pending["connection_id"])
        rights = connection.rights
        can_reply = bool(getattr(rights, "can_reply", False)) if rights else bool(
            getattr(connection, "can_reply", False)
        )
        if not connection.is_enabled or not can_reply:
            await callback.answer("Business ulanishida javob berish huquqi yo'q.", show_alert=True)
            return
        await bot.send_message(
            chat_id=pending["chat_id"],
            text=pending["suggested_reply"],
            business_connection_id=pending["connection_id"],
            parse_mode=None,
        )
        await resolve_pending(pending_id, "approved")
        await save_message(
            pending["connection_id"], pending["chat_id"], "assistant",
            pending["suggested_reply"]
        )
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Javob yuborildi!")
    except TelegramAPIError:
        logger.exception("Tasdiqlangan javobni yuborib bo'lmadi")
        await callback.answer("Yuborishda xato. Loglarni tekshiring.", show_alert=True)


@router.callback_query(F.data.startswith("reject:"))
async def reject_reply(callback: CallbackQuery):
    if not callback.from_user or callback.from_user.id != ADMIN_ID:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    pending_id = int(callback.data.split(":", 1)[1])
    changed = await resolve_pending(pending_id, "rejected")
    if changed:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Javob rad etildi.")
    else:
        await callback.answer("Bu javob allaqachon ko'rib chiqilgan.")


async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "JavobBot"})


async def start_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("HTTP health server listening on 0.0.0.0:%s", port)
    return runner


async def main():
    await init_db()
    health_runner = await start_health_server()
    logger.info("JavobBot polling orqali ishga tushmoqda")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        await health_runner.cleanup()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
