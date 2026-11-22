"""R-ENGINE-07: ONE line through the in-house engine mock ``own3d``: request -> start -> status -> fitted garment .glb -> (node render, run by CI) -> picture check. Mock only: no photo, no GPU, no model, no paid call.
   python scripts/own3d_path.py make  <out_dir>                 -> own3d.glb + own3d.json (the status the provider returned)
   python scripts/own3d_path.py check <turn_dir> [cuts_per_turn]  -> looks at the rendered cuts: the garment is really drawn from four sides (not blank)
The render itself is ``ai_creator_studio_3d_viewer/scripts/render_glb.mjs`` (headless Chromium, software WebGL)."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.assets.validation import validate_gltf_upload  # noqa: E402
from app.providers.own_mock import OwnMockProvider  # noqa: E402

REQUEST = {"sex": "female", "garment_kind": "top", "measurements": {"height_cm": 170, "chest_cm": 92}}
BACKGROUND = (0xF2, 0xF2, 0xF2)       # render_glb.mjs clear colour
MIN_SHARE = 0.004                      # at least 0.4% of the picture must differ from the background


def make(out: Path) -> int:
    provider = OwnMockProvider()
    loop = asyncio.new_event_loop()
    started = loop.run_until_complete(provider.start(REQUEST))
    done = loop.run_until_complete(provider.status(started["request_id"]))
    glb = provider.result_glb(started["request_id"])
    if done["status"] != "succeeded" or glb is None or validate_gltf_upload("own3d.glb", glb).media_type != "model/gltf-binary":
        print(json.dumps({"ok": False, "status": done["status"]}))
        return 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "own3d.glb").write_bytes(glb)
    (out / "own3d.json").write_text(json.dumps({"started": started, "status": done}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": True, "request_id": started["request_id"], "glb_bytes": len(glb), "charged": done["charged"]}))
    return 0


def share(path: Path) -> float:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    differing = sum(1 for r, g, b in img.getdata() if max(abs(r - BACKGROUND[0]), abs(g - BACKGROUND[1]), abs(b - BACKGROUND[2])) > 12)
    return round(differing / (img.width * img.height), 4)


def check(folder: Path, cuts: int) -> int:
    rows = [{"file": f"turn_{i:03d}.png", "garment_share": share(folder / f"turn_{i:03d}.png")} for i in (0, cuts // 4, cuts // 2, 3 * cuts // 4)]
    ok = all(r["garment_share"] >= MIN_SHARE for r in rows)
    print(json.dumps({"views": rows, "min_share": MIN_SHARE, "ok": ok}))
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "make":
        return make(Path(argv[1]))
    if len(argv) >= 2 and argv[0] == "check":
        return check(Path(argv[1]), int(argv[2]) if len(argv) > 2 else 120)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
