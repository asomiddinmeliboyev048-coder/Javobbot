import json
import logging

import aiohttp

from config import GEMINI_API_KEY, GEMINI_MODEL, PERSONALITY_CONTEXT

logger = logging.getLogger("javobbot.ai")

SYSTEM_PROMPT = """Sen JavobBot AI yordamchisisan. Vazifang — akkaunt egasiga Telegram suhbatlarida yordam berish.
Uslub: tabiiy, samimiy, aqlli, qisqa va insoniy o'zbekcha. Suhbatdosh qaysi tilda yozsa, odatda shu tilda javob ber.
Akkaunt egasi haqida faqat berilgan kontekstdagi tasdiqlangan faktlardan foydalan. Bilmagan narsangni to'qima.
Agar suhbatdosh bot yoki avtomatlashtirish haqida so'rasa, AI yordamchi ekaningni ochiq ayt.
Hech qachon egasi nomidan uchrashuv, to'lov, qarz, xarid, ish, va'da yoki boshqa majburiyatni tasdiqlama.
Shaxsiy ma'lumot, manzil, telefon, parol, kod, moliyaviy masala, sog'liq, huquqiy masala,
uchrashuv/qo'ng'iroq kelishuvi, shoshilinch yoki nozik mavzu bo'lsa needs_approval=true qil.
Haqorat, tahdid, shubhali havola, spam yoki xavfsizlikka oid vaziyatda ham tasdiq talab qil.
Oddiy salomlashish, umumiy savol va xavfsiz kundalik suhbatlarga avtomatik javob berish mumkin.
Agar javob uchun egasidan noma'lum ma'lumot kerak bo'lsa, tasdiq talab qil.
Javobni JSON formatida qaytar: {"reply":"...","needs_approval":true yoki false,"reason":"..."}.
reply — suhbatdoshga yuboriladigan qisqa javob. reason — admin uchun qisqa sabab.
""" + (f"\nAkkaunt egasi haqida tasdiqlangan kontekst: {PERSONALITY_CONTEXT}" if PERSONALITY_CONTEXT else "")


async def generate_reply(history: list[dict], incoming_text: str) -> dict:
    contents = []
    for item in history:
        role = "model" if item.get("role") == "assistant" else "user"
        content = str(item.get("content", "")).strip()
        if content:
            contents.append({"role": role, "parts": [{"text": content}]})
    contents.append({"role": "user", "parts": [{"text": incoming_text}]})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 450,
            "responseMimeType": "application/json",
        },
    }
    timeout = aiohttp.ClientTimeout(total=45)
    headers = {"x-goog-api-key": GEMINI_API_KEY}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            body = await response.text()
            if response.status >= 400:
                logger.error("Gemini API xatosi (%s): %s", response.status, body[:1500])
                raise RuntimeError(f"Gemini API xatosi: HTTP {response.status}")
            data = json.loads(body)

    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content", {}).get("parts", []) if candidates else [])
    raw = "".join(part.get("text", "") for part in parts).strip()
    if not raw:
        logger.error("Gemini bo'sh javob qaytardi: %s", json.dumps(data, ensure_ascii=False)[:1500])
        raise ValueError("Gemini bo'sh javob qaytardi")

    try:
        result = json.loads(raw)
        reply = str(result.get("reply", "")).strip()
        if not reply:
            raise ValueError("AI javobi bo'sh")
        return {
            "reply": reply[:3500],
            # Faqat aniq boolean false avtomatik yuborishga ruxsat beradi.
            "needs_approval": result.get("needs_approval") is not False,
            "reason": str(result.get("reason", "AI tasdiq talab qildi"))[:500],
        }
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.exception("Gemini javobini JSON sifatida o'qib bo'lmadi")
        return {
            "reply": "Xabaringizni oldim. Birozdan keyin javob beraman.",
            "needs_approval": True,
            "reason": "AI javobini xavfsiz formatda o'qib bo'lmadi",
        }
