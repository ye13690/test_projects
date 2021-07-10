import json

import telebot
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

# import asyncio
# import websockets

import config

bot = telebot.TeleBot(config.API_KEY)
ws_url = 'wss://stream.coinmarketcap.com/price/latest'
hide_keyboard = telebot.types.ReplyKeyboardRemove()
BUTTONS = {
    'btn_top10': telebot.types.KeyboardButton('get top 10 cryptocurrencies'),
    'btn_monitor': telebot.types.KeyboardButton('monitor chosen cryptocurrency'),
    'btn_start': telebot.types.KeyboardButton('start monitoring'),
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
parameters = {
    'start': '1',
    'limit': '10',
    'convert': 'USD'
}
headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': config.COINMARKETCAP_KEY,
}

# get top 10 cryptocurrencies and some info on them
@bot.message_handler(commands=['get_top_10'])
def get_top_10(message):
    session = Session()
    session.headers.update(headers)

    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        text = ''
        print(data)
        for coin in data['data']:
            text += f"{coin['cmc_rank']}. {coin['name']} ({coin['symbol']}):\n" \
                    f"\tprice: ${coin['quote']['USD']['price']}\n" \
                    f"\tmarket cap: ${coin['quote']['USD']['market_cap']}\n\n"
        bot.send_message(message.chat.id, text,
                             reply_markup=keyboard)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def command_default(message):
    msg = message.text
    if msg == "get top 10 cryptocurrencies":
        get_top_10(message)

bot.polling()
# @bot.message_handler(commands=['monitor'])
# def monitor(message):
#
#

