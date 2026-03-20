"""
Backwards-compatible entry point for the Piccolo UI.

All logic has moved to piccolo.__main__ — this file just delegates to main().
"""

from piccolo.__main__ import main

if __name__ == '__main__':
    main()
