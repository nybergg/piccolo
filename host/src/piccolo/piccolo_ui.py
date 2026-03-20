"""
Backwards-compatible entry point for the Piccolo UI.

All logic has moved to piccolo.ui.app — this file just delegates to main().
"""

from piccolo.ui.app import main

if __name__ == '__main__':
    main()
