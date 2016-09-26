# -*- coding: utf-8 -*-

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
from queue import Queue

workdir = os.path.dirname(os.path.realpath(__file__))

with open('{}/res/telebotsettings.json'.format(workdir)) as f:
    telecfg = json.load(f)

ignored_by_default = telecfg["ignored_by_default"]

# Support the old ignored string to array
if type(ignored_by_default) == unicode:
    print(time.strftime('[%H:%M:%S] ' + '[!] Warning, the ignored_by_default setting in telebotsettings.json should be now a array like [1,2,3] instead of a string like "1,2,3"'))
    sys.exit()

language = telecfg["language"]
radius_by_default = int(telecfg["radius_by_default"])
radius_step = telecfg["radius_step"]
radius_max = telecfg["radius_max"]
max_notis_per_user_and_cycle = telecfg["max_notis_per_user_and_cycle"]
time_between_cycles = telecfg["time_between_cycles"]
log_notifications = telecfg["log_notifications"]
log_to_file = telecfg["log_to_file"]
TELEGRAM_BOT_TOKEN = telecfg["TELEGRAM_BOT_TOKEN"]
info_about = telecfg["info_about"]

with open('{}/res/usersettings.json'.format(workdir)) as f:
    cfg = json.load(f)

messages = {}

if (language == "spanish"):
    messages = {"location": "Manda tu ubicacion",
                "greeting": "¡Hola! Este bot te mandara notificaciones de pokemon cercanos segun especifiques. ¡Manda tu ubicacion para comenzar!",
                "location_received": "¡Tu ubicacion ha sido recibida correctamente! Ahora puedes usar el menu para configurar tu radio o pokemon ignorados.",
                "actual_radius": "Tu radio actual es {}m",
                "check_ignored": "Pokemon ignorados",
                "restore_default_ignored": "Por defecto",
                "ignored_default_restored": "Configuracion de pokemon ignorados por defecto restaurada",
                "mark_all": "Notificar todos",
                "marked_all": "Notificaciones de todos los pokemon activadas",
                "unmark_all": "Ignorar todos",
                "unmarked_all": "Notificaciones de todos los pokemon desactivadas",
                "update_location": "Actualiza tu ubicacion",
                "turn_off": "Desactivar notificaciones",
                "turn_on": "Activar notificaciones",
                "notifications_on": "Las notificaciones han sido activadas",
                "notifications_off": "Las notificaciones han sido desactivadas",
                "check_location": "Ver ubicacion actual",
                "error": "Disculpa, un error ha ocurrido",
                "radius_button": "Radio: [{}m]",
                "check_radius": "Puedes ver tu radio actual aqui https://www.freemaptools.com/radius-around-point.htm?clat={}&clng={}&r={}&lc=FFFFFF&lw=1&fc=00FF00&mt=r&fs=true",
                "home": "Volver al menu principal",
                "ignored_intro": "Aqui tienes una lista de tus notificaciones de pokemon. Los pokemon con ✅ seran notificados y los pokemon con ❌ seran ignorados. Presiona para cambiar.",
                "returning_home": "De vuelta al menu principal",
                "pokemon_ignored": "El pokemon #{0} {1} no sera notificado",
                "pokemon_unignored": "El pokemon #{0} {1} sera notificado",
                "wild_pokemon": "¡Un <b>{0}</b> salvaje apareció!",
                "hidden_pokemon": "¡Un <b>{0} oculto</b> fue avistado!",
                "time_left": "Seguira ahi por <b>{0}</b> hasta {1}.",
                "time_hidden": "Seguira escondiendose por <b>{0}</b> hasta {1} y aparecera por <b>{2}</b> hasta {3}.",
                "time_return_later": "<b>{0}</b> mas tarde aparecera por <b>{1}</b> desde {2} hasta {3}.",
                "pokemon_distance": "Esta a tan solo <b>{arg[distance]}m</b>",
                "pokemon_address": ", cerca de <i>{arg[address]}</i>",
                "maximum_notifications": "Has llegado a tus notificaciones maximas consecutivas, que son {0} por {1} segundos, ¡intenta ignorar mas pokemon o hacer el rango mas pequeño!",
                "info": "Sobre el bot",
                "silence_hours": "No molestar",
                "silence_explanation": "Mediante esta opcion puedes configurar un intervalo de horas en el que el bot no te mandara notificaciones. Elige las dos horas que conforman el intervalo y se activara.",
                "silence_from": "de ->",
                "silence_to": "a ->",
                "silence_deactivate": "Quitar silencio",
                "silence_deactivated": "Silencio desactivado",
                "silence_activated": "Silencio activado",
                "silence_choose": "Ahora elige el otro marcador del intervalo"
                }
elif (language == "french"):
    messages = {"location": "Envoyer ma géolocalisation",
                "greeting": "Bonjour ! Grâce à ce bot vous pourrez recevoir les notifications pour les pokémons spécifiés à portée. Envoyez votre géolocalisation pour commencer !",
                "location_received": "Géolocalisation reçue, vous pouvez maintenant utiliser le menu pour configurer votre rayon et la liste des notifications !",
                "actual_radius": "Distance du rayon {}m.",
                "check_ignored": "Config. des notifications",
                "restore_default_ignored": "Par défaut",
                "ignored_default_restored": "Liste des pokémons notifiés par défaut chargée.",
                "mark_all": "Tous",
                "marked_all": "Vous recevrez une notification pour tous les pokémons.",
                "unmark_all": "Aucun",
                "unmarked_all": "Aucun pokémon ne vous sera notifié.",
                "update_location": "Me géolocaliser",
                "turn_off": "Désactifier les notifs",
                "turn_on": "Activer les notifs",
                "notifications_on": "Notifications activées.",
                "notifications_off": "Notifications désactivées.",
                "check_location": "Vérif. géolocalisation",
                "error": "Désolé, une erreur est survenue.",
                "radius_button": "Rayon: [{}m]",
                "check_radius": "Vous pouvez voir votre rayon ici https://www.freemaptools.com/radius-around-point.htm?clat={}&clng={}&r={}&lc=FFFFFF&lw=1&fc=00FF00&mt=r&fs=true",
                "home": "Menu principal",
                "ignored_intro": "Voici la liste des notifications. Les pokémons marqués d'un ✅ seront notifiés et les pokémons marqués d'un ❌ seront ignorés. Appuyez pour modifier.",
                "returning_home": "Retour au menu principal",
                "pokemon_ignored": "Le pokémon #{0} {1} ne sera pas notifié;",
                "pokemon_unignored": "Le pokémon #{0} {1} sera notifié",
                "wild_pokemon": "Un <b>{0}</b> sauvage apparaît !",
                "hidden_pokemon": "Un hidden {0} <b>caché</b> est découvert !",
                "time_left": "Il sera là pour <b>{0}</b> jusque {1}",
                "time_hidden": "Il restera caché pour <b>{0}</b> jusque {1} puis reviendra pour <b>{2}</b> jusque {3}",
                "time_return_later": "<b>{0}</b> plus tard, il reviendra pour <b>{1}</b> de {2} jusque {3}",
                "pokemon_distance": "Distance: <b>{arg[distance]}m</b>",
                "pokemon_address": ", près de <i>{arg[address]}</i>",
                "maximum_notifications": "Vous avez atteint le nombre maximum de notifications consécutives, qui est de {0} par {1} secondes, essayez d'ignorer plus de pokémons ou de réduire le rayon !",
                "info": "A propos",
                "silence_hours": "Ne pas déranger",
                "silence_explanation": "Vous pouvez configurer l'intervalle de temps durant laquelle vous ne voulez pas être dérangé.",
                "silence_from": "de ->",
                "silence_to": "a ->",
                "silence_deactivate": "Désactiver le mode silencieux",
                "silence_deactivated": "Silencieux désactivé",
                "silence_activated": "Silencieux activé",
                "silence_choose": "Sélectionnez maintenant jusqu'à quand vous ne voulez pas être dérangé"
                }
elif language == "dutch":
    messages = {"location": "Stuur uw lokatie",
                "greeting": "Hallo!, Deze bot zal u notificaties sturen van pokemons die in uw buurt zijn, stuur uw lokatie om te beginnen!",
                "location_received": "Uw lokatie is ontvangen! U kunt nu in het menu de settings aanpassen van de radius of pokemons waar u niet over genotificeerd wilt worden.",
                "actual_radius": "Uw radius is nu {}m.",
                "check_ignored": "Genegeerde pokemon",
                "restore_default_ignored": "Standaard",
                "ignored_default_restored": "Configuratie van standaard genegeerde pokemon hersteld.",
                "mark_all": "Notificatie aan voor alle pokemons ",
                "marked_all": "Alle pokemon notificaties zijn aan.",
                "unmark_all": "Negeer alle pokemons",
                "unmarked_all": "Alle pokemon notificaties zijn uit.",
                "update_location": "Update uw lokatie",
                "turn_off": "Zet notificaties uit",
                "turn_on": "Zet notificaties aan",
                "notifications_on": "Notificaties zijn aangezet.",
                "notifications_off": "Notificaties zijn uitgezet.",
                "check_location": "Check uw huidige locatie",
                "error": "Excuses, er was een error.",
                "radius_button": "Radius: [{}m]",
                "check_radius": "U kan hier uw radius checken https://www.freemaptools.com/radius-around-point.htm?clat={}&clng={}&r={}&lc=FFFFFF&lw=1&fc=00FF00&mt=r&fs=true",
                "home": "Terug naar hoofdmenu",
                "ignored_intro": "Hier is een lijst of alle pokemons, U krijgt notificaties van de pokemons gemarkeerd met ✅ en de pokemons gemarkeerd met ❌ worden genegeerd. Druk op de naam van de pokemon om de setting te veranderen.",
                "returning_home": "Terug naar het hoofdmenu",
                "pokemon_ignored": "Pokemon #{0} {1} genegeerd",
                "pokemon_unignored": "Pokemon #{0} {1} krijgt u notificaties van",
                "wild_pokemon": "Een wild <b>{0}</b> is gevonden!",
                "hidden_pokemon": "Een <b>verborgen {0}</b> is gevonden!",
                "time_left": "Het zal er zijn voor <b>{0}</b> tot {1}",
                "time_hidden": "Het zal verborgen zijn voor <b>{0}</b> tot {1} dan er weer zijn voor  <b>{2}</b> tot {3}",
                "time_return_later": "<b>{0}</b> later zal het er weer zijn voor <b>{1}</b> voor {2} tot {3}",
                "pokemon_distance": "Het is maar <b>{arg[distance]}m</b> van uw locaties verwijderd",
                "pokemon_address": ", bij <i>{arg[address]}</i>",
                "maximum_notifications": "U heeft de maximale notificaties gehad, Dat is {0} per {1} sekonden, probeer meer pokemons te negeren of maak uw radius kleiner!",
                "info": "Over deze bot!",
                "silence_hours": "Niet storen",
                "silence_explanation": "Met deze optie kan u instellen hoe lang u geen notificaties meer wilt ontvangen, de interval is in uren.",
                "silence_from": "vanaf ->",
                "silence_to": "tot ->",
                "silence_deactivate": "Deactiveer niet storen",
                "silence_deactivated": "Niet storen geactiveerd",
                "silence_activated": "Niet storen geactiveerd",
                "silence_choose": "Kies nu de andere marker voor het interval"
                }
else:  # if(language == "english"):
    messages = {"location": "Send your location",
                "greeting": "Hello! This bot will send you notifications of nearby pokemon as you specify. Send your ubication to start!",
                "location_received": "Your location has been received successfully! Now you can use the menu to configure your radius or ignored pokemon.",
                "actual_radius": "Your radius is set to {}m.",
                "check_ignored": "Ignored pokemon",
                "restore_default_ignored": "By default",
                "ignored_default_restored": "Configuration of pokemon ignored by default restored.",
                "mark_all": "Notify all",
                "marked_all": "All pokemon notifications turned on.",
                "unmark_all": "Ignore all",
                "unmarked_all": "All pokemon notifications turned off.",
                "update_location": "Update your location",
                "turn_off": "Turn notifications off",
                "turn_on": "Turn notifications on",
                "notifications_on": "Notifications have been turned on.",
                "notifications_off": "Notifications have been turned off.",
                "check_location": "Check current location",
                "error": "Sorry, an error happened.",
                "radius_button": "Radius: [{}m]",
                "check_radius": "You can see your current radius here https://www.freemaptools.com/radius-around-point.htm?clat={}&clng={}&r={}&lc=FFFFFF&lw=1&fc=00FF00&mt=r&fs=true",
                "home": "Go back to main men",
                "ignored_intro": "Here you have a list of your pokemon notifications. The pokemon marked with ✅ will be notified and the pokemon with ❌ will be ignored. Press to toggle.",
                "returning_home": "Returned to main men",
                "pokemon_ignored": "Pokemon #{0} {1} wont be notified",
                "pokemon_unignored": "Pokemon #{0} {1} will be notified",
                "wild_pokemon": "A wild <b>{0}</b> appeared!",
                "hidden_pokemon": "A <b>hidden {0}</b> has been spotted!",
                "time_left": "It will be there for <b>{0}</b> until {1}",
                "time_hidden": "It will keep hidding for <b>{0}</b> until {1} then appear for <b>{2}</b> until {3}",
                "time_return_later": "<b>{0}</b> later it will appear for <b>{1}</b> from {2} until {3}",
                "pokemon_distance": "Its just <b>{arg[distance]}m</b> away",
                "pokemon_address": ", near <i>{arg[address]}</i>",
                "maximum_notifications": "You have reached your maximum consecutive notifications, which are {0} per {1} seconds, try ignoring more pokemon or make your range smaller!",
                "info": "About the bot",
                "silence_hours": "Do not disturb",
                "silence_explanation": "With this option you can configure an interval of hours in which the bot won't send you notifications. Choose the two hours that form the interval and it will activate.",
                "silence_from": "from ->",
                "silence_to": "to ->",
                "silence_deactivate": "Deactivate silence",
                "silence_deactivated": "Silence deactivated",
                "silence_activated": "Silence activated",
                "silence_choose": "Now choose the other marker for the interval"
                }

POKEMONS = json.load(open('{}/webres/static/{}.json'.format(workdir, cfg["language"])))
POKEMON_NUM = 151

data_file = '{}/webres/data.db'.format(workdir)
telesettings_file = '{}/res/telegram_data.db'.format(workdir)

user_settings = {}
messages_ascii = {}

geolocator = Nominatim()

db_data = sqlite3.connect(data_file)

db_telebot = None


def init_data():
    global db_telebot,cursor_telebot
    db_telebot = sqlite3.connect(telesettings_file)
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
    cursor_telebot.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?,?,?)", [id, noti, round(lat, 5), round(lng, 5), rad, ','.join(map(str, ign)), nick, silence])
    db_telebot.commit()
    return user_settings[id]


def get_settings(id):
    if (id in user_settings):
        return user_settings[id]
    else:
        return None


def load_all_settings():
    cursor_telebot = db_telebot.cursor()
    for row in cursor_telebot.execute('SELECT id, notify, latitude, longitude, radius, ignored, nick, silence FROM users'):
        user_settings[row[0]] = {'id': row[0], 'noti': row[1], 'lat': row[2], 'lng': row[3], 'radius': row[4], 'ignored': [] if row[5].encode("ascii", "ignore") == "" else map(int, row[5].encode("ascii", "ignore").split(",")), 'nick': row[6], 'silence': "" if row[7] is None else row[7]}


def build_menu(stage, settings):
    markup = None
    if stage == "location":
        markup = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='📌 ' + messages["location"], request_location=True)]
        ])
    elif stage == "main":
        if (len(settings["silence"]) == 11):
            silence_time = " [{}]".format(settings["silence"])
        else:
            silence_time = ""
        if settings['radius'] < radius_step:
            radius_buttons = [messages['radius_button'].format(settings['radius']), str(radius_step) + "m"]
        elif settings['radius'] == radius_step:
            radius_buttons = [messages['radius_button'].format(settings['radius']), str(radius_step * 2) + "m"]
        elif settings['radius'] == radius_max:
            radius_buttons = [str(radius_max - radius_step) + "m", messages['radius_button'].format(settings['radius'])]
        else:
            radius_buttons = [str(settings['radius'] - radius_step) + "m", messages['radius_button'].format(settings['radius']), str(settings['radius'] + radius_step) + "m"]
        markup = ReplyKeyboardMarkup(keyboard=[
            radius_buttons,
            ["📝 " + messages["check_ignored"], "ℹ️ " + messages["info"]],
            ["🔔 " + messages["turn_on"] if settings['noti'] == -1 else "🔕 " + messages["turn_off"], "🛌 " + messages["silence_hours"] + silence_time],
            ["🌍 " + messages["check_location"], KeyboardButton(text='📌 ' + messages["update_location"], request_location=True)]
        ])
    elif stage == "ignored":
        pokemon_buttons = []
        for i in range(1, POKEMON_NUM + 1):
            if i in settings['ignored']:
                pokemon_buttons.append("❌ #".decode('utf-8') + str(i) + " " + POKEMONS[i])
            else:
                pokemon_buttons.append("✅ #".decode('utf-8') + str(i) + " " + POKEMONS[i])
        formatted_pokemon_buttons = []
        for i in xrange(0, len(pokemon_buttons), 3):
            formatted_pokemon_buttons.append(pokemon_buttons[i:i + 3])
        formatted_pokemon_buttons.insert(0, ["🏠 " + messages["home"]])
        formatted_pokemon_buttons.insert(0, ["♻️ " + messages["restore_default_ignored"], "☑️ " + messages["mark_all"], "◼️ " + messages["unmark_all"]])
        markup = ReplyKeyboardMarkup(keyboard=formatted_pokemon_buttons)
    elif stage == "silent":
        ignore_times = []
        for i in range(0, 24):
            ignore_times.append([messages["silence_from"] + " {:02}:00".format(i), messages["silence_to"] + " {:02}:00".format(i)])
        ignore_times.insert(0, ["🏠 " + messages["home"]])
        if len(settings["silence"]) == 11:
            ignore_times.insert(0, ["🗣 " + messages["silence_deactivate"] + " [{}]".format(settings["silence"])])
        markup = ReplyKeyboardMarkup(keyboard=ignore_times)
    return markup


def send_message(chat_id, text, disable_notification=False, reply_markup=None, disable_web_page_preview=False):
    try:
        if reply_markup is None:
            bot.sendMessage(chat_id, text, disable_notification=disable_notification, disable_web_page_preview=disable_web_page_preview)
        else:
            bot.sendMessage(chat_id, text, disable_notification=disable_notification, disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
    except BotWasBlockedError as err:
        print_log("[!] Bot was blocked. Couldn't send message.")
    except TelegramError as err:
        print_log("[!] An error happened while sending message " + str(err.json))
    except:
        print_log("[!] An unkown error happened while sending message")


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
            u_settings = set_settings(msg['from']['id'], noti=chat_id, lat=msg['location']['latitude'], lng=msg['location']['longitude'], rad=radius_by_default, ign=ignored_by_default, nick=nick, silence="")
        else:
            u_settings = set_settings(msg['from']['id'], lat=msg['location']['latitude'], lng=msg['location']['longitude'])
        send_message(chat_id, messages["location_received"] + " " + messages["actual_radius"].format(u_settings["radius"]), reply_markup=build_menu("main", u_settings))
    if content_type == 'text':
        text = msg['text'].encode('ascii', 'replace')
        print_log('[t] Text received: ' + tmp_nick + ": '" + text + "'")
        if (u_settings is None):
            send_message(chat_id, messages["greeting"], reply_markup=build_menu('location', u_settings))
        else:
            new_nick = "@" + msg['from']['username'] if 'username' in msg['from'] else msg['from']['first_name']
            if u_settings["nick"] != new_nick:
                set_settings(u_settings["id"], nick=new_nick)
            if messages_ascii["info"] in text:
                send_message(chat_id, info_about, disable_notification=True, disable_web_page_preview=True, reply_markup=build_menu("main", u_settings))
            elif messages_ascii["turn_on"] in text:
                u_settings = set_settings(u_settings['id'], noti=chat_id)
                send_message(chat_id, messages["notifications_on"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages_ascii["turn_off"] in text:
                u_settings = set_settings(u_settings['id'], noti=-1)
                send_message(chat_id, messages["notifications_off"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages_ascii["check_ignored"] in text:
                send_message(chat_id, messages["ignored_intro"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages_ascii["home"] in text:
                send_message(chat_id, messages["returning_home"], disable_notification=True, reply_markup=build_menu("main", u_settings))
            elif messages_ascii["restore_default_ignored"] in text:
                u_settings = set_settings(u_settings['id'], ign=ignored_by_default)
                send_message(chat_id, messages["ignored_default_restored"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages_ascii["unmark_all"] in text:
                all_pokes = [i + 1 for i in range(POKEMON_NUM)]
                u_settings = set_settings(u_settings['id'], ign=all_pokes)
                send_message(chat_id, messages["unmarked_all"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages_ascii["mark_all"] in text:
                u_settings = set_settings(u_settings['id'], ign=[])
                send_message(chat_id, messages["marked_all"], disable_notification=True, reply_markup=build_menu("ignored", u_settings))
            elif messages_ascii["silence_hours"] in text:
                send_message(chat_id, messages["silence_explanation"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages_ascii["silence_deactivate"] in text:
                u_settings = set_settings(chat_id, silence="")
                send_message(chat_id, messages["silence_deactivated"], disable_notification=True, reply_markup=build_menu("silent", u_settings))
            elif messages_ascii["silence_from"] in text:
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
            elif messages_ascii["silence_to"] in text:
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
            elif messages_ascii["check_location"] in text:
                try:
                    bot.sendLocation(chat_id, u_settings['lat'], u_settings['lng'], disable_notification=True, reply_markup=build_menu("main", u_settings))
                except BotWasBlockedError as err:
                    print_log("[!] Bot was blocked. Couldn't send location.")
                except TelegramError as err:
                    print_log("[!] An error happened while sending location " + err.json)
                except:
                    print_log("[!] An unkown error happened while sending location")
            elif messages_ascii["radius_button"].format(u_settings['radius']) in text:
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
    return cursor_data.execute('SELECT spawnid, latitude, longitude, spawntype, pokeid, expiretime FROM spawns WHERE (expiretime > ?) AND (fromtime >= 0)', (timenow,)).fetchall()


def haversine(lon1, lat1, lon2, lat2):  # aaron-d from stackoverflow
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6367 * c
    return km * 1000


def print_log(s):
    print(time.strftime('[%H:%M:%S] ') + str(s))
    if log_to_file:
        log_queue.put(time.strftime('%d/%m/%y %H:%M:%S ') + str(s))


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


if (log_to_file):
    log_queue = Queue()

init_data()
load_all_settings()

for m in messages:
    messages_ascii[m] = messages[m].decode("utf-8").encode('ascii', 'replace')

bot = telepot.Bot(TELEGRAM_BOT_TOKEN)

bot.message_loop({'chat': on_chat_message})
print_log('[+] Telegram bot for PGO-mapscan-opt started!')

notified = {}

time_re = re.compile(r'^(([01]\d|2[0-3]):([0-5]\d)|24:00)$')

while 1:
    if log_to_file:
        queue_to_file = log_queue
        log_queue = Queue()
        with open('{}/res/telegram_log.txt'.format(workdir), 'a') as f:
            while not queue_to_file.empty():
                f.write(queue_to_file.get() + '\n')
        del queue_to_file
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
                dist = int(haversine(lng, lat, us['lng'], us['lat']))
                if dist <= us['radius']:
                    if address is None:
                        try:
                            address = geolocator.reverse('{},{}'.format(lat, lng)).address.encode("utf-8")
                            address = address.split(", ")[1] + ", " + address.split(", ")[0]
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
                                print_log("[N] Notified user " + us['nick'] + " (" + str(us['id']) + ") of " + POKEMONS[pokeid] + " " + str(dist) + "m away!")
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
