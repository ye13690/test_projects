import logging
import os
import time
from datetime import datetime
from functools import wraps

# heroku database connected to hobby-dev plan (10 000 rows)
# to change plan: https://devcenter.heroku.com/articles/updating-heroku-postgres-databases
import psycopg2
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request

import config

bot = telebot.TeleBot(config.API_KEY)

BUTTONS = {
    'btn_start': telebot.types.KeyboardButton("say hi to the bot"),
    'btn_change_name': telebot.types.KeyboardButton("change your name"),
    'btn_show_all_notif': telebot.types.KeyboardButton('show all notifications'),
    'btn_new_notif': telebot.types.KeyboardButton("new 🗒"),
    'btn_redact_notif': telebot.types.KeyboardButton("redact 🗒"),
    'btn_delete_notif': telebot.types.KeyboardButton("delete 🗒"),
    'btn_delete': telebot.types.KeyboardButton("delete your data from the database"),
    'help': telebot.types.KeyboardButton("help"),
    'btn_all_users': telebot.types.KeyboardButton("show all users"),
    'btn_set_new_admin': telebot.types.KeyboardButton("set user as admin"),
    'btn_demote_from_admin': telebot.types.KeyboardButton("demote user from admin"),
    'btn_block_user': telebot.types.KeyboardButton("block user")
}

hide_keyboard = telebot.types.ReplyKeyboardRemove()
user_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
user_keyboard.row(BUTTONS['btn_start']).row(BUTTONS['btn_change_name']).row(BUTTONS['btn_show_all_notif'])
user_keyboard.row(BUTTONS['btn_new_notif'], BUTTONS['btn_redact_notif'], BUTTONS['btn_delete_notif'])
user_keyboard.row(BUTTONS['help']).row(BUTTONS['btn_delete'])
admin_keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
admin_keyboard.row(BUTTONS['btn_start']).row(BUTTONS['btn_change_name']).row(BUTTONS['btn_show_all_notif'])
admin_keyboard.row(BUTTONS['btn_new_notif'], BUTTONS['btn_redact_notif'], BUTTONS['btn_delete_notif'])
admin_keyboard.row(BUTTONS['help']).row(BUTTONS['btn_delete'])
admin_keyboard.row(BUTTONS['btn_all_users']).row(BUTTONS['btn_set_new_admin'])
admin_keyboard.row(BUTTONS['btn_demote_from_admin']).row(BUTTONS['btn_block_user'])


# check if user is admin
def is_admin(user_id):
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT admin FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        fetch = cursor.fetchone()[0]
        return fetch
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)


# creating a decorator to disallow access to bot for blocked users
def not_blocked_access():
    def deco_resctrict(f):
        @wraps(f)
        def f_restrict(message, *args, **kwargs):
            user_id = message.from_user.id
            try:
                conn = psycopg2.connect(
                    host=config.HOST,
                    database=config.DATABASE,
                    user=config.USER,
                    password=config.PASSWORD)
                cursor = conn.cursor()
                query = "SELECT id FROM blocked WHERE id = %s"
                cursor.execute(query, (user_id,))
                if not cursor.fetchone():
                    return f(message, *args, **kwargs)
            except (Exception, psycopg2.DatabaseError) as error:
                print(error)
                bot.reply_to(message, f"Oops! I encountered some error.\nTry again later🙃")
            else:
                conn.close()

        return f_restrict

    return deco_resctrict


# TODO: /start - say hi to the bot👋
@bot.message_handler(commands=['start'])
@not_blocked_access()
def start(message):
    try:
        chat_id, name = message.from_user.id, message.from_user.first_name
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT name, admin FROM users WHERE id=%s"
        cursor.execute(query, (chat_id,))
        user = cursor.fetchone()
        if not user:
            query = "INSERT INTO users(id, name, username, admin) VALUES (%s, %s, %s, %s)"
            cursor.execute(query,
                           (chat_id, name, message.from_user.username if message.from_user.username else '---', 'f'))
            conn.commit()
            bot.send_message(chat_id, f"Hi, {name}👋\nI'm random bot, nice to meet you!")
            help(message)
            cursor.execute('SELECT COUNT(id) FROM users WHERE admin=FALSE')
            all_users = cursor.fetchone()[0]
            cursor.execute('SELECT id FROM users WHERE admin=TRUE')
            rows = cursor.fetchall()
            for row in rows:
                bot.send_message(row[0],
                                 f"New user!\nId: {chat_id}\n"
                                 f"Full name: {message.from_user.first_name} {message.from_user.last_name}\n"
                                 f"Currently there are {all_users} users (non-admin)")
        else:
            bot.send_message(chat_id, f"Hi, {user[0]}👋\nLong time no see.",
                             reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /change_name - change your name in the bot's database🗃
@bot.message_handler(commands=['change_name'])
@not_blocked_access()
def change_name(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
    bot.send_message(message.from_user.id, "Send me your new name, please.", reply_markup=keyboard)
    bot.register_next_step_handler(message, process_name_step)


def process_name_step(message):
    try:
        chat_id = message.from_user.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT name FROM users WHERE id=%s"
        cursor.execute(query, (chat_id,))
        old_name = cursor.fetchone()[0]
        new_name = message.text.strip()
        query = "UPDATE users SET name=%s WHERE id=%s"
        cursor.execute(query, (new_name, chat_id))
        conn.commit()
        bot.send_message(chat_id, f"Your name was changed from {old_name} to {new_name}!",
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /show_all_notif - show all your notifications📑
@bot.message_handler(commands=['show_all_notif'])
@not_blocked_access()
def show_all_notif(message):
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT time, message FROM schedule WHERE id_user=%s ORDER BY time ASC"
        cursor.execute(query, (message.chat.id,))
        all_notif = cursor.fetchall()
        text = ''
        if all_notif:
            for row in all_notif:
                text += f'{row[0]}:\n  {row[1]}\n'
        else:
            text = "You don't have any notifications yet!"
        bot.send_message(message.from_user.id, text,
                         reply_markup=admin_keyboard if is_admin(message.chat.id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /create_notif - create new notification📝
@bot.message_handler(commands=['create_notif'])
@not_blocked_access()
def create_notif(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
    bot.send_message(message.from_user.id,
                     "Enter the time for notification in the following format:\nhh:mm\nExample: 09:30",
                     reply_markup=keyboard)
    bot.register_next_step_handler(message, process_time_step)


def process_time_step(message):
    try:
        chat_id = message.from_user.id
        notif_time = message.text.strip()
        time.strptime(notif_time, '%H:%M')
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
        msg = bot.send_message(chat_id,
                               "Now enter the message you want to attach to the notification!\n"
                               "Maximum length is 255 characters, but it's better to keep it short.",
                               reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_message_step, notif_time)
    except ValueError:
        msg = bot.reply_to(message, "Not the right time format!\nTry again, please.")
        bot.register_next_step_handler(msg, process_time_step)
        return
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")


def process_message_step(message, notif_time):
    try:
        chat_id = message.from_user.id
        notif_msg = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "INSERT INTO schedule(id_user, time, message) VALUES (%s, %s, %s)"
        cursor.execute(query, (chat_id, notif_time, notif_msg))
        conn.commit()
        bot.send_message(chat_id, 'Notification was successfully created!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")


# TODO: /redact_notif - redact notification in the database✍️
@bot.message_handler(commands=['redact_notif'])
@not_blocked_access()
def redact_notif(message):
    keyboard_notif = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard_notif.row(
        telebot.types.KeyboardButton('Cancel')
    )
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT time, message FROM schedule WHERE id_user=%s ORDER BY time ASC"
        cursor.execute(query, (message.chat.id,))
        all_notif = cursor.fetchall()
        if all_notif:
            for notif in all_notif:
                keyboard_notif.row(
                    telebot.types.KeyboardButton(f'{notif[0]} -> {notif[1]}'),
                )
            bot.send_message(message.from_user.id,
                             "Which notification do you want to redact?",
                             reply_markup=keyboard_notif)
            bot.register_next_step_handler(message, process_notif_step)
        else:
            bot.send_message(message.from_user.id, "You don't have any notifications to redact!",
                             reply_markup=admin_keyboard if is_admin(message.from_user.id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


def process_notif_step(message):
    try:
        if message.text == 'Cancel':
            text = "Cancelled! Nothing was changed or added🙂"
            bot.send_message(message.chat.id, text)
            bot.clear_step_handler(message)
            return
        notif_time = message.text[:5]
        keyboard_choice = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        keyboard_choice.row(
            telebot.types.KeyboardButton('Time'),
            telebot.types.KeyboardButton('Message')
        )
        keyboard_choice.row(
            telebot.types.KeyboardButton('Cancel')
        )
        bot.send_message(message.chat.id,
                         "What do you want to redact?",
                         reply_markup=keyboard_choice)
        bot.register_next_step_handler(message, process_redact_notif_step, notif_time)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")


def process_redact_notif_step(message, notif_time):
    try:
        column_to_redact = message.text.lower()
        if column_to_redact == 'cancel':
            text = "Cancelled! Nothing was changed or added🙂"
            bot.send_message(message.chat.id, text)
            bot.clear_step_handler(message)
        elif column_to_redact == 'time':
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
            bot.send_message(message.chat.id,
                             "Enter new time for the notification in the following format:\nhh:mm\nExample: 09:30",
                             reply_markup=keyboard)
            bot.register_next_step_handler(message, process_redact_time_step, notif_time)
        elif column_to_redact == 'message':
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
            bot.send_message(message.chat.id,
                             "Enter new message for the notification.\n"
                             "Maximum length is 255 characters, but it's better to keep it short.",
                             reply_markup=keyboard)
            bot.register_next_step_handler(message, process_redact_message_step, notif_time)
    except Exception as error:
        print(error)
        bot.reply_to(message.chat.id, "Oops! I encountered some error.\nTry again later🙃")


def process_redact_time_step(message, notif_time):
    try:
        chat_id = message.chat.id
        new_time = message.text.strip()
        time.strptime(new_time, '%H:%M')
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "UPDATE schedule SET time=%s WHERE id_user=%s AND time=%s"
        cursor.execute(query, (new_time, chat_id, notif_time))
        conn.commit()
        bot.send_message(chat_id, 'Notification was successfully updated!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except ValueError:
        msg = bot.reply_to(message, "Not the right time format!\nTry again, please.")
        bot.register_next_step_handler(msg, process_redact_time_step, notif_time)
        return
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message.chat.id, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


def process_redact_message_step(message, notif_time):
    try:
        chat_id = message.chat.id
        new_message = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "UPDATE schedule SET message=%s WHERE id_user=%s AND time=%s"
        cursor.execute(query, (new_message, chat_id, notif_time))
        conn.commit()
        bot.send_message(chat_id, 'Notification was successfully updated!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message.chat.id, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /delete_notif - delete notification🗑
@bot.message_handler(commands=['delete_notif'])
@not_blocked_access()
def delete_notif(message):
    keyboard_notif = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard_notif.row(
        telebot.types.KeyboardButton('Cancel')
    )
    try:
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT time, message FROM schedule WHERE id_user=%s ORDER BY time ASC"
        cursor.execute(query, (message.chat.id,))
        all_notif = cursor.fetchall()
        if all_notif:
            for notif in all_notif:
                keyboard_notif.row(
                    telebot.types.KeyboardButton(f'{notif[0]} -> {notif[1]}'),
                )
            bot.send_message(message.from_user.id,
                             "Which notification do you want to delete?",
                             reply_markup=keyboard_notif)
            bot.register_next_step_handler(message, process_delete_step)
        else:
            bot.send_message(message.from_user.id,
                             "You don't have any notifications!",
                             reply_markup=admin_keyboard if is_admin(message.from_user.id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
        bot.clear_step_handler(message)
    else:
        conn.close()


def process_delete_step(message):
    try:
        chat_id = message.chat.id
        if message.text == 'Cancel':
            text = "Cancelled! Nothing was changed or added🙂"
            bot.send_message(message.chat.id, text, reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
            bot.clear_step_handler(message)
            return
        notif_time = message.text[:5]
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "DELETE FROM schedule WHERE id_user=%s AND time=%s"
        cursor.execute(query, (chat_id, notif_time))
        conn.commit()
        bot.send_message(chat_id, 'Notification was successfully deleted!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")


# TODO : As an admin you also can: /all_users - show list of all users
@bot.message_handler(commands=['all_users'])
@not_blocked_access()
def all_users(message):
    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id, name, username, admin FROM users WHERE id != %s"
        cursor.execute(query, (chat_id,))
        users_list = ''
        admin_list = ''
        for row in cursor.fetchall():
            print(row[3])
            if row[3]:
                admin_list += f'id: {row[0]} : {row[1]} : @{row[2]}\n'
            else:
                users_list += f'{row[0]} : {row[1]} : @{row[2]}\n'
        text = f'Admins:\n{admin_list}\nUsers:\n{users_list}'
        split_text = telebot.util.smart_split(text)
        for msg in split_text:
            bot.send_message(chat_id, msg)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")


# TODO: /set_new_admin - set user as admin
@bot.message_handler(commands=['set_new_admin'])
@not_blocked_access()
def set_new_admin(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id, name, username FROM users WHERE id != %s AND admin=FALSE"
        cursor.execute(query, (chat_id,))
        text = 'All users:\n'
        for row in cursor.fetchall():
            text += f'id: {row[0]} : {row[1]} : @{row[2]}\n'
        split_text = telebot.util.smart_split(text)
        for msg in split_text:
            bot.send_message(chat_id, msg)
        bot.send_message(chat_id,
                         "Who do you want to set as new admin?\nPlease, write their Id.",
                         reply_markup=keyboard)
        bot.register_next_step_handler(message, process_check_user_step)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
        bot.clear_step_handler(message)
    else:
        conn.close()


def process_check_user_step(message):
    try:
        chat_id = message.chat.id
        user_id = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user_id = cursor.fetchone()[0]
        if not cursor:
            msg = bot.reply_to(message, f"Couldn't find {user_id} in the database.\n"
                                        f"Check the id and try again, please.")
            bot.register_next_step_handler(msg, process_check_user_step)
            return

        query = "UPDATE users SET admin=TRUE WHERE id=%s"
        cursor.execute(query, (user_id,))
        conn.commit()
        bot.send_message(chat_id, f'User with id {user_id} was set as admin!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
        bot.send_message(user_id, 'You was set as an admin!\nCheck /help to see what you can do now.',
                         reply_markup=admin_keyboard if is_admin(user_id) else user_keyboard)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /demote_from_admin - demote user from admin
@bot.message_handler(commands=['demote_from_admin'])
@not_blocked_access()
def demote_from_admin(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id, name, username FROM users WHERE id != %s AND admin=TRUE"
        cursor.execute(query, (chat_id,))
        text = 'All admins:\n'
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                text += f'id: {row[0]} : {row[1]} : @{row[2]}\n'
            split_text = telebot.util.smart_split(text)
            for msg in split_text:
                bot.send_message(chat_id, msg)
            bot.send_message(chat_id,
                             "Who do you want to demote from being an admin?\nPlease, write their id.",
                             reply_markup=keyboard)
            bot.register_next_step_handler(message, process_check_admin_step)

        else:
            bot.send_message(chat_id,
                             "There is no other admins beside you!",
                             reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
        bot.clear_step_handler(message)
    else:
        conn.close()


def process_check_admin_step(message):
    try:
        chat_id = message.chat.id
        user_id = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        user_id = cursor.fetchone()[0]
        if not cursor:
            msg = bot.reply_to(message, f"Couldn't find {user_id} in the database.\n"
                                        f"Check the id and try again, please.")
            bot.register_next_step_handler(msg, process_check_user_step)
            return

        query = "UPDATE users SET admin=FALSE WHERE id=%s"
        cursor.execute(query, (user_id,))
        conn.commit()
        bot.send_message(chat_id, f'User with id {user_id} was demoted from being an admin!',
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
        bot.send_message(user_id,
                         'You was demoted from being an admin!\nCheck /help to see what options were disabled.',
                         reply_markup=admin_keyboard if is_admin(user_id) else user_keyboard)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /block_user - block user
@bot.message_handler(commands=['block_user'])
@not_blocked_access()
def block_user(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Cancel', callback_data='cancel'))
    try:
        chat_id = message.chat.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id, name, username FROM users WHERE id != %s"
        cursor.execute(query, (chat_id,))
        text = 'All admins:\n'
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                text += f'id: {row[0]} : {row[1]} : @{row[2]}\n'
            split_text = telebot.util.smart_split(text)
            for msg in split_text:
                bot.send_message(chat_id, msg)
            bot.send_message(chat_id,
                             "Who do you want to block?\nPlease, write their id.",
                             reply_markup=keyboard)
            bot.register_next_step_handler(message, process_check_user_for_block_step)
        else:
            bot.send_message(chat_id,
                             "There are no users to block at the moment!",
                             reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
        bot.clear_step_handler(message)
    else:
        conn.close()


def process_check_user_for_block_step(message):
    try:
        chat_id = message.chat.id
        user_id = message.text.strip()
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id=%s"
        cursor.execute(query, (user_id,))
        user_id = cursor.fetchone()[0]
        if not cursor:
            msg = bot.reply_to(message, f"Couldn't find {user_id} in the database.\n"
                                        f"Check the id and try again, please.")
            bot.register_next_step_handler(msg, process_check_user_step)
            return

        query = "DELETE FROM users WHERE id=%s"
        cursor.execute(query, (user_id,))
        conn.commit()
        query = "INSERT INTO blocked(id) VALUES %s"
        cursor.execute(query, (user_id,))
        conn.commit()
        bot.send_message(chat_id, f'User {user_id} was blocked!')
        bot.send_message(user_id,
                         "You was blocked by one of admins!Now you can't use this bot.\n"
                         "Your messages from now on will be ignored.",
                         reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except Exception as error:
        print(error)
        bot.reply_to(message, "Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


# TODO: /help - get all available commands and other info🙋
@bot.message_handler(commands=['help'])
@not_blocked_access()
def help(message):
    try:
        chat_id = message.from_user.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT admin FROM users WHERE id=%s"
        cursor.execute(query, (chat_id,))
        msg = cursor.fetchone()[0]
        text = "This bot is created for practice purpose.🧪\n" \
               "To interact with the bot you can use following commands that are available in your keyboard below!\n\n" \
               "/start - say hi to the bot👋\n" \
               "/change_name - change your name in the bot's database🗃\n" \
               "/show_all_notif - show all your notifications📑" \
               "/create_notif - create new notification📝\n" \
               "/redact_notif - redact notification in the database✍\n" \
               "/delete_notif - delete notification🗑\n" \
               "/delete - delete your data from the bot's database🚮\n" \
               "/help - get all available commands and other info🙋"

        if msg:
            text += "\n\nAs an admin🕴 you also can:\n" \
                    "/all_users - show list of all users\n" \
                    "/set_new_admin - set user as admin\n" \
                    "/demote_from_admin - demote user from admin\n" \
                    "/block_user - block user"
        bot.send_message(chat_id, text, reply_markup=admin_keyboard if is_admin(chat_id) else user_keyboard)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


@bot.message_handler(commands=['delete'])
@not_blocked_access()
def delete(message):
    try:
        chat_id = message.from_user.id
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "DELETE FROM users WHERE id=%s"
        cursor.execute(query, (chat_id,))
        conn.commit()
        bot.send_message(chat_id, f"Your info was deleted from the database😐\n"
                                  f"You won't receive any notifications in future.",
                         reply_markup=None)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        bot.reply_to(message, f"Oops! I encountered some error.\nTry again later🙃")
    else:
        conn.close()


@bot.callback_query_handler(func=lambda call: call.data in ['cancel'])
def callback_cancel(call):
    if call.message:
        if call.data == "cancel":
            text = "Cancelled! Nothing was changed or added🙂"
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text)
            bot.answer_callback_query(callback_query_id=call.id, show_alert=False, text="Cancelled!")
            bot.clear_step_handler(call.message)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def command_default(message):
    msg = message.text
    if msg == "say hi to the bot":
        start(message)
    elif msg == "change your name":
        change_name(message)
    elif msg == 'show all notifications':
        show_all_notif(message)
    elif msg == "new 🗒":
        create_notif(message)
    elif msg == "redact 🗒":
        redact_notif(message)
    elif msg == "delete 🗒":
        delete_notif(message)
    elif msg == "delete your data from the database":
        delete(message)
    elif msg == "help":
        help(message)
    elif msg == "show all users" and is_admin(message.chat.id):
        all_users(message)
    elif msg == "set user as admin" and is_admin(message.chat.id):
        set_new_admin(message)
    elif msg == "demote user from admin" and is_admin(message.chat.id):
        demote_from_admin(message)
    elif msg == "block user" and is_admin(message.chat.id):
        block_user(message)


logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

server = Flask(__name__)

schedule = BackgroundScheduler(daemon=True)


@server.route(f'/{config.API_KEY}', methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@server.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f'https://telegrambotproject7.herokuapp.com/{config.API_KEY}')
    return "?", 200


def job():
    try:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        conn = psycopg2.connect(
            host=config.HOST,
            database=config.DATABASE,
            user=config.USER,
            password=config.PASSWORD)
        cursor = conn.cursor()
        query = "SELECT id_user, time, message FROM schedule WHERE time=%s"
        cursor.execute(query, (current_time,))
        rows = cursor.fetchall()
        print(current_time)
        if rows:
            for row in rows:
                user_id, t, msg = row[0], row[1], row[2]
                print(row)
                bot.send_message(user_id, msg)

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    else:
        conn.close()


schedule.add_job(func=job, trigger='interval', seconds=60)
schedule.start()

if __name__ == "__main__":
    server.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
