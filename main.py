import logging
import asyncio
import fastf1
import json
import os
import feedparser
import aiohttp
from googletrans import Translator
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters.command import Command
from aiogram.types import FSInputFile, InputMediaPhoto
from datetime import datetime, timedelta,date
from aiogram.exceptions import TelegramBadRequest


def find_image(filename):
    for root, dirs, files in os.walk('.'):
        if filename in files:
            return os.path.join(root, filename)
    return None


TOKEN = "7509468581:AAFEBq-zWoYOcZoG5cUfi28DXPrEOFxSuig"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

user_data = {}

cache_dir = '/opt/render/project/src/F1Pulse'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

fastf1.Cache.enable_cache(cache_dir)

logging.basicConfig(level=logging.INFO)



async def send_main_menu(chat_id, language):
    buttons = [
        [
            InlineKeyboardButton(text="🏁 Гран-при" if language == "ru" else "🏁 Grand Prix", callback_data="grand_prix"),
            InlineKeyboardButton(text="🏆 Чемпионат" if language == "ru" else "🏆 Championship", callback_data="championship")
        ],
        [
            InlineKeyboardButton(text="🛠️ Паддок" if language == "ru" else "🛠️ Paddock", callback_data="paddock"),
            InlineKeyboardButton(text="📰 Новости" if language == "ru" else "📰 News", callback_data="f1_news")
        ],
        [InlineKeyboardButton(text="🔮 Прогнозы" if language == "ru" else "🔮 Predictions", callback_data="predictions")],
        [InlineKeyboardButton(text="⚙️ Настройки" if language == "ru" else "⚙️ Settings", callback_data="settings")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Find and load the image
    image_path = find_image("main_menu.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        await bot.send_photo(
            chat_id,
            photo=photo,
            reply_markup=keyboard
        )
    else:
        # Fallback to text-only message if image is not found
        await bot.send_message(
            chat_id,
            "Главное меню F1" if language == "ru" else "F1 Main Menu",
            reply_markup=keyboard
        )



@router.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id

    # Если пользователь новый, создаем запись с языком по умолчанию
    if user_id not in user_data:
        user_data[user_id] = {"language": "en"}  # Установить язык по умолчанию при первом запуске
        await send_language_selection(message.chat.id)  # Показать выбор языка
    else:
        # Если язык уже сохранен, открываем главное меню
        language = user_data[user_id]["language"]
        await send_main_menu(message.chat.id, language)

async def send_language_selection(chat_id):
    buttons = [
        [InlineKeyboardButton(text="English", callback_data="set_lang_en")],
        [InlineKeyboardButton(text="Русский", callback_data="set_lang_ru")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(chat_id, "Please select your language", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("set_lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[2]

    # Обновляем язык пользователя в данных
    user_data[user_id]["language"] = lang_code
    await save_user_data()  # Сохраняем изменения

    await callback.answer("Language updated!" if lang_code == 'en' else 'Язык обновлен!')
    await callback.message.delete()
    await send_main_menu(callback.message.chat.id, lang_code)


# Путь к файлу для хранения данных
DATA_FILE = 'user_data.json'

# Загрузка данных при запуске бота
def load_user_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as file:
                data = json.load(file)
                # Преобразуем строковые ключи обратно в целые числа
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"Error loading user data: {e}")
            return {}
    return {}

# Сохранение данных
async def save_user_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving user data: {e}")

async def send_text_menu(callback, language, keyboard):
    text = "\u200B"  # Невидимый символ
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)


async def fetch_championship_data(year, championship_type):
    base_url = "http://api.jolpi.ca/ergast/f1"
    endpoint = "driverstandings" if championship_type == "drivers" else "constructorstandings"
    url = f"{base_url}/{year}/{endpoint}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None


@router.callback_query(lambda c: c.data == "championship")
async def show_championship_archive(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    buttons = [
        [InlineKeyboardButton(text="2009-2013", callback_data="seasons_2009_2013")],
        [InlineKeyboardButton(text="2014-2017", callback_data="seasons_2014_2017")],
        [InlineKeyboardButton(text="2018-2022", callback_data="seasons_2018_2022")],
        [InlineKeyboardButton(text="2023-2025", callback_data="seasons_2023_2025")],
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "Выберите период:" if language == "ru" else "Select a period:"

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "there is no text in the message to edit" in str(e):
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.answer(text, reply_markup=keyboard)



@router.callback_query(lambda c: c.data.startswith("championship_"))
async def show_championship_type(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    year = callback.data.split("_")[1]
    buttons = [
        [
            InlineKeyboardButton(
                text="🏆 Личный зачет" if language == "ru" else "🏆 Drivers' Championship",
                callback_data=f"drivers_championship_{year}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏆 Кубок конструкторов" if language == "ru" else "🏆 Constructors' Championship",
                callback_data=f"constructors_championship_{year}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="championship")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"Выберите тип чемпионата для {year} года:" if language == "ru" else f"Select championship type for {year}:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("seasons_"))
async def show_seasons(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    _, start_year, end_year = callback.data.split("_")
    seasons = range(int(start_year), int(end_year) + 1)
    buttons = [
        [InlineKeyboardButton(text=f"{year}", callback_data=f"championship_{year}")]
        for year in seasons
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="championship")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "📅 Выберите сезон:" if language == "ru" else "📅 Select a season:"
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("drivers_championship_"))
async def show_drivers_championship(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    year = callback.data.split("_")[2]
    await callback.message.edit_text("Загрузка результатов..." if language == "ru" else "Loading results...")

    data = await fetch_championship_data(year, "drivers")
    if data and "MRData" in data and "StandingsTable" in data["MRData"]:
        standings = data["MRData"]["StandingsTable"]["StandingsLists"]
        if standings and standings[0]["DriverStandings"]:
            standings = standings[0]["DriverStandings"]
            text = f"🏆 {'Личный зачет' if language == 'ru' else 'Drivers Championship'} {year}:\n\n"
            for driver in standings:
                position = driver.get('position', 'N/A')  # Используем get для безопасного доступа
                name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
                nationality = driver['Driver']['nationality']
                points = driver['points']
                flag = get_flag_emoji(nationality)
                text += f"{position}. {flag}{name} ({points})\n"
        else:
            text = "Данные недоступны" if language == "ru" else "Data unavailable"
    else:
        text = "Данные недоступны" if language == "ru" else "Data unavailable"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data=f"championship_{year}")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("constructors_championship_"))
async def show_constructors_championship(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    year = callback.data.split("_")[2]
    await callback.message.edit_text("Загрузка результатов..." if language == "ru" else "Loading results...")

    data = await fetch_championship_data(year, "constructors")
    if data and "MRData" in data and "StandingsTable" in data["MRData"]:
        standings = data["MRData"]["StandingsTable"]["StandingsLists"]
        if standings and standings[0]["ConstructorStandings"]:
            standings = standings[0]["ConstructorStandings"]
            text = f"🏆 {'Кубок конструкторов' if language == 'ru' else 'Constructors Championship'} {year}:\n\n"
            for constructor in standings:
                position = constructor.get('position', 'N/A')  # Используем get для безопасного доступа
                name = constructor['Constructor']['name']
                nationality = constructor['Constructor']['nationality']
                points = constructor['points']
                flag = get_flag_emoji(nationality)
                text += f"{position}. {flag}{name} ({points})\n"
        else:
            text = "Данные недоступны" if language == "ru" else "Data unavailable"
    else:
        text = "Данные недоступны" if language == "ru" else "Data unavailable"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data=f"championship_{year}")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)


def get_flag_emoji(nationality):
    # Словарь соответствия национальностей и флагов
    flags = {
        "Dutch": "🇳🇱", "British": "🇬🇧", "Monegasque": "🇲🇨", "Australian": "🇦🇺",
        "Spanish": "🇪🇸", "Mexican": "🇲🇽", "French": "🇫🇷", "German": "🇩🇪",
        "Japanese": "🇯🇵", "Canadian": "🇨🇦", "Danish": "🇩🇰", "Thai": "🇹🇭",
        "Chinese": "🇨🇳", "Finnish": "🇫🇮", "American": "🇺🇸", "Italian": "🇮🇹",
        "Austrian": "🇦🇹", "Swiss": "🇨🇭", "New Zealander": '🇳🇿', "Polish": "🇵🇱",
        "Russian": "🇷🇺", "Brazilian": "🇧🇷", "Belgian": "🇧🇪", "Swedish": "🇸🇪",
        "Venezuelan": "🇻🇪", "Indian": "🇮🇳", "Malaysian": "🇲🇾", "Indonesian": "🇮🇩",

    }
    return flags.get(nationality, "")


async def fetch_weather_data():
    url = "https://api.openf1.org/v1/weather"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                logging.info(f"Weather data fetched: {data}")
                return data
            else:
                logging.error(f"Failed to fetch weather data: {response.status}")
                return None


@router.callback_query(lambda c: c.data == "weather")
async def show_weather(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]

    try:
        await callback.message.delete()
        loading_message = await bot.send_message(callback.message.chat.id,
                                                 "Загрузка результатов..." if language == "ru" else "Loading results...")

        weather_data = await fetch_weather_data()

        if weather_data:
            text = format_weather_data(weather_data, language)
        else:
            text = "Данные о погоде недоступны" if language == "ru" else "Weather data unavailable"
    except Exception as e:
        logging.error(f"Error fetching weather data: {e}")
        text = "Ошибка при получении данных о погоде" if language == "ru" else "Error fetching weather data"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="grand_prix")]
    ])

    try:
        await loading_message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            await loading_message.delete()
            await bot.send_message(callback.message.chat.id, text, reply_markup=keyboard)


def format_weather_data(weather_data, language):
    if not weather_data or not isinstance(weather_data, list) or len(weather_data) == 0:
        return "Ошибка формата данных о погоде." if language == "ru" else "Weather data format error."

    latest_weather = weather_data[-1]

    # Получаем информацию о трассе
    meeting_key = latest_weather.get('meeting_key', 'N/A')

    # Здесь нужно добавить словарь для сопоставления meeting_key с названиями трасс
    track_names = {
        1252: {"ru": "Яс Марина", "en": "Yas Marina"},
        # Добавьте другие трассы по мере необходимости
    }

    track_name = track_names.get(meeting_key, {}).get(language, "Unknown Track")

    air_temp = latest_weather.get('air_temperature', 'N/A')
    humidity = latest_weather.get('humidity', 'N/A')
    rainfall = latest_weather.get('rainfall', 'N/A')
    wind_speed = latest_weather.get('wind_speed', 'N/A')
    track_temp = latest_weather.get('track_temperature', 'N/A')
    pressure = latest_weather.get('pressure', 'N/A')
    wind_direction = latest_weather.get('wind_direction', 'N/A')

    if language == "ru":
        return (f"🌤️ Погода на трассе {track_name}:\n\n"
                f"🌡️ Температура воздуха: {air_temp}°C\n"
                f"🛣️ Температура трассы: {track_temp}°C\n"
                f"💧 Влажность: {humidity}%\n"
                f"🌧️ Вероятность осадков: {rainfall}%\n"
                f"💨 Скорость ветра: {wind_speed} км/ч\n"
                f"🧭 Направление ветра: {wind_direction}°\n"
                f"🔬 Давление: {pressure} гПа")
    else:
        return (f"🌤️ Weather at {track_name} track:\n\n"
                f"🌡️ Air temperature: {air_temp}°C\n"
                f"🛣️ Track temperature: {track_temp}°C\n"
                f"💧 Humidity: {humidity}%\n"
                f"🌧️ Rainfall probability: {rainfall}%\n"
                f"💨 Wind speed: {wind_speed} km/h\n"
                f"🧭 Wind direction: {wind_direction}°\n"
                f"🔬 Pressure: {pressure} hPa")



@router.callback_query(lambda c: c.data == "grand_prix")
async def show_grand_prix_menu(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    buttons = [
    [
        InlineKeyboardButton(text="📅 Расписание" if language == "ru" else "📅 Schedule", callback_data="schedule"),
        InlineKeyboardButton(text="🏁 Недавний GP" if language == "ru" else "🏁 Last GP",callback_data="last_results"),
    ],
    [
        InlineKeyboardButton(text="🌤️ Погода" if language == "ru" else "🌤️ Weather", callback_data="weather"),
        InlineKeyboardButton(text="📚 Архив" if language == "ru" else "📚 Archive", callback_data="archive"),
    ],
    [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]

    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    image_path = find_image("grand_prix.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        try:
            # Пытаемся отредактировать существующее сообщение
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo),
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            if "there is no media in the message to edit" in str(e).lower():
                # Если нет медиа для редактирования, удаляем старое сообщение и отправляем новое
                await callback.message.delete()
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=photo,
                    reply_markup=keyboard
                )
            else:
                # Если возникла другая ошибка, пробуем отправить только текст
                await callback.message.edit_text( reply_markup=keyboard)
    else:
        # Если изображение не найдено, отправляем только текст
        try:
            await callback.message.edit_text( reply_markup=keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                # Если возникла другая ошибка, отправляем новое сообщение
                await callback.message.delete()
                await callback.message.answer( reply_markup=keyboard)



@router.callback_query(lambda c: c.data.startswith("set_lang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[2]
    user_data[user_id]["language"] = lang_code
    await callback.answer("Language updated!" if lang_code == 'en' else 'Язык обновлен!')
    await callback.message.delete()
    await send_main_menu(callback.message.chat.id, lang_code)


@router.callback_query(lambda c: c.data == "archive")
async def show_archive_seasons(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    seasons = [2021, 2023, 2024, 2025]
    buttons = [
        [InlineKeyboardButton(text=f"Сезон {year}" if language == "ru" else f"Season {year}",
                              callback_data=f"season_{year}")]
        for year in seasons
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="grand_prix")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "Выберите сезон:" if language == "ru" else "Select a season:"

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        elif "message to edit not found" in str(e).lower() or "there is no text in the message to edit" in str(
                e).lower():
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            raise


@router.callback_query(lambda c: c.data.startswith("season_"))
async def show_season_races(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    year = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "Загрузка результатов..." if language == "ru" else "Loading results..."
    )
    try:
        if year == 2025:
            # Проверка доступности данных для 2025 года
            current_year = datetime.now().year
            if current_year < 2025:
                raise Exception("Data for 2025 is not available yet")

        schedule = fastf1.get_event_schedule(year)
        # Фильтруем гонки, исключая предсезонные тесты
        race_schedule = schedule[schedule['EventFormat'] == 'conventional']

        buttons = [
            [InlineKeyboardButton(text=f"{race['RoundNumber']}. {race['EventName']}",
                                  callback_data=f"race_{year}_{race['RoundNumber']}")]
            for _, race in race_schedule.iterrows()
        ]
        buttons.append(
            [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="archive")]
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(
            f"Гонки сезона {year}:" if language == "ru" else f"Races of {year} season:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error loading season data: {e}")
        error_message = "Данные о сезоне 2025 пока недоступны." if year == 2025 else "Ошибка загрузки данных сезона."
        error_message = error_message if language == "ru" else "Data for 2025 season is not available yet." if year == 2025 else "Error loading season data."
        await callback.message.edit_text(
            error_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="archive")]
            ])
        )


@router.callback_query(lambda c: c.data.startswith("race_"))
async def show_race_details(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    _, year, round_number = callback.data.split("_")
    year = int(year)
    round_number = int(round_number)

    await callback.message.edit_text(
        "Загрузка результатов..." if language == "ru" else "Loading results..."
    )

    try:
        # Загружаем данные с помощью FastF1
        session = fastf1.get_session(year, round_number, 'R')
        session.load()

        # Формирование информации о гонке
        results = session.results
        podium = results.iloc[:3][['DriverNumber', 'FullName', 'TeamName']]
        fastest_lap = session.laps.pick_fastest()

        race_info = f"🏎️ {session.event['EventName']} {year}\n"
        race_info += f"📅 {session.date.strftime('%d.%m.%Y')}\n\n"
        race_info += "Подиум:\n" if language == "ru" else "Podium:\n"
        for i, (_, driver) in enumerate(podium.iterrows(), 1):
            race_info += f"{i}. {driver['FullName']} ({driver['TeamName']})\n"

        # Форматируем информацию о быстром круге
        fastest_lap_time = fastest_lap['LapTime'].total_seconds()
        minutes = int(fastest_lap_time // 60)
        seconds = int(fastest_lap_time % 60)
        milliseconds = int((fastest_lap_time % 1) * 1000)
        race_info += (
            f"\n⏱ {'Быстрый круг' if language == 'ru' else 'Fastest lap'}: {fastest_lap['Driver']} "
            f"- {minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        )

        # Автоматическое создание ссылки на видео
        race_name_slug = session.event['EventName'].replace(" ", "_").lower()
        youtube_url = f"https://www.youtube.com/results?search_query={year}_{race_name_slug}_highlights"

        # Создаем клавиатуру с кнопкой YouTube
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="▶️ Основные моменты гонки" if language == 'ru' else "▶️ Race highlights",
                url=youtube_url
            )],
            [InlineKeyboardButton(
                text="🔙 Назад" if language == 'ru' else "🔙 Back",
                callback_data=f"season_{year}"
            )]
        ])

        # Отправляем результаты
        await callback.message.edit_text(
            race_info,
            reply_markup=keyboard
        )

    except Exception as e:
        print(f"Error loading race data: {e}")
        await callback.message.edit_text(
            "Ошибка загрузки данных гонки" if language == "ru" else "Error loading race data",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔙 Назад" if language == 'ru' else "🔙 Back",
                    callback_data=f"season_{year}"
                )]
            ])
        )


async def fetch_f1_news(language):
    feed_url = "https://www.racefans.net/feed/"
    feed = await asyncio.to_thread(feedparser.parse, feed_url)

    translator = Translator()
    news_items = []
    for entry in feed.entries[:3]:  # Берем только 3 последние новости
        pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S +0000")
        title = entry.title if language == 'en' else translator.translate(entry.title, dest='ru').text
        news_items.append({
            "title": title,
            "link": entry.link,
            "published": pub_date,
            "image_url": entry.media_content[0]['url'] if 'media_content' in entry else None
        })

    return news_items


@router.callback_query(lambda c: c.data == "f1_news")
async def show_f1_news(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]

    # Показать сообщение о загрузке данных
    loading_message = await bot.send_message(callback.message.chat.id,
        "Загрузка данных..." if language == "ru" else "Loading data...")

    news = await fetch_f1_news(language)

    # Удалить старое меню
    await callback.message.delete()

    sent_messages = []
    for item in news[:3]:  # Показать только 3 последние новости
        caption = f"📰 {item['title']}\n\n📅 {item['published']}\n\n🔗 {item['link']}"

        try:
            if item['image_url']:
                message = await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=item['image_url'],
                    caption=caption,
                    parse_mode='HTML'
                )
            else:
                message = await bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=caption,
                    parse_mode='HTML'
                )
            sent_messages.append(message.message_id)
        except Exception as e:
            print(f"Error sending news: {e}")

    # Удалить сообщение о загрузке
    await loading_message.delete()

    buttons = [[InlineKeyboardButton(text="🔙" if language == "ru" else "🔙",
                                     callback_data=f"delete_news_{','.join(map(str, sent_messages))}")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="Назад:" if language == "ru" else "Back:",
        reply_markup=keyboard
    )




@router.callback_query(lambda c: c.data.startswith("delete_news_"))
async def delete_news_and_return(callback: types.CallbackQuery):
    message_ids = callback.data.split("_")[2].split(",")
    for message_id in message_ids:
        try:
            await bot.delete_message(callback.message.chat.id, int(message_id))
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")

    await callback.message.delete()
    await send_main_menu(callback.message.chat.id, user_data[callback.from_user.id]["language"])




race_cache = {}
CACHE_EXPIRATION = timedelta(hours=1)


LAST_RACE_FILE = 'last_race.json'

# Функция для загрузки данных о последней гонке
def load_last_race():
    if os.path.exists(LAST_RACE_FILE):
        with open(LAST_RACE_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return None

# Функция для сохранения данных о последней гонке
def save_last_race(race_data):
    with open(LAST_RACE_FILE, 'w', encoding='utf-8') as file:
        json.dump(race_data, file, ensure_ascii=False, indent=4)


NOTIFICATIONS_FILE = 'notifications.json'

# Функция для загрузки данных о уведомлениях
def load_notifications():
    if os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

# Функция для сохранения данных о уведомлениях
def save_notifications(notifications):
    with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as file:
        json.dump(notifications, file, ensure_ascii=False, indent=4)


@router.callback_query(lambda c: c.data == "last_results")
async def show_last_results(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]

    # Удаляем старое меню
    await callback.message.delete()

    # Показываем сообщение о загрузке
    loading_message = await bot.send_message(callback.message.chat.id,
                                             "Загрузка результатов..." if language == "ru" else "Loading results...")

    race_data = await get_race_results()

    if race_data and race_data["completed"]:
        formatted_results = format_race_results(race_data, language)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="grand_prix")]
        ])
        await loading_message.edit_text(formatted_results, reply_markup=keyboard, parse_mode="HTML")
    else:
        error_text = "Извините, результаты последней гонки недоступны." if language == "ru" else "Sorry, the results of the last race are not available."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="grand_prix")]
        ])
        await loading_message.edit_text(error_text, reply_markup=keyboard)


async def get_race_results():
    try:
        current_year = datetime.now().year
        schedule = fastf1.get_event_schedule(current_year)
        last_race = schedule[schedule['EventDate'] < datetime.now()].iloc[-1]
        session = fastf1.get_session(current_year, last_race['EventName'], 'R')
        await asyncio.to_thread(session.load)
        results = session.results

        fetched_results = {
            "name": last_race['EventName'],
            "date": last_race['EventDate'].strftime("%Y-%m-%d"),
            "completed": True,
            "results": [
                {
                    "position": int(result['Position']) if isinstance(result['Position'], (int, float)) else result[
                        'PositionText'],
                    "driver": result.get('FullName', 'Unknown Driver'),
                    "team": result.get('TeamName', 'Unknown Team'),
                    "points": int(result.get('Points', 0)),
                }
                for _, result in results.iterrows()
            ]
        }
        return fetched_results
    except Exception as e:
        print(f"Ошибка получения результатов гонки: {e}")
        return None


async def send_favorite_notifications(race_results):
    notifications = load_notifications()  # Загружаем существующие уведомления
    for user_id, data in user_data.items():
        favorite_driver = data.get("favorite_driver")
        favorite_team = data.get("favorite_team")

        # Проверяем, выбраны ли любимые пилоты или команды
        if not favorite_driver and not favorite_team:
            continue  # Пропускаем пользователей без выбора

        language = data["language"]

        # Форматируем название гонки и дату
        race_name = race_results["name"]
        race_date_obj = datetime.strptime(race_results["date"], "%Y-%m-%d")
        race_date = (
            race_date_obj.strftime("%d %B %Y").replace("December", "Декабря") if language == "ru"
            else race_date_obj.strftime("%B %d, %Y")
        )

        # Заголовок уведомления
        header = (
            f"🏎️ Недавние результаты в гонке {race_name}:\nДата: {race_date}\n\n"
            if language == "ru"
            else f"🏎️ Recent results in the {race_name}:\nDate: {race_date}\n\n"
        )

        driver_message = ""
        if favorite_driver:
            driver_result = next((r for r in race_results["results"] if r["driver"] == favorite_driver), None)
            if driver_result:
                position = driver_result["position"]
                points = driver_result["points"]
                if position in ["DNF", "DSQ"]:
                    driver_message = (
                        f"👤 Ваш любимый пилот {favorite_driver} не финишировал (статус: {position}).\n"
                        if language == "ru"
                        else f"👤 Your favorite driver {favorite_driver} did not finish (status: {position}).\n"
                    )
                elif points > 0:
                    driver_message = (
                        f"👤 Ваш любимый пилот {favorite_driver} занял {position} место и заработал {points} очков.\n"
                        if language == "ru"
                        else f"👤 Your favorite driver {favorite_driver} finished {position}th and earned {points} points.\n"
                    )
                else:
                    driver_message = (
                        f"👤 Ваш любимый пилот {favorite_driver} занял {position} место.\n"
                        if language == "ru"
                        else f"👤 Your favorite driver {favorite_driver} finished {position}th.\n"
                    )

        team_message = ""
        if favorite_team:
            team_results = [r for r in race_results["results"] if r["team"] == favorite_team]
            total_points = sum(r["points"] for r in team_results)
            team_message = (
                f"🏁 Ваша любимая команда {favorite_team} заработала {total_points} очков в этой гонке."
                if language == "ru"
                else f"🏁 Your favorite team {favorite_team} earned {total_points} points in this race."
            )

        full_message = header + driver_message + team_message

        try:
            message = await bot.send_message(user_id, full_message)
            # Сохраняем время отправки сообщения
            notifications[user_id] = {
                'message_id': message.message_id,
                'timestamp': datetime.now().isoformat(),
                'race_name': race_name,
                'race_date': race_results['date']
            }
            save_notifications(notifications)  # Сохраняем обновленные данные о уведомлениях
        except Exception as e:
            print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")


async def delete_old_notifications():
    notifications = load_notifications()  # Загружаем существующие уведомления
    current_time = datetime.now()

    for user_id, data in list(notifications.items()):
        timestamp = datetime.fromisoformat(data['timestamp'])

        # Проверяем, прошло ли 48 часов с момента отправки
        if current_time - timestamp > timedelta(hours=48):
            try:
                await bot.delete_message(user_id, data['message_id'])  # Удаляем сообщение
                del notifications[user_id]  # Удаляем запись из словаря
            except Exception as e:
                print(f"Ошибка удаления сообщения у пользователя {user_id}: {e}")

    save_notifications(notifications)  # Сохраняем обновленные данные о уведомлениях


def format_race_results(results, language):
    if not results or not results.get("results"):
        return "Извините, результаты гонки недоступны." if language == "ru" else "Sorry, race results are not available."

    title = "Результаты" if language == "ru" else "Results"
    date_obj = datetime.strptime(results['date'], "%Y-%m-%d")

    if language == "ru":
        formatted_date = date_obj.strftime("%d %B %Y").replace("December", "Декабря")
    else:
        formatted_date = date_obj.strftime("%B %d %Y")

    header = f"🏎️ {title}: {results['name']}\n📅 {formatted_date}\n\n"




    team_logos = {
        "McLaren": "🟠",
        "Ferrari": "🔴",
        "Red Bull Racing": "🔵",
        "Mercedes": "⚪️",
        "Aston Martin": "💚",
        "Alpine": "💙",
        "Haas F1 Team": "⚪️",
        "RB": "🔵",
        "Williams": "🔵",
        "Kick Sauber": "💚"
    }




    medals = ["🥇", "🥈", "🥉"]
    table = ""
    for i, result in enumerate(results["results"], 1):
        position = medals[i - 1] if i <= 3 else f"{i:2d}."
        driver = result['driver']
        team = result['team']
        team_logo = team_logos.get(team, "")
        points = result['points']

        if i <= 10:
            table += f"{position} <b>{driver}</b>\n{team_logo}{team} | {points} {'очков' if language == 'ru' else 'pts'}\n\n"
        else:
            table += f"{position} <b>{driver}</b>\n{team_logo}{team}\n\n"

    return header + table


@router.callback_query(lambda c: c.data == "paddock")
async def show_technical_menu(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    buttons = [
        [
            InlineKeyboardButton(text="👥 Пилоты" if language == "ru" else "👥 Drivers", callback_data="drivers"),
            InlineKeyboardButton(text="🏎️ Болиды" if language == "ru" else "🏎️ Cars", callback_data="tech_cars")
        ],
        [
            InlineKeyboardButton(text="🔧 Двигатели" if language == "ru" else "🔧 Engines", callback_data="tech_engines"),
            InlineKeyboardButton(text="📏 Регламент" if language == "ru" else "📏 Regulations", callback_data="tech_regulations")
        ],
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    image_path = find_image("paddock.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        try:
            await callback.message.delete()
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error sending photo: {e}")
            await callback.message.edit_text(reply_markup=keyboard)
    else:
        await callback.message.edit_text(reply_markup=keyboard)



@router.callback_query(lambda c: c.data == "tech_cars")
async def show_tech_cars(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]
    text = ("🏎️ Информация о болидах Формулы 1:\n\n"
            "• Шасси: Монокок из углеродного волокна\n"
            "• Вес: Минимум 798 кг с пилотом\n"
            "• Размеры: Длина до 5.6 м, ширина до 2 м\n"
            "• Аэродинамика: Переднее и заднее антикрыло, днище с эффектом земли") if language == "ru" else \
        ("🏎️ Formula 1 Car Information:\n\n"
         "• Chassis: Carbon fiber monocoque\n"
         "• Weight: Minimum 798 kg including driver\n"
         "• Dimensions: Up to 5.6 m long, 2 m wide\n"
         "• Aerodynamics: Front and rear wings, ground effect floor")


    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="paddock")]
    ])

    image_path = find_image("car.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        await callback.message.delete()
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)



@router.callback_query(lambda c: c.data == "tech_engines")
async def show_tech_engines(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]
    text = ("🔧 Информация о двигателях Формулы 1:\n\n"
            "• Тип: 1.6 л V6 турбо-гибрид\n"
            "• Мощность: Около 1000 л.с.\n"
            "• Обороты: До 15,000 об/мин\n"
            "• Гибридная система: MGU-K и MGU-H") if language == "ru" else \
        ("🔧 Formula 1 Engine Information:\n\n"
         "• Type: 1.6L V6 turbo-hybrid\n"
         "• Power: Around 1000 hp\n"
         "• RPM: Up to 15,000 rpm\n"
         "• Hybrid system: MGU-K and MGU-H")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="paddock")]
    ])
    image_path = find_image("f1_engine.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        await callback.message.delete()
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "tech_regulations")
async def show_tech_regulations(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]
    text = ("📏 Технический регламент Формулы 1 2025:\n\n"
            "• Ограничение бюджета: $135 млн на сезон\n"
            "• Аэродинамика: Новые ограничения по тестам в аэродинамической трубе\n"
            "• Двигатели: Увеличение доли экологичного топлива до 100%\n"
            "• Шины: Специальные составы для спринт-гонок\n"
            "• Безопасность: Усиленная защита кокпита и боковых понтонов\n"
            "• Вес: Минимальный вес болида снижен до 795 кг") if language == "ru" else \
        ("📏 Formula 1 Technical Regulations 2025:\n\n"
         "• Budget cap: $135 million per season\n"
         "• Aerodynamics: New wind tunnel testing restrictions\n"
         "• Engines: Increased sustainable fuel ratio to 100%\n"
         "• Tires: Special compounds for sprint races\n"
         "• Safety: Enhanced cockpit and sidepod protection\n"
         "• Weight: Minimum car weight reduced to 795 kg")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Полный регламент" if language == "ru" else "📋 Full Regulations",
            url="https://www.fia.com/regulation/category/110"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад" if language == "ru" else "🔙 Back",
            callback_data="paddock"
        )]
    ])

    image_path = find_image("f1_regulations.jpg")
    if image_path:
        photo = FSInputFile(image_path)
        await callback.message.delete()
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)



drivers_info = {
    "Max Verstappen": {
        "birthdate": date(1997, 9, 30),
        "nationality": {"ru": "Нидерланды", "en": "Netherlands"},
        "team": "Red Bull Racing",
        "number": 1
    },
    "Liam Lawson": {
        "birthdate": date(2002, 2, 11),
        "nationality": {"ru": "Новая Зеландия", "en": "New Zealand"},
        "team": "Red Bull Racing",
        "number": 30
    },
    "Lewis Hamilton": {
        "birthdate": date(1985, 1, 7),
        "nationality": {"ru": "Великобритания", "en": "United Kingdom"},
        "team": "Ferrari",
        "number": 44
    },
    "Charles Leclerc": {
        "birthdate": date(1997, 10, 16),
        "nationality": {"ru": "Монако", "en": "Monaco"},
        "team": "Ferrari",
        "number": 16
    },
    "George Russell": {
        "birthdate": date(1998, 2, 15),
        "nationality": {"ru": "Великобритания", "en": "United Kingdom"},
        "team": "Mercedes",
        "number": 63
    },
    "Andrea Kimi Antonelli": {
        "birthdate": date(2006, 8, 25),
        "nationality": {"ru": "Италия", "en": "Italy"},
        "team": "Mercedes",
        "number": 12
    },
    "Lando Norris": {
        "birthdate": date(1999, 11, 13),
        "nationality": {"ru": "Великобритания", "en": "United Kingdom"},
        "team": "McLaren",
        "number": 4
    },
    "Oscar Piastri": {
        "birthdate": date(2001, 4, 6),
        "nationality": {"ru": "Австралия", "en": "Australia"},
        "team": "McLaren",
        "number": 81
    },
    "Lance Stroll": {
        "birthdate": date(1998, 10, 29),
        "nationality": {"ru":"Канада","en":"Canada"},
        "team": "Aston Martin",
        "number": 18
    },
    'Fernando Alonso': {
        'birthdate': date(1981, 7, 29),
        'nationality': {'ru': 'Испания', 'en': 'Spain'},
        "team": "Aston Martin",
        "number": 14
    },
    'Alex Albon': {
        'birthdate': date(1996, 3, 23),
        'nationality': {'ru': 'Таиланд', 'en': 'Thailand'},

        "team": "Williams",
        "number": 23
    },
    'Carlos Sainz Jr.': {
        'birthdate': date(1994, 9, 1),
        'nationality': {'ru': 'Испания', 'en': 'Spain'},
        "team": "Williams",
        "number": 55
    },
    'Nico Hülkenberg': {
        'birthdate': date(1987, 8, 18),
        'nationality': {'ru': 'Германия', 'en': 'Germany'},
        "team": "Kick Sauber",
        "number": 27
    },
    'Gabriel Bortoleto': {
        'birthdate': date(2004, 10, 14),
        'nationality': {'ru':'Бразилия','en':'Brazil'},
        "team": "Kick Sauber",
        "number": 5
    },
    'Pierre Gasly': {
        'birthdate': date(1996, 2, 7),
        'nationality': {'ru':'Франция','en':'France'},
        "team": "Alpine",
        "number": 10
    },
    'Jack Doohan': {
         'birthdate': date(2003, 1, 20),
         'nationality': {'ru':'Австралия','en':'Australia'},
        "team": "Alpine",
        "number": 7
    },
    'Yuki Tsunoda': {
         'birthdate': date(2000,5,11),
         'nationality': {'ru':'Япония','en':'Japan'},
        "team": "Racing Bulls",
        "number": 22
    },
    'Isack Hadjar': {
         'birthdate': date(2004,9,28),
         'nationality': {'ru':'Франция','en':'France'},
        "team": "Racing Bulls",
        "number": 6
    },
    'Oliver Bearman': {
         'birthdate': date(2005,5,8),
         'nationality': {"ru": "Великобритания", "en": "United Kingdom"},
        "team": "Haas",
        "number": 87
    },
    'Esteban Ocon': {
         'birthdate': date(1996,9,17),
         'nationality': {'ru':'Франция','en':'France'},
        "team": "Haas",
        "number": 31
    }
}



def calculate_age(birthdate):
    today = date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age


team_logos = {
    "McLaren": "🟠",
    "Ferrari": "🔴",
    "Red Bull Racing": "🔵",
    "Mercedes": "⚪️",
    "Aston Martin": "💚",
    "Alpine": "💙",
    "Haas": "⚪️",
    "Racing Bulls": "🔵",
    "Williams": "🔵",
    "Kick Sauber": "💚"
}


@router.callback_query(lambda c: c.data == "drivers")
async def show_drivers(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    # Словарь с URL логотипов команд

    # Группируем пилотов по командам
    team_drivers = {}
    for driver, data in drivers_info.items():
        team = data["team"]
        if team not in team_drivers:
            team_drivers[team] = []
        team_drivers[team].append(driver)


        team_buttons = []
        for team, drivers in team_drivers.items():
            if len(drivers) == 2:
                row = [
                    InlineKeyboardButton(
                        text=f"{team_logos[team]} {drivers[0]}",
                        callback_data=f"driver_{drivers[0]}"
                    ),
                    InlineKeyboardButton(
                        text=f"{team_logos[team]} {drivers[1]}",
                        callback_data=f"driver_{drivers[1]}"
                    )
                ]
                team_buttons.append(row)



    team_buttons = [
        # McLaren
        [
            InlineKeyboardButton(text=f"{team_logos['McLaren']} Lando Norris", callback_data="driver_Lando Norris"),
            InlineKeyboardButton(text=f"{team_logos['McLaren']} Oscar Piastri", callback_data="driver_Oscar Piastri")
        ],
        # Ferrari
        [
            InlineKeyboardButton(text=f"{team_logos['Ferrari']} Charles Leclerc",
                                 callback_data="driver_Charles Leclerc"),
            InlineKeyboardButton(text=f"{team_logos['Ferrari']} Lewis Hamilton", callback_data="driver_Lewis Hamilton")
        ],
        # Red Bull
        [
            InlineKeyboardButton(text=f"{team_logos['Red Bull Racing']} Max Verstappen",
                                 callback_data="driver_Max Verstappen"),
            InlineKeyboardButton(text=f"{team_logos['Red Bull Racing']} Liam Lawson", callback_data="driver_Liam Lawson")
        ],
        # Mercedes
        [
            InlineKeyboardButton(text=f"{team_logos['Mercedes']} George Russell",
                                 callback_data="driver_George Russell"),
            InlineKeyboardButton(text=f"{team_logos['Mercedes']} Andrea Kimi Antonelli",
                                 callback_data="driver_Andrea Kimi Antonelli")
        ],
        # Aston Martin
        [
            InlineKeyboardButton(text=f"{team_logos['Aston Martin']} Fernando Alonso",
                                 callback_data="driver_Fernando Alonso"),
            InlineKeyboardButton(text=f"{team_logos['Aston Martin']} Lance Stroll", callback_data="driver_Lance Stroll")
        ],
        # Alpine
        [
            InlineKeyboardButton(text=f"{team_logos['Alpine']} Pierre Gasly", callback_data="driver_Pierre Gasly"),
            InlineKeyboardButton(text=f"{team_logos['Alpine']} Jack Doohan", callback_data="driver_Jack Doohan")
        ],
        # Haas
        [
            InlineKeyboardButton(text=f"{team_logos['Haas']} Esteban Ocon", callback_data="driver_Esteban Ocon"),
            InlineKeyboardButton(text=f"{team_logos['Haas']} Oliver Bearman", callback_data="driver_Oliver Bearman")
        ],
        # Racing Bulls
        [
            InlineKeyboardButton(text=f"{team_logos['Racing Bulls']} Yuki Tsunoda",
                                 callback_data="driver_Yuki Tsunoda"),
            InlineKeyboardButton(text=f"{team_logos['Racing Bulls']} Isack Hadjar", callback_data="driver_Isack Hadjar")
        ],
        # Williams
        [
            InlineKeyboardButton(text=f"{team_logos['Williams']} Carlos Sainz Jr.",
                                 callback_data="driver_Carlos Sainz Jr."),
            InlineKeyboardButton(text=f"{team_logos['Williams']} Alex Albon", callback_data="driver_Alex Albon")
        ],
        # Sauber
        [
            InlineKeyboardButton(text=f"{team_logos['Kick Sauber']} Nico Hülkenberg",
                                 callback_data="driver_Nico Hülkenberg"),
            InlineKeyboardButton(text=f"{team_logos['Kick Sauber']} Gabriel Bortoleto",
                                 callback_data="driver_Gabriel Bortoleto")
        ],
        # Кнопка "Назад"
        [InlineKeyboardButton(text="🔙 Назад" if language == 'ru' else "🔙 Back", callback_data="paddock")]
    ]


    keyboard = InlineKeyboardMarkup(inline_keyboard=team_buttons)

    try:
        await callback.message.delete()
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo="https://scontent-waw2-2.xx.fbcdn.net/v/t39.30808-6/470815360_874503911561169_9079399726029356248_n.jpg?_nc_cat=106&ccb=1-7&_nc_sid=127cfc&_nc_ohc=j5TRKOQvjfwQ7kNvgGdsmv2&_nc_zt=23&_nc_ht=scontent-waw2-2.xx&_nc_gid=AxZZBp-0VsyrFWup1asFFh4&oh=00_AYC41mrImpg--JH8eEXHAyBmdh4AZW7Lc41LUcIgr56YYw&oe=6775C750",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error in show_drivers: {e}")


@router.callback_query(lambda c: c.data.startswith("driver_"))
async def show_driver_info(callback: types.CallbackQuery):
    try:
        user_language = user_data[callback.from_user.id]["language"]
        driver_name = callback.data.split("_")[1]
        driver_data = drivers_info.get(driver_name)

        if not driver_data:
            await callback.answer(
                "Информация о пилоте недоступна." if user_language == "ru" else "Driver information is unavailable."
            )
            return

        # Подготовка данных
        age = calculate_age(driver_data["birthdate"])
        nationality = driver_data["nationality"][user_language]
        team_name = driver_data["team"]
        driver_number = driver_data["number"]

        # Формируем имя файла один раз
        name_parts = driver_name.split()
        file_name = f"{name_parts[0][:3].lower()}{name_parts[-1][:3].lower()}.png"
        photo = FSInputFile(f"drivers_photo/{file_name}")

        # Формируем текст сообщения
        text = (
            f"🏎️ <b>{'Имя' if user_language == 'ru' else 'Name'}:</b> {driver_name}\n"
            f"🏁 <b>{'Команда' if user_language == 'ru' else 'Team'}:</b> {team_name}\n"
            f"🔢 <b>{'Номер' if user_language == 'ru' else 'Number'}:</b> {driver_number}\n"
            f"🎂 <b>{'Возраст' if user_language == 'ru' else 'Age'}:</b> {age} {'лет' if user_language == 'ru' else 'years old'}\n"
            f"🌍 <b>{'Национальность' if user_language == 'ru' else 'Nationality'}:</b> {nationality}"
        )

        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔙 Назад" if user_language == 'ru' else "🔙 Back",
                callback_data="drivers"
            )]
        ])

        # Редактируем существующее сообщение
        await callback.message.edit_media(
            media=InputMediaPhoto(media=photo, caption=text, parse_mode='HTML'),
            reply_markup=keyboard
        )

    except Exception as e:
        print(f"Error in show_driver_info: {e}")
        await callback.answer("Произошла ошибка при обработке запроса")




async def show_menu(callback: types.CallbackQuery, menu_type: str):
    language = user_data[callback.from_user.id]["language"]
    buttons = []

    if menu_type == "grand_prix":
        buttons = [
            [InlineKeyboardButton(text="📅 Расписание" if language == "ru" else "📅 Schedule", callback_data="schedule")],
            [InlineKeyboardButton(text="🏁 Результаты" if language == "ru" else "🏁 Results", callback_data="results")],
            [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
        ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Меню Гран-при" if menu_type == "grand_prix" else "Меню Пелетон",
                                     reply_markup=keyboard)



async def send_back_button(language):
    buttons = [
        [InlineKeyboardButton(text="🔙 Back" if language == "en" else "🔙 Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


races = [
    {
        "name": {"ru": "Гран-при Австралии", "en": "Australian Grand Prix"},
        "date": {"ru": "14-16 марта", "en": "March 14-16"},
        "info": {
            "ru": """
<b>• Гран-при Австралии 🇦🇺</b>

📅 14-16 марта 2025
🏎️ Трасса: Альберт-Парк, Мельбурн
🔄 Кругов: 58
📏 Длина круга: 5,278 км
🏁 Общая дистанция: 306,124 км

🗺️ Описание трассы:
Живописная городская трасса, проложенная вокруг искусственного озера в парке Альберт.
Сочетает в себе быстрые повороты и техничные секции.

🏆 Рекорд круга:
1:19.813 - Шарль Леклер (Ferrari, 2024)
""",
            "en": """
<b>• Australian Grand Prix 🇦🇺</b>

📅 March 14-16, 2025
🏎️ Circuit: Albert Park, Melbourne
🔄 Laps: 58
📏 Lap length: 5.278 km
🏁 Total distance: 306.124 km

🗺️ Circuit description:
A picturesque street circuit laid out around an artificial lake in Albert Park. 
It combines fast corners with technical sections.

🏆 Lap record:
1:19.813 - Charles Leclerc (Ferrari, 2024)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Australia_Circuit"
    },
    {
        "name": {"ru": "Гран-при Китая", "en": "Chinese Grand Prix"},
        "date": {"ru": "21-23 марта", "en": "March 21-23"},
        "info": {
            "ru": """
<b>• Гран-при Китая 🇨🇳</b>

📅 21-23 марта 2025
🏎️ Трасса: Международный автодром Шанхая
🔄 Кругов: 56
📏 Длина круга: 5,451 км
🏁 Общая дистанция: 305,066 км

🗺️ Описание трассы:
Современная трасса с уникальной конфигурацией, включающей длинную заднюю прямую и сложные повороты.

🏆 Рекорд круга:
1:32.238 - Михаэль Шумахер (Ferrari, 2004)
""",
            "en": """
<b>• Chinese Grand Prix 🇨🇳</b>

📅 March 21-23, 2025
🏎️ Circuit: Shanghai International Circuit
🔄 Laps: 56
📏 Lap length: 5.451 km
🏁 Total distance: 305.066 km

🗺️ Circuit description:
A modern track with a unique layout, featuring a long back straight and challenging corners.

🏆 Lap record:
1:32.238 - Michael Schumacher (Ferrari, 2004)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/China_Circuit"
    },
    {
        "name": {"ru": "Гран-при Японии", "en": "Japanese Grand Prix"},
        "date": {"ru": "4-6 апреля", "en": "April 4-6"},
        "info": {
            "ru": """
<b>• Гран-при Японии 🇯🇵</b>

📅 4-6 апреля 2025
🏎️ Трасса: Судзука
🔄 Кругов: 53
📏 Длина круга: 5,807 км
🏁 Общая дистанция: 307,471 км

🗺️ Описание трассы:
Легендарная трасса в форме восьмерки с техничными поворотами и знаменитым S-образным участком.

🏆 Рекорд круга:
1:30.983 - Льюис Хэмилтон (Mercedes, 2019)
""",
            "en": """
<b>• Japanese Grand Prix 🇯🇵</b>

📅 April 4-6, 2025
🏎️ Circuit: Suzuka
🔄 Laps: 53
📏 Lap length: 5.807 km
🏁 Total distance: 307.471 km

🗺️ Circuit description:
A legendary figure-8 track with technical corners and the famous S-curves section.

🏆 Lap record:
1:30.983 - Lewis Hamilton (Mercedes, 2019)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Japan_Circuit"
    },
    {
        "name": {"ru": "Гран-при Бахрейна", "en": "Bahrain Grand Prix"},
        "date": {"ru": "11-13 апреля", "en": "April 11-13"},
        "info": {
            "ru": """
<b>• Гран-при Бахрейна 🇧🇭</b>

📅 11-13 апреля 2025
🏎️ Трасса: Международный автодром Бахрейна
🔄 Кругов: 57
📏 Длина круга: 5,412 км
🏁 Общая дистанция: 308,238 км

🗺️ Описание трассы:
Современная трасса в пустыне с длинными прямыми и техничными секциями.

🏆 Рекорд круга:
1:31.447 - Педро де ла Роса (McLaren, 2005)
""",
            "en": """
<b>• Bahrain Grand Prix 🇧🇭</b>

📅 April 11-13, 2025
🏎️ Circuit: Bahrain International Circuit
🔄 Laps: 57
📏 Lap length: 5.412 km
🏁 Total distance: 308.238 km

🗺️ Circuit description:
A modern desert track with long straights and technical sections.

🏆 Lap record:
1:31.447 - Pedro de la Rosa (McLaren, 2005)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Bahrain_Circuit"
    },
    {
        "name": {"ru": "Гран-при Саудовской Аравии", "en": "Saudi Arabian Grand Prix"},
        "date": {"ru": "18-20 апреля", "en": "April 18-20"},
        "info": {
            "ru": """
<b>• Гран-при Саудовской Аравии 🇸🇦</b>

📅 18-20 апреля 2025
🏎️ Трасса: Джидда Корниш Трек
🔄 Кругов: 50
📏 Длина круга: 6,174 км
🏁 Общая дистанция: 308,450 км

🗺️ Описание трассы:
Скоростная городская трасса с длинными прямыми и быстрыми поворотами.

🏆 Рекорд круга:
1:30.734 - Льюис Хэмилтон (Mercedes, 2021)
""",
            "en": """
<b>• Saudi Arabian Grand Prix 🇸🇦</b>

📅 April 18-20, 2025
🏎️ Circuit: Jeddah Corniche Circuit
🔄 Laps: 50
📏 Lap length: 6.174 km
🏁 Total distance: 308.450 km

🗺️ Circuit description:
A high-speed street circuit with long straights and fast corners.

🏆 Lap record:
1:30.734 - Lewis Hamilton (Mercedes, 2021)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Saudi_Arabia_Circuit"
    },
    {
        "name": {"ru": "Гран-при Майами", "en": "Miami Grand Prix"},
        "date": {"ru": "2-4 мая", "en": "May 2-4"},
        "info": {
            "ru": """
<b>• Гран-при Майами 🇺🇸</b>

📅 2-4 мая 2025
🏎️ Трасса: Международный автодром Майами
🔄 Кругов: 57
📏 Длина круга: 5,412 км
🏁 Общая дистанция: 308,326 км

🗺️ Описание трассы:
Городская трасса вокруг стадиона Hard Rock с длинными прямыми и техничными секциями.

🏆 Рекорд круга:
1:29.708 - Макс Ферстаппен (Red Bull, 2023)
""",
            "en": """
<b>• Miami Grand Prix 🇺🇸</b>

📅 May 2-4, 2025
🏎️ Circuit: Miami International Autodrome
🔄 Laps: 57
📏 Lap length: 5.412 km
🏁 Total distance: 308.326 km

🗺️ Circuit description:
A street circuit around the Hard Rock Stadium with long straights and technical sections.

🏆 Lap record:
1:29.708 - Max Verstappen (Red Bull, 2023)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Miami_Circuit"
    },
    {
        "name": {"ru": "Гран-при Эмилии-Романьи", "en": "Emilia Romagna Grand Prix"},
        "date": {"ru": "16-18 мая", "en": "May 16-18"},
        "info": {
            "ru": """
<b>• Гран-при Эмилии-Романьи 🇮🇹</b>

📅 16-18 мая 2025
🏎️ Трасса: Автодром Энцо и Дино Феррари
🔄 Кругов: 63
📏 Длина круга: 4,909 км
🏁 Общая дистанция: 309,049 км

🗺️ Описание трассы:
Историческая трасса с техничными поворотами и перепадами высот.

🏆 Рекорд круга:
1:15.484 - Льюис Хэмилтон (Mercedes, 2020)
""",
            "en": """
<b>• Emilia Romagna Grand Prix 🇮🇹</b>

📅 May 16-18, 2025
🏎️ Circuit: Autodromo Enzo e Dino Ferrari
🔄 Laps: 63
📏 Lap length: 4.909 km
🏁 Total distance: 309.049 km

🗺️ Circuit description:
A historic track with technical corners and elevation changes.

🏆 Lap record:
1:15.484 - Lewis Hamilton (Mercedes, 2020)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Emilia_Romagna_Circuit"
    },
    {
        "name": {"ru": "Гран-при Монако", "en": "Monaco Grand Prix"},
        "date": {"ru": "23-25 мая", "en": "May 23-25"},
        "info": {
            "ru": """
<b>• Гран-при Монако 🇲🇨</b>

📅 23-25 мая 2025
🏎️ Трасса: Трасса Монако
🔄 Кругов: 78
📏 Длина круга: 3,337 км
🏁 Общая дистанция: 260,286 км

🗺️ Описание трассы:
Легендарная городская трасса с узкими улицами и сложными поворотами.

🏆 Рекорд круга:
1.10.166 - Льюис Хэмилтон (Mercedes, 2019)
""",
            "en": """
<b>• Monaco Grand Prix 🇲🇨</b>

📅 May 23-25, 2025
🏎️ Circuit: Circuit de Monaco
🔄 Laps: 78
📏 Lap length: 3.337 km
🏁 Total distance: 260.286 km

🗺️ Circuit description:
A legendary street circuit with narrow streets and challenging corners.

🏆 Lap record:
1.10.166 - Lewis Hamilton (Mercedes, 2019)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Monaco_Circuit"
    },
    {
        "name": {"ru": "Гран-при Испании", "en": "Spanish Grand Prix"},
        "date": {"ru": "30 мая - 1 июня", "en": "May 30 - June 1"},
        "info": {
            "ru": """
<b>• Гран-при Испании 🇪🇸</b>

📅 30 мая - 1 июня 2025
🏎️ Трасса: Барселона-Каталунья
🔄 Кругов: 66
📏 Длина круга: 4,657 км
🏁 Общая дистанция: 307,236 км

🗺️ Описание трассы:
Современная трасса с разнообразными поворотами и техничными секциями.

🏆 Рекорд круга:
1:18.149 - Макс Ферстаппен (Red Bull, 2021)
""",
            "en": """
<b>• Spanish Grand Prix 🇪🇸</b>

📅 May 30 - June 1, 2025
🏎️ Circuit: Circuit de Barcelona-Catalunya
🔄 Laps: 66
📏 Lap length: 4.657 km
🏁 Total distance: 307.236 km

🗺️ Circuit description:
A modern track with a variety of corners and technical sections.

🏆 Lap record:
1:18.149 - Max Verstappen (Red Bull, 2021)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Spain_Circuit"
    },
    {
        "name": {"ru": "Гран-при Канады", "en": "Canadian Grand Prix"},
        "date": {"ru": "13-15 июня", "en": "June 13-15"},
        "info": {
            "ru": """
<b>• Гран-при Канады 🇨🇦</b>

📅 13-15 июня 2025
🏎️ Трасса: Жиль Вильнёв
🔄 Кругов: 70
📏 Длина круга: 4,361 км
🏁 Общая дистанция: 305,270 км

🗺️ Описание трассы:
Полугородская трасса на острове Нотр-Дам с длинными прямыми и шиканами.

🏆 Рекорд круга:
1:13.078 - Валттери Боттас (Mercedes, 2019)
""",
            "en": """
<b>• Canadian Grand Prix 🇨🇦</b>

📅 June 13-15, 2025
🏎️ Circuit: Circuit Gilles Villeneuve
🔄 Laps: 70
📏 Lap length: 4.361 km
🏁 Total distance: 305.270 km

🗺️ Circuit description:
A semi-street circuit on Notre Dame Island with long straights and chicanes.

🏆 Lap record:
1:13.078 - Valtteri Bottas (Mercedes, 2019)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Canada_Circuit"
    },
    {
        "name": {"ru": "Гран-при Австрии", "en": "Austrian Grand Prix"},
        "date": {"ru": "27-29 июня", "en": "June 27-29"},
        "info": {
            "ru": """
<b>• Гран-при Австрии 🇦🇹</b>

📅 27-29 июня 2025
🏎️ Трасса: Ред Булл Ринг
🔄 Кругов: 71
📏 Длина круга: 4,318 км
🏁 Общая дистанция: 306,452 км

🗺️ Описание трассы:
Короткая, но динамичная трасса с перепадами высот и быстрыми поворотами.

🏆 Рекорд круга:
1:05.619 - Карлос Сайнс (Ferrari, 2020)
""",
            "en": """
<b>• Austrian Grand Prix 🇦🇹</b>

📅 June 27-29, 2025
🏎️ Circuit: Red Bull Ring
🔄 Laps: 71
📏 Lap length: 4.318 km
🏁 Total distance: 306.452 km

🗺️ Circuit description:
A short but dynamic track with elevation changes and fast corners.

🏆 Lap record:
1:05.619 - Carlos Sainz (Ferrari, 2020)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Austria_Circuit"
    },
    {
        "name": {"ru": "Гран-при Великобритании", "en": "British Grand Prix"},
        "date": {"ru": "4-6 июля", "en": "July 4-6"},
        "info": {
            "ru": """
<b>• Гран-при Великобритании 🇬🇧</b>

📅 4-6 июля 2025
🏎️ Трасса: Сильверстоун
🔄 Кругов: 52
📏 Длина круга: 5,891 км
🏁 Общая дистанция: 306,198 км

🗺️ Описание трассы:
Историческая трасса с быстрыми поворотами и длинными прямыми участками.

🏆 Рекорд круга:
1.24.303 - Льюис Хэмильтое (Mercedes, 2020)
""",
            "en": """
<b>• British Grand Prix 🇬🇧</b>

📅 July 4-6, 2025
🏎️ Circuit: Silverstone
🔄 Laps: 52
📏 Lap length: 5.891 km
🏁 Total distance: 306.198 km

🗺️ Circuit description:
A historic track with fast corners and long straight sections.

🏆 Lap record:
1.24.303 - Lewis Hamilton (Mercedes, 2020)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Great_Britain_Circuit"
    },
    {
        "name": {"ru": "Гран-при Венгрии", "en": "Hungarian Grand Prix"},
        "date": {"ru": "1-3 августа", "en": "August 1-3"},
        "info": {
            "ru": """
<b>• Гран-при Венгрии 🇭🇺</b>

📅 1-3 августа 2025
🏎️ Трасса: Хунгароринг
🔄 Кругов: 70
📏 Длина круга: 4,381 км
🏁 Общая дистанция: 306,663 км

🗺️ Описание трассы:
Извилистая трасса с множеством медленных поворотов.

🏆 Рекорд круга:
1:13,447 - Льюис Хэмилтон (Mercedes, 2020)
""",
            "en": """
<b>• Hungarian Grand Prix 🇭🇺</b>

📅 August 1-3, 2025
🏎️ Circuit: Hungaroring
🔄 Laps: 70
📏 Lap length: 4.381 km
🏁 Total distance: 306.663 km

🗺️ Circuit description:
A twisty track with many slow corners.

🏆 Lap record:
1:16.627 - Lewis Hamilton (Mercedes, 2020)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Hungary_Circuit"
    },
{
        "name": {"ru": "Гран-при Бельгии", "en": "Belgian Grand Prix"},
        "date": {"ru": "25-27 июля", "en": "July 25-27"},
        "info": {
            "ru": """
<b>• Гран-при Бельгии 🇧🇪</b>

📅 25-27 июля 2025
🏎️ Трасса: Спа-Франкоршам
🔄 Кругов: 44
📏 Длина круга: 7,004 км
🏁 Общая дистанция: 308,052 км

🗺️ Описание трассы:
Легендарная трасса с перепадами высот и знаменитым поворотом Eau Rouge.

🏆 Рекорд круга:
1:41,252 - Льюис Хэмильтон (Mercedes, 2020)
""",
            "en": """
<b>• Belgian Grand Prix 🇧🇪</b>

📅 July 25-27, 2025
🏎️ Circuit: Circuit de Spa-Francorchamps
🔄 Laps: 44
📏 Lap length: 7.004 km
🏁 Total distance: 308.052 km

🗺️ Circuit description:
A legendary track with elevation changes and the famous Eau Rouge corner.

🏆 Lap record:
1:46.286 - Valtteri Bottas (Mercedes, 2018)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Belgium_Circuit"
    },
    {
        "name": {"ru": "Гран-при Нидерландов", "en": "Dutch Grand Prix"},
        "date": {"ru": "29-31 августа", "en": "August 29-31"},
        "info": {
            "ru": """
<b>• Гран-при Нидерландов 🇳🇱</b>

📅 29-31 августа 2025
🏎️ Трасса: Зандворт
🔄 Кругов: 72
📏 Длина круга: 4,259 км
🏁 Общая дистанция: 306,587 км

🗺️ Описание трассы:
Техничная трасса с уникальными наклонными поворотами.

🏆 Рекорд круга:
1:08,885 - Макс Ферстаппен (Red Bull, 2021)
""",
            "en": """
<b>• Dutch Grand Prix 🇳🇱</b>

📅 August 29-31, 2025
🏎️ Circuit: Circuit Zandvoort
🔄 Laps: 72
📏 Lap length: 4.259 km
🏁 Total distance: 306.587 km

🗺️ Circuit description:
A technical track with unique banked corners.

🏆 Lap record:
1:08,885 - Max Verstappen (Red Bull, 2021)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Netherlands_Circuit"
    },
 {
        "name": {"ru": "Гран-при Италии", "en": "Italian Grand Prix"},
        "date": {"ru": "5-7 сентября", "en": "September 5-7"},
        "info": {
            "ru": """
<b>• Гран-при Италии 🇮🇹</b>

📅 5-7 сентября 2025
🏎️ Трасса: Монца
🔄 Кругов: 53
📏 Длина круга: 5,793 км
🏁 Общая дистанция: 306,720 км

🗺️ Описание трассы:
Скоростная трасса с длинными прямыми и знаменитыми шиканами.

🏆 Рекорд круга:
1:18,887 - Льюис Хэмильтон (Mercedes, 2020)
""",
            "en": """
<b>• Italian Grand Prix 🇮🇹</b>

📅 September 5-7, 2025
🏎️ Circuit: Monza
🔄 Laps: 53
📏 Lap length: 5.793 km
🏁 Total distance: 306.720 km

🗺️ Circuit description:
A high-speed track with long straights and famous chicanes.

🏆 Lap record:
1:18,887 - Lewis Hamilton (Mercedes, 2020)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Italy_Circuit"
    },
    {
        "name": {"ru": "Гран-при Азербайджана", "en": "Azerbaijan Grand Prix"},
        "date": {"ru": "19-21 сентября", "en": "September 19-21"},
        "info": {
            "ru": """
<b>• Гран-при Азербайджана 🇦🇿</b>

📅 19-21 сентября 2025
🏎️ Трасса: Городская трасса Баку
🔄 Кругов: 51
📏 Длина круга: 6,003 км
🏁 Общая дистанция: 306,049 км

🗺️ Описание трассы:
Городская трасса с самой длинной прямой в календаре и узким участком в старом городе.

🏆 Рекорд круга:
1:40,203 - Шарль Леклер (Ferrari, 2023)
""",
            "en": """
<b>• Azerbaijan Grand Prix 🇦🇿</b>

📅 September 19-21, 2025
🏎️ Circuit: Baku City Circuit
🔄 Laps: 51
📏 Lap length: 6.003 km
🏁 Total distance: 306.049 km

🗺️ Circuit description:
A street circuit with the longest straight on the calendar and a narrow section in the old city.

🏆 Lap record:
1:40,203 - Charles Leclerc (Ferrari, 2023)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Baku_Circuit"
    },
 {
        "name": {"ru": "Гран-при Сингапура", "en": "Singapore Grand Prix"},
        "date": {"ru": "3-5 октября", "en": "October 3-5"},
        "info": {
            "ru": """
<b>• Гран-при Сингапура 🇸🇬</b>

📅 3-5 октября 2025
🏎️ Трасса: Марина-Бэй
🔄 Кругов: 62
📏 Длина круга: 4,940 км
🏁 Общая дистанция: 306,143 км

🗺️ Описание трассы:
Ночная городская трасса с искусственным освещением и сложными поворотами.

🏆 Рекорд круга:
1:29,525 - Ландо Норрис (McLaren, 2024)
""",
            "en": """
<b>• Singapore Grand Prix 🇸🇬</b>

📅 October 3-5, 2025
🏎️ Circuit: Marina Bay Street Circuit
🔄 Laps: 62
📏 Lap length: 4.940 km
🏁 Total distance: 306.143 km

🗺️ Circuit description:
A night street circuit with artificial lighting and challenging corners.

🏆 Lap record:
1:41.905 - Lewis Hamilton (Mercedes, 2018)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Singapore_Circuit"
    },
    {
        "name": {"ru": "Гран-при США", "en": "United States Grand Prix"},
        "date": {"ru": "17-19 октября", "en": "October 17-19"},
        "info": {
            "ru": """
<b>• Гран-при США 🇺🇸</b>

📅 17-19 октября 2025
🏎️ Трасса: Трасса Америк
🔄 Кругов: 56
📏 Длина круга: 5,513 км
🏁 Общая дистанция: 308,405 км

🗺️ Описание трассы:
Современная трасса с перепадами высот и техничными поворотами.

🏆 Рекорд круга:
1:32,029 - Валттери Боттам (Mercedes, 2019)
""",
            "en": """
<b>• United States Grand Prix 🇺🇸</b>

📅 October 17-19, 2025
🏎️ Circuit: Circuit of The Americas
🔄 Laps: 56
📏 Lap length: 5.513 km
🏁 Total distance: 308.405 km

🗺️ Circuit description:
A modern track with elevation changes and technical corners.

🏆 Lap record:
1:32,029 - Valtteri Bottas (Mercedes, 2019)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/USA_Circuit"
    },
 {
        "name": {"ru": "Гран-при Мексики", "en": "Mexican Grand Prix"},
        "date": {"ru": "24-26 октября", "en": "October 24-26"},
        "info": {
            "ru": """
<b>• Гран-при Мексики 🇲🇽</b>

📅 24-26 октября 2025
🏎️ Трасса: Автодром имени братьев Родригес
🔄 Кругов: 71
📏 Длина круга: 4,304 км
🏁 Общая дистанция: 305,584 км

🗺️ Описание трассы:
Высокогорная трасса с длинной прямой и знаменитым стадионным комплексом.

🏆 Рекорд круга:
1:14,759 - Даниэль Риккардо (Red Bull, 2018)
""",
            "en": """
<b>• Mexican Grand Prix 🇲🇽</b>

📅 October 24-26, 2025
🏎️ Circuit: Autódromo Hermanos Rodríguez
🔄 Laps: 71
📏 Lap length: 4.304 km
🏁 Total distance: 305.584 km

🗺️ Circuit description:
A high-altitude track with a long straight and famous stadium section.

🏆 Lap record:
1:14,759 - Daniel Ricciardo (Red Bull, 2018)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Mexico_Circuit"
    },
    {
        "name": {"ru": "Гран-при Бразилии", "en": "Brazilian Grand Prix"},
        "date": {"ru": "7-9 ноября", "en": "November 7-9"},
        "info": {
            "ru": """
<b>• Гран-при Бразилии 🇧🇷</b>

📅 7-9 ноября 2025
🏎️ Трасса: Интерлагос
🔄 Кругов: 71
📏 Длина круга: 4,309 км
🏁 Общая дистанция: 305,879 км

🗺️ Описание трассы:
Классическая трасса с перепадами высот и техничными поворотами.

🏆 Рекорд круга:
1:10.540 - Валттери Боттас (Mercedes, 2018)
""",
            "en": """
<b>• Brazilian Grand Prix 🇧🇷</b>

📅 November 7-9, 2025
🏎️ Circuit: Interlagos
🔄 Laps: 71
📏 Lap length: 4.309 km
🏁 Total distance: 305.879 km

🗺️ Circuit description:
A classic track with elevation changes and technical corners.

🏆 Lap record:
1:10.540 - Valtteri Bottas (Mercedes, 2018)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Brazil_Circuit"
    },
 {
        "name": {"ru": "Гран-при Лас-Вегаса", "en": "Las Vegas Grand Prix"},
        "date": {"ru": "20-22 ноября", "en": "November 20-22"},
        "info": {
            "ru": """
<b>• Гран-при Лас-Вегаса 🇺🇸</b>

📅 20-22 ноября 2025
🏎️ Трасса: Лас-Вегас Стрип Серкит
🔄 Кругов: 50
📏 Длина круга: 6,201 км
🏁 Общая дистанция: 310,050 км

🗺️ Описание трассы:
Ночная городская трасса, проходящая по знаменитому Стрипу Лас-Вегаса.

🏆 Рекорд круга:
1:35.490 - Оскар Пиастри (McLaren, 2023)
""",
            "en": """
<b>• Las Vegas Grand Prix 🇺🇸</b>

📅 November 20-22, 2025
🏎️ Circuit: Las Vegas Strip Circuit
🔄 Laps: 50
📏 Lap length: 6.201 km
🏁 Total distance: 310.050 km

🗺️ Circuit description:
A night street circuit running through the famous Las Vegas Strip.

🏆 Lap record:
1:35.490 - Oscar Piastri (McLaren, 2023)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Las_Vegas_Circuit"
    },
    {
        "name": {"ru": "Гран-при Катара", "en": "Qatar Grand Prix"},
        "date": {"ru": "28-30 ноября", "en": "November 28-30"},
        "info": {
            "ru": """
<b>• Гран-при Катара 🇶🇦</b>

📅 28-30 ноября 2025
🏎️ Трасса: Лусаил
🔄 Кругов: 57
📏 Длина круга: 5,419 км
🏁 Общая дистанция: 308,883 км

🗺️ Описание трассы:
Современная ночная трасса с быстрыми поворотами и длинными прямыми.

🏆 Рекорд круга:
1:24.319 - Макс Ферстаппен (Red Bull, 2023)
""",
            "en": """
<b>• Qatar Grand Prix 🇶🇦</b>

📅 November 28-30, 2025
🏎️ Circuit: Lusail International Circuit
🔄 Laps: 57
📏 Lap length: 5.419 km
🏁 Total distance: 308.883 km

🗺️ Circuit description:
A modern night circuit with fast corners and long straights.

🏆 Lap record:
1:24.319 - Max Verstappen (Red Bull, 2023)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Qatar_Circuit"
    },
    {
        "name": {"ru": "Гран-при Абу-Даби", "en": "Abu Dhabi Grand Prix"},
        "date": {"ru": "5-7 декабря", "en": "December 5-7"},
        "info": {
            "ru": """
<b>• Гран-при Абу-Даби 🇦🇪</b>

📅 5-7 декабря 2025
🏎️ Трасса: Яс Марина
🔄 Кругов: 58
📏 Длина круга: 5,281 км
🏁 Общая дистанция: 306,183 км

🗺️ Описание трассы:
Современная трасса с уникальным отелем и подземным пит-лейном.

🏆 Рекорд круга:
1:26.103 - Макс Ферстаппен (Red Bull, 2021)
""",
            "en": """
<b>• Abu Dhabi Grand Prix 🇦🇪</b>

📅 December 5-7, 2025
🏎️ Circuit: Yas Marina Circuit
🔄 Laps: 58
📏 Lap length: 5.281 km
🏁 Total distance: 306.183 km

🗺️ Circuit description:
A modern circuit with a unique hotel and underground pit lane.

🏆 Lap record:
1:26.103 - Max Verstappen (Red Bull, 2021)
"""
        },
        "image_url": "https://media.formula1.com/image/upload/f_auto,c_limit,q_auto,w_771/content/dam/fom-website/2018-redesign-assets/Circuit%20maps%2016x9/Abu_Dhabi_Circuit"
    }
]


@router.callback_query(lambda c: c.data == "schedule")
async def show_schedule(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]
    buttons = [
        [InlineKeyboardButton(text=f"{i + 1}. {race['name'][language]}", callback_data=f"track_{i}")]
        for i, race in enumerate(races)
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="grand_prix")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "📅 Расписание гонок на 2025 год:" if language == "ru" else "📅 2025 Race Schedule:"

    try:
        # Попытка отредактировать существующее сообщение
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "there is no text in the message to edit" in str(e).lower():
            # Если сообщение не содержит текста, удаляем его и отправляем новое
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)
        elif "message is not modified" in str(e).lower():
            # Игнорируем ошибку, если сообщение не изменилось
            pass
        else:
            # Если возникла другая ошибка, пробуем отправить новое сообщение
            await callback.message.answer(text, reply_markup=keyboard)



@router.callback_query(lambda c: c.data.startswith("track_"))
async def show_track_info(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    track_id = int(callback.data.split("_")[1])
    track = races[track_id]

    text = (f"{track['info'][language]}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад" if language == 'ru' else '🔙 Back', callback_data='schedule')]
    ])

    await callback.message.delete()

    await bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=track['image_url'],
        caption=text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def get_pilots_list():
    return [
        "Max Verstappen",
        "Lando Norris",
        "Charles Leclerc",
        "Oscar Piastri",
        "Lewis Hamilton",
        "George Russell",
        "Fernando Alonso",
        "Lance Stroll",
        "Pierre Gasly",
        "Jack Doohan",
        "Esteban Ocon",
        "Oliver Bearman",
        "Gabriel Bortoleto",
        "Nico Hülkenberg",
        "Liam Lawson",
        "Isack Hadjar",
        "Franco Colapinto",
        "Carlos Sainz Jr.",
        "Andrea Kimi Antonelli"
    ]

async def get_teams_list():
    return [
        "Red Bull Racing",
        "Ferrari",
        "Mercedes",
        "McLaren",
        "Aston Martin",
        "Alpine",
        "Williams",
        "Racing Bulls",
        "Sauber",
        "Haas"
    ]


@router.callback_query(lambda c: c.data == "predictions")
async def show_predictions_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]

    loading_text = "Загрузка данных..." if language == "ru" else "Loading data..."

    try:
        await callback.message.edit_text(loading_text)
    except TelegramBadRequest:
        await callback.message.delete()
        loading_message = await callback.message.answer(loading_text)
    else:
        loading_message = callback.message

    next_race = await get_next_race()

    if not next_race:
        # Если нет предстоящих гонок, показываем соответствующее сообщение
        text = "Нет предстоящих гонок" if language == "ru" else "No upcoming races"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
        ])
        await loading_message.edit_text(text, reply_markup=keyboard)
        return

    buttons = [
        [InlineKeyboardButton(text=f"🥇 {pos}" if language == "ru" else f"🥇 {pos}", callback_data=f"predict_1_{pos}") for
         pos in range(1, 4)],
        [InlineKeyboardButton(text=f"🥈 {pos}" if language == "ru" else f"🥈 {pos}", callback_data=f"predict_2_{pos}") for
         pos in range(1, 4)],
        [InlineKeyboardButton(text=f"🥉 {pos}" if language == "ru" else f"🥉 {pos}", callback_data=f"predict_3_{pos}") for
         pos in range(1, 4)],
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = f"🏁 {'Прогноз на' if language == 'ru' else 'Prediction for'} {next_race['name']}\n📅 {next_race['date']}"

    await loading_message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("predict_"))
async def handle_prediction(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = user_data[user_id]["language"]
    _, position, driver_number = callback.data.split("_")

    if "predictions" not in user_data[user_id]:
        user_data[user_id]["predictions"] = {}

    next_race = await get_next_race()
    user_data[user_id]["predictions"][next_race['name']] = user_data[user_id]["predictions"].get(next_race['name'], {})
    user_data[user_id]["predictions"][next_race['name']][position] = driver_number

    await save_user_data()
    await callback.answer("Прогноз сохранен" if language == "ru" else "Prediction saved")
    await show_predictions_menu(callback)

async def check_predictions(race_data):
    for user_id, data in user_data.items():
        if "predictions" in data and race_data['name'] in data["predictions"]:
            prediction = data["predictions"][race_data['name']]
            result = ""
            for pos, driver in prediction.items():
                actual = race_data['results'][int(pos) - 1]['DriverNumber']
                result += f"{pos}: {driver} {'✅' if driver == actual else ''}\n"

            language = data["language"]
            message = f"{'Ваш прогноз на' if language == 'ru' else 'Your prediction for'} {race_data['name']}:\n{result}"
            await bot.send_message(user_id, message)

            del data["predictions"][race_data['name']]
            await save_user_data()



async def get_next_race():
    schedule = fastf1.get_event_schedule(2025)
    future_races = schedule[schedule['EventDate'] > datetime.now()]
    if future_races.empty:
        return None
    next_race = future_races.iloc[0]
    return {
        'name': next_race['EventName'],
        'date': next_race['EventDate'].strftime("%d.%m.%Y")
    }


# Обработчик для настроек
@router.callback_query(lambda c: c.data == "settings")
async def show_settings(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    favorite_driver = user_data[callback.from_user.id].get("favorite_driver", "")
    favorite_team = user_data[callback.from_user.id].get("favorite_team", "")

    buttons = [
        [InlineKeyboardButton(text="🌐 Язык / Language", callback_data="change_language")],
        [InlineKeyboardButton(
            text=f"👤 {'Любимый пилот:' if language == 'ru' else 'Favorite Driver:'} {favorite_driver} ✅" if favorite_driver else f"👤 {'Любимый пилот' if language == 'ru' else 'Favorite Driver'}",
            callback_data="select_pilot")],
        [InlineKeyboardButton(
            text=f"🏎 {'Любимая команда:' if language == 'ru' else 'Favorite Team:'} {favorite_team} ✅" if favorite_team else f"🏎 {'Любимая команда' if language == 'ru' else 'Favorite Team'}",
            callback_data="select_team")],
        [InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="main_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "Настройки:" if language == "ru" else "Settings:"

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "there is no text in the message to edit" in str(e):
            # Если сообщение не содержит текста, удаляем его и отправляем новое
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            # Если возникла другая ошибка, пробуем отправить только текст
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "select_pilot")
async def select_favorite_pilot(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    pilots = await get_pilots_list()

    buttons = [
        [InlineKeyboardButton(
            text=f"{pilot} {'✅' if user_data[callback.from_user.id].get('favorite_driver') == pilot else ''}",
            callback_data=f"set_favorite_driver_{pilot}"
        )] for pilot in pilots
    ]

    # Кнопка для очистки выбора
    buttons.append([InlineKeyboardButton(
        text="Очистить выбор ❌" if language == "ru" else "Clear selection ❌",
        callback_data="clear_favorite_driver"
    )])

    buttons.append([InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="settings")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "Выберите любимого пилота:" if language == "ru" else "Select your favorite driver:",
        reply_markup=keyboard
    )



@router.callback_query(lambda c: c.data.startswith("set_favorite_driver_"))
async def set_favorite_driver(callback: types.CallbackQuery):
    driver_name = callback.data.split("_")[3]
    user_id = callback.from_user.id
    user_data[user_id]["favorite_driver"] = driver_name
    await save_user_data()

    language = user_data[user_id]["language"]
    await callback.answer("✅ Любимый пилот выбран!" if language == "ru" else "✅ Favorite driver selected!")
    await show_settings(callback)



@router.callback_query(lambda c: c.data == "clear_favorite_driver")
async def clear_favorite_driver(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]["favorite_driver"] = None  # Очистка выбора
    await save_user_data()  # Сохраняем изменения

    language = user_data[user_id]["language"]
    await callback.answer(
        "✅ Выбор любимого пилота очищен!" if language == "ru" else "✅ Favorite driver selection cleared!")

    await show_settings(callback)  # Возврат к настройкам



@router.callback_query(lambda c: c.data == "select_team")
async def select_favorite_team(callback: types.CallbackQuery):
    language = user_data[callback.from_user.id]["language"]
    teams = await get_teams_list()

    buttons = [
        [InlineKeyboardButton(
            text=f"{team} {'✅' if user_data[callback.from_user.id].get('favorite_team') == team else ''}",
            callback_data=f"set_favorite_team_{team}"
        )] for team in teams
    ]

    # Кнопка для очистки выбора
    buttons.append([InlineKeyboardButton(
        text="Очистить выбор ❌" if language == "ru" else "Clear selection ❌",
        callback_data="clear_favorite_team"
    )])

    buttons.append([InlineKeyboardButton(text="🔙 Назад" if language == "ru" else "🔙 Back", callback_data="settings")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "Выберите любимую команду:" if language == "ru" else "Select your favorite team:",
        reply_markup=keyboard
    )



@router.callback_query(lambda c: c.data.startswith("set_favorite_team_"))
async def set_favorite_team(callback: types.CallbackQuery):
    team_name = "_".join(callback.data.split("_")[3:])
    user_id = callback.from_user.id
    user_data[user_id]["favorite_team"] = team_name
    await save_user_data()

    language = user_data[user_id]["language"]
    await callback.answer("✅ Любимая команда выбрана!" if language == "ru" else "✅ Favorite team selected!")
    await show_settings(callback)



@router.callback_query(lambda c: c.data == "clear_favorite_team")
async def clear_favorite_team(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]["favorite_team"] = None  # Очистка выбора
    await save_user_data()  # Сохраняем изменения

    language = user_data[user_id]["language"]
    await callback.answer(
        "✅ Выбор любимой команды очищен!" if language == "ru" else "✅ Favorite team selection cleared!")

    await show_settings(callback)  # Возврат к настройкам



async def delete_message_after_delay(message, delay):
    await asyncio.sleep(delay)

    try:
        await message.delete()
    except Exception as e:
        logging.error(f"Ошибка удаления сообщения: {e}")



@router.callback_query(lambda c: c.data == 'change_language')
async def change_language(callback: types.CallbackQuery):
    buttons = [
        [InlineKeyboardButton(text="English", callback_data="set_lang_en")],
        [InlineKeyboardButton(text="Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton(text="🔙 Назад / Back", callback_data="settings")]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text("Выберите язык / Choose your language:", reply_markup=keyboard)


@router.callback_query(lambda c: c.data == 'main_menu')
async def go_back_to_main_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.delete()
    await send_main_menu(callback.message.chat.id, user_data[user_id]["language"])



async def send_messages_in_batches(chat_id, messages):
    for message in messages:
        await bot.send_message(chat_id, message)
        await asyncio.sleep(0.1)


async def periodic_check():
    last_sent_race_data = load_last_race()
    while True:
        await delete_old_notifications()
        race_data = await get_race_results()
        if race_data and race_data["completed"]:
            if last_sent_race_data != {'name': race_data['name'], 'date': race_data['date']}:
                await send_favorite_notifications(race_data)
                await check_predictions(race_data)
                save_last_race({'name': race_data['name'], 'date': race_data['date']})
        await asyncio.sleep(40000)

async def main():
    global user_data  # Объявляем user_data как глобальную переменную
    user_data.update(load_user_data())  # Загружаем данные пользователей

    bot_task = dp.start_polling(bot)  # Запускаем опрос бота
    check_task = periodic_check()  # Запускаем периодическую проверку
    await asyncio.gather(bot_task, check_task)  # Ожидаем завершения задач


if __name__ == "__main__":
    asyncio.run(main())
