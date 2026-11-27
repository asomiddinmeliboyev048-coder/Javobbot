import json
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, PERSONALITY_CONTEXT

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": incoming_text})

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=350,
    )
    raw = response.choices[0].message.content or "{}"
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
        return {
            "reply": "Xabaringizni oldim. Birozdan keyin javob beraman.",
            "needs_approval": True,
            "reason": "AI javobini xavfsiz formatda o'qib bo'lmadi",
        }
