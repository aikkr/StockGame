import secrets

from nicegui import app, core

from server.state import database


CURRENT_SAVE = 'current'


def load_user() -> tuple[dict, dict]:

    if core.is_script_mode_preflight():
        return {'id': 0, 'name': 'Preview'}, {}

    browser = app.storage.browser
    token = browser.get('session_token')
    user = database.getUserBySession(token)
    if user is None:
        user = database.addUser('Player')
        browser['session_token'] = database.addSession(user['id'])
    else:
        database.login(user['id'])
    return user, database.getSave(user['id'], CURRENT_SAVE) or {}


def save_progress(user_id: int, progress: dict, previous=None) -> None:
    database.addSave(user_id, CURRENT_SAVE, progress, expected=previous)


def reset_progress(user_id: int) -> None:
    database.addSave(user_id, CURRENT_SAVE, {'_generation': secrets.token_urlsafe(16)})
