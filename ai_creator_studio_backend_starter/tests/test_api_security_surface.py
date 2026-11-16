"""Guard the API authentication boundary and its deliberately public exceptions."""
from fastapi.routing import APIRoute


def _depends_on(dependant, target) -> bool:
    if dependant.call is target:
        return True
    return any(_depends_on(child, target) for child in dependant.dependencies)


def iter_api_routes(routes, prefix=""):
    """Yield (path, APIRoute) for every API route, also those inside included routers.

    FastAPI 0.115 keeps included routes directly in ``app.routes``; newer versions wrap each included router in an
    object that only exposes ``original_router`` (and ``include_context.prefix``). Walking both shapes keeps this
    guard from silently skipping routes after a framework upgrade.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            yield from iter_api_routes(inner.routes, prefix + (getattr(context, "prefix", "") or ""))


def test_the_route_walk_sees_every_documented_route():
    """The guards below are only worth anything if they see every route: compare with the OpenAPI document."""
    from app.main import app

    walked = {(method, path) for path, route in iter_api_routes(app.routes) if route.include_in_schema for method in (route.methods or set()) if method != "HEAD"}
    documented = {(method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item if method.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}}
    assert walked == documented, f"missed by the walk: {sorted(documented - walked)}; not documented: {sorted(walked - documented)}"
    assert len(walked) > 60, "suspiciously few routes"


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
        ("GET", "/v1/legal/documents"), ("GET", "/v1/error-catalog"),  # R-072: public text table  # public: lists legal document names and versions only
        ("GET", "/v1/assets/{asset_id}/preview"),
        ("GET", "/v1/assets/{asset_id}/thumb/{size}"),   # R-061: signed, short-lived display picture
        ("GET", "/v1/assets/{asset_id}/versions/{version_id}/preview"),
        ("GET", "/v1/library/items/{item_id}/versions/{version}/preview"),  # R-032: signed, short-lived link
    }
    seen_public = set()
    unclassified = []
    for path, route in iter_api_routes(app.routes):
        for method in route.methods or set():
            key = (method, path)
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

    internal = [(path, route) for path, route in iter_api_routes(app.routes) if path.startswith("/internal/")]
    assert len(internal) >= 8, f"expected the internal operations routes to be found, saw {len(internal)}"
    for path, route in internal:
        assert _depends_on(route.dependant, current_user), path
