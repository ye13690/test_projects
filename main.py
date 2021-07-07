import logging
import os

import psycopg2
import telebot
from flask import Flask, request

import config

# now = datetime.now()
# current_time = now.strftime("%H:%M")

ids = []

# get ids of all users in the db
try:
    conn = psycopg2.connect(
        host="ec2-34-242-89-204.eu-west-1.compute.amazonaws.com",
        database="d7cevg37mv6gi1",
        user="pjusxohbtpdfxj",
        password="0b4da611f6e516b06bd6e1f3dc4fefbb1ba047761e7662c4820936db93029b0e")
    cursor = conn.cursor()
    query = "SELECT id FROM users"
    cursor.execute(query)
    ids = [row[0] for row in cursor]
except (Exception, psycopg2.DatabaseError) as error:
    print(error)
else:
    conn.close()

bot = telebot.TeleBot(config.API_KEY)
bot.state = None


@bot.message_handler(commands=['start'])
def start(message):
    chat_id, name = message.from_user.id, message.from_user.first_name
    try:
        conn = psycopg2.connect(
            host="ec2-34-242-89-204.eu-west-1.compute.amazonaws.com",
            database="d7cevg37mv6gi1",
            user="pjusxohbtpdfxj",
            password="0b4da611f6e516b06bd6e1f3dc4fefbb1ba047761e7662c4820936db93029b0e")
        cursor = conn.cursor()
        query = f"SELECT * FROM users WHERE id={chat_id}"
        cursor.execute(query)
        msg = cursor.fetchone()
        if not msg:
            query = "INSERT INTO users(id, name, username, admin) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (chat_id, name, message.from_user.username, 'f'))
            conn.commit()
            bot.send_message(chat_id, f"Hi, {name}👋\nI'm random bot, nice to meet you!")
            help(message)
        else:
            cursor.execute(query)
            data = [i for i in cursor]
            bot.send_message(chat_id, f"Hi, {data[0][1]}👋\nLong time no see.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    else:
        conn.close()


@bot.message_handler(commands=['help'])
def help(message):
    chat_id = message.from_user.id
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(
        "/start - say hi to the bot", callback_data="/start"))
    keyboard.add(telebot.types.InlineKeyboardButton(
        "/change_name - change your name in the bot's database", callback_data="/change_name"))
    keyboard.add(telebot.types.InlineKeyboardButton(
        "/delete - delete your data from the database.", callback_data="/delete"))
    text = "This bot is created for practice purpose.🧪\n" \
           "The bot is copying your text-messages (non-commands ones) and counts the total number of them.\n" \
           "Available commands:"
    bot.send_message(chat_id, text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda query: True)
def callback(update, context):
    print(update, context)
    input = update.callback_query.data
    if input == "/start":
        start(update, context)
    elif input == "/change_name":
        change_name(update, context)
    elif input == "/delete":
        delete(update, context)


@bot.message_handler(commands=['change_name'])
def change_name(message):
    chat_id = message.from_user.id
    bot.send_message(chat_id, "Send me your new name, please.\nP.S. you can /cancel this operation")
    bot.state = "New name"


@bot.message_handler(commands=['cancel'])
def cancel(message):
    chat_id = message.from_user.id
    bot.send_message(chat_id, "Cancelled! Your name stays the same🙂")


@bot.message_handler(func=lambda message: bot.state == "New name")
def set_name(message):
    chat_id = message.from_user.id
    try:
        conn = psycopg2.connect(
            host="ec2-34-242-89-204.eu-west-1.compute.amazonaws.com",
            database="d7cevg37mv6gi1",
            user="pjusxohbtpdfxj",
            password="0b4da611f6e516b06bd6e1f3dc4fefbb1ba047761e7662c4820936db93029b0e")
        cursor = conn.cursor()
        query = f"SELECT name FROM users WHERE id={chat_id}"
        cursor.execute(query)
        old_name = [i for i in cursor][0][0]
        new_name = message.text.strip()
        query = "UPDATE users SET name=%s WHERE id=%s"
        cursor.execute(query, (new_name, chat_id))
        conn.commit()
        bot.send_message(chat_id, f"Your name was changed from {old_name} to {new_name}!")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.send_message(chat_id, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


@bot.message_handler(commands=['delete'])
def delete(message):
    chat_id = message.from_user.id
    try:
        conn = psycopg2.connect(
            host="ec2-34-242-89-204.eu-west-1.compute.amazonaws.com",
            database="d7cevg37mv6gi1",
            user="pjusxohbtpdfxj",
            password="0b4da611f6e516b06bd6e1f3dc4fefbb1ba047761e7662c4820936db93029b0e")
        cursor = conn.cursor()
        query = f"DELETE FROM users WHERE id={chat_id}"
        cursor.execute(query)
        conn.commit()
        bot.send_message(chat_id, f"Your info was deleted from the database😐\nNow I don't know you.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.send_message(chat_id, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


@bot.message_handler(func=lambda message: True,
                     regexp=r"^[/start|/help|/delete|/change_name].*")
def default_command(message):
    chat_id = message.from_user.id
    try:
        conn = psycopg2.connect(
            host="ec2-34-242-89-204.eu-west-1.compute.amazonaws.com",
            database="d7cevg37mv6gi1",
            user="pjusxohbtpdfxj",
            password="0b4da611f6e516b06bd6e1f3dc4fefbb1ba047761e7662c4820936db93029b0e")
        cursor = conn.cursor()
        query = f"UPDATE users SET count = count + 1 WHERE id={chat_id}"
        cursor.execute(query)
        conn.commit()
        query = f"SELECT count FROM users WHERE id={chat_id}"
        cursor.execute(query)
        count = [i for i in cursor][0]
        if message.content_type == 'text':
            bot.send_message(chat_id, f"{message.text}\n✉{count[0]} messages")
        else:
            bot.send_message(chat_id,
                             f"I can't send your {message.content_type} back, but I'll count it in!\n✉{count[0]} messages")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.send_message(chat_id, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# bot.set_webhook(url='https://telegrambotproject7.herokuapp.com/')

# if "HEROKU" in list(os.environ.keys()):
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

server = Flask(__name__)

@server.route(f'/{config.API_KEY}', methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@server.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f'https://telegrambotproject7.herokuapp.com/{config.API_KEY}')
    return "?", 200

server.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

# else:
#     bot.remove_webhook()
#     bot.polling(none_stop=True)
#
#


# if __name__ == "__main__":
#     server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8443)))
# def schedule_checker():
#     while True:
#         schedule.run_pending()
#         sleep(1)


# def send_message(some_id, message):
#     print(some_id, message)
#     return bot.send_message(some_id, message)

# bot.polling()
# if __name__ == "__main__":
#     # for chat_id in ids:
#     #     for key in dict:
#     #         schedule.every().day.at(key).do(send_message, chat_id, dict[key])
#     #
#     Thread(target=schedule_checker).start()
#     bot.polling()
