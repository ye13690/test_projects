import asyncio
import json

import psycopg2
import websockets
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import BotCommand
from aiogram.dispatcher.filters import Filter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

import config

threshold_value = 2.5
params = {"method": "subscribe", "id": "price", "data": {
    "cryptoIds": [1, 1027, 825, 1839, 2010, 52, 74, 3408, 6636, 7083, 4687, 1831, 2, 5426, 1975, 3717, 3890, 2416, 1321,
                  512, 8916, 4943, 3077, 2280, 1958, 328, 7278, 1765, 4172, 3794, 3635, 5994, 7186, 4030, 4195, 3957,
                  1518, 3602, 4023, 4256, 1376, 2011, 5692, 6945, 1720, 6719, 5805, 7129, 3822, 5034, 1168, 6892, 4847,
                  3718, 2502, 4066, 4642, 1274, 2563, 2700, 4157, 1437, 131, 2586, 1966, 5864, 5665, 2634, 2130, 873,
                  2087, 6783, 6758, 2682, 3155, 3330, 2694, 6535, 8335, 2394, 3945, 2469, 4558, 1697, 2083, 5567, 1727,
                  1698, 6538, 1896, 1684, 2499, 1042, 2566, 2135, 109, 1808, 1567, 3897, 2099, 9023, 9022],
    "index": None}}

params_json = json.dumps(params)
url = 'wss://stream.coinmarketcap.com/price/latest?method=subscribe&id=price&data=cryptoIds=1=1027=825=1839=2010=52&index=null'
url_for_id_map = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map'

headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': config.COINMARKETCAP_KEY,
}

currency_info = {}


async def listen(chat_id):
    global currency_info
    async with websockets.connect(url, ping_interval=None) as client:
        await client.send(params_json)
        data = json.loads(await client.recv())
        p1h = data['d']['cr']['p1h']
        id = data['d']['cr']['id']
        currency_info[id]['latest_p1h'] = p1h
        while True:
            data = json.loads(await client.recv())
            p1h = data['d']['cr']['p1h']
            id = data['d']['cr']['id']
            if p1h > threshold_value and currency_info[id]['latest_p1h'] != p1h:
                emoji = '📈' if p1h > currency_info[id]['latest_p1h'] else '📉'
                currency_info[id]['latest_p1h'] = p1h
                await bot.send_message(chat_id,
                                       text=f"{currency_info[id]['name']}({currency_info[id]['symbol']}) -> {p1h}{emoji}\n"
                                            f"Currently ranks {currency_info[id]['rank']}", disable_notification=True)


bot = Bot(token=config.API_KEY)
dp = Dispatcher(bot, storage=MemoryStorage())

loop = asyncio.get_event_loop()
monitoring_task = None

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Say hi to the bot"),
        BotCommand(command="/redact_profile", description="Redact your profile"),
        BotCommand(command="/start_monitoring", description="Start monitoring cryptocurrency"),
        BotCommand(command="/help", description="Help")
    ]
    await bot.set_my_commands(commands)



BUTTONS = {
    'btn_help': KeyboardButton('Help'),
    'btn_cancel': KeyboardButton('Cancel'),
    'btn_start_monitoring': KeyboardButton('Start monitoring'),
    'btn_stop_monitoring': KeyboardButton('Stop monitoring'),
    'btn_redact_profile': KeyboardButton('Redact profile'),
    'btn_redact_full_name': KeyboardButton('Full name'),
    'btn_redact_phone_number': KeyboardButton('Phone number')
}

ADMIN_ADDITIONAL = {
    'btn_change_user_type': KeyboardButton('Change user type')
}

general_kb = ReplyKeyboardMarkup(row_width=1)
general_kb.add(
    BUTTONS['btn_start_monitoring'],
    BUTTONS['btn_redact_profile'],
    BUTTONS['btn_help']
)

monitoring_kb = ReplyKeyboardMarkup(row_width=1)
monitoring_kb.add(
    BUTTONS['btn_stop_monitoring'],
    BUTTONS['btn_redact_profile'],
    BUTTONS['btn_help']
)


class GeneralStates(StatesGroup):
    contact_info = State()


class RedactStates(StatesGroup):
    redaction = State()
    redact_name = State()
    redact_phone = State()

class AdminStates(StatesGroup):
    start_changing_type = State()
    changing_user_type = State()


async def get_type(chat_id):
    """
    Get user type (admin -> a100, editor -> e60, general user -> g20)
    :param chat_id: int
    :return: user_code: string
    """
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT t.type_code FROM user_types t JOIN users u ON t.id=u.user_type WHERE u.id=%s"
        cursor.execute(query, (chat_id,))
        user = cursor.fetchone()
        return user[0]
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await bot.send_message(chat_id, "Oops! I encountered some error.\nTry again later🙃")

async def decide_keyboard(chat_id):
    """
    Decides which keyboard is suitable for the user and currently running processes
    :param chat_id:
    :return: ReplyKeyboardMarkup()
    """
    keyboard = monitoring_kb if monitoring_task in asyncio.all_tasks() else general_kb
    if await get_type(chat_id) == "a100":
        keyboard.add(ADMIN_ADDITIONAL['btn_change_user_type'])
    return keyboard


@dp.message_handler(commands=['help'])
@dp.message_handler(lambda message: message.text.lower() == 'help')
async def help(message: types.Message):
    await message.answer("/start - get to the start\n"
                         "/redact_profile - redact your profile\n"
                         "/start_monitoring - to monitor cryptocurrency\n"
                         "/stop_monitoring - to stop monitoring process\n"
                         "/help - basic commands",
                         reply_markup=await decide_keyboard(message.chat.id))


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    """
    Searching for user with corresponding id in the database.
    if found greet user, else - start state process of registration:
    request user contact information for filling it into the database.
    """
    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id=%s"
        cursor.execute(query, (chat_id,))
        user = cursor.fetchone()
        if not user:
            await GeneralStates.contact_info.set()

            keyboard = ReplyKeyboardMarkup(row_width=1)
            keyboard.add(
                KeyboardButton('Yes', request_contact=True),
                KeyboardButton('No')
            )

            await message.answer("Do you allow to use your contact information?",
                                 reply_markup=keyboard)
        else:
            await bot.send_message(chat_id, f"Hi, {user[1]}.\nLong time no see.",
                                   reply_markup=await decide_keyboard(chat_id))
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.reply("Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


@dp.message_handler(lambda message: message.text.lower() not in ["yes", "no", "y", "n"],
                    state=GeneralStates.contact_info)
async def process_contact_info_invalid(message: types.Message):
    """
    Checks if user input is suitable for the contact_info question
    """
    return await message.reply("Invalid input.\n"
                               "You have to either use keyboard or type Yes/No yourself.")


@dp.message_handler(state=GeneralStates.contact_info, content_types=['contact', 'text'])
async def process_contact_info(message, state: FSMContext):
    """
    Add new user to the database
    """
    try:
        chat_id = message.from_user.id
        first_name = message.from_user.first_name if message.from_user.first_name else ' '
        last_name = message.from_user.last_name if message.from_user.last_name else ' '
        full_name = first_name + ' ' + last_name
        username = message.from_user.username if message.from_user.username is not None else ' '
        phone_number = message.contact.phone_number if message.contact is not None else ' '
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "INSERT INTO users(id, full_name, username, phone_number, user_type) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query,
                       (chat_id, full_name, username, phone_number, 3))
        conn.commit()
        await bot.send_message(chat_id, f"Hi, {full_name}.\nNice to meet you!", reply_markup=general_kb)
        await help(message)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.reply("Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()
    await state.finish()


@dp.message_handler(commands=['redact_profile'])
@dp.message_handler(lambda message: message.text.lower() == 'redact profile')
async def redact_profile(message: types.Message):
    """
    Ask user what they want to redact
    """
    keyboard = ReplyKeyboardMarkup()
    keyboard.row(BUTTONS['btn_redact_full_name'], BUTTONS['btn_redact_phone_number'])
    keyboard.row(BUTTONS['btn_cancel'])
    await RedactStates.redaction.set()
    await message.answer('What do you want to redact?',
                         reply_markup=keyboard)


@dp.message_handler(lambda message: message.text.lower() not in ["full name", "phone number", "cancel"],
                    state=RedactStates.redaction)
async def process_redact_invalid(message: types.Message):
    """
    Check if user input valid command/message
    """
    return await message.reply("You should enter either 'Full name', 'Phone number' via buttons or keyboard.\n"
                               "Or you can cancel redacting at all.")


@dp.message_handler(lambda message: message.text.lower() == 'cancel', state='*')
@dp.message_handler(commands=['cancel'], state='*')
async def process_cancel(message: types.Message, state: FSMContext):
    """
    Cancelling redacting state
    """
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.answer("Cancelled!\nNothing was changed or added.",
                         reply_markup=await decide_keyboard(message.chat.id))


@dp.message_handler(lambda message: message.text.lower() == 'full name', state=RedactStates.redaction)
async def process_redact_name(message: types.Message):
    """
    Entering new name
    """
    await RedactStates.redact_name.set()
    await message.answer("Enter new name.", reply_markup=ReplyKeyboardRemove())


@dp.message_handler(state=RedactStates.redact_name, content_types=['text'])
async def process_set_new_name(message: types.Message, state: FSMContext):
    """
    Sets user's new name
    """
    try:
        chat_id = message.from_user.id
        new_name = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "UPDATE users SET full_name=%s, update_date=NOW() WHERE id=%s"
        cursor.execute(query, (new_name, chat_id))
        conn.commit()
        await message.answer("New name set!",
                             reply_markup=await decide_keyboard(chat_id))
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.reply("Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()
    await state.finish()


@dp.message_handler(lambda message: message.text.lower() == 'phone number', state=RedactStates.redaction)
async def process_redact_name(message: types.Message):
    """
    Entering new phone number
    """
    await RedactStates.redact_phone.set()
    await message.answer("Enter new phone number.\nP.S. Make sure it contains only numbers and country code.\n"
                         "Example: +380123456789",
                         reply_markup=ReplyKeyboardRemove())


@dp.message_handler(lambda message: not all(c.isdigit() or c == '+' for c in message.text.lower()),
                    state=RedactStates.redact_phone)
async def process_redact_invalid_phone(message: types.Message):
    """
    Check if user input valid number
    """
    return await message.reply("The phone number should contain only numbers and +\nTry again.")


@dp.message_handler(state=RedactStates.redact_phone, content_types=['text'])
async def process_set_new_number(message: types.Message, state: FSMContext):
    """
    Sets user's new phone number
    """
    try:
        chat_id = message.from_user.id
        new_phone = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "UPDATE users SET phone_number=%s, update_date=NOW() WHERE id=%s"
        cursor.execute(query, (new_phone, chat_id))
        conn.commit()
        await message.answer("New phone number set!",
                             reply_markup=await decide_keyboard(chat_id))
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.reply("Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()
    await state.finish()


@dp.message_handler(lambda message: message.text.lower() == 'start monitoring')
@dp.message_handler(commands=['start_monitoring'])
async def start_monitoring(message: types.Message):
    """
    Creates new async task which connects to coinmarketcap websocket
    """
    global monitoring_task
    monitoring_task = asyncio.ensure_future(listen(message.chat.id))
    await message.reply(
        f"Started monitoring!\nYou'll receive updates about currencies whose 1h% is greater than {threshold_value}",
        reply_markup=monitoring_kb)


@dp.message_handler(lambda message: message.text.lower() == 'stop monitoring')
@dp.message_handler(commands=['stop_monitoring'])
async def stop_monitoring(message: types.Message):
    """
    Stops async monitoring task and disconnects from websocket
    """
    global monitoring_task
    monitoring_task.cancel()
    await message.answer("Stopped monitoring!\nPress button to start monitoring.", reply_markup=general_kb)

@dp.message_handler(lambda message: (message.text.lower() == 'change user type'))
@dp.message_handler(commands=['change_user_type'])
async def change_user_type(message: types.Message):
    """
    Start change_user_type routine (AVAILABLE ONLY FOR ADMINS)
    """
    if await get_type(message.chat.id) != 'a100':
        return await message.answer("You don't have access to this command!")

    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT u.id, u.full_name, t.type_name FROM user_types t JOIN users u ON t.id=u.user_type WHERE u.id!=%s ORDER BY t.privilege_level DESC"
        cursor.execute(query, (chat_id,))
        users = cursor.fetchall()
        text = 'All users:\n' \
               'Name\t|\tId\t|\tType\n'
        for row in users:
            text += f"{row[1]}\t|\t{row[0]}\t|\t{row[2]}\n"
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await message.answer('Enter id of the user whose type you want to change.', reply_markup=ReplyKeyboardRemove())
        await AdminStates.start_changing_type.set()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.answer("Oops! I encountered some error.\nTry again later🙃")

@dp.message_handler(state=AdminStates.start_changing_type, content_types=['text'])
async def process_admin_change_invalid_id(message: types.Message, state: FSMContext):
    """
    Check if input is valid user id
    """
    chat_id = message.chat.id
    id_for_changing = message.text.strip()
    if any(not c.isdigit() for c in id_for_changing):
        return await message.reply("The id should be numeric.\nTry again.")
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT user_type FROM users WHERE id=%s"
        cursor.execute(query, (id_for_changing,))
        user = cursor.fetchone()
        if user:
            async with state.proxy() as data:
                data['id'] = id_for_changing
            keyboard = ReplyKeyboardMarkup()
            query = "SELECT type_name FROM user_types WHERE id!=1 AND id!=%s"
            cursor.execute(query, (user[0],))
            row = cursor.fetchone()
            for i in row:
                keyboard.row(f"Set as {i}")
            keyboard.row('Cancel')
            await message.answer("Choose new type for this user using buttons below.", reply_markup=keyboard)
            await AdminStates.next()
        else:
            return await message.answer('No such id in the database!\nTry again.', reply_markup=ReplyKeyboardRemove())
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.answer("Oops! I encountered some error.\nTry again later🙃")


@dp.message_handler(state=AdminStates.changing_user_type, content_types=['text'])
async def process_set_new_user_type(message: types.Message, state: FSMContext):
    """
    Sets new type for user
    """
    try:
        async with state.proxy() as data:
            user_id = data['id']
        chat_id = message.from_user.id
        new_type = message.text[6:].strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id FROM user_types WHERE type_name=%s"
        cursor.execute(query, (new_type,))
        type_id = cursor.fetchone()[0]
        if not type_id:
            return await message.answer("No such type!\nTry again.")
        query = "UPDATE users SET user_type=%s, update_date=NOW() WHERE id=%s"
        cursor.execute(query, (type_id, user_id))
        conn.commit()
        await message.answer(f"The user is now set as {new_type}",
                             reply_markup=await decide_keyboard(chat_id))
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        await message.reply("Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()
    await state.finish()


if __name__ == "__main__":

    session = Session()
    session.headers.update(headers)

    # get map of all cryptocurrencies (id, rank, name, symbol)
    try:
        response = session.get(url_for_id_map)
        data = json.loads(response.text)
        for coin in data['data']:
            currency_info[coin['id']] = {'rank': coin['rank'],
                                         'name': coin['name'],
                                         'symbol': coin['symbol'],
                                         'latest_p1h': 0}
    except (ConnectionError, Timeout, TooManyRedirects) as error:
        print(error)

    executor.start_polling(dp, skip_updates=True)
