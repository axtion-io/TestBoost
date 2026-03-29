"""Allow running as: python -m testboost <command> <project_path>"""

import sys

from src.lib.cli import main

sys.exit(main())
