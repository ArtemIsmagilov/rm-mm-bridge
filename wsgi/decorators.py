import logging, traceback, functools
from flask import g, request
from httpx import HTTPError
from redminelib.exceptions import BaseRedmineError

from wsgi import views


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            login_mm = request.json['context']['acting_user']['username']
            return views.unregister_mm_account(login_mm)
        return view(**kwargs)
    return wrapped_view


def decorator_http_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as exp:
            logging.error("<###traceback###\n%s\n###traceback###>\n\n", traceback.format_exc())
            return exp
    return wrapper


def decorator_redmine_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseRedmineError as exp:
            logging.error("<###traceback###\n%s\n###traceback###>\n\n", traceback.format_exc())
            return exp
    return wrapper
