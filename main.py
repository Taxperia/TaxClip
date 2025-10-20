import os
import sys

# Qt uyarılarını gizle
os.environ["QT_LOGGING_RULES"] = "qt.qpa.mime=false"

from clipstack.app import run_app

if __name__ == "__main__":
    run_app()