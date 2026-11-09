"""Guard the API authentication boundary and its deliberately public exceptions."""
from fastapi.routing import APIRoute


def _depends_on(dependant, target) -> bool:
    if dependant.call is target:
        return True
    return any(_depends_on(child, target) for child in dependant.dependencies)


def test_every_api_route_is_authenticated_or_explicitly_public():
    from app.main import app
    from app.assets.routes import current_user

    # Signed preview URLs are short-lived bearer capabilities. Their issuing
    # endpoints require current workspace membership; possession grants read
    # access only until expiry (at most 15 minutes).
    public_routes = {
        ("GET", "/health"),
        ("GET", "/v1/engines/capabilities"),
        ("GET", "/v1/engines/models"),
        ("GET", "/v1/assets/{asset_id}/preview"),
        ("GET", "/v1/assets/{asset_id}/versions/{version_id}/preview"),
    }
    seen_public = set()
    unclassified = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            key = (method, route.path)
            authenticated = _depends_on(route.dependant, current_user)
            if key in public_routes:
                seen_public.add(key)
                if authenticated:
                    unclassified.append(f"public route unexpectedly changed auth contract: {key}")
            elif not authenticated:
                unclassified.append(f"route has no current_user dependency and is not allowlisted: {key}")
    assert seen_public == public_routes
    assert not unclassified, "\\n".join(unclassified)


def test_internal_operations_routes_require_authentication():
    from app.main import app
    from app.assets.routes import current_user

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/internal/"):
            assert _depends_on(route.dependant, current_user), route.path
