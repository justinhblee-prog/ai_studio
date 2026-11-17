"""E-09a: print the IoU table of the background-removal candidates on the synthetic evaluation set.   python scripts/bg_eval.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bg_removal import evaluate  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
