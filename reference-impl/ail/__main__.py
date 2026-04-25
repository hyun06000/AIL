"""Allow `python -m ail ...` to dispatch to the CLI.

process_manager's Deploy spawns `python -m ail run <file>` to start
evolve-server programs (qna_bot field test 2026-04-26: deploy was
silently failing with `No module named ail.__main__`). Without this
shim, the package isn't a runnable module and Deploy spawn dies
immediately with that error in deployment.log while the UI shows a
phantom "running" record.
"""
from .cli import main

if __name__ == "__main__":
    main()
