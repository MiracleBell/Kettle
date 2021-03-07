# coding: utf-8
import logging
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import functools


class TeleBot(telebot.TeleBot):
    def __init__(self, markup_file, *args, **kwargs):
        self.markup_file = markup_file
        self.global_buttons = {}
        self.markups = {}
        self.sign2markup = {}
        self.grname2markup = {}
        self.muname2markup = {}
        self._markups_exception_handler = None
        self.delimiter = ":"
        super().__init__(*args, **kwargs)
        self.parse_markup_file(self.markup_file)

    def parse_markup_file(self, markup_file):
        from . import parser
        import sys

        log = logging.getLogger(__name__)

        file_as_dict = parser.get_config(sys.argv, markup_file)
        log.debug("parsing succeed")

        for button in file_as_dict.get("buttons", []):
            button = _Button(**button)
            self.global_buttons[button.name] = button

        for markupd in file_as_dict["markups"]:
            markup = _Markup(**markupd)
            for buttond in markupd.get("buttons", []):
                button = None
                if buttond.get("text"):
                    button = _Button(**buttond)
                else:
                    button = self.global_buttons[buttond["name"]]
                assert button.name
                markup.static_buttons.append(button)
            self.markups[markup.name] = markup
            self.sign2markup[markup.sign] = markup

        for key, value in file_as_dict.get("config", {}).items():
            if "delimiter" == key:
                self.delimiter = value

    def except_handler(self, func):
        def default_markups_exception_handler(*args, **kwargs):
            logging.getLogger(__name__).exception("default markups exception handler")

        @functools.wraps(func)
        def processing(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseException as exception:
                try:
                    _markups_exception_handler = (
                        self._markups_exception_handler
                        or default_markups_exception_handler
                    )
                    _markups_exception_handler(*args, **kwargs, exception=exception)
                except BaseException:
                    logging.getLogger().exception(
                        "_markups_exception_handler call exception"
                    )

        return processing

    def _is_parent_markup_next(self, next_markup):
        return next_markup == "_parent_markup"

    def _is_markup_value_next(self, next_markup):
        return next_markup == "_markup_value"

    def _is_current_markup_next(self, next_markup):
        return next_markup == "_current_markup"

    def _parent_path_calldata(self, callback_data):
        callbacks = callback_data.split(self.delimiter)
        return self.delimiter.join(callbacks[:-1])

    def _parent_only_calldata(self, callback_data):
        callbacks = callback_data.split(self.delimiter)
        try:
            parent_cd = callbacks[-2]
        except IndexError:
            parent_cd = callbacks[-1]
        return parent_cd

    def _next_callback_data(self, prev_callback_data, next_markup_sign, next_button_cd):
        """sum prev_callback_data, delimiter and new buttons callback data
           if prev_callback_data is not empty, else new buttons callback data only"""
        if not next_button_cd:
            return ""
        if prev_callback_data:
            return (
                prev_callback_data + self.delimiter + next_markup_sign + next_button_cd
            )
        return next_markup_sign + next_button_cd

    def _get_next_markup_name(self, next_markup, callback_data):
        log = logging.getLogger(__name__)
        log.debug(
            "next markup string: %s, callback_data: %s", next_markup, callback_data
        )
        if next_markup[0] != "_":
            return next_markup
        log = logging.getLogger(__name__)
        next_markup_name = None
        if self._is_parent_markup_next(next_markup):
            parent_cd = self._parent_only_calldata(callback_data)
            parent_sign = parent_cd[0]
            next_markup_name = self.sign2markup[parent_sign].name
        elif self._is_current_markup_next(next_markup):
            current_cd = callback_data.split(self.delimiter)[-1]
            current_sign = current_cd[0]
            next_markup_name = self.sign2markup[current_sign].name
        elif self._is_markup_value_next(next_markup):
            pass
        else:
            log.warning(
                "markup next starts with _ but template unknown. Returning as is"
            )
            next_markup_name = next_markup
        log.debug("next markup name: %s", next_markup_name)
        return next_markup_name

    def next_markup(self, markup_name, from_markup=None):
        log = logging.getLogger(__name__)

        def decorator(handler):

            _call = None

            @self.except_handler
            def markup_cond(call):
                log.debug("call.data: %s", call.data)
                last_cd = call.data.split(self.delimiter)[-1]
                markup_sign, button_callback = last_cd[0], last_cd[1:]
                markup_clicked = self.sign2markup[markup_sign]

                log.debug(
                    "markup_sign: %s, markup_name: %s, button pseudo callback: %s, button real callback: %s",
                    markup_sign,
                    markup_clicked.name,
                    button_callback,
                    call.data,
                )

                if from_markup and from_markup != markup_clicked.name:
                    log.debug(
                        "from markup specified (%s) and != markup_clicked (%s)",
                        from_markup,
                        markup_clicked.name,
                    )
                    return False

                next_markup_name = None
                next_from_scheme = markup_clicked.next

                for button in markup_clicked.static_buttons:
                    if button.callback != button_callback:
                        continue
                    log.debug(
                        "Next markup (%s) is overriden by button clicked: %s. Next markup: %s",
                        next_from_scheme,
                        button.name,
                        button.next,
                    )
                    next_from_scheme = button.next
                    break

                next_markup_name = self._get_next_markup_name(
                    next_from_scheme, call.data
                )

                if next_markup_name != markup_name:
                    return False

                # modify if only we are sure it's right markup

                if self._is_parent_markup_next(next_from_scheme):
                    parent_cd = self._parent_path_calldata(call.data)
                    new_callback_data = self._parent_path_calldata(parent_cd)
                    call.data = new_callback_data
                    log.debug("new callback_data: %s", call.data)

                log.debug(
                    "%s == %s (%s), from_markup: %s",
                    next_markup_name,
                    markup_name,
                    next_markup_name == markup_name,
                    from_markup,
                )
                nonlocal _call
                _call = call
                return next_markup_name == markup_name

            @functools.wraps(handler)
            @self.except_handler
            def handler_wrap(*args, **kwargs):
                res = handler(*args, **kwargs)

                if not res:
                    return

                next_markup_name = markup_name
                callback_data = _call.data

                log.debug(
                    "next markup name: %s, callback_data: %s",
                    next_markup_name,
                    callback_data,
                )

                new_text = None
                new_ikmarkup = None

                if type(res) == tuple:
                    assert len(res) == 2
                    new_text, tmp = res
                    res = tmp

                next_markup_sign = self.markups[next_markup_name].sign
                log.debug("next markup sign: %s", next_markup_sign)

                if type(res) == list:
                    assert type(res[0]) == InlineKeyboardButton
                    text, ikmarkup = self.get_static_markup(
                        next_markup_name, callback_data
                    )
                    static_buttons = ikmarkup.keyboard
                    ikmarkup.keyboard = []

                    def buttons_gen():
                        for ikbutton in res:
                            ikbutton.callback_data = self._next_callback_data(
                                callback_data, next_markup_sign, ikbutton.callback_data
                            )
                            assert len(ikbutton.callback_data) < 65
                            yield ikbutton

                    ikmarkup.add(*buttons_gen())
                    ikmarkup.keyboard += static_buttons
                    log.debug("row_width: %s", ikmarkup.row_width)
                    if not new_text:
                        new_text = text
                    new_ikmarkup = ikmarkup

                elif type(res) == InlineKeyboardMarkup:
                    new_ikmarkup = res
                    for row in new_ikmarkup.keyboard:
                        for ikbutton in row:
                            ikbutton["callback_data"] = self._next_callback_data(
                                callback_data,
                                next_markup_sign,
                                ikbutton.get("callback_data"),
                            )

                elif type(res) == str:
                    new_text = res
                    new_ikmarkup = self._inline_markup_from(_call.message)

                assert new_text
                assert new_ikmarkup

                log.debug(
                    "Next markup keyboard:\n%s",
                    "\n".join(
                        str(ikbutton)
                        for row in new_ikmarkup.keyboard
                        for ikbutton in row
                    ),
                )
                self.edit_message_text(
                    message_id=_call.message.message_id,
                    chat_id=_call.message.chat.id,
                    text=new_text,
                    reply_markup=new_ikmarkup,
                )
                # self.send_message(text=new_text, chat_id=_call.message.chat.id, reply_markup=new_ikmarkup)

            handler_dict = self._build_handler_dict(handler_wrap, func=markup_cond)
            self.add_callback_query_handler(handler_dict)

            return handler_wrap

        return decorator

    def last_calldata(self, callback_data):
        last_cd = callback_data.split(self.delimiter)[-1]
        return last_cd[1:]

    def calldata_chain(self, callback_data):
        chain = []
        for cd in callback_data.split(self.delimiter):
            chain.append(cd[1:])
        return chain

    def get_static_markup(self, markup_name, callback_data=None):
        log = logging.getLogger(__name__)
        markup = self.markups.get(markup_name)
        if not markup:
            log.warning("No markup with name: %s", markup_name)
            return None, None

        text = markup.caption
        ikmarkup = InlineKeyboardMarkup(markup.row_width)

        for button in markup.static_buttons:
            bcallback_data = self._next_callback_data(
                callback_data, markup.sign, button.callback
            )
            ikbutton = InlineKeyboardButton(**button.ikbutton.to_dic())
            ikbutton.callback_data = bcallback_data
            ikmarkup.row(ikbutton)
        return text, ikmarkup

    def get_static_markup_pure(self, markup_name):
        log = logging.getLogger(__name__)
        markup = self.markups.get(markup_name)
        if not markup:
            log.warning("No markup with name: %s", markup_name)
            return None, None

        text = markup.caption
        ikmarkup = InlineKeyboardMarkup(markup.row_width)

        for button in markup.static_buttons:
            ikmarkup.row(button.ikbutton)
        return text, ikmarkup

    def _inline_markup_from(self, message):
        ikmarkup = InlineKeyboardMarkup()
        ikmarkup.keyboard = message.json.get("reply_markup", {}).get(
            "inline_keyboard", []
        )
        return ikmarkup


class DefaultRepr:
    def __repr__(self):
        import json

        return json.dumps(
            self.__dict__,
            sort_keys=True,
            ensure_ascii=False,
            indent=4,
            default=lambda obj: obj.__dict__,
        )


class _Markup(DefaultRepr):
    def __init__(self, name, caption, sign, next, **kwargs):
        self.name = name
        self.caption = caption
        self.sign = sign
        self.row_width = kwargs.get("row_width")
        self.next = next
        self.static_buttons = []


class _Button(DefaultRepr):
    def __init__(self, name, text, next, **kwargs):
        self.name = name
        self.text = text
        self.next = next
        self.ikbutton = InlineKeyboardButton(text, **kwargs)
        self.callback = self.ikbutton.callback_data
