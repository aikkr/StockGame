"""Connect NiceGUI browser sessions to locally persisted users and saves."""

from nicegui import app, core

from DB import UserDatabase


CURRENT_SAVE = 'current'
database = UserDatabase()


def load_user() -> tuple[dict, dict]:
    """Load the current browser's user and saved progress, creating it if absent.

    Dependencies: NiceGUI browser storage and the local UserDatabase.
    Side effects: may create a user/session and updates login metadata.
    Failure impact: database errors prevent the market page from loading.
    """
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


def save_progress(user_id: int, progress: dict) -> None:
    """Persist the current game state under the user's active save.

    Dependencies: the local UserDatabase and JSON-serializable state.
    Side effects: replaces the user's current save.
    Failure impact: progress since the previous save may be lost.
    """
    database.addSave(user_id, CURRENT_SAVE, progress)
