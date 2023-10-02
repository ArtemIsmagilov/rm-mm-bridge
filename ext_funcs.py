from typing import Sequence
from redminelib.resources import Issue


def choose_name(full_name: str, login_mm: str) -> str:
    return full_name if full_name else login_mm


def sing_plur_tasks(seq: Sequence[Issue]) -> str:
    return 'tasks' if len(seq) > 1 else 'task'


def create_full_name(first_name: str, last_name: str):
    if first_name or last_name:
        return '{} {}'.format(first_name, last_name)
