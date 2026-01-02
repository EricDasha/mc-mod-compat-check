import sys
import os

# Ensure src is in path if running from root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mc_mod_compat.gui.app import ModCompatApp

if __name__ == "__main__":
    app = ModCompatApp()
    app.mainloop()
