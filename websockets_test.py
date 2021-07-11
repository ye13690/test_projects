import asyncio
import json

import websockets
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import Command, Text
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
    print('in outer')
    global currency_info
    async with websockets.connect(url, ping_interval=None) as client:
        print('in with')
        await client.send(params_json)
        data = json.loads(await client.recv())
        p1h = data['d']['cr']['p1h']
        id = data['d']['cr']['id']
        currency_info[id]['latest_p1h'] = p1h
        while True:
            print('in while')
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
dp = Dispatcher(bot)

loop = asyncio.get_event_loop()

BUTTONS = {
    'btn_start_monitoring': KeyboardButton('Start monitoring'),
    'btn_stop_monitoring': KeyboardButton('Stop monitoring')
}


@dp.message_handler(Command('help'))
async def start(message: types.Message):
    await message.answer("/start - get to the start\n"
                         "/start_monitoring - to monitor cryptocurrency\n"
                         "/stop_monitoring - to stop monitoring process\n"
                         "/help - basic commands")


@dp.message_handler(Command('start'))
async def start(message: types.Message):
    keyboard = ReplyKeyboardMarkup()
    keyboard.add(BUTTONS['btn_start_monitoring'])
    await message.answer("Press button to start monitoring.", reply_markup=keyboard)


@dp.message_handler(Command('start_monitoring'))
async def start_monitoring(message: types.Message):
    global monitoring_task
    keyboard = ReplyKeyboardMarkup()
    keyboard.add(BUTTONS['btn_stop_monitoring'])
    await message.reply(
        f"Started monitoring!\nYou'll receive updates about currencies whose 1h% is greater than {threshold_value}",
        reply_markup=keyboard)
    monitoring_task = asyncio.ensure_future(listen(message.chat.id))


@dp.message_handler(Command('stop_monitoring'))
async def stop_monitoring(message: types.Message):
    global monitoring_task
    keyboard = ReplyKeyboardMarkup()
    keyboard.add(BUTTONS['btn_start_monitoring'])
    await message.answer("Stopped monitoring!\nPress button to start monitoring.", reply_markup=keyboard)
    monitoring_task.cancel()


@dp.message_handler(Text(equals=['Start monitoring', 'Stop monitoring']))
async def handle_buttons_feedback(message: types.Message):
    if message.text == 'Start monitoring':
        await start_monitoring(message)
    elif message.text == 'Stop monitoring':
        await stop_monitoring(message)


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
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

    executor.start_polling(dp, skip_updates=True)
