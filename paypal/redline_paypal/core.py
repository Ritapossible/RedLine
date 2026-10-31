"""RedLine's GenLayer modules, imported unchanged.

``contracts/redline_core.py``, ``redline_text.py`` and ``redline_prompts.py``
are pure Python with no ``gl.*`` calls. The PayPal server uses them as they
are, so the cover's states and money, the visible-text rules and the question
put to the models are the same code the GenLayer contracts run, under the same
tests.
"""

import os
import sys

_CONTRACTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "contracts")
if _CONTRACTS not in sys.path:
    sys.path.insert(0, _CONTRACTS)

import redline_core as core  # noqa: E402
import redline_prompts as prompts  # noqa: E402
import redline_text as text  # noqa: E402

__all__ = ["core", "prompts", "text"]
