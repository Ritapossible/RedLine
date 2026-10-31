"""The scheduled checker: every 15 minutes from GitHub Actions, for covers
longer than a server's uptime, and for settlement. Demo pages are never read
here; demo covers are the web process's (architecture 7).

    python -m redline_paypal.worker --once
"""

import argparse
import sys

from .config import App


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit (the only mode)")
    ap.parse_args(argv)
    app = App()
    done = app.covers.tick(demo_checks=False)
    ok, bad = app.ledger.verify()
    print("checked %d cover(s); log %s" % (len(done), "verifies" if ok else "BROKEN at %s" % bad))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
