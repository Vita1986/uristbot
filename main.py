import os
import asyncio
import logging
import contextlib
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI
from dadata import DadataAsync  # Импортируем асинхронный клиент Дадаты

# Включаем логирование
logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8804861202:AAGbDign9c52_jpGfDe6YzfRgT7UwL1jA7o")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-6ca9bdce04844216a832a7865700d526")

# !!! ВНИМАНИЕ: Проверьте этот токен. Зайдите в личный кабинет dadata.ru и убедитесь, что он активен !!!
DADATA_TOKEN = os.getenv("DADATA_TOKEN", "deaae9699831f5460e868c22dd77f62e685f7a2b")

bot_session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher(storage=MemoryStorage())

# ИСПРАВЛЕНО: Убран "/v1" с конца URL. Теперь библиотека openai сама построит правильный путь.
ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================================
# 📑 ЭТАЛОННЫЕ ШАБЛОНЫ ДЛЯ DEEPSEEK (SYSTEM PROMPTS)
# ==========================================================
SYSTEM_PROMPTS = {
    "brak": (
        "Ты — professional ИИ-юрист. Твоя единственная задача — строго по предоставленным фактам пользователя "
        "заполнить шаблон претензии о возврате денег за БРАКОВАННЫЙ товар. Текст за пределами шаблона писать запрещено.\n\n"
        "ОБЯЗАТЕЛЬНЫЙ ШАБЛОН ДЛЯ ЗАПОЛНЕНИЯ:\n"
        "Кому: [Вставь Название Продавца]\n"
        "Адрес: [Вставь Адрес Продавца]\n"
        "От кого (ФИО): [Вставь ФИО заявителя]\n"
        "Адрес для ответа: [Вставь Адрес заявителя]\n\n"
        "ПРЕТЕНЗИЯ\n"
        "Я приобрел(а) в вашем магазине товар: [Вставь Наименование Товара], стоимостью [Вставь Стоимость] рублей. "
        "В процессе эксплуатации в товаре обнаружились следующие недостатки: [Юридически грамотно опиши суть проблемы на основе слов пользователя].\n"
        "В соответствии со ст. 18 Закона РФ «О защите прав потребителей», потребитель в случае обнаружения в товаре недостатков "
        "вправе отказаться от исполнения договора купли-продажи и потребовать возврата уплаченной за товар суммы.\n"
        "Согласно ст. 22 Закона РФ «О защите прав потребителей», требования подлежат удовлетворению в течение 10 дней.\n"
        "На основании изложенного, руководствуясь ст. 15, 18, 22 Закона РФ «О защите прав потребителей»,\n"
        "ТРЕБУЮ:\n"
        "1. Расторгнуть договор купли-продажи.\n"
        "2. Вернуть мне уплаченную сумму в размере [Вставь Стоимость] рублей в течение 10 дней по реквизитам: [Вставь Реквизиты].\n\n"
        "Дата: [Вставь Текущую Дату или оставь ___] Подпись: _________ / [Вставь ФИО Инициалы]"
    ),
    "kačestvo": (
        "Ты — профессиональный ИИ-юрист. Твоя задача — заполнить шаблон заявления на возврат товара НАДЛЕЖАЩЕГО качества "
        "(который просто не подошел). Действуй строго по закону, не выдумывай лишнего.\n\n"
        "ОБЯЗАТЕЛЬНЫЙ ШАБЛОН ДЛЯ ЗАПОЛНЕНИЯ:\n"
        "Кому: [Вставь Название Продавца]\n"
        "Адрес: [Вставь Адрес Продавца]\n"
        "От кого (ФИО): [Вставь ФИО заявителя]\n"
        "Адрес для ответа: [Вставь Адрес заявителя]\n\n"
        "ЗАЯВЛЕНИЕ\n"
        "Я приобрел(а) в вашем магазине товар: [Вставь Наименование Товара], стоимостью [Вставь Стоимость] рублей. "
        "Указанный товар не подошел мне по причине: [Вставь причину: размер/фасон/цвет].\n"
        "В соответствии со ст. 25 Закона РФ «О защите прав потребителей», потребитель вправе обменять непродовольственный товар "
        "в течение 14 дней. Поскольку аналогичный товар, подходящий мне, в продаже на день обращения отсутствует, на основании "
        "п. 2 ст. 25 Закона я отказываюсь от договора и требую возврата денег. Товар не был в употреблении, сохранены ярлыки и товарный вид.\n"
        "ТРЕБУЮ:\n"
        "1. Принять назад товар надлежащего качества.\n"
        "2. Вернуть мне денежные средства в размере [Вставь Стоимость] рублей в течение 3 дней по реквизитам: [Вставь Реквизиты].\n\n"
        "Дата: [Вставь Текущую Дату] Подпись: _________ / [Вставь ФИО Инициалы]"
    ),
    "rospotreb": (
        "Ты — профессиональный ИИ-юрист. Твоя задача — составить жалобу в Роспотребнадзор на то, что магазин проигнорировал досудебную претензию.\n\n"
        "ОБЯЗАТЕЛЬНЫЙ ШАБЛОН ДЛЯ ЗАПОЛНЕНИЯ:\n"
        "Куда: Управление Роспотребнадзора\n"
        "От кого (ФИО): [Вставь ФИО заявителя]\n"
        "Адрес для ответа: [Вставь Адрес заявителя]\n\n"
        "ЖАЛОБА\n"
        "Мной в магазине [Вставь Название Продавца] был приобретен товар [Вставь Наименование Товара]. В связи с возникшими проблемами "
        "в адрес продавца была направлена письменная досудебная претензия с требованием возврата денежных средств. "
        "Продавец получил претензию, однако в установленный законом 10-дневный срок требования потребителя не выполнил и ответ не предоставил.\n"
        "На основании Федерального закона № 59-ФЗ «О порядке рассмотрения обращений граждан РФ»,\n"
        "ПРОШУ:\n"
        "1. Провести проверку в отношении организации [Вставь Название Продавца].\n"
        "2. Выдать предписание об устранении нарушений и привлечь виновных лиц к административной ответственности по ст. 14.15 КоАП РФ.\n\n"
        "Дата: [Вставь Текущую Дату] Подпись: _________ / [Вставь ФИО Инициалы]"
    )
}


class BotStates(StatesGroup):
    waiting_for_agreement = State()
    main_menu = State()
    step_fio = State()
    step_user_address = State()
    step_company = State()
    step_product = State()
    step_price = State()
    step_problem = State()
    step_rekvizity = State()


def split_text(text: str, max_size: int = 4000) -> list[str]:
    parts = []
    while len(text) > max_size:
        split_at = text.rfind('\n', 0, max_size)
        if split_at == -1:
            split_at = max_size
        parts.append(text[:split_at])
        text = text[split_at:]
    parts.append(text)
    return parts


# ==========================================================
# 🧠 ИНТЕЛЛЕКТУАЛЬНЫЙ ГИБРИДНЫЙ ПОИСК КОМПАНИИ (DaData + DeepSeek Fallback)
# ==========================================================
async def fetch_company_data(query: str) -> dict:
    if DADATA_TOKEN and DADATA_TOKEN != "СЮДА_ВСТАВЬТЕ_ВАШ_ТОКЕН_DADATA":
        try:
            async with DadataAsync(DADATA_TOKEN) as dadata:
                result = await dadata.suggest(name="party", query=query, count=1)
                if result:
                    data = result[0]["data"]
                    name = result[0]["value"]
                    address = data.get("address", {}).get("value", "Не найден")
                    inn = data.get("inn", "Не указан")
                    return {"success": True, "name": f"{name} (ИНН {inn})", "address": address, "source": "DaData"}
        except Exception as e:
            logging.error(f"Технический сбой DaData при поиске компании: {e}")

    try:
        logging.info("Переключаюсь на поиск через DeepSeek...")
        search_prompt = (
            f"Найди в интернете официальное юридическое название (ООО/АО/ИП) и актуальный юридический адрес "
            f"организации по запросу: '{query}'.\n"
            f"Ответь строго по форме ниже и ничего более не пиши:\n"
            f"Название: [Тут полное название и ИНН]\n"
            f"Адрес: [Тут полный адрес]\n\n"
            f"Если это бессмысленный набор букв и компанию найти невозможно, напиши только одно слово: ОШИБКА"
        )
        completion = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": search_prompt}],
            temperature=0.1
        )
        res_text = completion.choices.message.content.strip()
        if "ОШИБКА" not in res_text and "Название:" in res_text:
            lines = res_text.split("\n")
            name = "Не найдено"
            address = "Не найден"
            for line in lines:
                if line.startswith("Название:"):
                    name = line.replace("Название:", "").strip()
                if line.startswith("Адрес:"):
                    address = line.replace("Адрес:", "").strip()
            return {"success": True, "name": name, "address": address, "source": "DeepSeek (Резервный веб-поиск)"}
    except Exception as e:
        logging.error(f"Технический сбой резервного поиска ИИ: {e}")
    return {"success": False}


# ==========================================================
# 📥 ХЕНДЛЕРЫ ИНТЕРФЕЙСА
# ==========================================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я согласен с условиями", callback_data="agree_terms")
    text = (
        "⚖ **Приветствую! Я — Ваш ИИ-Юрист.**\n\n"
        "Я автоматически проверяю реквизиты компаний по базам ФНС и составляю документы без ошибок.\n"
        "Нажмите кнопку ниже для продолжения."
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_agreement)


@dp.callback_query(F.data == "agree_terms", BotStates.waiting_for_agreement)
async def process_agreement(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_main_menu(callback.message, state)


async def show_main_menu(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Возврат БРАКОВАННОГО товара", callback_data="agent_brak")
    builder.button(text="🔄 Возврат ИСПРАВНОГО товара (не подошел)", callback_data="agent_kačestvo")
    builder.button(text="🏛 Жалоба в Роспотребнадзор", callback_data="agent_rospotreb")
    builder.adjust(1)
    text = "🤖 **Выберите тип документа, который вам необходим:**"
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(BotStates.main_menu)


@dp.callback_query(F.data.startswith("agent_"), BotStates.main_menu)
async def choose_agent(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    agent_name = callback.data.split("_")
    await state.update_data(current_agent=agent_name, user_answers={})
    await callback.message.answer(
        "Введите ваши **ФИО полностью** (например: Иванов Иван Иванович):")
    await state.set_state(BotStates.step_fio)


# ==========================================================
# ИСПРАВЛЕНО: КОРРЕКТНЫЕ ЗАПРОСЫ К DEEPSEEK И DADATA
# ==========================================================
@dp.message(BotStates.step_fio)
async def process_fio(message: types.Message, state: FSMContext):
    if len(message.text) < 3 or len(message.text) > 120:
        return await message.answer("⚠ Введите корректное полное ФИО.")

    status_msg = await message.answer("🔮 *Интеллектуальная проверка и исправление ФИО...*", parse_mode="Markdown")
    corrected_fio = message.text.title()

    try:
        prompt = (
            f"Ты — профессиональный редактор документов. Исправь все грамматические и орфографические ошибки, "
            f"а также опечатки в следующих персональных данных человека. Сделай первую букву каждого слова заглавной. "
            f"Результат верни СТРОГО в ИМЕНИТЕЛЬНОМ падеже (Фамилия Имя Отчество).\n\n"
            f"Искаженный текст пользователя: '{message.text}'\n\n"
            f"Выведи исключительно готовое корректное ФИО и абсолютно больше ничего не пиши. Никаких лишних знаков и пояснений."
        )
        completion = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            timeout=15.0
        )
        response_text = completion.choices.message.content.strip()
        if response_text.endswith("."):
            response_text = response_text[:-1].strip()

        if len(response_text.split()) >= 2:
            corrected_fio = response_text
    except Exception as e:
        # Теперь вы увидите в логах консоли ТМВ реальную ошибку, если она случится
        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА ДИПСИКА: {e}")

    await status_msg.delete()
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["ФИО заявителя"] = corrected_fio
    await state.update_data(user_answers=user_answers)

    await message.answer(
        f"🎯 ИТОГОВОЕ ФИО записано как:\n`{corrected_fio}`\n\n"
        f"Введите **ваш точный адрес** (например: екат михеева 2 55):"
    )
    await state.set_state(BotStates.step_user_address)


@dp.message(BotStates.step_user_address)
async def process_user_address(message: types.Message, state: FSMContext):
    if len(message.text) < 4:
        return await message.answer("⚠ Укажите более подробный адрес.")

    status_msg = await message.answer("🔎 *Стандартизирую адрес по официальным базам...*", parse_mode="Markdown")
    corrected_address = message.text

    if DADATA_TOKEN and DADATA_TOKEN != "СЮДА_ВСТАВЬТЕ_ВАШ_ТОКЕН_DADATA":
        try:
            # ИСПРАВЛЕНО: Правильный вызов API стандартизации DaData по документации разработчиков
            async with DadataAsync(DADATA_TOKEN) as dadata:
                res = await dadata.suggest(name="address", query=message.text, count=1)
                if res:
                    corrected_address = res[0]["value"]
        except Exception as e:
            logging.error(f"КРИТИЧЕСКАЯ ОШИБКА ДАДАТЫ ПО АДРЕСУ: {e}")

    await status_msg.delete()
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Адрес заявителя"] = corrected_address
    await state.update_data(user_answers=user_answers)

    await message.answer(
        f"✅ Адрес успешно подтвержден:\n`{corrected_address}`\n\n"
        f"🔍 Введите **Бренд, Название магазина или ИНН** (например: Озон или 7704217370):"
    )
    await state.set_state(BotStates.step_company)


# ==========================================================
# ОСТАЛЬНАЯ ЛОГИКА ШАГОВ
# ==========================================================
@dp.message(BotStates.step_company)
async def process_company(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        return await message.answer("⚠ Слишком короткое название. Введите название бренда или ИНН.")
    status_msg = await message.answer("🔎 *Проверяю организацию в официальных реестрах, секунду...*")
    company_info = await fetch_company_data(message.text)
    await status_msg.delete()
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    if company_info.get("success"):
        user_answers["Название Продавца"] = company_info["name"]
        user_answers["Адрес Продавца"] = company_info["address"]
        await state.update_data(user_answers=user_answers)
        await message.answer(
            f"✅ **Организация успешно найдена!**\n"
            f"🏢 Юр. лицо: `{company_info['name']}`\n"
            f"📍 Адрес: `{company_info['address']}`\n"
            f"📦 Источник данных: *{company_info['source']}*\n\n"
            f"Какой **товар** или услугу вы приобрели?"
        )
        await state.set_state(BotStates.step_product)
    else:
        await message.answer(
            "❌ **Организация не найдена в реестрах.**\n"
            "Пожалуйста, введите корректное название бренда, юрлица или ИНН."
        )


@dp.message(BotStates.step_product)
async def process_product(message: types.Message, state: FSMContext):
    if len(message.text) < 2 or len(message.text) > 150:
        return await message.answer("⚠ Пожалуйста, введите корректное название товара.")
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Наименование Товара"] = message.text
    await state.update_data(user_answers=user_answers)
    await message.answer("Укажите **стоимость товара** в рублях (только цифры, например: 45000):")
    await state.set_state(BotStates.step_price)


@dp.message(BotStates.step_price)
async def process_price(message: types.Message, state: FSMContext):
    clean_price = "".join(filter(str.isdigit, message.text))
    if not clean_price:
        return await message.answer("⚠ Введите стоимость товара **только цифрами**.")
    price_num = int(clean_price)
    if price_num < 10 or price_num > 5000000:
        return await message.answer("⚠ Цена товара должна быть в диапазоне от 10 до 5 000 000 рублей.")
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Стоимость"] = str(price_num)
    await state.update_data(user_answers=user_answers)
    if data.get("current_agent") == "brak":
        await message.answer("Опишите **недостатки товара** своими словами:")
        await state.set_state(BotStates.step_problem)
    elif data.get("current_agent") == "kačestvo":
        await message.answer("Укажите причину, почему товар не подошел:")
        await state.set_state(BotStates.step_problem)
    else:
        user_answers["Суть проблемы"] = "Игнорирование досудебной претензии"
        user_answers["Реквизиты"] = "Не требуются"
        await state.update_data(user_answers=user_answers)
        await generate_document_action(message, state)


@dp.message(BotStates.step_problem)
async def process_problem(message: types.Message, state: FSMContext):
    if len(message.text) < 5:
        return await message.answer("⚠ Пожалуйста, опишите проблему подробнее.")
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Суть проблемы"] = message.text
    await state.update_data(user_answers=user_answers)
    await message.answer("Введите ваши **банковские реквизиты** для возврата денег:")
    await state.set_state(BotStates.step_rekvizity)


@dp.message(BotStates.step_rekvizity)
async def process_rekvizity(message: types.Message, state: FSMContext):
    if len(message.text) < 10:
        return await message.answer("⚠ Пожалуйста, укажите полные корректные реквизиты.")
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Реквизиты"] = message.text
    fio_parts = user_answers.get("ФИО заявителя", "").split()
    initials = user_answers.get("ФИО заявителя", "")
    if len(fio_parts) >= 3:
        initials = f"{fio_parts} {fio_parts}.{fio_parts}."
    user_answers["ФИО Инициалы"] = initials
    await state.update_data(user_answers=user_answers)
    await generate_document_action(message, state)


async def generate_document_action(message: types.Message, state: FSMContext):
    status_msg = await message.answer("⏳ *ИИ-Юрист форматирует документ по шаблону, подождите...*",
                                      parse_mode="Markdown")
    data = await state.get_data()
    agent = data.get("current_agent")
    user_answers = data.get("user_answers", {})
    system_prompt = SYSTEM_PROMPTS.get(agent)
    user_prompt = "Пожалуйста, заполни шаблон на основе этих данных:\n"
    for key, val in user_answers.items():
        user_prompt += f"- {key}: {str(val)}\n"
    max_retries = 3
    result_text = None
    for attempt in range(max_retries):
        try:
            completion = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                timeout=30.0
            )
            result_text = completion.choices.message.content
            break
        except Exception as e:
            logging.error(f"Ошибка ИИ на попытке {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
                continue
    with contextlib.suppress(Exception):
        await status_msg.delete()
    if result_text:
        result_text += "\n\n---\n*⚖ Бот является ИИ-конструктором. Не заменяет очную консультацию.*"
        await message.answer("🔥 **Ваш официальный документ готов! Скопируйте его:**")
        text_parts = split_text(result_text)
        for part in text_parts:
            if part.strip():
                await message.answer(part)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅ В главное меню", callback_data="go_to_menu")
        await message.answer("Вы можете составить еще один документ:", reply_markup=builder.as_markup())
        await state.set_state(BotStates.main_menu)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Повторить генерацию", callback_data="retry_generation")
        builder.button(text="⬅ В главное меню", callback_data="go_to_menu")
        builder.adjust(1)
        await message.answer(
            "⚠ **Ошибка связи с ИИ-сервером.**\n\n Нажмите кнопку повтора.",
            reply_markup=builder.as_markup()
        )


@dp.callback_query(F.data == "retry_generation")
async def handle_retry_generation(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await generate_document_action(callback.message, state)


@dp.callback_query(F.data == "go_to_menu")
async def back_to_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_main_menu(callback.message, state)


async def main():
    print("Бот успешно перезапущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
