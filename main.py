import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

# Включаем логирование, чтобы видеть подробные отчеты в консоли
logging.basicConfig(level=logging.INFO)

# ==========================================================
# 🔑 МЕСТО ДЛЯ ВАШИХ API КЛЮЧЕЙ (ЗАПОЛНИТЕ ИХ ПЕРЕД ЗАПУСКОМ)
# ==========================================================
BOT_TOKEN = "8804861202:AAGbDign9c52_jpGfDe6YzfRgT7UwL1jA7o"
DEEPSEEK_API_KEY = "sk-6ca9bdce04844216a832a7865700d526"

# os.environ["http_proxy"] = "http://127.0.0.1:7890"
# os.environ["https_proxy"] = "http://127.0.0.1:7890"

# Создаем сессию для бота, которая автоматически подхватывает системный прокси/VPN
bot_session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher(storage=MemoryStorage())

# Инициализируем DeepSeek строго по официальному API-адресу v1

ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ==========================================================
# 📑 БАЗЫ ЗНАНИЙ ИИ-АГЕНТОВ (SYSTEM PROMPTS)
# ==========================================================
SYSTEM_PROMPTS = {
    "marketplaces": (
        "Ты — юрист по электронной коммерции в РФ. Твоя задача — составить досудебную претензию. "
        "База знаний: ст. 26.1 ЗоЗПП (Дистанционная торговля), ст. 18-22 ЗоЗПП (Брак), ст. 23 ЗоЗПП (Неустойка 1% в день). "
        "ПРАВИЛО: Перечень ТСТ №924 НЕ применяется для исправного товара в первые 7 дней дистанционной покупки (ст. 26.1). "
        "Покупатель вправе вернуть даже исправный смартфон. Требуй неустойку 1% в день, если нарушен срок возврата денег (10 дней). "
        "Не собирай паспортные данные, пиши заглушки: [Паспорт: серия ___ № ___]. Тон жесткий, официальный."
    ),
    "jkh": (
        "Ты — суровый инспектор по ЖКХ и жилищному праву РФ. Твоя цель — составить претензию к Управляющей Компании (УК). "
        "База знаний: ЖК РФ, Постановление Правительства № 354, Постановление Госстроя № 170. "
        "ПРАВИЛО: Забудь про ЗоЗПП на первом этапе. Если жалоба на отопление — норма не ниже +18°C (угловые +20°C). "
        "Если есть перерасчет по калькулятору, включи требование снизить плату на 0,15% за каждый час нарушения. "
        "При заливе/лифте ссылайся на Постановление Госстроя № 170. Не собирай паспортные данные, пиши заглушки."
    ),
    "consumer_rights": (
        "Ты — адвокат по общей защите прав потребителей РФ (офлайн-магазины, автосалоны, фитнес, онлайн-курсы). "
        "База знаний: ст. 18, 25, 32 ЗоЗПП, ст. 782 ГК РФ, Постановление Правительства № 2463. "
        "ПРАВИЛО: Для онлайн-курсов ссылайся на ст. 32 ЗоЗПП. Условия оферт 'деньги не возвращаются' ничтожны по ст. 16 ЗоЗПП. "
        "Исполнитель обязан доказать Фактически Понесенные Расходы (ФПР) на конкретного студента, иначе это ст. 1102 ГК РФ. "
        "Для исправного офлайн-товара проверяй перечень №2463 — если он там есть, возврат надлежащего качества невозможен."
    )
}


# ==========================================================
# 🔄 СОСТОЯНИЯ ДЛЯ ПОШАГОВЫХ ОПРОСОВ (FSM)
# ==========================================================
class BotStates(StatesGroup):
    waiting_for_agreement = State()
    main_menu = State()
    step_company = State()
    step_problem = State()
    step_address = State()
    step_temp = State()


# ==========================================================
# 📥 ХЕНДЛЕРЫ И ЛОГИКА ИНТЕРФЕЙСА
# ==========================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я согласен с условиями оферты", callback_data="agree_terms")

    text = (
        "⚖️ **Приветствую! Я — Твой Личный Юрист | ИИ.**\n\n"
        "Больше не нужно переплачивать юристам за простые бланки или скачивать устаревшие шаблоны. "
        "Я работаю на базе нейросети DeepSeek, знаю все тонкости законодательства РФ и составлю "
        "идеальный документ за 2 минуты!\n\n"
        "Нажимая кнопку ниже, вы соглашаетесь с условиями пользовательского соглашения и оферты. "
        "Бот является интеллектуальным конструктором и не заменяет очную консультацию адвоката."
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_agreement)


@dp.callback_query(F.data == "agree_terms", BotStates.waiting_for_agreement)
async def process_agreement(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_main_menu(callback.message, state)


async def show_main_menu(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Маркетплейсы (WB, Ozon)", callback_data="agent_marketplaces")
    builder.button(text="🏢 ЖКХ, Отопление и Дом", callback_data="agent_jkh")
    builder.button(text="🛍️ Возврат денег (Курсы, Магазины)", callback_data="agent_consumer_rights")
    builder.adjust(1)

    text = (
        "🤖 **Выберите, какую проблему нам нужно решить прямо сейчас:**\n\n"
        "🛒 **Маркетплейсы** — Вернем деньги за брак или отказ в возврате.\n"
        "🏢 **ЖКХ и Дом** — Заставим УК включить отопление, починить крышу или сделать перерасчет.\n"
        "🛍️ **Права потребителя** — Возврат денег за курсы, страховки или технику."
    )
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(BotStates.main_menu)


# ==========================================================
# 🚀 МЕХАНИКА ПЕРЕКЛЮЧЕНИЯ АГЕНТОВ И СБОР ДАННЫХ
# ==========================================================

@dp.callback_query(F.data.startswith("agent_"), BotStates.main_menu)
async def choose_agent(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    agent_name = callback.data.split("_")[1]

    await state.update_data(current_agent=agent_name, user_answers={})

    themes = {"marketplaces": "онлайн-торговле", "jkh": "жилищному праву",
              "consumer_rights": "защите прав потребителей"}
    await callback.message.answer(
        f"⚡ **Отлично, переключаюсь на базу знаний по {themes[agent_name]}!**\n\n"
        f"Пожалуйста, напишите название компании, к которой у вас претензия (или ИНН из чека):"
    )
    await state.set_state(BotStates.step_company)


@dp.message(BotStates.step_company)
async def process_company(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Название компании/УК"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Опишите кратко, что произошло? (Например: товар пришел с браком, или УК не убирает подъезд):")
    await state.set_state(BotStates.step_problem)


@dp.message(BotStates.step_problem)
async def process_problem(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Суть проблемы"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Укажите ваш адрес (Город, улица, дом, квартира) для официального бланка:")
    await state.set_state(BotStates.step_address)


@dp.message(BotStates.step_address)
async def process_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Адрес заявителя"] = message.text
    await state.update_data(user_answers=user_answers)

    if data.get("current_agent") == "jkh":
        await message.answer(
            "📊 **Калькулятор температуры:** Сколько градусов сейчас у вас в комнате? Пришлите просто число:")
        await state.set_state(BotStates.step_temp)
    else:
        await generate_document_action(message, state)


@dp.message(BotStates.step_temp)
async def process_temp(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Температура в комнате"] = f"{message.text}°C"
    await state.update_data(user_answers=user_answers)
    await generate_document_action(message, state)


# ==========================================================
# 🧠 ВЗАИМОДЕЙСТВИЕ С DEEPSEEK API
# ==========================================================

async def generate_document_action(message: types.Message, state: FSMContext):
    status_msg = await message.answer("⏳ *ИИ-Юрист изучает законы и составляет документ, подождите...*",
                                      parse_mode="Markdown")

    data = await state.get_data()
    agent = data.get("current_agent")
    user_answers = data.get("user_answers", {})

    system_prompt = SYSTEM_PROMPTS.get(agent, SYSTEM_PROMPTS["consumer_rights"])

    user_prompt = "Сформируй досудебную претензию по законам РФ на основе анкеты:\n"
    for key, val in user_answers.items():
        user_prompt += f"- {key}: {val}\n"

    if agent == "jkh" and "Температура в комнате" in user_answers:
        try:
            temp_val = float(user_answers["Температура в комнате"].replace("°C", ""))
            if temp_val < 18:
                user_prompt += f"\nДоп. инструкция: температура {temp_val}°C ниже нормы. Рассчитай неустойку по ПП №354 (0.15% в час)."
        except ValueError:
            pass

    max_retries = 3
    result_text = None

    # Попытки отправить запрос к ИИ через включенный VPN
    for attempt in range(max_retries):
        try:
            completion = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )
            result_text = completion.choices[0].message.content
            break
        except Exception as e:
            logging.error(f"Попытка {attempt + 1} провалилась: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)  # Ждем 3 секунды перед повтором
            continue

    try:
        if not result_text:
            raise Exception("Не удалось получить ответ от DeepSeek.")

        result_text += "\n\n---\n*⚖️ Бот является ИИ-конструктором. Не заменяет очную консультацию.*"

        await status_msg.delete()
        await message.answer("🔥 **Ваш документ готов! Скопируйте его ниже:**")
        await message.answer(result_text)

        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В главное меню", callback_data="go_to_menu")
        await message.answer("Вы можете составить новый документ:", reply_markup=builder.as_markup())
        await state.set_state(BotStates.main_menu)

    except Exception:
        await status_msg.delete()

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Попробовать еще раз", callback_data="retry_generation")
        builder.button(text="⬅️ В главное меню", callback_data="go_to_menu")
        builder.adjust(1)

        await message.answer(
            "⚠️ **Сервер ИИ сейчас недоступен (ошибка соединения).**\n\n"
            "Убедитесь, что ваш **VPN включен**. Ваши введенные данные полностью сохранены! "
            "Пожалуйста, нажмите кнопку ниже, чтобы повторить генерацию.",
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


# ==========================================================
# 🏁 ЗАПУСК БОТА
# ==========================================================
async def main():
    print("Бот успешно запущен и готов работать через DeepSeek!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
