"""No-install entry point: python3 onboard.py --workspace PATH <command>."""
from hub.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
