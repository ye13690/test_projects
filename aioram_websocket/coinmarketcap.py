import asyncio
import json

import telebot
import websockets
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

from telebot.pyTelegramBotAPI import config

bot = telebot.AsyncTeleBot(config.API_KEY)
# task = bot.get_me()
# print(task)
hide_keyboard = telebot.types.ReplyKeyboardRemove()
BUTTONS = {
    'btn_top10': telebot.types.KeyboardButton('get top 10 cryptocurrencies (API)'),
    'btn_monitor': telebot.types.KeyboardButton('monitor cryptocurrency (WSS)'),
    # 'btn_start': telebot.types.KeyboardButton('start monitoring'),
    'btn_stop': telebot.types.KeyboardButton('stop monitoring')
}
# print(f"name: ,"
#       f"symbol: ,"
#       f"cmc_rank: ,"
#       f"last_updated: {coin['last_updated']},"
#       f"price: ,"
#       f"volume_24h: {coin['quote']['USD']['volume_24h']},"
#       f"% 24h: {coin['quote']['USD']['percent_change_24h']},"
#       f"% 1h: {coin['quote']['USD']['percent_change_1h']},"
#       f"% 7d: {coin['quote']['USD']['percent_change_7d']},"
#       f"% 30d: {coin['quote']['USD']['percent_change_30d']},"
#       f"% 60d: {coin['quote']['USD']['percent_change_60d']},"
#       f"% 90d: {coin['quote']['USD']['percent_change_90d']}")
keyboard = telebot.types.ReplyKeyboardMarkup()
keyboard.row(BUTTONS['btn_top10']).row(BUTTONS['btn_monitor'])

url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
wss_url = 'wss://stream.coinmarketcap.com/price/latest?method=subscribe&id=price&data=cryptoIds=1=1027=825=1839=2010=52&index=null'
id_map_url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/map'

headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': config.COINMARKETCAP_KEY,
}

listing_latest_parameters = {
    'start': '1',
    'limit': '10',
    'convert': 'USD'
}

wss_parameters = {"method": "subscribe", "id": "price", "data": {
    "cryptoIds": [1, 1027, 825, 1839, 2010, 52, 74, 3408, 6636, 7083, 4687, 1831, 2, 5426, 1975, 3717, 3890, 2416, 1321,
                  512, 8916, 4943, 3077, 2280, 1958, 328, 7278, 1765, 4172, 3794, 3635, 5994, 7186, 4030, 4195, 3957,
                  1518, 3602, 4023, 4256, 1376, 2011, 5692, 6945, 1720, 6719, 5805, 7129, 3822, 5034, 1168, 6892, 4847,
                  3718, 2502, 4066, 4642, 1274, 2563, 2700, 4157, 1437, 131, 2586, 1966, 5864, 5665, 2634, 2130, 873,
                  2087, 6783, 6758, 2682, 3155, 3330, 2694, 6535, 8335, 2394, 3945, 2469, 4558, 1697, 2083, 5567, 1727,
                  1698, 6538, 1896, 1684, 2499, 1042, 2566, 2135, 109, 1808, 1567, 3897, 2099, 9023, 9022],
    "index": None}}

wss_parameters_json = json.dumps(wss_parameters)

threshold_value = 2

currency_info = {}

session = Session()
session.headers.update(headers)

# get map of all cryptocurrencies (id, rank, name, symbol)
try:
    response = session.get(id_map_url)
    data = json.loads(response.text)
    for coin in data['data']:
        currency_info[coin['id']] = {'rank': coin['rank'],
                                     'name': coin['name'],
                                     'symbol': coin['symbol'],
                                     'latest_p1h': 0}
except (ConnectionError, Timeout, TooManyRedirects) as e:
    print(e)




# get top 10 cryptocurrencies and some info on them
@bot.message_handler(commands=['get_top_10'])
def get_top_10(message):
    try:
        response = session.get(url, params=listing_latest_parameters)
        print(response.url)
        data = json.loads(response.text)
        text = ''
        for coin in data['data']:
            text += f"{coin['cmc_rank']}. {coin['name']} ({coin['symbol']}):\n" \
                    f"\tprice: ${coin['quote']['USD']['price']}\n" \
                    f"\tmarket cap: ${coin['quote']['USD']['market_cap']}\n\n"
        bot.send_message(message.chat.id, text,
                         reply_markup=keyboard)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


@bot.message_handler(commands=['monitor'])
def monitor(message):
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.add(BUTTONS['btn_stop'])



@bot.message_handler(func=lambda message: True, content_types=['text'])
def command_default(message):
    msg = message.text
    if msg == 'get top 10 cryptocurrencies (API)':
        get_top_10(message)
    elif msg == 'monitor cryptocurrency (WSS)':
        monitor(message)
    elif msg == 'stop monitoring':
        loop.close()


async def listen():
    global currency_info, loop
    async with websockets.connect(url, ping_interval=None) as client:
        await client.send(wss_parameters_json)
        data = json.loads(await client.recv())
        p1h = data['d']['cr']['p1h']
        id = data['d']['cr']['id']
        currency_info[id]['latest_p1h'] = p1h
        while True:
            data = json.loads(await client.recv())
            p1h = data['d']['cr']['p1h']
            id = data['d']['cr']['id']
            if p1h >= threshold_value and currency_info[id]['latest_p1h'] != p1h:
                currency_info[id]['latest_p1h'] = p1h
                # bot.send_message(message.chat.id, text=f"{currency_info[id]['name']}({currency_info[id]['symbol']}) -> {p1h}\n"
                #       f"Currently ranks {currency_info[id]['rank']}",
                #                  reply_markup=keyboard)

loop = asyncio.get_event_loop()
loop.run_until_complete(listen())

bot.polling()