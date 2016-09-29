# -*- coding: utf-8-*-
import sqlite3
import telepot
import os
import time
import sys
import json
import re

from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardHide
from telepot.exception import TelegramError, BotWasBlockedError

from geopy.geocoders import Nominatim
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
import Queue
from res.maplib import get_distance

workdir = os.path.dirname(os.path.realpath(__file__))
data_file = '{}/webres/data.db'.format(workdir)
telesettings_file = '{}/res/telegram_data.db'.format(workdir)

geolocator = Nominatim()
db_data = sqlite3.connect(data_file)
db_telebot = None

POKEMON_NUM = 151

time_re = re.compile(r'^(([01]\d|2[0-3]):([0-5]\d)|24:00)$')

symbols = {'pin': u'📌 ', 'list': u'📝 ', 'info': u'ℹ ', 'bell': u'🔔 ', 'bell_crossed': u'🔕 ' , 'bed': u'🛌 ', 'globe': u'🌍 ', 'home': u'🏠 ', 'silence': u'🗣 ', 'yes': u"✅ ", 'no': u'❌ ', 'reset': u'♻ ', 'check': u'☑ ', 'uncheck':  u'◼ '}
user_settings = {}

log_queue = Queue.Queue()

def do_settings():
    global radius_by_default,radius_step,radius_max,messages, POKEMONS, POKEMON_NUM,about,bot,log_queue,log_to_file,ignored_default,log_notifications,max_notis_per_user_and_cycle,time_between_cycles
    with open('{}/res/telebotsettings.json'.format(workdir)) as f:
        telecfg = json.load(f)

    language = telecfg["language"]
    radius_by_default = int(telecfg["radius_by_default"])
    radius_step = telecfg["radius_step"]
    radius_max = telecfg["radius_max"]
    max_notis_per_user_and_cycle = telecfg["max_notis_per_user_and_cycle"]
    time_between_cycles = telecfg["time_between_cycles"]
    log_notifications = telecfg["log_notifications"]

    log_to_file = telecfg["log_to_file"]

    bot = telepot.Bot(str(telecfg["TELEGRAM_BOT_TOKEN"]))
    about = telecfg["info_about"]

    ignored_default = telecfg["ignored_by_default"]
    if type(ignored_default) == unicode:
        print(time.strftime('[%H:%M:%S] ' + '[!] Warning, the ignored_by_default setting in telebotsettings.json should be now a array like [1,2,3] instead of a string like "1,2,3"'))
        sys.exit()

    with open('{}/res/languages/{}.json'.format(workdir, language)) as f:
        messages = json.load(f)

    with open('{}/webres/static/{}.json'.format(workdir, language)) as f:
        POKEMONS = json.load(f)




def init_data():
    global db_telebot
    db_telebot = sqlite3.connect(telesettings_file,check_same_thread=False)
    db_telebot.text_factory = str
    cursor_telebot = db_telebot.cursor()
    cursor_telebot.execute("PRAGMA journal_mode = WAL")
    cursor_telebot.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, notify INTEGER, latitude REAL, longitude REAL, radius INTEGER, ignored TEXT, nick TEXT, silence TEXT)")
    db_telebot.commit()

def set_settings(id, noti=None, lat=None, lng=None, rad=None, ign=None, nick=None, silence=None):
    if noti is None:
        noti = user_settings[id]["noti"]
    if lat is None or lng is None:
        lat = user_settings[id]["lat"]
        lng = user_settings[id]["lng"]
    if rad is None:
        rad = user_settings[id]["radius"]
    if ign is None:
        ign = user_settings[id]["ignored"]
    if nick is None:
        nick = user_settings[id]["nick"]
    if silence is None:
        if "silence" in user_settings[id]:
            silence = user_settings[id]["silence"]
        else:
            silence = ""
    user_settings[id] = {'id': id, "noti": noti, "lat": lat, "lng": lng, "radius": rad, "ignored": ign, "nick": nick, "silence": silence}
    cursor_telebot = db_telebot.cursor()

    while True:
        try:
            cursor_telebot.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?,?,?)", [id, noti, round(lat, 5), round(lng, 5), rad, ','.join(map(str, ign)), nick, silence])
            db_telebot.commit()
            return user_settings[id]
        except sqlite3.OperationalError:
            pass

def get_settings(id):
    if (id in user_settings):
        return user_settings[id]
    else:
        return None


def load_all_settings():
    cursor_telebot = db_telebot.cursor()

    while True:
        try:
            for row in cursor_telebot.execute('SELECT id, notify, latitude, longitude, radius, ignored, nick, silence FROM users'):
                user_settings[row[0]] = {'id': row[0], 'noti': row[1], 'lat': row[2], 'lng': row[3], 'radius': row[4], 'ignored': [] if row[5].encode("ascii", "ignore") == "" else map(int, row[5].encode("ascii", "ignore").split(",")), 'nick': row[6], 'silence': "" if row[7] is None else row[7]}
            return
        except sqlite3.OperationalError:
            pass

def build_menu(stage, settings):
    markup = None
    if stage == "location":
        markup = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=symbols['pin'] + messages["location"], request_location=True)]
        ])
    elif stage == "main":
        if (len(settings["silence"]) == 11):
            silence_time = " [{}]".format(settings["silence"])
        else:
            silence_time = ""
        if settings['radius'] < radius_step:
            radius_buttons = [messages['radius_button'].format(settings['radius']), radius_step + "m"]
        elif settings['radius'] == radius_step:
            radius_buttons = [messages['radius_button'].format(settings['radius']), str(radius_step * 2) + "m"]
        elif settings['radius'] == radius_max:
            radius_buttons = [str(radius_max - radius_step) + "m", messages['radius_button'].format(settings['radius'])]
        else:
            radius_buttons = [str(settings['radius'] - radius_step) + "m", messages['radius_button'].format(settings['radius']), str(settings['radius'] + radius_step) + "m"]
        markup = ReplyKeyboardMarkup(keyboard=[
            radius_buttons,
            [symbols['list'] + messages["check_ignored"], symbols['info'] + messages["info"]],
            [symbols['bell'] + messages["turn_on"] if settings['noti'] == -1 else symbols['bell_crossed'] + messages["turn_off"], symbols['bed'] + messages["silence_hours"] + silence_time],
            [symbols['globe'] + messages["check_location"], KeyboardButton(text= symbols['pin'] + messages["update_location"], request_location=True)]
        ])
    elif stage == "ignored":
        pokemon_buttons = []
        for i in range(1, POKEMON_NUM + 1):
            if i in settings['ignored']:
                pokemon_buttons.append(symbols['no'] + "#" + str(i) + " " + POKEMONS[i])
            else:
                pokemon_buttons.append(symbols['yes'] + "#" + str(i) + " " + POKEMONS[i])
        formatted_pokemon_buttons = [[symbols['reset'] + messages["restore_default_ignored"], symbols['check'] + messages["mark_all"], symbols['uncheck']+ messages["unmark_all"]],[symbols['home'] + messages["home"]]]
        for i in range(0, len(pokemon_buttons), 3):
            formatted_pokemon_buttons.append(pokemon_buttons[i:i + 3])
        markup = ReplyKeyboardMarkup(keyboard=formatted_pokemon_buttons)
    elif stage == "silent":
        ignore_times = []
        for i in range(0, 24):
            ignore_times.append([messages["silence_from"] + " {:02}:00".format(i), messages["silence_to"] + " {:02}:00".format(i)])
        ignore_times.insert(0, [symbols['home'] + messages["home"]])
        if len(settings["silence"]) == 11:
            ignore_times.insert(0, [symbols['silence'] + messages["silence_deactivate"] + " [{}]".format(settings["silence"])])
        markup = ReplyKeyboardMarkup(keyboard=ignore_times)
    return markup


def send_message(chat_id, text, disable_notification=False, reply_markup=None, disable_web_page_preview=False):
    try:
        if reply_markup is None:
            bot.sendMessage(chat_id, text, parse_mode='HTML', disable_notification=disable_notification, disable_web_page_preview=disable_web_page_preview)
        else:
            bot.sendMessage(chat_id, text, parse_mode='HTML', disable_notification=disable_notification, disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
    except BotWasBlockedError:
        print_log("[!] Bot was blocked. Couldn't send message.")
    except TelegramError as e:
        print_log("[!] An error happened while sending message " + str(e.json))
    except Exception as e:
        print_log("[!] An unkown error happened while sending message, error: {}".format(e))


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    u_settings = get_settings(msg['from']['id'])
    tmp_nick = ("@" + msg['from']['username'] if 'username' in msg['from'] else msg['from']['first_name']) + " (" + str(msg['from']['id']) + ")"
    if content_type != 'text' and content_type != 'location':
        print_log('[o] Message received: ' + tmp_nick + ": " + str(content_type) + ", " + str(chat_type) + ", " + str(chat_id))
    if content_type == 'location':
        print_log('[l] Location received: ' + tmp_nick + ": [" + str(msg['location']['latitude']) + "," + str(msg['location']['longitude']) + "]")
        nick = ("@" + msg['from']['username'] if 'username' in msg['from'] else msg['from']['first_name'])
        if u_settings is None:
            u_settings = set_settings(msg['from']['id'], noti=chat_id, lat=msg['location']['latitude'], lng=msg['location']['longitude'], rad=radius_by_default, ign=ignored_default, nick=nick, silence="")
        else:
            u_settings = set_settings(msg['from']['id'], lat=msg['location']['latitude'], lng=msg['location']['longitude'])
        send_message(chat_id, messages["location_received"] + " " + messages["actual_radius"].format(u_settings["radius"]), reply_markup=build_menu("main", u_settings))
    if content_type == 'text':
        text = msg['text']
        print_log(u'[t] Text received: {}: "{}"'.format(tmp_nick,text))
        if (u_settings is None):
            send_message(chat_id, messages["greeting"], reply_markup=build_menu('location', u_settings))
        else:
            new_nick = "@" + msg['from']['username'] if 'username' in msg['from'] else msg['from']['first_name']
            if u_settings["nick"] != new_nick:
                set_settings(u_settings["id"], nick=new_nick)
            if messages["info"] in text:
                send_message(chat_id, about, disable_notification=True, disable_web_page_preview=True, reply_markup=build_menu("main", u_settings))
            elif messages["turn_on"] in text:
                u_settings = set_settings(u_settings['id'], noti=chat_id)
                send_message(chat_id, messages["notifications_on"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages["turn_off"] in text:
                u_settings = set_settings(u_settings['id'], noti=-1)
                send_message(chat_id, messages["notifications_off"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages["check_ignored"] in text:
                send_message(chat_id, messages["ignored_intro"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages["home"] in text:
                send_message(chat_id, messages["returning_home"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages["restore_default_ignored"] in text:
                u_settings = set_settings(u_settings['id'], ign=ignored_default)
                send_message(chat_id, messages["ignored_default_restored"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages["unmark_all"] in text:
                all_pokes = [i + 1 for i in range(POKEMON_NUM)]
                u_settings = set_settings(u_settings['id'], ign=all_pokes)
                send_message(chat_id, messages["unmarked_all"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages["mark_all"] in text:
                u_settings = set_settings(u_settings['id'], ign=[])
                send_message(chat_id, messages["marked_all"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages["silence_hours"] in text:
                send_message(chat_id, messages["silence_explanation"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages["silence_deactivate"] in text:
                u_settings = set_settings(chat_id, silence="")
                send_message(chat_id, messages["silence_deactivated"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages["silence_from"] in text:
                time = str(text[-5:])
                if len(time) == 5 and time_re.match(time):
                    if u_settings["silence"] == "" or ("-" in u_settings["silence"] and u_settings["silence"].split("-")[1] == ""):
                        u_settings = set_settings(u_settings["id"], silence=time + "-")
                        send_message(chat_id, messages["silence_choose"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
                    else:
                        u_settings = set_settings(u_settings["id"], silence=time + "-" + u_settings["silence"].split("-")[1])
                        send_message(chat_id, messages["silence_activated"] + " " + messages["silence_from"] + " " + str(u_settings["silence"].split("-")[0]) + " " + messages["silence_to"] + " " + str(u_settings["silence"].split("-")[1]), disable_notification=True,
                                     reply_markup=build_menu("silent", u_settings))
                else:
                    send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages["silence_to"] in text:
                time = str(text[-5:])
                if len(time) == 5 and time_re.match(time):
                    if u_settings["silence"] == "" or ("-" in u_settings["silence"] and u_settings["silence"].split("-")[0] == ""):
                        u_settings = set_settings(u_settings["id"], silence="-" + time)
                        send_message(chat_id, messages["silence_choose"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
                    else:
                        u_settings = set_settings(u_settings["id"], silence=u_settings["silence"].split("-")[0] + "-" + time)
                        send_message(chat_id, messages["silence_activated"] + " " + messages["silence_from"] + " " + str(u_settings["silence"].split("-")[0]) + " " + messages["silence_to"] + " " + str(u_settings["silence"].split("-")[1]), disable_notification=True,
                                     reply_markup=build_menu("silent", u_settings))
                else:
                    send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages["check_location"] in text:
                try:
                    bot.sendLocation(chat_id, u_settings['lat'], u_settings['lng'], disable_notification=True, reply_markup=build_menu("main", u_settings))
                except BotWasBlockedError as err:
                    print_log("[!] Bot was blocked. Couldn't send location.")
                except TelegramError as err:
                    print_log("[!] An error happened while sending location " + err.json)
                except:
                    print_log("[!] An unkown error happened while sending location")
            elif messages["radius_button"].format(u_settings['radius']) in text:
                send_message(chat_id, messages['check_radius'].format(u_settings['lat'], u_settings['lng'], float(u_settings['radius']) / 1000), disable_web_page_preview=True, disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif len(text) >= 2 and text[-1] == 'm' and text[:-1].isdigit():
                try:
                    rad = int(text[:-1])
                except:
                    print_log("[!] Error while parsing the distance '" + text[:-1] + "'")
                    send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("main", u_settings))
                else:
                    if (rad > radius_max):
                        rad = radius_max
                    if (rad < 0):
                        send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("main", u_settings))
                    elif rad == u_settings['radius']:
                        pass
                    else:
                        u_settings = set_settings(u_settings['id'], rad=rad)
                        send_message(chat_id, messages["actual_radius"].format(rad), disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif "#" in text:
                try:
                    poke_n = int(text[text.find("#") + 1:text.find(" ", text.find("#"))])
                except:
                    print_log("[!] Error while getting pokemon number for ignore list '" + text + "'")
                    send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
                else:
                    if (poke_n > POKEMON_NUM or poke_n <= 0):
                        send_message(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
                    else:
                        if (poke_n in u_settings['ignored']):
                            u_settings['ignored'].remove(poke_n)
                            send_message(chat_id, messages["pokemon_unignored"].format(poke_n, POKEMONS[poke_n]), disable_notification=True, reply_markup=build_menu("ignored", u_settings))
                        else:
                            u_settings['ignored'].append(poke_n)
                            send_message(chat_id, messages["pokemon_ignored"].format(poke_n, POKEMONS[poke_n]), disable_notification=True, reply_markup=build_menu("ignored", u_settings))
                        u_settings = set_settings(u_settings['id'], ign=u_settings['ignored'])

def get_active_pokemon():
    timenow = int(round(time.time(), 0))
    cursor_data = db_data.cursor()

    while True:
        try:
            return cursor_data.execute('SELECT spawnid, latitude, longitude, spawntype, pokeid, expiretime FROM spawns WHERE (expiretime > ?) AND (fromtime >= 0)', (timenow,)).fetchall()
        except sqlite3.OperationalError:
            pass


def print_log(s):
    log = u'{}{}'.format(time.strftime('[%H:%M:%S] '),s)
    print(log)
    if log_to_file:
        log_queue.put(log)


def is_time_interval_now(start, end):
    now = int(time.strftime('%H')) * 60 + int(time.strftime('%M'))
    sta = int(start.split(":")[0]) * 60 + int(start.split(":")[1])
    end = int(end.split(":")[0]) * 60 + int(end.split(":")[1])
    if sta < end:
        return sta < now and now < end
    elif sta > end:
        return now > sta or end > now
    else:
        return now == sta

def format_address(input, fieldnum):
    fields = input.split(', ')
    output = fields[0]
    for f in range(1,min(fieldnum,len(fields))):
        output += ', ' + fields[f]
    return output

def main():
    init_data()
    load_all_settings()
    do_settings()

    bot.message_loop({'chat': on_chat_message})
    print_log('[+] Telegram bot for PGO-mapscan-opt started!')

    notified = {}

    while True:
        if log_to_file:
            with open('{}/res/telegram_log.txt'.format(workdir), 'ab') as f:
                while not log_queue.empty():
                    f.write(u'{}\n'.format(log_queue.get(1)))
        time.sleep(time_between_cycles)
        pokes = get_active_pokemon()
        active_ids = set([])
        if max_notis_per_user_and_cycle > 0:
            received_notifications = {}
            for user in user_settings:
                received_notifications[user_settings[user]["id"]] = 0
        for poke in pokes:
            spawnid, lat, lng, spawntype, pokeid, expiretime = poke
            active_ids.add(spawnid)
            pokeid = int(pokeid)
            timenow = int(round(time.time(), 0))
            timeleft = expiretime - timenow
            mins, secs = divmod(timeleft, 60)
            time_spawned = "{}m {}s".format(mins, secs)
            time_despawn = datetime.fromtimestamp(expiretime).strftime('%H:%M:%S')
            message = messages["wild_pokemon"].format(POKEMONS[pokeid]) + '\n' + messages["time_left"].format(time_spawned, time_despawn)
            spawntype_times = [[15, 15, 15], [30, 15, 15], [15, 15, 30], [15, 30, 15]]  # Spawn types in format [Appear, Pause, Return] being the first one type = 1, next one type = 2...
            return_or_hidden = None
            roh_extra_time = None
            for i in range(len(spawntype_times)):
                if spawntype == (i + 1):
                    if timeleft > (60 * (spawntype_times[i][0] + spawntype_times[i][1])):
                        return_or_hidden = "return"
                        expiretime = expiretime - (60 * (spawntype_times[i][0] + spawntype_times[i][1]))
                        roh_for_time = (spawntype_times[i][1], spawntype_times[i][2])
                    elif timeleft > (60 * spawntype_times[i][0]):
                        return_or_hidden = "hidden"
                        expiretime = expiretime - (60 * spawntype_times[i][0])
                        roh_for_time = spawntype_times[i][2]
            if return_or_hidden == "return":
                timeleft = expiretime - timenow
                time_hide = datetime.fromtimestamp(expiretime).strftime('%H:%M:%S')
                mins, secs = divmod(timeleft, 60)
                time_till_hide = "{}m {}s".format(mins, secs)
                time_show = datetime.fromtimestamp(expiretime + (roh_for_time[0] * 60)).strftime('%H:%M:%S')
                message = messages["wild_pokemon"].format(POKEMONS[pokeid]) + '\n' + messages["time_left"].format(time_till_hide, time_hide) + '\n' + messages["time_return_later"].format(str(roh_for_time[0]) + "m", str(roh_for_time[1]) + "m", time_show, time_despawn)
            elif return_or_hidden == "hidden":
                timeleft = expiretime - timenow
                time_show = datetime.fromtimestamp(expiretime).strftime('%H:%M:%S')
                mins, secs = divmod(timeleft, 60)
                time_till_show = "{}m {}s".format(mins, secs)
                message = messages["hidden_pokemon"].format(POKEMONS[pokeid]) + '\n' + messages["time_hidden"].format(time_till_show, time_show, str(roh_for_time) + "m", time_despawn)
            address = None
            for user in user_settings:
                us = user_settings[user]
                user_id = int(us['id'])
                chat_id = int(us['noti'])
                if max_notis_per_user_and_cycle > 0:
                    if user_id not in received_notifications:
                        received_notifications[user_id] = 0
                    else:
                        if received_notifications[user_id] == max_notis_per_user_and_cycle:
                            send_message(chat_id, messages["maximum_notifications"].format(max_notis_per_user_and_cycle, time_between_cycles))
                            received_notifications[user_id] = received_notifications[user_id] + 1
                            print_log("[N] " + us['nick'] + " (" + str(us['id']) + ") got maximum notifications per cycle")
                            break
                        elif received_notifications[user_id] > max_notis_per_user_and_cycle:
                            break
                if chat_id not in notified:
                    notified[chat_id] = set([])
                if len(us['silence']) == 11:
                    silenced = is_time_interval_now(us['silence'].split("-")[0], us['silence'].split("-")[1])
                else:
                    silenced = False
                if (chat_id != -1) and (spawnid not in notified[chat_id]) and (not silenced) and (pokeid not in us['ignored']):
                    dist = round(get_distance((lat,lng),(us['lat'],us['lng'])))
                    if dist <= us['radius']:
                        if address is None:
                            try:
                                address = format_address(geolocator.reverse('{},{}'.format(lat, lng)).address,4)
                            except:
                                address = ""
                        if (address == ""):
                            message = message[0:message.find("\n")] + ' ' + messages['pokemon_distance'] + message[message.find("\n"):]
                        else:
                            message = message[0:message.find("\n")] + ' ' + messages['pokemon_distance'] + messages['pokemon_address'] + message[message.find("\n"):]
                        try:
                            if (message != ""):
                                argdic = {'distance': dist, 'address': address}
                                bot.sendMessage(chat_id, message.format(arg=argdic), parse_mode="html")
                                bot.sendLocation(chat_id, lat, lng, disable_notification=True)
                                if max_notis_per_user_and_cycle > 0:
                                    received_notifications[user_id] = received_notifications[user_id] + 1
                                if log_notifications:
                                    print_log(u"[N] Notified user {} ({}) of {} {}m away!".format(us['nick'],us['id'], POKEMONS[pokeid],dist))
                            notified[chat_id].add(spawnid)
                        except BotWasBlockedError as err:
                            print_log("[!] Bot was blocked. Deactivated notifications for " + us['nick'] + " (" + str(us['id']) + ")")
                            us = set_settings(us['id'], noti=-1)
                        except TelegramError as err:
                            if (err.error_code == 400):
                                print_log("[!] Chat is not available or message is wrong. Deactivated notifications for " + us['nick'] + " (" + str(us['id']) + ")")
                                us = set_settings(us['id'], noti=-1)
                            else:
                                print_log("[!] Error on notification sending! Notifications deactivated for " + us['nick'] + " (" + str(us['id']) + ")")
                                us = set_settings(us['id'], noti=-1)
                            try:
                                bot.sendMessage(chat_id, messages["error"], disable_notification=True, reply_markup=build_menu("main", us))
                            except:
                                pass
        for k in notified:  # remove inactive spawns from notified list so it doesn't overflow TOO MUCH
            notified[k] = notified[k].intersection(active_ids)

if __name__ == '__main__':
    main()