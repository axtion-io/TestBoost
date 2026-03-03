"""Allow running as: python -m testboost_lite <command> <project_path>"""

import sys

from testboost_lite.lib.cli import main

sys.exit(main())
