from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/app/PublicLanding.tsx").read_text(encoding="utf-8")
styles = (ROOT / "src/app/PublicLanding.css").read_text(encoding="utf-8")
main = (ROOT / "src/app/main.tsx").read_text(encoding="utf-8")

required_sections = ["id=\"top\"", "id=\"platform\"", "id=\"workflow\"", "id=\"business\""]
for section in required_sections:
    assert section in source, f"Missing public landing section: {section}"
assert "onLogin" in source and "onSignup" in source
assert "워크스페이스 시작" in source
assert "AI Provider" in source and "별도 검증" in source, "Capability scope disclosure must remain visible"
assert "capabilities.map" in source and source.count("{ number:") == 6
assert "@media(max-width:620px)" in styles, "Mobile layout breakpoint is required"
assert "PublicLanding" in main and "onLogin" in main and "onSignup" in main
assert "setShowAuth(true)" in main and "setShowAuth(false)" in main
print("Public landing contract: 4 sections, 6 capability cards, login/signup CTAs, mobile breakpoint, disclosure PASS")
