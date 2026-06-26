"""
main.py
=======
Entry point for NET_FIX_PROTOCOL.

Admin elevation is checked BEFORE importing the app module, so the UAC
prompt happens before any GUI libraries (customtkinter, matplotlib) are
even loaded - matching the original script's behavior.
"""

import utils

if not utils.check_admin():
    utils.elevate_and_restart()

from app import NetFixApp  # noqa: E402  (must come after the admin check)


def main() -> None:
    app = NetFixApp()
    app.run()


if __name__ == "__main__":
    main()
