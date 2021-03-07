from telebot import types
from pprint import pprint

import telebot
import pymorphy2
import airtable

API_KEY = "keyWW51qc3XJ1IAcL"
BASE_ID = "appThlWBsBPCRJHmz"
TOKEN = "1671740637:AAEwC7Ny9zVmjvyoX0yj93vGApPV0vUrF78"

bot = telebot.TeleBot(TOKEN, parse_mode=None)
morph = pymorphy2.MorphAnalyzer()


now = types.ReplyKeyboardMarkup(resize_keyboard=True)
now.add(types.KeyboardButton("Начать поиск"))

START_KEYBOARD = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
START_KEYBOARD.add(types.KeyboardButton('Вывести всех'), types.KeyboardButton('Вывести по фамилии'),
                   types.KeyboardButton('Вывести по кафедре'), types.KeyboardButton('Найти дипломную работу'))


class Teacher:
    def __init__(self, surname, name, middle_name, department, email, phone, other_social):
        self.name = name
        self.surname = surname
        self.middleName = "" if middle_name == "Незивестно" else middle_name
        self.phone = phone
        self.email = email
        self.department = department
        self.otherSocial = other_social if other_social != "Неизвестно" else ""

    def info(self):
        return "ФИО: {}\nКафедра: {}\nПочта: {}\nНомер: {}{}".format(f"{self.surname} {self.name} {self.middleName}",
                                                                     self.department, self.email, self.phone,
                                                                     f"\nДругая связь: {self.otherSocial}"
                                                                     if self.otherSocial != "" else "")


# Проверка на наличие ключа
def field_validation(fields):
    list_column = ["Surname", "Name", "MiddleName", "Department", "Email address", "Phone", "SocialNetwork"]

    dict_teacher = {}
    for column in list_column:
        dict_teacher[column] = ""

    for column in range(len(list_column)):
        name_column = list_column[column]
        try:
            dict_teacher[name_column] = fields[name_column]
        except KeyError:
            dict_teacher[name_column] = "Неизвестно"

    return dict_teacher


# Возвращает количество подходящих под требования поиска, и их список из класса Teacher
def return_value_bd(search_column="surname", value=""):
    at = airtable.Airtable(BASE_ID, "TeacherList", API_KEY)

    try:
        TeacherList = []
        value_list = at.search(search_column, value)
        len_list = len(value_list)

        if len_list != 0:
            for elem in value_list:
                dt = field_validation(elem['fields'])
                TeacherList.append(Teacher(dt['Surname'], dt['Name'], dt["MiddleName"], dt["Department"],
                                           dt['Email address'], dt['Phone'], dt["SocialNetwork"]))

        return len_list, TeacherList
    except KeyError:
        return -1, "Данный преподаватель не найден"

    except Exception:
        return -1, "Ой, произошла ошибочка"


# Вернет названия кафедр во множестве
def set_by_buttons(name_table, name_search):
    at = airtable.Airtable(BASE_ID, name_table, API_KEY)
    set_list = set()

    for i in at.get_all():
        try:
            set_list.add(i["fields"][name_search])

        except KeyError:
            pass

    return set_list


# Старт бота и то что он умеет
@bot.message_handler(content_types=['text'])
def start(message):

    msg = bot.send_message(message.from_user.id, "Привет, я умею находить контакты преподавателей. А дальше по кнопкам",
                           reply_markup=START_KEYBOARD)

    bot.register_next_step_handler(msg, send)


# Основной процесс, распределение выбора между ключем поиска
def send(message):
    text = message.text.lower()

    if text == "вывести всех":
        bot.send_message(message.from_user.id, "Внимание! В базе данных содержится огромное количество преподавателей, "
                                               "во избежание травмы вашей психики мы выведем только первые 10...",
                         reply_markup=now)
        output_all(message)

    elif text == "вывести по кафедре":
        set_list = set_by_buttons("TeacherList", "Department")

        department_keyboard = types.ReplyKeyboardMarkup(row_width=len(set_list) // 2, resize_keyboard=True)
        for i in set_list:
            department_keyboard.add(types.KeyboardButton(i))

        msg = bot.send_message(message.from_user.id, f"Поиск по кафедре. Введите кафедру",
                               reply_markup=department_keyboard)
        bot.register_next_step_handler(msg, search_chair)

    elif text == "вывести по фамилии":
        msg = bot.send_message(message.from_user.id, f"Поиск по фамилии. Введите фамилию")
        bot.register_next_step_handler(msg, search_surname)

    elif text == "найти дипломную работу":
        set_list = set_by_buttons("GraduateWork", "Subject")

        subject_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i in set_list:
            subject_keyboard.add(types.KeyboardButton(i))

        msg = bot.send_message(message.from_user.id, "Введите название предмета", reply_markup=subject_keyboard)
        bot.register_next_step_handler(msg, diplom)

    else:
        bot.send_message(message.from_user.id, "Пожалуйста, нажмите кнопку")


# Вывод всех преподавателей с ограничением в 10 человек
def output_all(message):
    at = airtable.Airtable(BASE_ID, "TeacherList", API_KEY)
    TeacherList = []

    for elem in at.get_all():
        dt = field_validation(elem['fields'])

        TeacherList.append(Teacher(dt['Surname'], dt['Name'], dt["MiddleName"], dt["Department"], dt['Email address'],
                                   dt['Phone'], dt["SocialNetwork"]))
    for ind, teacher in enumerate(TeacherList):
        if ind >= 10:
            break
        bot.send_message(message.from_user.id, teacher.info())


# Поиск преподователей по кафедре
def search_chair(message):
    department = message.text

    set_list = set_by_buttons("TeacherList", "Department")

    if department in set_list:
        len_list, value_list = return_value_bd("Department", department)

        for i in value_list:
            bot.send_message(message.from_user.id, i.info(), reply_markup=now)
    else:
        bot.send_message(message.from_user.id, "Введенная кафедра не найдена", reply_markup=now)


# Поиск преподователей по фамилии
def search_surname(message):
    len_list, value_list = return_value_bd("surname", message.text.split(" ")[0].title())

    if len_list > 1:
        action_keyboard = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True, resize_keyboard=True)
        action_keyboard.add(types.KeyboardButton("Вывести всех"), types.KeyboardButton("Ввести имя"))

        msg = bot.send_message(message.from_user.id,
                               "Было найдено {} "
                               "{}.".format(len_list,
                                            morph.parse('однофамилец')[0].make_agree_with_number(len_list).word),
                               reply_markup=action_keyboard)

        bot.register_next_step_handler(msg, output_teacher, value_list)

    elif len_list == 1:
        bot.send_message(message.from_user.id, value_list[0].info(), reply_markup=now)
    elif len_list == 0:
        bot.send_message(message.from_user.id, "Данный преподаватель не найден", reply_markup=now)
    elif len_list == -1:
        bot.send_message(message.from_user.id, value_list, reply_markup=now)


# Выводит список преподавателя(ей)
def output_teacher(message, value_list):
    text = message.text.lower()
    if text == "вывести всех":
        for i in value_list:
            bot.send_message(message.from_user.id, i.info(), reply_markup=now)
    elif text == "ввести имя":
        msg = bot.send_message(message.from_user.id, "Введите имя")
        bot.register_next_step_handler(msg, output_teacher_name, value_list)


# Поиск по имени, если есть однофамильцы
def output_teacher_name(message, value_list):
    text = message.text
    len_list = len(value_list)

    if len_list == 0:
        bot.send_message(message.from_user.id, "Данный преподаватель не найден", reply_markup=now)
    elif len_list >= 1:
        for i in range(len(value_list)):
            if value_list[i].name == text:
                bot.send_message(message.from_user.id, value_list[i].info(), reply_markup=now)
    elif len_list == -1:
        bot.send_message(message.from_user.id, value_list, reply_markup=now)


def diplom(message):
    at_subject = airtable.Airtable(BASE_ID, "GraduateWork", API_KEY)

    list_column = ["Description", "Deadline"]
    dict_subject = {}

    for elem in at_subject.search("Subject", message.text):
        for column in list_column:
            dict_subject[column] = ""

        for column in range(len(list_column)):
            name_column = list_column[column]
            try:
                dict_subject[name_column] = elem['fields'][name_column]
            except KeyError:
                dict_subject[name_column] = "Неизвестно"

        bot.send_message(message.from_user.id, f"Описание: {dict_subject['Description']}\n\nДедлайн: {dict_subject['Deadline']}", reply_markup=now)


bot.polling(none_stop=True, interval=0)
