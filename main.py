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

# Включаем логирование
logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8804861202:AAGbDign9c52_jpGfDe6YzfRgT7UwL1jA7o")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-6ca9bdce04844216a832a7865700d526")

bot_session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher(storage=MemoryStorage())

# Инициализируем DeepSeek v1
ai_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://deepseek.com")

# ==========================================================
# 📑 ЭТАЛОННЫЕ ШАБЛОНЫ ДЛЯ DEEPSEEK (SYSTEM PROMPTS)
# ==========================================================
SYSTEM_PROMPTS = {
    "brak": (
        "Ты — профессиональный ИИ-юрист. Твоя единственная задача — строго по предоставленным фактам пользователя "
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


# ==========================================================
# 🔄 ОБНОВЛЕННЫЕ СОСТОЯНИЯ (FSM)
# ==========================================================
class BotStates(StatesGroup):
    waiting_for_agreement = State()
    main_menu = State()
    step_fio = State()
    step_user_address = State()
    step_company = State()
    step_company_address = State()
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
# 📥 ХЕНДЛЕРЫ ИНТЕРФЕЙСА
# ==========================================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я согласен с условиями", callback_data="agree_terms")
    text = (
        "⚖ **Приветствую! Я — Ваш ИИ-Юрист.**\n\n"
        "Я помогу вам составить официальные документы для возврата денег и защиты ваших прав.\n"
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


# ==========================================================
# 🚀 СБОР ДАННЫХ ПОД НОВЫЕ ДОКУМЕНТЫ
# ==========================================================
@dp.callback_query(F.data.startswith("agent_"), BotStates.main_menu)
async def choose_agent(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    agent_name = callback.data.split("_")[1]
    await state.update_data(current_agent=agent_name, user_answers={})

    await callback.message.answer("Введите ваши **ФИО полностью** (для шапки документа):")
    await state.set_state(BotStates.step_fio)


@dp.message(BotStates.step_fio)
async def process_fio(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["ФИО заявителя"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Введите **ваш адрес** (для направления ответа):")
    await state.set_state(BotStates.step_user_address)


@dp.message(BotStates.step_user_address)
async def process_user_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Адрес заявителя"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Введите **название магазина / компании** (например, ООО 'Вайлдберриз'):")
    await state.set_state(BotStates.step_company)


@dp.message(BotStates.step_company)
async def process_company(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Название Продавца"] = message.text
    await state.update_data(user_answers=user_answers)

    if data.get("current_agent") == "rospotreb":
        # Для Роспотребнадзора адрес магазина не обязателен в шапке, переходим к товару
        user_answers["Адрес Продавца"] = "Не указан"
        await state.update_data(user_answers=user_answers)
        await message.answer("Какой **товар** или услугу вы приобрели?")
        await state.set_state(BotStates.step_product)
    else:
        await message.answer("Введите **юридический или фактический адрес магазина**:")
        await state.set_state(BotStates.step_company_address)


@dp.message(BotStates.step_company_address)
async def process_company_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Адрес Продавца"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Укажите **наименование товара** (например: Смартфон Apple iPhone 15):")
    await state.set_state(BotStates.step_product)


@dp.message(BotStates.step_product)
async def process_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Наименование Товара"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Укажите **стоимость товара** в рублях (только цифры):")
    await state.set_state(BotStates.step_price)


@dp.message(BotStates.step_price)
async def process_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Стоимость"] = message.text
    await state.update_data(user_answers=user_answers)

    if data.get("current_agent") == "brak":
        await message.answer("Опишите **недостатки товара** (что именно сломалось или работает не так?):")
        await state.set_state(BotStates.step_problem)
    elif data.get("current_agent") == "kačestvo":
        await message.answer("Укажите причину, почему товар не подошел (например: не подошел по размеру и фасону):")
        await state.set_state(BotStates.step_problem)
    else:
        # Для Роспотребнадзора сразу переходим к финальному шагу
        user_answers["Суть проблемы"] = "Игнорирование досудебной претензии"
        user_answers["Реквизиты"] = "Не требуются"
        await state.update_data(user_answers=user_answers)
        await generate_document_action(message, state)


@dp.message(BotStates.step_problem)
async def process_problem(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Суть проблемы"] = message.text
    await state.update_data(user_answers=user_answers)

    await message.answer("Введите ваши **банковские реквизиты** для возврата денег (БИК, номер счета, банк):")
    await state.set_state(BotStates.step_rekvizity)


@dp.message(BotStates.step_rekvizity)
async def process_rekvizity(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_answers = data.get("user_answers", {})
    user_answers["Реквизиты"] = message.text

    # Делаем инициалы для подписи автоматически из ФИО
    fio_parts = user_answers.get("ФИО заявителя", "").split()
    initials = user_answers.get("ФИО заявителя", "")
    if len(fio_parts) >= 3:
        initials = f"{fio_parts[0]} {fio_parts[1][0]}.{fio_parts[2][0]}."
    user_answers["ФИО Инициалы"] = initials

    await state.update_data(user_answers=user_answers)
    await generate_document_action(message, state)


# ==========================================================
# 🧠 ОТПРАВКА ДАННЫХ В DEEPSEEK
# ==========================================================
async def generate_document_action(message: types.Message, state: FSMContext):
    status_msg = await message.answer("⏳ *ИИ-Юрист форматирует документ по шаблону, подождите...*",
                                      parse_mode="Markdown")

    data = await state.get_data()
    agent = data.get("current_agent")
    user_answers = data.get("user_answers", {})
    system_prompt = SYSTEM_PROMPTS.get(agent)

    user_prompt = "Пожалуйста, заполни шаблон на основе этих данных:\n"
    for key, val in user_answers.items():
        user_prompt += f"- {key}: {val}\n"

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
                temperature=0.1  # Низкая температура, чтобы ИИ строго следовал тексту и не фантазировал
            )
            result_text = completion.choices[0].message.content
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
            "⚠ **Ошибка связи с DeepSeek.**\n\nПроверьте настройки сети/VPN на сервере и нажмите кнопку повтора.",
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
    print("Бот успешно перезапущен на новые шаблоны!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
