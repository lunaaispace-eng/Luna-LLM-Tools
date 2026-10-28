"""pytest: let the test modules `import _comfy` (the helper beside them) as `unittest discover -s tests` does."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
