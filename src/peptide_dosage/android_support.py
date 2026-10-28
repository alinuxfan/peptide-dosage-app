"""Android-only integrations that Toga 0.5 does not expose.

Everything here imports the Chaquopy Java bridge (``java``, ``android.*``)
lazily inside functions, so this module is safe to import on every platform;
on desktop each helper simply returns False without doing anything. They
are best-effort: any failure is swallowed and reported through the return
value, so a missing API never takes the app down.

* ``BackHandler`` -- routes the system Back gesture/button to the in-app
  navigation stack (Toga's Android Activity has no back-press hook).
* ``share_text`` -- hands text to Android's share sheet, which is how exports
  leave the app-private data folder (Drive, email, messaging, ...).
"""

import sys
from typing import Callable

_API_BACK_CALLBACK = 33  # Activity.getOnBackInvokedDispatcher() needs Android 13+


def is_android() -> bool:
    return hasattr(sys, "getandroidapilevel") or sys.platform == "android"


def _activity(app):
    return app._impl.native  # toga-android: the MainActivity singleton


class BackHandler:
    """Intercept Back only while there is something to pop.

    ``OnBackInvokedCallback`` cannot pass an event through to the system, so
    the callback is registered while the active stack is deeper than its root
    and unregistered at the root, where the default behaviour (leave the app)
    is wanted. Call ``sync()`` whenever the stack depth or active tab changes.
    """

    def __init__(self, app, can_go_back: Callable[[], bool], go_back: Callable[[], None]):
        self.app = app
        self.can_go_back = can_go_back
        self.go_back = go_back
        self._callback = None
        self._registered = False
        self._supported = is_android()

    def sync(self) -> bool:
        """Register/unregister the callback to match ``can_go_back()``.
        Returns True while the callback is registered."""
        if not self._supported:
            return False
        try:
            want = bool(self.can_go_back())
            if want and not self._registered:
                self._register()
            elif not want and self._registered:
                self._unregister()
        except Exception as e:  # unsupported API level, bridge differences, ...
            print(f"Back handling unavailable: {e}")
            self._supported = False
            self._registered = False
        return self._registered

    def _dispatcher(self):
        from android.os import Build

        if Build.VERSION.SDK_INT < _API_BACK_CALLBACK:
            raise RuntimeError("needs Android 13 or newer")
        return _activity(self.app).getOnBackInvokedDispatcher()

    def _register(self):
        from android.window import OnBackInvokedCallback, OnBackInvokedDispatcher
        from java import dynamic_proxy

        if self._callback is None:
            go_back = self.go_back

            class _Callback(dynamic_proxy(OnBackInvokedCallback)):
                def onBackInvoked(self):
                    go_back()

            self._callback = _Callback()
        self._dispatcher().registerOnBackInvokedCallback(
            OnBackInvokedDispatcher.PRIORITY_DEFAULT, self._callback
        )
        self._registered = True

    def _unregister(self):
        self._dispatcher().unregisterOnBackInvokedCallback(self._callback)
        self._registered = False


def share_text(app, text: str, subject: str = "") -> bool:
    """Open Android's share sheet with `text`. Returns False when not on
    Android or if the sheet could not be started."""
    if not is_android():
        return False
    try:
        from android.content import Intent

        intent = Intent(Intent.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(Intent.EXTRA_TEXT, text)
        if subject:
            intent.putExtra(Intent.EXTRA_SUBJECT, subject)
        _activity(app).startActivity(Intent.createChooser(intent, subject or "Share"))
        return True
    except Exception as e:
        print(f"Share unavailable: {e}")
        return False
