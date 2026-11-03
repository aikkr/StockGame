import secrets

from nicegui import app

from server.state import database


CURRENT_SAVE = 'current'


def load_user():
    browser = app.storage.browser
    token = browser.get('session_token')
    user = database.getUserBySession(token)
    if user is None:
        user = database.addUser('Player')
        browser['session_token'] = database.addSession(user['id'])
    else:
        database.login(user['id'])
    return user, database.getSave(user['id'], CURRENT_SAVE) or {}


def save_progress(user_id, progress, previous=None):
    database.addSave(user_id, CURRENT_SAVE, progress, expected=previous)


def reset_progress(user_id):
    database.addSave(user_id, CURRENT_SAVE, {'_generation': secrets.token_urlsafe(16)})
