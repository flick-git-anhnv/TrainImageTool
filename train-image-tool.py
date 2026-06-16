import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tool.core.app import App

if __name__ == "__main__":
    App().mainloop()
