# coding: utf-8

import argparse
from trafaret_config import commandline
import trafaret as T


BUTTON = T.Dict(
    {
        "name": T.String(min_length=1),
        "text": T.String(min_length=1),
        "next": T.String(min_length=1),
        T.Key("url", optional=True): T.String,
        T.Key("login_url", optional=True): T.String,
        T.Key("callback_data", optional=True): T.String(min_length=1, max_length=64),
        T.Key("switch_inline_query", optional=True): T.String,
        T.Key("switch_inline_query_current_chat", optional=True): T.String(
            allow_blank=True
        ),
        T.Key("callback_game", optional=True): T.String,
        T.Key("pay", optional=True): T.String,
        # T.Key("callback_strategy", optional=True, default="sum"): T.String
    }
)

MARKUP = T.Dict(
    {
        "name": T.String(min_length=1),
        "caption": T.String(min_length=1),
        "sign": T.String(max_length=1),
        T.Key("row_width", optional=True, default=1): T.Int(),
        T.Key("next", optional=True, default=""): T.String(allow_blank=True),
        T.Key("buttons", optional=True): T.List(
            T.Or(BUTTON, T.Dict({"name": T.String(min_length=1)}))
        ),
    }
)

CONFIG = T.Dict({"callback_strategy": T.String, "delimiter": T.String(min_length=1)})

TRAFARET = T.Dict(
    {
        T.Key("markups"): T.List(MARKUP),
        T.Key("buttons", optional=True): T.List(BUTTON),
        T.Key("config", optional=True): CONFIG,
    }
)


def get_config(argv, filepath):
    ap = argparse.ArgumentParser()
    commandline.standard_argparse_options(ap, default_config=filepath)
    options, unknown = ap.parse_known_args(argv)
    config = commandline.config_from_options(options, TRAFARET)
    return config
