"""Build probe_week.py: RedLine's own text rules (contracts/redline_text.py),
so "present" means what it means to the watcher, plus the probe class."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
text = open(os.path.join(ROOT, "contracts", "redline_text.py")).read()
if text.lstrip().startswith('"""'):
    s = text.lstrip()
    text = s[s.find('"""', 3) + 3 :].lstrip("\n")
shell = open(os.path.join(HERE, "probe_week_shell.py")).read()
src = '# v0.2.0\n# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }\nfrom genlayer import *\nimport json\n\n' + text + "\n\n" + shell
open(os.path.join(HERE, "probe_week.py"), "w").write(src)
print("probe_week.py", len(src.encode()), "bytes")
