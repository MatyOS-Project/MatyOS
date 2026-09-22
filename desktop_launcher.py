"""PyInstaller entry point for the MatyOS desktop app.

Kept at the repo root so PyInstaller runs it as ``__main__`` while
``matyos.desktop`` is imported as a proper package submodule (its relative
imports then resolve). Not used by the ``matyos-desktop`` console script, which
calls :func:`matyos.desktop.main` directly.
"""
from matyos.desktop import main

if __name__ == "__main__":
    main()
