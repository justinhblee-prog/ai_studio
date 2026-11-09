"""Live PostgreSQL repository tests.

Skipped unless ACS_TEST_DATABASE_URL points at a disposable database.
Never point this at a shared, TEST Supabase or Production database: the test
applies migrations and writes rows.
"""
from __future__ import annotations

import os
import uuid

import pytest

DSN = os.environ.get("ACS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="ACS_TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def repos():
    from app import config
    old = config.DATABASE_URL
    config.DATABASE_URL = DSN
    try:
        from app.repositories.postgres_assets import PostgreSQLAssetMetadataRepository
        from app.repositories.postgres_products import PostgreSQLProductRepository
        from app.repositories.postgres_project_products import PostgreSQLProjectProductRepository
        from app.repositories.postgres_projects import PostgreSQLProjectRepository
        from app.repositories.postgres_characters import PostgreSQLCharacterRepository
        from app.repositories.postgres_photos import PostgreSQLPhotoRepository
        from app.repositories.postgres_lookbooks import PostgreSQLLookbookRepository
        assets = PostgreSQLAssetMetadataRepository()
        assets.initialize()
        yield {
            "assets": assets,
            "projects": PostgreSQLProjectRepository(),
            "products": PostgreSQLProductRepository(),
            "links": PostgreSQLProjectProductRepository(),
            "characters": PostgreSQLCharacterRepository(),
            "photos": PostgreSQLPhotoRepository(),
            "lookbooks": PostgreSQLLookbookRepository(),
        }
    finally:
        config.DATABASE_URL = old


def _ids():
    s = uuid.uuid4().hex[:10]
    return f"ws_{s}", f"owner_{s}", f"editor_{s}", f"viewer_{s}", f"outsider_{s}", s


def _workspace(repos):
    ws, owner, editor, viewer, outsider, s = _ids()
    a = repos["assets"]
    a.create_workspace(ws, owner)
    a.add_workspace_member(ws, editor, "editor", actor_id=owner)
    a.add_workspace_member(ws, viewer, "viewer", actor_id=owner)
    return ws, owner, editor, viewer, outsider, s


def _image(repos, ws, owner, tag):
    aid = "ast_" + uuid.uuid4().hex
    repos["assets"].register_asset(
        asset_id=aid, owner_id=owner, workspace_id=ws, original_filename=f"{tag}.png",
        storage_key=f"{ws}/{aid}.png", media_type="image/png", size_bytes=10,
        checksum_sha256="a" * 64)
    return aid


def test_migrations_are_idempotent(repos):
    again = repos["assets"].initialize()
    assert again.applied == ()
    assert len(again.already_applied) >= 10


def test_owner_role_cannot_be_overwritten(repos):
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    a = repos["assets"]
    with pytest.raises(Exception):
        a.add_workspace_member(ws, owner, "viewer", actor_id=owner)
    assert a.workspace_role(ws, owner) == "owner"
    with pytest.raises(Exception):
        a.add_workspace_member(ws, outsider, "editor", actor_id=viewer)
    assert a.workspace_role(ws, outsider) is None


def test_project_crud_and_role_enforcement(repos):
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    p = repos["projects"]
    created = p.create(workspace_id=ws, actor_id=editor, name="Spring")
    pid = created["project_id"]
    with pytest.raises(PermissionError):
        p.create(workspace_id=ws, actor_id=viewer, name="nope")
    with pytest.raises(PermissionError):
        p.create(workspace_id=ws, actor_id=outsider, name="nope")
    assert p.get(pid, viewer)["name"] == "Spring"
    with pytest.raises(PermissionError):
        p.get(pid, outsider)
    assert [x["project_id"] for x in p.list_for_workspace(ws, viewer)] == [pid]
    updated = p.update(pid, editor, name="Spring 2", project_type="general", status="ARCHIVED")
    assert updated["status"] == "ARCHIVED" and updated["name"] == "Spring 2"
    with pytest.raises(PermissionError):
        p.update(pid, viewer, name="x", project_type="general", status="ACTIVE")


def test_product_variant_sku_rules_and_isolation(repos):
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    pr = repos["products"]
    product = pr.create(workspace_id=ws, actor_id=editor, sku=f"SKU-{s}", name="Coat",
                        description=None, category="outerwear", image_asset_ids=[_image(repos, ws, owner, "a")])
    pid = product["product_id"]
    with pytest.raises(Exception):  # duplicate product SKU, case-insensitive
        pr.create(workspace_id=ws, actor_id=editor, sku=f"sku-{s}", name="Dup",
                  description=None, category="outerwear", image_asset_ids=[_image(repos, ws, owner, "a")])
    var = pr.create_variant(product_id=pid, workspace_id=ws, actor_id=editor,
                            sku=f"VAR-{s}", option_values={"size": "M"})
    with pytest.raises(Exception):  # variant SKU colliding with product SKU
        pr.create_variant(product_id=pid, workspace_id=ws, actor_id=editor,
                          sku=f"sku-{s}", option_values={"size": "L"})
    with pytest.raises(Exception):  # viewer cannot write
        pr.create_variant(product_id=pid, workspace_id=ws, actor_id=viewer,
                          sku=f"V2-{s}", option_values={"size": "S"})
    assert pr.get(pid, ws, viewer) is not None
    with pytest.raises(Exception):
        pr.get(pid, ws, outsider)
    archived = pr.archive_variant(pid, var["variant_id"], ws, editor)
    assert archived is not None


def test_project_product_assignment_and_cross_workspace_denial(repos):
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    ws2, owner2, _, _, _, s2 = _workspace(repos)
    prj = repos["projects"].create(workspace_id=ws, actor_id=editor, name="Link")["project_id"]
    prd = repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"L-{s}", name="A",
                                   description=None, category="top", image_asset_ids=[_image(repos, ws, owner, "b")])["product_id"]
    foreign = repos["products"].create(workspace_id=ws2, actor_id=owner2, sku=f"F-{s2}", name="F",
                                       description=None, category="top", image_asset_ids=[_image(repos, ws2, owner2, "c")])["product_id"]
    links = repos["links"]
    links.replace_for_project(prj, ws, [prd], editor)
    listed = links.list_for_project(prj, ws, viewer)
    assert prd in str(listed)
    with pytest.raises(Exception):  # product from another workspace
        links.replace_for_project(prj, ws, [foreign], editor)
    with pytest.raises(Exception):  # viewer cannot replace
        links.replace_for_project(prj, ws, [], viewer)
    links.replace_for_project(prj, ws, [], editor)
    assert prd not in str(links.list_for_project(prj, ws, viewer).get("products", listed and []))


def _char(name="Mina", outfits=None, active=None):
    return {"identity": {"name": name}, "outfits": outfits or [], "active_outfit_id": active}


def test_character_crud_roles_assets_and_soft_delete(repos):
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    ws2, owner2, _, _, _, _ = _workspace(repos)
    c = repos["characters"]
    a1, a2 = _image(repos, ws, owner, "m1"), _image(repos, ws, owner, "m2")
    foreign = _image(repos, ws2, owner2, "x")
    outfit = {"id": "o1", "name": "Casual"}
    created = c.create(workspace_id=ws, actor_id=editor, payload=_char(outfits=[outfit], active="o1"),
                       asset_ids=[a2, a1])
    cid = created["character_id"]
    assert created["asset_ids"] == [a2, a1] and created["active_outfit_id"] == "o1"
    with pytest.raises(PermissionError):
        c.create(workspace_id=ws, actor_id=viewer, payload=_char())
    with pytest.raises(PermissionError):
        c.create(workspace_id=ws, actor_id=outsider, payload=_char())
    with pytest.raises(ValueError):  # asset from another workspace
        c.create(workspace_id=ws, actor_id=editor, payload=_char(), asset_ids=[foreign])
    with pytest.raises(ValueError):  # active outfit must exist
        c.create(workspace_id=ws, actor_id=editor, payload=_char(active="nope"))
    assert c.get(cid, ws, viewer)["identity"]["name"] == "Mina"
    with pytest.raises(PermissionError):
        c.get(cid, ws, outsider)
    assert c.get(cid, ws2, owner2) is None  # cross-workspace id does not leak
    updated = c.update(cid, ws, editor, payload=_char(name="Mina 2"), asset_ids=[a1])
    assert updated["asset_ids"] == [a1] and updated["identity"]["name"] == "Mina 2"
    with pytest.raises(PermissionError):
        c.update(cid, ws, viewer, payload=_char(), asset_ids=[])
    assert [x["character_id"] for x in c.list_for_workspace(ws, viewer)] == [cid]
    with pytest.raises(PermissionError):
        c.soft_delete(cid, ws, viewer)
    assert c.soft_delete(cid, ws, editor) is True
    assert c.get(cid, ws, viewer) is None and c.list_for_workspace(ws, viewer) == []
    assert c.soft_delete(cid, ws, editor) is False


def test_character_asset_trigger_blocks_cross_workspace_link(repos):
    import psycopg
    ws, owner, editor, *_ = _workspace(repos)
    ws2, owner2, *_ = _workspace(repos)
    cid = repos["characters"].create(workspace_id=ws, actor_id=editor, payload=_char())["character_id"]
    foreign = _image(repos, ws2, owner2, "y")
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("INSERT INTO character_assets(character_id,asset_id) VALUES(%s,%s)", (cid, foreign))


def _photo_payload(src, operation="ENHANCE", **extra):
    return {"source_asset_id": src, "operation": operation, "output_format": "PNG", "output_count": 1, **extra}


def test_photo_draft_lifecycle_roles_events_and_isolation(repos):
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    ws2, owner2, *_ = _workspace(repos)
    ph = repos["photos"]
    src = _image(repos, ws, owner, "src")
    ref = _image(repos, ws, owner, "ref")
    foreign = _image(repos, ws2, owner2, "f")
    d = ph.create_draft(ws, editor, _photo_payload(src, "BACKGROUND", reference_asset_ids=[ref]))
    did = d["draft_id"]
    assert d["status"] == "draft" and d["input"]["source_version_id"] and d["input"]["source_checksum_sha256"]
    with pytest.raises(PermissionError):
        ph.create_draft(ws, viewer, _photo_payload(src))
    with pytest.raises(PermissionError):
        ph.create_draft(ws, outsider, _photo_payload(src))
    with pytest.raises(ValueError):  # foreign asset
        ph.create_draft(ws, editor, _photo_payload(src, reference_asset_ids=[foreign]))
    with pytest.raises(ValueError):  # duplicate image across roles
        ph.create_draft(ws, editor, _photo_payload(src, reference_asset_ids=[src]))
    assert ph.get_draft(did, ws, viewer)["input"]["operation"] == "BACKGROUND"
    assert ph.get_draft(did, ws2, owner2) is None
    up = ph.update_draft(did, ws, editor, _photo_payload(src, "RETOUCH"))
    assert up["input"]["operation"] == "RETOUCH"
    with pytest.raises(PermissionError):
        ph.update_draft(did, ws, viewer, _photo_payload(src))
    with pytest.raises(ValueError):
        ph.update_draft(did, ws, editor, {**_photo_payload(src), "workspace_id": ws2})
    assert ph.list_drafts(ws, viewer)["total"] == 1
    arch = ph.archive_draft(did, ws, editor)
    assert arch["status"] == "archived"
    assert ph.list_drafts(ws, viewer)["total"] == 0 and ph.list_drafts(ws, viewer, True)["total"] == 1
    with pytest.raises(LookupError):
        ph.archive_draft(did, ws, editor)
    types = [e["event_type"] for e in ph.list_events(did, ws, viewer)["items"]]
    assert types == ["photo.draft_archived", "photo.draft_updated", "photo.draft_created"]


def test_photo_run_idempotency_lease_and_append_only(repos):
    import psycopg
    ws, owner, editor, viewer, *_ = _workspace(repos)
    ph = repos["photos"]
    src = _image(repos, ws, owner, "s")
    did = ph.create_draft(ws, editor, _photo_payload(src))["draft_id"]
    with pytest.raises(PermissionError):
        ph.claim_local_run(did, ws, viewer, "key-1")
    c1 = ph.claim_local_run(did, ws, editor, "key-1")
    assert not c1["already_succeeded"]
    with pytest.raises(ValueError):  # lease still active
        ph.claim_local_run(did, ws, editor, "key-1")
    with pytest.raises(ValueError):  # same key, different draft
        other = ph.create_draft(ws, editor, _photo_payload(src, "LIGHTING"))["draft_id"]
        ph.claim_local_run(other, ws, editor, "key-1")
    assert ph.complete_local_run(c1["run_id"], "wrong-token", editor, asset_id="a", version_id="v",
                                 checksum="c" * 64, quality={}) is False
    assert ph.complete_local_run(c1["run_id"], c1["claim_token"], editor, asset_id="ast_out",
                                 version_id="ver_out", checksum="c" * 64, quality={"score": 1}) is True
    again = ph.claim_local_run(did, ws, editor, "key-1")
    assert again["already_succeeded"] and again["run"]["quality"] == {"score": 1}
    assert "claimed_by" not in again["run"] and "idempotency_key" not in again["run"]
    # failed run can be retried with the same key; attempts increments
    did2 = ph.create_draft(ws, editor, _photo_payload(src, "LIGHTING"))["draft_id"]
    c2 = ph.claim_local_run(did2, ws, editor, "key-2")
    assert ph.fail_local_run(c2["run_id"], c2["claim_token"], editor, "boom") is True
    c3 = ph.claim_local_run(did2, ws, editor, "key-2")
    assert c3["run_id"] == c2["run_id"]
    runs = ph.list_processing_runs(did2, ws, viewer)["items"]
    assert runs[0]["attempts"] == 2 and runs[0]["status"] == "processing"
    # expired lease is reclaimable
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE photo_processing_runs SET lease_expires_at=now()-interval '1 minute' WHERE run_id=%s",
                     (c3["run_id"],))
    c4 = ph.claim_local_run(did2, ws, editor, "key-2")
    assert c4["claim_token"] != c3["claim_token"]
    assert ph.complete_local_run(c3["run_id"], c3["claim_token"], editor, asset_id="a", version_id="v",
                                 checksum="d" * 64, quality={}) is False  # stale claim rejected
    types = [e["event_type"] for e in ph.list_processing_events(c2["run_id"], did2, ws, viewer)["items"]]
    assert types == ["photo.local_run_reclaimed", "photo.local_run_retried",
                     "photo.local_run_failed", "photo.local_run_started"]  # newest first (legacy contract)
    # unsupported operation / extra inputs are rejected for local processing
    bad = ph.create_draft(ws, editor, _photo_payload(src, "COMPOSE"))["draft_id"]
    with pytest.raises(ValueError):
        ph.claim_local_run(bad, ws, editor, "key-3")
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE photo_processing_events SET event_type='x'")
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM photo_draft_events")


def test_photo_concurrent_claims_have_single_winner(repos):
    import threading
    ws, owner, editor, *_ = _workspace(repos)
    ph = repos["photos"]
    src = _image(repos, ws, owner, "c")
    did = ph.create_draft(ws, editor, _photo_payload(src))["draft_id"]
    results, errors = [], []

    def work():
        try:
            results.append(ph.claim_local_run(did, ws, editor, "race-key"))
        except ValueError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=work) for _ in range(8)]
    [th.start() for th in threads]; [th.join() for th in threads]
    assert len(results) == 1 and len(errors) == 7
    assert all("in progress" in e for e in errors)


def _lookbook_world(repos):
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    prod = repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"LB-{s}", name="Dress",
                                    description=None, category="dress",
                                    image_asset_ids=[_image(repos, ws, owner, "p")])["product_id"]
    proj = repos["projects"].create(workspace_id=ws, actor_id=editor, name="Campaign")["project_id"]
    chr_ = repos["characters"].create(workspace_id=ws, actor_id=editor, payload=_char())["character_id"]
    return ws, owner, editor, viewer, outsider, prod, proj, chr_


def _approved_photo_output(repos, ws, owner, editor, key):
    ph = repos["photos"]
    src = _image(repos, ws, owner, "ph-src-" + key)
    did = ph.create_draft(ws, editor, _photo_payload(src))["draft_id"]
    claim = ph.claim_local_run(did, ws, editor, "lb-" + key)
    out = _image(repos, ws, owner, "ph-out-" + key)
    ph.complete_local_run(claim["run_id"], claim["claim_token"], editor, asset_id=out,
                          version_id="ver_" + key, checksum="e" * 64, quality={})
    ph.record_output_review(did, claim["run_id"], ws, editor, decision="approved", asset_id=out,
                            asset_version_id="ver_" + key, provenance_id="prov_" + key, checksum_sha256="e" * 64)
    return claim["run_id"]


def _real_approved_photo_output(repos, ws, owner, editor, key):
    """A Photo output produced by the real local pipeline (real bytes, version and provenance) and approved."""
    from app.assets.validation import validate_image_upload
    from app import config
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort
    from app.photo_engine import PhotoDraftInput
    data = _png(31)
    src = PostgreSQLAssetBytesPort(repos["assets"]).save(ws, owner, "s.png", data,
                                                         validate_image_upload("s.png", data, max_bytes=config.ASSET_MAX_UPLOAD_BYTES))["asset_id"]
    port = PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"])
    did = port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))["draft_id"]
    res = port.process_local(did, ws, editor, "real-" + key)
    port.decide(did, res["run"]["run_id"], ws, owner, "approved", "")
    return res["run"]["run_id"]


def test_lookbook_planning_workflow_roles_and_character_lock(repos):
    from app.repositories.postgres_characters import CharacterConflictError
    from app.repositories.postgres_lookbooks import LookbookStateError
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    lb = repos["lookbooks"]
    body = {"title": "SS27", "product_ids": [prod], "project_id": proj, "character_id": chr_, "output_count": 2}
    d = lb.create_draft(ws, editor, body)
    did = d["draft_id"]
    assert d["workflow_status"] == "draft"
    with pytest.raises(PermissionError):
        lb.create_draft(ws, viewer, body)
    with pytest.raises(ValueError):
        lb.create_draft(ws, editor, {"title": "x"})  # no product reference
    with pytest.raises(ValueError):
        lb.create_draft(ws, editor, {**body, "character_id": "chr_missing"})
    assert lb.get_draft(did, ws, viewer)["input"]["title"] == "SS27"
    with pytest.raises(PermissionError):
        lb.get_draft(did, ws, outsider)
    # active draft locks the Character against edit and delete
    with pytest.raises(CharacterConflictError):
        repos["characters"].update(chr_, ws, editor, payload=_char(name="Changed"), asset_ids=[])
    with pytest.raises(CharacterConflictError):
        repos["characters"].soft_delete(chr_, ws, editor)
    with pytest.raises(LookbookStateError):
        lb.decide_review(did, ws, owner, "APPROVED")  # not submitted yet
    assert lb.submit_for_review(did, ws, editor)["workflow_status"] == "in_review"
    with pytest.raises(LookbookStateError):
        lb.update_draft(did, ws, editor, body)  # locked while in review
    with pytest.raises(PermissionError):
        lb.decide_review(did, ws, editor, "APPROVED")  # editors cannot approve
    with pytest.raises(ValueError):
        lb.decide_review(did, ws, owner, "CHANGES_REQUESTED")  # comment required
    lb.decide_review(did, ws, owner, "CHANGES_REQUESTED", "fix title")
    lb.update_draft(did, ws, editor, {**body, "title": "SS27 v2"})
    lb.submit_for_review(did, ws, editor)
    approved = lb.decide_review(did, ws, owner, "APPROVED")
    assert approved["workflow_status"] == "approved" and approved["reviewed_by"] == owner
    assert lb.export_plan_manifest(did, ws, viewer)["input"]["title"] == "SS27 v2"
    types = [e["event_type"] for e in lb.list_events(did, ws, viewer)["items"]]
    assert types[0] == "lookbook.approved" and types[-1] == "lookbook.draft_created"
    # archiving releases the Character lock
    lb.archive_draft(did, ws, editor)
    assert repos["characters"].update(chr_, ws, editor, payload=_char(name="Changed"), asset_ids=[])["identity"]["name"] == "Changed"
    assert repos["characters"].soft_delete(chr_, ws, editor) is True


def test_lookbook_entity_trigger_blocks_cross_workspace_reference(repos):
    import psycopg
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    ws2, owner2, *_ = _workspace(repos)
    foreign_proj = repos["projects"].create(workspace_id=ws2, actor_id=owner2, name="Other")["project_id"]
    d = repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_ids": [prod]})["draft_id"]
    with pytest.raises(ValueError):
        repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_ids": [prod], "project_id": foreign_proj})
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("INSERT INTO lookbook_draft_entities(draft_id,entity_type,entity_id) VALUES(%s,'project',%s)",
                         (d, foreign_proj))


def _always_verified(base):
    from app.ports.photos import verify_output_base
    return verify_output_base(base)


class _VerifiedLookbooks:
    """Repository-level tests inject the real Photo output verifier the port layer normally supplies."""

    def __init__(self, repo):
        self._repo = repo

    def __getattr__(self, name):
        return getattr(self._repo, name)

    def attach_approved_photo_output(self, *a, **kw):
        return self._repo.attach_approved_photo_output(*a, verify=_always_verified, **kw)

    def get_assembly_review(self, d, w, a):
        return self._repo.get_assembly_review(d, w, a, _always_verified)

    def submit_assembly(self, d, w, a):
        return self._repo.submit_assembly(d, w, a, _always_verified)

    def decide_assembly(self, d, w, a, decision, comment=""):
        return self._repo.decide_assembly(d, w, a, decision, comment, _always_verified)

    def create_output_manifest(self, d, w, a):
        return self._repo.create_output_manifest(d, w, a, _always_verified)


def test_lookbook_output_assembly_review_and_manifest(repos, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    import psycopg
    from app.repositories.postgres_lookbooks import LookbookStateError
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    lb = _VerifiedLookbooks(repos["lookbooks"])
    did = lb.create_draft(ws, editor, {"title": "Out", "product_ids": [prod]})["draft_id"]
    run1 = _real_approved_photo_output(repos, ws, owner, editor, "1" + uuid.uuid4().hex[:6])
    with pytest.raises(LookbookStateError):  # planning not approved yet
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run1, page_order=1)
    lb.submit_for_review(did, ws, editor); lb.decide_review(did, ws, owner, "APPROVED")
    # an unreviewed run cannot be attached
    ph = repos["photos"]
    src = _image(repos, ws, owner, "unrev")
    d2 = ph.create_draft(ws, editor, _photo_payload(src))["draft_id"]
    cl = ph.claim_local_run(d2, ws, editor, "unrev-" + uuid.uuid4().hex[:6])
    ph.complete_local_run(cl["run_id"], cl["claim_token"], editor, asset_id=_image(repos, ws, owner, "o"),
                          version_id="v", checksum="f" * 64, quality={})
    with pytest.raises(LookbookStateError):
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=cl["run_id"], page_order=1)
    # a later changes_requested decision supersedes an earlier approval
    run_rej = _real_approved_photo_output(repos, ws, owner, editor, "r" + uuid.uuid4().hex[:6])
    row = repos["photos"].latest_output_review(run_rej, ws)
    ph.record_output_review(row["draft_id"], run_rej, ws, editor, decision="changes_requested", comment="redo",
                            asset_id=row["asset_id"], asset_version_id=row["asset_version_id"],
                            provenance_id=row["provenance_id"], checksum_sha256=row["checksum_sha256"])
    with pytest.raises(LookbookStateError):
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run_rej, page_order=3)
    with pytest.raises(PermissionError):
        lb.attach_approved_photo_output(did, ws, viewer, photo_run_id=run1, page_order=1)
    with pytest.raises(LookbookStateError):  # product not in plan
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run1, page_order=1, product_id="prd_other00")
    item = lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run1, page_order=1, product_id=prod,
                                           caption="cover")
    assert item["product_id"] == prod and item["page_order"] == 1
    with pytest.raises(Exception):  # same run twice / same page twice
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run1, page_order=2)
    assert lb.list_outputs(did, ws, viewer)["total"] == 1
    assert lb.get_assembly_review(did, ws, viewer)["status"] == "pending_review"
    with pytest.raises(LookbookStateError):  # manifest requires approved assembly
        lb.create_output_manifest(did, ws, editor)
    with pytest.raises(LookbookStateError):  # not submitted
        lb.decide_assembly(did, ws, owner, "approved")
    review = lb.submit_assembly(did, ws, editor)
    assert review["status"] == "in_review" and len(review["snapshot_sha256"]) == 64
    with pytest.raises(LookbookStateError):  # frozen after submission
        lb.attach_approved_photo_output(did, ws, editor, photo_run_id=run_rej, page_order=2)
    with pytest.raises(LookbookStateError):  # cannot submit twice
        lb.submit_assembly(did, ws, editor)
    with pytest.raises(PermissionError):
        lb.decide_assembly(did, ws, editor, "approved")
    # tampering with the Photo review after submission is detected
    original_checksum = repos["photos"].latest_output_review(run1, ws)["checksum_sha256"]
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("ALTER TABLE photo_output_review_events DISABLE TRIGGER trg_photo_output_reviews_no_update")
        conn.execute("UPDATE photo_output_review_events SET checksum_sha256=%s WHERE run_id=%s", ("9" * 64, run1))
        conn.execute("ALTER TABLE photo_output_review_events ENABLE TRIGGER trg_photo_output_reviews_no_update")
    assert lb.get_assembly_review(did, ws, viewer)["status"] == "integrity_error"
    with pytest.raises(LookbookStateError):
        lb.decide_assembly(did, ws, owner, "approved")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("ALTER TABLE photo_output_review_events DISABLE TRIGGER trg_photo_output_reviews_no_update")
        conn.execute("UPDATE photo_output_review_events SET checksum_sha256=%s WHERE run_id=%s", (original_checksum, run1))
        conn.execute("ALTER TABLE photo_output_review_events ENABLE TRIGGER trg_photo_output_reviews_no_update")
    assert lb.get_assembly_review(did, ws, viewer)["status"] == "in_review"
    approved = lb.decide_assembly(did, ws, owner, "approved", "ok")
    assert approved["status"] == "approved"
    result = lb.create_output_manifest(did, ws, editor)
    m = result["manifest"]
    assert m["output_assembly_snapshot_sha256"] == approved["snapshot_sha256"] and len(m["outputs"]) == 1
    assert m["publication_authorized"] is False and len(result["manifest_sha256"]) == 64
    export_id = lb.record_package_export(did, ws, editor, storage_key=f"pkg/{uuid.uuid4().hex}.zip",
                                         package_sha256="a" * 64, package_size_bytes=10, manifest_sha256=result["manifest_sha256"],
                                         snapshot_sha256=approved["snapshot_sha256"], output_count=1, expires_at=2_000_000_000)
    assert [e["export_id"] for e in lb.list_package_exports(did, ws, viewer)] == [export_id]
    # immutability of outputs and audit trails
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM lookbook_output_assets")
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE lookbook_output_package_exports SET output_count=2")
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE lookbook_output_assembly_review_events SET comment='x'")


def _character_port_scenario(port, ws, owner, editor, viewer, outsider):
    """Run one scenario and return (status, detail/shape) pairs as the HTTP layer would answer."""
    from app.repo_errors import map_exception

    def attempt(fn):
        try:
            result = fn()
            return ("ok", result)
        except Exception as exc:  # noqa: BLE001 - mapping every outcome is the point
            mapped = map_exception(exc)
            return (mapped.status, mapped.detail)

    payload = {"identity": {"name": "Mina"}, "outfits": [{"id": "o1", "name": "Casual"}], "active_outfit_id": "o1"}
    out = []
    created = attempt(lambda: port.create(ws, editor, payload, []))
    out.append(("create", created[0], sorted(created[1]) if created[0] == "ok" else created[1]))
    cid = created[1]["character_id"]
    for label, fn in (
        ("viewer-create", lambda: port.create(ws, viewer, payload, [])),
        ("outsider-get", lambda: port.get(ws, cid, outsider)),
        ("outsider-list", lambda: port.list(ws, outsider)),
        ("viewer-update", lambda: port.update(ws, cid, viewer, payload, [])),
        ("foreign-asset", lambda: port.create(ws, editor, payload, ["ast_does_not_exist"])),
        ("missing-get", lambda: port.get(ws, "chr_missing", editor)),
        ("missing-update", lambda: port.update(ws, "chr_missing", editor, payload, [])),
        ("missing-delete", lambda: port.delete(ws, "chr_missing", editor)),
    ):
        r = attempt(fn)
        out.append((label, r[0], None if r[0] == "ok" else r[1]))
    got = attempt(lambda: port.get(ws, cid, viewer))
    out.append(("viewer-get", got[0], got[1]["identity"]["name"] if got[0] == "ok" else got[1]))
    upd = attempt(lambda: port.update(ws, cid, editor, {**payload, "identity": {"name": "Mina 2"}}, []))
    out.append(("update", upd[0], upd[1]["identity"]["name"] if upd[0] == "ok" else upd[1]))
    lst = attempt(lambda: port.list(ws, viewer))
    out.append(("list", lst[0], [i["identity"]["name"] for i in lst[1]["items"]] if lst[0] == "ok" else lst[1]))
    out.append(("delete", *(lambda r: (r[0], None))(attempt(lambda: port.delete(ws, cid, editor)))))
    after = attempt(lambda: port.get(ws, cid, viewer))
    out.append(("get-after-delete", after[0], None if after[0] == "ok" else after[1]))
    out.append(("list-after-delete", "ok", attempt(lambda: port.list(ws, viewer))[1]["items"]))
    return out


def test_character_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.characters import PostgreSQLCharacterPort, SQLiteCharacterPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity.sqlite3")
    store.initialize()
    names = ("owner", "editor", "viewer", "outsider")

    sqlite_ids = [f"{n}_sq" for n in names]
    store.create_workspace("parity-ws", sqlite_ids[0])
    store.add_workspace_member("parity-ws", sqlite_ids[1], "editor")
    store.add_workspace_member("parity-ws", sqlite_ids[2], "viewer")
    sqlite_out = _character_port_scenario(SQLiteCharacterPort(SQLiteWorkspacePort()), "parity-ws", *sqlite_ids)

    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_out = _character_port_scenario(PostgreSQLCharacterPort(repos["characters"]), ws, owner, editor, viewer, outsider)

    assert pg_out == sqlite_out
    statuses = {label: status for label, status, _ in sqlite_out}
    assert statuses["viewer-create"] == 403 and statuses["outsider-get"] == 404
    assert statuses["foreign-asset"] == 422 and statuses["missing-get"] == 404


def _outcome(fn):
    from fastapi import HTTPException

    from app.repo_errors import map_exception
    try:
        return ("ok", fn())
    except HTTPException as exc:  # legacy SQLite code raises these directly; routes pass them through
        return (exc.status_code, exc.detail)
    except Exception as exc:  # noqa: BLE001
        mapped = map_exception(exc)
        return (mapped.status, mapped.detail)


def _project_port_scenario(port, ws, owner, editor, viewer, outsider):
    f = {"name": "Spring", "project_type": "general", "description": "d", "external_reference": None}
    out = []
    created = _outcome(lambda: port.create(ws, editor, f))
    out.append(("create", created[0], sorted(created[1])))
    pid = created[1]["project_id"]
    steps = (
        ("viewer-create", lambda: port.create(ws, viewer, f)),
        ("outsider-create", lambda: port.create(ws, outsider, f)),
        ("outsider-list", lambda: port.list(ws, outsider, None)),
        ("outsider-get", lambda: port.get(pid, outsider)),
        ("missing-get", lambda: port.get("prj_missing", editor)),
        ("viewer-update", lambda: port.update(pid, viewer, {**f, "status": "ARCHIVED"})),
        ("outsider-update", lambda: port.update(pid, outsider, {**f, "status": "ARCHIVED"})),
        ("missing-update", lambda: port.update("prj_missing", editor, {**f, "status": "ARCHIVED"})),
    )
    for label, fn in steps:
        r = _outcome(fn)
        out.append((label, r[0], None if r[0] == "ok" else r[1]))
    g = _outcome(lambda: port.get(pid, viewer))
    out.append(("viewer-get", g[0], g[1]["name"] if g[0] == "ok" else g[1]))
    u = _outcome(lambda: port.update(pid, editor, {**f, "name": "Spring 2", "status": "COMPLETED"}))
    out.append(("update", u[0], (u[1]["name"], u[1]["status"]) if u[0] == "ok" else u[1]))
    for flt in (None, "COMPLETED", "ACTIVE"):
        lst = _outcome(lambda: port.list(ws, viewer, flt))
        out.append((f"list-{flt}", lst[0], [i["name"] for i in lst[1]["items"]] if lst[0] == "ok" else lst[1]))
    return out


def test_project_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.projects import PostgreSQLProjectPort, SQLiteProjectPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-projects.sqlite3")
    store.initialize()
    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-prj", sq[0])
    store.add_workspace_member("parity-prj", sq[1], "editor")
    store.add_workspace_member("parity-prj", sq[2], "viewer")
    sqlite_out = _project_port_scenario(SQLiteProjectPort(SQLiteWorkspacePort()), "parity-prj", *sq)

    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_out = _project_port_scenario(PostgreSQLProjectPort(repos["projects"]), ws, owner, editor, viewer, outsider)

    assert pg_out == sqlite_out
    statuses = {label: status for label, status, _ in sqlite_out}
    assert statuses["viewer-create"] == 403 and statuses["outsider-create"] == 404
    assert statuses["outsider-get"] == 404 and statuses["missing-get"] == 404


def test_project_status_change_is_blocked_while_active_lookbook_references_it(repos):
    from app.repositories.postgres_projects import ProjectConflictError
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    lb, pr = repos["lookbooks"], repos["projects"]
    fields = {"name": "Campaign", "project_type": "general", "description": None}
    draft = lb.create_draft(ws, editor, {"title": "L", "product_ids": [prod], "project_id": proj})["draft_id"]
    # ACTIVE edits stay allowed; leaving ACTIVE is blocked while an active draft references the project
    assert pr.update(proj, editor, status="ACTIVE", **fields)["status"] == "ACTIVE"
    for status in ("ARCHIVED", "COMPLETED"):
        with pytest.raises(ProjectConflictError):
            pr.update(proj, editor, status=status, **fields)
    lb.archive_draft(draft, ws, editor)
    assert pr.update(proj, editor, status="ARCHIVED", **fields)["status"] == "ARCHIVED"
    with pytest.raises(Exception):  # an archived project can no longer back a new lookbook draft
        lb.create_draft(ws, editor, {"title": "L2", "product_ids": [prod], "project_id": proj})


def _project_product_scenario(port, project_id, products, archived_project_id, owner, editor, viewer, outsider):
    p1, p2 = products
    ids = lambda r: [i["product_id"] for i in r["items"]]  # noqa: E731
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))

    step("empty", lambda: port.list(project_id, viewer), lambda r: (ids(r), r["total"]))
    step("viewer-replace", lambda: port.replace(project_id, viewer, [p1]))
    step("outsider-replace", lambda: port.replace(project_id, outsider, [p1]))
    step("outsider-list", lambda: port.list(project_id, outsider))
    step("outsider-events", lambda: port.events(project_id, outsider))
    step("missing-list", lambda: port.list("prj_missing", editor))
    step("missing-replace", lambda: port.replace("prj_missing", editor, [p1]))
    step("missing-events", lambda: port.events("prj_missing", editor))
    step("unknown-product", lambda: port.replace(project_id, editor, [p1, "prd_missing"]))
    step("assign", lambda: port.replace(project_id, editor, [p1, p2]), ids_total := (lambda r: (ids(r), r["total"])))
    step("reorder", lambda: port.replace(project_id, editor, [p2, p1]), ids_total)
    step("noop", lambda: port.replace(project_id, editor, [p2, p1]), ids_total)
    step("shrink", lambda: port.replace(project_id, editor, [p2]), ids_total)
    step("viewer-list", lambda: port.list(project_id, viewer), ids_total)
    step("archived-replace-editor", lambda: port.replace(archived_project_id, editor, [p1]))
    step("archived-replace-outsider", lambda: port.replace(archived_project_id, outsider, [p1]))
    step("events", lambda: port.events(project_id, viewer),
         lambda r: (r["total"], [(e["event_type"], e["details"], e["actor_id"] == editor) for e in r["items"]]))
    return out


def test_project_product_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import io

    from fastapi.testclient import TestClient
    from PIL import Image

    import app.config as config
    from app.main import app
    from app.ports.project_products import PostgreSQLProjectProductPort, SQLiteProjectProductPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-pp.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "p" * 48)
    users = {n: f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")}
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"tok-{n}": u for n, u in users.items()})
    from app.assets import store
    store.initialize()
    client = TestClient(app)
    h = lambda n: {"Authorization": f"Bearer tok-{n}"}  # noqa: E731
    assert client.post("/v1/workspaces", headers=h("owner"), json={"workspace_id": "parity-pp"}).status_code == 201
    store.add_workspace_member("parity-pp", users["editor"], "editor")
    store.add_workspace_member("parity-pp", users["viewer"], "viewer")
    buf = io.BytesIO(); Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="PNG")
    image = client.post("/v1/assets/images", headers=h("owner"), data={"workspace_id": "parity-pp"},
                        files={"file": ("p.png", buf.getvalue(), "image/png")}).json()["asset_id"]
    sq_products = []
    for sku in ("PP-1", "PP-2"):
        r = client.post("/v1/products", headers=h("editor"), json={
            "workspace_id": "parity-pp", "sku": sku, "name": sku, "category": "apparel", "image_asset_ids": [image]})
        assert r.status_code == 201, r.text
        sq_products.append(r.json()["product_id"])
    live = client.post("/v1/projects", headers=h("editor"), json={"workspace_id": "parity-pp", "name": "Live"}).json()["project_id"]
    gone = client.post("/v1/projects", headers=h("editor"), json={"workspace_id": "parity-pp", "name": "Gone"}).json()["project_id"]
    assert client.put(f"/v1/projects/{gone}", headers=h("editor"),
                      json={"name": "Gone", "project_type": "general", "status": "ARCHIVED"}).status_code == 200
    sqlite_out = _project_product_scenario(SQLiteProjectProductPort(SQLiteWorkspacePort()), live, sq_products, gone,
                                           users["owner"], users["editor"], users["viewer"], users["outsider"])

    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    img = _image(repos, ws, owner, "pp")
    pg_products = [repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"PP-{i}-{uuid.uuid4().hex[:6]}", name=f"P{i}",
                                            description=None, category="apparel", image_asset_ids=[img])["product_id"]
                   for i in (1, 2)]
    pg_live = repos["projects"].create(workspace_id=ws, actor_id=editor, name="Live")["project_id"]
    pg_gone = repos["projects"].create(workspace_id=ws, actor_id=editor, name="Gone")["project_id"]
    repos["projects"].update(pg_gone, editor, name="Gone", project_type="general", status="ARCHIVED")
    pg_out = _project_product_scenario(PostgreSQLProjectProductPort(repos["links"]), pg_live, pg_products, pg_gone,
                                       owner, editor, viewer, outsider)

    def normalise(rows, mapping):
        text = repr(rows)
        for a, b in mapping.items():
            text = text.replace(a, b)
        return text

    sq_map = {sq_products[0]: "P1", sq_products[1]: "P2", users["editor"]: "EDITOR"}
    pg_map = {pg_products[0]: "P1", pg_products[1]: "P2", editor: "EDITOR"}
    assert normalise(pg_out, pg_map) == normalise(sqlite_out, sq_map)
    statuses = {label: status for label, status, _ in sqlite_out}
    assert statuses["viewer-replace"] == 403 and statuses["outsider-replace"] == 404
    assert statuses["missing-list"] == 404 and statuses["unknown-product"] == 422
    assert statuses["archived-replace-editor"] == 409 and statuses["archived-replace-outsider"] == 404


def test_concurrent_project_product_replace_is_serialised(repos):
    from concurrent.futures import ThreadPoolExecutor
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    img = _image(repos, ws, owner, "cc")
    prods = [repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"CC-{i}-{s}", name=f"C{i}",
                                      description=None, category="apparel", image_asset_ids=[img])["product_id"]
             for i in range(3)]
    proj = repos["projects"].create(workspace_id=ws, actor_id=editor, name="Race")["project_id"]
    links = repos["links"]
    lists = [prods[:2], prods[1:], prods, list(reversed(prods))] * 2
    with ThreadPoolExecutor(8) as pool:
        futures = [pool.submit(links.replace_for_project, proj, ws, ids, editor) for ids in lists]
        for f in futures:
            f.result()  # no unique-index violation / deadlock may leak out
    final = [i["product_id"] for i in links.list_for_project(proj, ws, editor)["items"]]
    assert final in lists
    assert len(final) == len(set(final))


def _product_port_scenario(port, ws, imgs, other_ws_img, owner, editor, viewer, outsider, mkproject):
    """imgs: two usable image asset ids; other_ws_img: image from another workspace; mkproject() -> project_id."""
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))

    def fields(sku, **kw):
        base = {"workspace_id": ws, "sku": sku, "name": "Dress", "description": "d", "category": "apparel",
                "image_asset_ids": [imgs[0]]}
        base.update(kw)
        return base

    def vfields(sku, **kw):
        base = {"workspace_id": ws, "sku": sku, "option_values": {"size": "M"}, "image_asset_ids": []}
        base.update(kw)
        return base

    shape = lambda r: sorted(k for k in r if k not in ("product_id", "created_at", "updated_at", "archived_at"))  # noqa: E731
    created = _outcome(lambda: port.create(editor, fields("SKU-A")))
    out.append(("create", created[0], (shape(created[1]), created[1]["status"], created[1]["image_asset_ids"] == [imgs[0]])))
    pid = created[1]["product_id"]
    step("viewer-create", lambda: port.create(viewer, fields("SKU-V")))
    step("outsider-create", lambda: port.create(outsider, fields("SKU-O")))
    step("dup-sku", lambda: port.create(editor, fields("sku-a".upper())))
    step("bad-image", lambda: port.create(editor, fields("SKU-B", image_asset_ids=["ast_missing"])))
    step("foreign-image", lambda: port.create(editor, fields("SKU-B", image_asset_ids=[other_ws_img])))
    step("bad-image-and-dup", lambda: port.create(editor, fields("SKU-A", image_asset_ids=["ast_missing"])))
    second = _outcome(lambda: port.create(editor, fields("SKU-B", image_asset_ids=imgs)))
    out.append(("create-2", second[0], second[1]["image_asset_ids"] == imgs))
    p2 = second[1]["product_id"]
    step("get", lambda: port.get(ws, pid, viewer), lambda r: (r["sku"], r["status"], shape(r)))
    step("outsider-get", lambda: port.get(ws, pid, outsider))
    step("outsider-get-missing", lambda: port.get(ws, "prd_missing", outsider))
    step("missing-get", lambda: port.get(ws, "prd_missing", editor))
    step("list", lambda: port.list(ws, viewer, False, 50, 0), lambda r: (sorted(i["sku"] for i in r["items"]), r["total"], r["limit"], r["offset"]))
    step("list-page", lambda: port.list(ws, viewer, False, 1, 1), lambda r: (len(r["items"]), r["total"]))
    step("outsider-list", lambda: port.list(ws, outsider, False, 50, 0))
    step("update", lambda: port.update(pid, editor, fields("SKU-A", name="Dress 2", image_asset_ids=imgs)),
         lambda r: (r["name"], r["image_asset_ids"] == imgs))
    step("viewer-update", lambda: port.update(pid, viewer, fields("SKU-A")))
    step("outsider-update", lambda: port.update(pid, outsider, fields("SKU-A")))
    step("missing-update", lambda: port.update("prd_missing", editor, fields("SKU-A")))
    step("update-dup-sku", lambda: port.update(pid, editor, fields("SKU-B")))
    step("update-bad-image", lambda: port.update(pid, editor, fields("SKU-A", image_asset_ids=["ast_missing"])))
    v = _outcome(lambda: port.create_variant(pid, editor, vfields("VAR-1", image_asset_ids=[imgs[0]])))
    out.append(("variant-create", v[0], (sorted(k for k in v[1] if k not in ("variant_id", "created_at", "updated_at", "archived_at")), v[1]["status"], v[1]["option_values"]) if v[0] == "ok" else v[1]))
    vid = v[1]["variant_id"]
    step("variant-dup-sku", lambda: port.create_variant(pid, editor, vfields("VAR-1")))
    step("variant-sku-eq-product", lambda: port.create_variant(pid, editor, vfields("SKU-B")))
    step("variant-viewer", lambda: port.create_variant(pid, viewer, vfields("VAR-2")))
    step("variant-outsider", lambda: port.create_variant(pid, outsider, vfields("VAR-2")))
    step("variant-missing-product", lambda: port.create_variant("prd_missing", editor, vfields("VAR-2")))
    step("variant-bad-image", lambda: port.create_variant(pid, editor, vfields("VAR-2", image_asset_ids=["ast_missing"])))
    step("variant-list", lambda: port.list_variants(ws, pid, viewer, False), lambda r: [i["sku"] for i in r["items"]])
    step("variant-list-outsider", lambda: port.list_variants(ws, pid, outsider, False))
    step("variant-list-missing", lambda: port.list_variants(ws, "prd_missing", viewer, False))
    step("variant-update", lambda: port.update_variant(pid, vid, editor, vfields("VAR-1", option_values={"size": "L"})),
         lambda r: r["option_values"])
    step("variant-update-missing", lambda: port.update_variant(pid, "pvr_missing", editor, vfields("VAR-1")))
    step("variant-update-viewer", lambda: port.update_variant(pid, vid, viewer, vfields("VAR-1")))
    step("variant-update-dup", lambda: port.update_variant(pid, vid, editor, vfields("SKU-B")))
    step("variant-archive-viewer", lambda: port.archive_variant(ws, pid, vid, viewer))
    step("variant-archive", lambda: port.archive_variant(ws, pid, vid, editor), lambda r: r["status"])
    step("variant-archive-again", lambda: port.archive_variant(ws, pid, vid, editor))
    step("variant-list-active", lambda: port.list_variants(ws, pid, viewer, False), lambda r: [i["sku"] for i in r["items"]])
    step("variant-list-all", lambda: port.list_variants(ws, pid, viewer, True), lambda r: [(i["sku"], i["status"]) for i in r["items"]])
    # archive guard: an ACTIVE project assignment blocks archiving
    project_id = mkproject(p2)
    step("archive-assigned", lambda: port.archive(ws, p2, editor))
    mkproject(p2, clear=True)
    step("archive-viewer", lambda: port.archive(ws, p2, viewer))
    step("archive-outsider", lambda: port.archive(ws, p2, outsider))
    step("archive-missing", lambda: port.archive(ws, "prd_missing", editor))
    step("p2-variant", lambda: port.create_variant(p2, editor, vfields("VAR-P2")), lambda r: r["status"])
    step("archive", lambda: port.archive(ws, p2, editor), lambda r: (r["status"], [(v["sku"], v["status"]) for v in r["variants"]]))
    step("get-archived", lambda: port.get(ws, p2, viewer), lambda r: (r["status"], [(v["sku"], v["status"]) for v in r["variants"]]))
    step("variant-list-archived-parent", lambda: port.list_variants(ws, p2, viewer, True), lambda r: [i["sku"] for i in r["items"]])
    step("variant-create-archived-parent", lambda: port.create_variant(p2, editor, vfields("VAR-P3")))
    step("archive-again", lambda: port.archive(ws, p2, editor))
    step("update-archived", lambda: port.update(p2, editor, fields("SKU-B")))
    step("list-active-after", lambda: port.list(ws, viewer, False, 50, 0), lambda r: (sorted(i["sku"] for i in r["items"]), r["total"]))
    step("list-all-after", lambda: port.list(ws, viewer, True, 50, 0), lambda r: (sorted((i["sku"], i["status"]) for i in r["items"]), r["total"]))
    step("events", lambda: port.events(ws, pid, viewer, 100, 0),
         lambda r: (r["total"], sorted(e["event_type"] for e in r["items"])))
    step("events-page", lambda: port.events(ws, pid, viewer, 2, 1), lambda r: (r["total"], len(r["items"])))
    step("events-outsider", lambda: port.events(ws, pid, outsider, 100, 0))
    step("events-missing", lambda: port.events(ws, "prd_missing", viewer, 100, 0))
    return out


def test_product_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import io

    from fastapi.testclient import TestClient
    from PIL import Image

    import app.config as config
    from app.main import app
    from app.ports.products import PostgreSQLProductPort, SQLiteProductPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-products.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "p" * 48)
    users = {n: f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")}
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"tok-{n}": u for n, u in users.items()})
    from app.assets import store
    store.initialize()
    client = TestClient(app)
    h = lambda n: {"Authorization": f"Bearer tok-{n}"}  # noqa: E731
    for wid in ("parity-prod", "parity-prod-2"):
        assert client.post("/v1/workspaces", headers=h("owner"), json={"workspace_id": wid}).status_code == 201
    store.add_workspace_member("parity-prod", users["editor"], "editor")
    store.add_workspace_member("parity-prod", users["viewer"], "viewer")

    def upload(wid, shade):
        buf = io.BytesIO(); Image.new("RGB", (16, 16), (shade, 2, 3)).save(buf, format="PNG")
        r = client.post("/v1/assets/images", headers=h("owner"), data={"workspace_id": wid},
                        files={"file": ("p.png", buf.getvalue(), "image/png")})
        assert r.status_code == 201, r.text
        return r.json()["asset_id"]

    sq_imgs = [upload("parity-prod", 1), upload("parity-prod", 9)]
    sq_foreign = upload("parity-prod-2", 5)
    project = client.post("/v1/projects", headers=h("editor"), json={"workspace_id": "parity-prod", "name": "P"}).json()["project_id"]

    def sq_assign(product_id, clear=False):
        ids = [] if clear else [product_id]
        assert client.put(f"/v1/projects/{project}/products", headers=h("editor"), json={"product_ids": ids}).status_code == 200
        return project

    sqlite_out = _product_port_scenario(SQLiteProductPort(SQLiteWorkspacePort()), "parity-prod", sq_imgs, sq_foreign,
                                        users["owner"], users["editor"], users["viewer"], users["outsider"], sq_assign)

    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    ws2 = _workspace(repos)
    pg_imgs = [_image(repos, ws, owner, "pa"), _image(repos, ws, owner, "pb")]
    pg_foreign = _image(repos, ws2[0], ws2[1], "pf")
    pg_project = repos["projects"].create(workspace_id=ws, actor_id=editor, name="P")["project_id"]

    def pg_assign(product_id, clear=False):
        repos["links"].replace_for_project(pg_project, ws, [] if clear else [product_id], editor)
        return pg_project

    pg_out = _product_port_scenario(PostgreSQLProductPort(repos["products"]), ws, pg_imgs, pg_foreign,
                                    owner, editor, viewer, outsider, pg_assign)

    def normalise(rows, mapping):
        text = repr(rows)
        for a, b in mapping.items():
            text = text.replace(a, b)
        return text

    import os
    if os.environ.get('DUMP_PARITY'):
        for row in sqlite_out: print('PARITY', row)
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mismatches = [(sq[0], sq[1:], pg[1:]) for sq, pg in zip(sqlite_out, pg_out)
                  if normalise(sq, {"parity-prod": "WS"}) != normalise(pg, {ws: "WS"})]
    assert not mismatches, mismatches
    status = {label: s for label, s, _ in sqlite_out}
    assert status["viewer-create"] == 403 and status["outsider-create"] == 404 and status["dup-sku"] == 409
    assert status["bad-image"] == 422 and status["archive-assigned"] == 409 and status["missing-get"] == 404
    assert status["outsider-get-missing"] == 404
    # guard against vacuous parity: the variant listing steps must really have run as the intended actor
    shown = {label: (s, detail) for label, s, detail in sqlite_out}
    assert shown["variant-list"] == ("ok", ["VAR-1"]) and shown["variant-list-outsider"][0] == 404
    assert shown["variant-list-missing"] == (404, "Product not found")
    assert shown["archive"] == ("ok", ("archived", [("VAR-P2", "archived")]))
    assert shown["variant-list-active"] == ("ok", []) and shown["variant-list-all"] == ("ok", [("VAR-1", "archived")])


def test_product_update_and_archive_are_blocked_by_active_lookbook_draft(repos):
    from app.repositories.postgres_products import ProductConflictError
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    pr, lb = repos["products"], repos["lookbooks"]
    img = _image(repos, ws, owner, "lbp")
    kw = dict(sku="LB-EDIT", name="Dress", description=None, category="dress", image_asset_ids=[img])
    draft = lb.create_draft(ws, editor, {"title": "L", "product_ids": [prod], "project_id": proj})["draft_id"]
    with pytest.raises(ProductConflictError):
        pr.update(prod, ws, editor, **kw)
    with pytest.raises(ProductConflictError):
        pr.archive(prod, ws, editor)
    lb.archive_draft(draft, ws, editor)
    assert pr.update(prod, ws, editor, **kw)["sku"] == "LB-EDIT"
    assert pr.archive(prod, ws, editor)["status"] == "archived"


def _workspace_port_scenario(port, ids, owner, admin_candidate, editor_candidate, viewer_candidate, outsider):
    first, second = ids
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))

    keys = lambda r, drop=(): sorted(k for k in r if k not in drop)  # noqa: E731
    step("create", lambda: port.create(first, owner), lambda r: (keys(r, ("created_at",)), r["role"], r["owner_id"] == owner))
    step("create-dup", lambda: port.create(first, owner))
    step("create-dup-other-user", lambda: port.create(first, outsider))
    step("create-second", lambda: port.create(second, owner), lambda r: r["role"])
    step("list", lambda: port.list(owner), lambda r: ([i["workspace_id"] for i in r["items"]], [i["role"] for i in r["items"]], keys(r["items"][0], ("created_at",))))
    step("list-outsider", lambda: port.list(outsider), lambda r: r)
    step("add-admin", lambda: port.add_member(first, owner, admin_candidate, "admin"), lambda r: (keys(r, ("created_at",)), r["role"]))
    step("add-by-viewer-fails-setup", lambda: port.add_member(first, owner, viewer_candidate, "viewer"), lambda r: r["role"])
    step("viewer-adds", lambda: port.add_member(first, viewer_candidate, editor_candidate, "editor"))
    step("outsider-adds", lambda: port.add_member(first, outsider, editor_candidate, "editor"))
    step("missing-workspace", lambda: port.add_member("ws-missing-xyz", owner, editor_candidate, "editor"))
    step("admin-adds-editor", lambda: port.add_member(first, admin_candidate, editor_candidate, "editor"), lambda r: r["role"])
    step("duplicate-member", lambda: port.add_member(first, owner, editor_candidate, "viewer"))
    step("add-owner-again", lambda: port.add_member(first, owner, owner, "viewer"))
    step("member-sees-ws", lambda: port.list(editor_candidate), lambda r: ([i["workspace_id"] for i in r["items"]], [i["role"] for i in r["items"]]))
    step("not-visible-in-second", lambda: port.add_member(second, editor_candidate, outsider, "viewer"))
    return out


def test_workspace_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.workspace import PostgreSQLWorkspacePort, SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-ws.sqlite3")
    store.initialize()
    sq = [f"{n}_sq" for n in ("owner", "admin", "editor", "viewer", "outsider")]
    sqlite_out = _workspace_port_scenario(SQLiteWorkspacePort(), ("ws-par-one", "ws-par-two"), sq[0], sq[1], sq[2], sq[3], sq[4])

    suffix = uuid.uuid4().hex[:8]
    pg = [f"{n}_{suffix}" for n in ("owner", "admin", "editor", "viewer", "outsider")]
    pg_ids = (f"ws-par-one-{suffix}", f"ws-par-two-{suffix}")
    pg_out = _workspace_port_scenario(PostgreSQLWorkspacePort(repos["assets"]), pg_ids, *pg)

    def normalise(rows, mapping):
        text = repr(rows)
        for a, b in mapping.items():
            text = text.replace(a, b)
        return text

    sq_map = {"ws-par-one": "WS1", "ws-par-two": "WS2"}
    pg_map = {pg_ids[0]: "WS1", pg_ids[1]: "WS2"}
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mismatches = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out)
                  if normalise(a, sq_map) != normalise(b, pg_map)]
    assert not mismatches, mismatches
    shown = {label: (s, d) for label, s, d in sqlite_out}
    assert shown["create-dup"] == (409, "Workspace ID already exists")
    assert shown["viewer-adds"] == (403, "Insufficient workspace role") and shown["outsider-adds"][0] == 404
    assert shown["missing-workspace"] == (404, "Workspace not found")
    assert shown["duplicate-member"] == (409, "Member already exists or workspace is invalid")
    assert shown["add-owner-again"][0] == 409
    assert shown["list"][1][0] == ["ws-par-two", "ws-par-one"]  # newest first, as in the legacy API
    assert shown["not-visible-in-second"][0] == 404 and shown["list-outsider"] == ("ok", {"items": []})


def _asset_port_scenario(port, ws, ids, owner, editor, viewer, outsider, mkproduct, archive_product):
    a, b, c = ids
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))

    keys = lambda r, drop=(): sorted(k for k in r if k not in drop)  # noqa: E731
    rel_view = lambda r: (r["source_asset_id"], r["target_asset_id"], r["relation_type"], r["created_by"])  # noqa: E731
    step("get", lambda: port.get(a, viewer), lambda r: (keys(r), r["asset_kind"], r["embedded_binary"], r["gltf_version"], r["media_type"]))
    step("get-outsider", lambda: port.get(a, outsider))
    step("get-missing", lambda: port.get("ast_missing", viewer))
    step("list-all", lambda: port.list(ws, viewer, "all"), lambda r: [i["asset_id"] for i in r["items"]])
    step("list-image", lambda: port.list(ws, viewer, "image"), lambda r: len(r["items"]))
    step("list-model", lambda: port.list(ws, viewer, "model"), lambda r: len(r["items"]))
    step("list-outsider", lambda: port.list(ws, outsider, "all"))
    step("versions", lambda: port.versions(a, viewer), lambda r: [(keys(i), i["version_number"], i["is_current"]) for i in r["items"]])
    step("versions-outsider", lambda: port.versions(a, outsider))
    step("versions-missing", lambda: port.versions("ast_missing", viewer))
    step("provenance", lambda: port.provenance(a, viewer, 100, 0), lambda r: [(keys(i), i["event_type"], i["details"], i["version_number"]) for i in r["items"]])
    step("provenance-page", lambda: port.provenance(a, viewer, 1, 5), lambda r: len(r["items"]))
    step("provenance-outsider", lambda: port.provenance(a, outsider, 100, 0))
    step("rel-viewer", lambda: port.add_relation(a, viewer, b, "derived_from"))
    step("rel-outsider", lambda: port.add_relation(a, outsider, b, "derived_from"))
    step("rel-missing-source", lambda: port.add_relation("ast_missing", editor, b, "derived_from"))
    step("rel-self", lambda: port.add_relation(a, editor, a, "paired_with"))
    step("rel-bad-type", lambda: port.add_relation(a, editor, b, "owns"))
    step("rel-missing-target", lambda: port.add_relation(a, editor, "ast_missing", "paired_with"))
    step("rel-create", lambda: port.add_relation(a, editor, b, "derived_from"), lambda r: (keys(r, ("relation_id", "created_at")), rel_view(r)))
    step("rel-duplicate", lambda: port.add_relation(a, editor, b, "derived_from"))
    step("rel-cycle", lambda: port.add_relation(b, editor, a, "derived_from"))
    step("rel-reverse-other-type", lambda: port.add_relation(b, editor, a, "paired_with"), lambda r: rel_view(r))
    step("rel-second", lambda: port.add_relation(a, editor, c, "variant_of"), lambda r: rel_view(r))
    step("rel-list", lambda: port.relations(a, viewer), lambda r: [(rel_view(i), keys(i, ("relation_id", "created_at"))) for i in r["items"]])
    step("rel-list-outsider", lambda: port.relations(a, outsider))
    step("prov-a-after", lambda: port.provenance(a, viewer, 100, 0),
         lambda r: sorted((i["event_type"], tuple(sorted(k for k in i["details"] if k != "relation_id"))) for i in r["items"]))
    step("prov-b-after", lambda: port.provenance(b, viewer, 100, 0),
         lambda r: sorted((i["event_type"], tuple(sorted(k for k in i["details"] if k != "relation_id"))) for i in r["items"]))
    step("delete-viewer", lambda: port.delete(c, viewer))
    step("delete-outsider", lambda: port.delete(c, outsider))
    step("delete-missing", lambda: port.delete("ast_missing", editor))
    product_id = mkproduct(a)
    step("delete-product-ref", lambda: port.delete(a, editor))
    archive_product(product_id)
    step("delete-c", lambda: port.delete(c, editor))
    step("delete-c-again", lambda: port.delete(c, editor))
    step("get-deleted", lambda: port.get(c, editor))
    step("list-after", lambda: port.list(ws, viewer, "all"), lambda r: len(r["items"]))
    step("delete-a-after-archive", lambda: port.delete(a, editor))
    step("prov-deleted-gone", lambda: port.provenance(a, viewer, 100, 0))
    return out


def test_asset_metadata_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import io

    from fastapi.testclient import TestClient
    from PIL import Image

    import app.config as config
    from app.main import app
    from app.ports.assets import PostgreSQLAssetMetadataPort, SQLiteAssetMetadataPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-assets.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "p" * 48)
    users = {n: f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")}
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"tok-{n}": u for n, u in users.items()})
    from app.assets import store
    store.initialize()
    client = TestClient(app)
    h = lambda n: {"Authorization": f"Bearer tok-{n}"}  # noqa: E731
    assert client.post("/v1/workspaces", headers=h("owner"), json={"workspace_id": "parity-ast"}).status_code == 201
    store.add_workspace_member("parity-ast", users["editor"], "editor")
    store.add_workspace_member("parity-ast", users["viewer"], "viewer")

    def upload(shade):
        buf = io.BytesIO(); Image.new("RGB", (16, 16), (shade, 2, 3)).save(buf, format="PNG")
        r = client.post("/v1/assets/images", headers=h("owner"), data={"workspace_id": "parity-ast"},
                        files={"file": (f"p{shade}.png", buf.getvalue(), "image/png")})
        assert r.status_code == 201, r.text
        return r.json()["asset_id"]

    sq_ids = [upload(1), upload(2), upload(3)]

    def sq_product(asset_id):
        r = client.post("/v1/products", headers=h("editor"), json={
            "workspace_id": "parity-ast", "sku": "AST-P1", "name": "P", "category": "apparel", "image_asset_ids": [asset_id]})
        assert r.status_code == 201, r.text
        return r.json()["product_id"]

    def sq_archive(product_id):
        assert client.post(f"/v1/products/{product_id}/archive?workspace_id=parity-ast", headers=h("editor")).status_code == 200

    sqlite_out = _asset_port_scenario(SQLiteAssetMetadataPort(SQLiteWorkspacePort()), "parity-ast", sq_ids,
                                      users["owner"], users["editor"], users["viewer"], users["outsider"],
                                      sq_product, sq_archive)

    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    pg_ids = [_image(repos, ws, owner, f"pa{i}") for i in range(3)]

    def pg_product(asset_id):
        return repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"AST-P1-{s}", name="P",
                                        description=None, category="apparel", image_asset_ids=[asset_id])["product_id"]

    def pg_archive(product_id):
        repos["products"].archive(product_id, ws, editor)

    pg_out = _asset_port_scenario(PostgreSQLAssetMetadataPort(repos["assets"]), ws, pg_ids,
                                  owner, editor, viewer, outsider, pg_product, pg_archive)

    import json
    import sqlite3

    from app.postgres import connect as pg_connect
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as sdb:
        sq_audit = sorted((r[0], json.loads(r[1]), r[2]) for r in sdb.execute(
            "SELECT event_type,details_json,version_number FROM asset_provenance WHERE event_type IN ('asset.deleted','asset.uploaded')"))
    with pg_connect() as pdb:
        pg_audit = sorted((r["event_type"], r["details_json"], r["version_number"]) for r in pdb.execute(
            "SELECT event_type,details_json,version_number FROM asset_provenance WHERE workspace_id=%s "
            "AND event_type IN ('asset.deleted','asset.uploaded')", (ws,)).fetchall())
    assert pg_audit == sq_audit, (pg_audit, sq_audit)
    assert ("asset.deleted", {"source": "user_delete"}, None) in sq_audit

    def normalise(row, mapping):
        text = repr(row)
        for a, b in mapping.items():
            text = text.replace(a, b)
        return text

    sq_map = {"parity-ast": "WS", **{v: n for v, n in zip(sq_ids, "ABC")},
              **{u: n.upper() for n, u in users.items()}}
    pg_map = {ws: "WS", **{v: n for v, n in zip(pg_ids, "ABC")},
              **{u: n for u, n in zip((owner, editor, viewer, outsider), ("OWNER", "EDITOR", "VIEWER", "OUTSIDER"))}}
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mismatches = [(sq[0], sq[1:], pg[1:]) for sq, pg in zip(sqlite_out, pg_out)
                  if normalise(sq, sq_map) != normalise(pg, pg_map)]
    assert not mismatches, "\n" + "\n".join(f"{m[0]}\n   sqlite={m[1]}\n   pg    ={m[2]}" for m in mismatches)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["delete-product-ref"] == (409, "Asset is referenced by an active Product; update or archive the Product first")
    assert shown["rel-duplicate"] == (409, "This asset relation already exists")
    assert shown["rel-cycle"][0] == 422 and shown["rel-self"][0] == 422 and shown["rel-missing-target"][0] == 404
    assert shown["delete-c"] == ("ok", None) and shown["delete-c-again"][0] == 404 and shown["list-after"] == ("ok", 2)
    assert shown["prov-a-after"][0] == "ok" and ("asset.relation_created", ("relation_type", "target_asset_id")) in shown["prov-a-after"][1]
    assert shown["prov-b-after"][0] == "ok" and any(e[0] == "asset.relation_received" for e in shown["prov-b-after"][1])


def test_asset_delete_guards_cover_variant_photo_lookbook_and_generated_output(repos):
    from app.postgres import connect
    from app.repositories.postgres_assets import AssetConflictError
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    assets, products, photos, lookbooks = repos["assets"], repos["products"], repos["photos"], repos["lookbooks"]

    # variant reference
    base = _image(repos, ws, owner, "g-base")
    variant_img = _image(repos, ws, owner, "g-var")
    prod = products.create(workspace_id=ws, actor_id=editor, sku=f"G-{s}", name="P", description=None,
                           category="x", image_asset_ids=[base])["product_id"]
    var = products.create_variant(product_id=prod, workspace_id=ws, actor_id=editor, sku=f"GV-{s}",
                                  option_values={"size": "M"}, image_asset_ids=[variant_img])["variant_id"]
    with pytest.raises(AssetConflictError, match="Product Variant"):
        assets.soft_delete_asset(variant_img, ws, actor_id=editor)
    products.archive_variant(prod, var, ws, editor)
    assert assets.soft_delete_asset(variant_img, ws, actor_id=editor) is True

    # photo draft reference
    src = _image(repos, ws, owner, "g-photo")
    draft = photos.create_draft(ws, editor, _photo_payload(src))["draft_id"]
    with pytest.raises(AssetConflictError, match="Photo Draft"):
        assets.soft_delete_asset(src, ws, actor_id=editor)
    photos.archive_draft(draft, ws, editor)
    assert assets.soft_delete_asset(src, ws, actor_id=editor) is True

    # generated / processed output (retained through the Output workflow, not the delete route)
    out_asset = _image(repos, ws, owner, "g-out")
    with connect() as conn:
        conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,event_type,actor_id)
                        VALUES(%s,%s,%s,'asset.photo_processed',%s)""",
                     ("ap_" + uuid.uuid4().hex, ws, out_asset, editor))
    with pytest.raises(AssetConflictError, match="Output retention"):
        assets.soft_delete_asset(out_asset, ws, actor_id=editor)

    # lookbook draft reference (an asset linked to an active draft that no Product/Variant/Photo guard covers)
    lws, lowner, leditor, _, _, lprod, lproj, _ = _lookbook_world(repos)
    draft = lookbooks.create_draft(lws, leditor, {"title": "L", "product_ids": [lprod], "project_id": lproj})["draft_id"]
    extra = _image(repos, lws, lowner, "g-lb")
    with connect() as conn:
        role = conn.execute("SELECT role FROM lookbook_draft_assets WHERE draft_id=%s LIMIT 1", (draft,)).fetchone()["role"]
        conn.execute("INSERT INTO lookbook_draft_assets(draft_id,asset_id,role) VALUES(%s,%s,%s)", (draft, extra, role))
    with pytest.raises(AssetConflictError, match="Lookbook Draft"):
        assets.soft_delete_asset(extra, lws, actor_id=leditor)
    lookbooks.archive_draft(draft, lws, leditor)
    assert assets.soft_delete_asset(extra, lws, actor_id=leditor) is True
    # roles: viewers/outsiders may not delete, and a missing asset reports False
    from app.repo_errors import InsufficientRoleError, NotAMemberError
    spare = _image(repos, ws, owner, "g-spare")
    with pytest.raises(InsufficientRoleError):
        assets.soft_delete_asset(spare, ws, actor_id=viewer)
    with pytest.raises(NotAMemberError):
        assets.soft_delete_asset(spare, ws, actor_id=outsider)
    assert assets.soft_delete_asset("ast_missing", ws, actor_id=editor) is False


def test_asset_kind_model_matches_legacy_contract_and_excludes_buffers(repos):
    ws, owner, editor, viewer, outsider, s = _workspace(repos)
    assets = repos["assets"]
    for media, name in (("model/gltf-binary", "m.glb"), ("application/octet-stream", "buf.bin"), ("image/png", "i.png")):
        aid = "ast_" + uuid.uuid4().hex
        assets.register_asset(asset_id=aid, owner_id=owner, workspace_id=ws, original_filename=name,
                              storage_key=f"{ws}/{aid}", media_type=media, size_bytes=1, checksum_sha256="b" * 64)
    names = lambda kind: sorted(a["original_filename"] for a in assets.list_assets(ws, kind=kind))  # noqa: E731
    assert names("model") == ["m.glb"]          # legacy: only model/*; raw buffers are not "models"
    assert names("image") == ["i.png"]
    assert names("all") == ["buf.bin", "i.png", "m.glb"]


def _png(shade: int) -> bytes:
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (shade, 40, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _asset_bytes_scenario(port, meta_port, ws, owner, editor, viewer, outsider, storage_dir):
    import hashlib

    from app import config
    from app.assets.validation import validate_image_upload

    out = []
    files = lambda: sorted(p.name for p in storage_dir.iterdir() if p.is_file())  # noqa: E731
    png1, png2 = _png(10), _png(200)
    val = lambda data: validate_image_upload("a.png", data, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    sha = lambda data: hashlib.sha256(data).hexdigest()  # noqa: E731

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    keys = lambda r: sorted(r)  # noqa: E731
    saved = step("save", lambda: port.save(ws, editor, "a.png", png1, val(png1)),
                 lambda r: (keys(r), r["asset_kind"], r["media_type"], r["size_bytes"], r["original_filename"], r["checksum_sha256"] == sha(png1), len(files())))
    asset_id = saved[1]["asset_id"]
    step("save-viewer", lambda: port.save(ws, viewer, "b.png", png1, val(png1)), None)
    step("save-outsider", lambda: port.save(ws, outsider, "b.png", png1, val(png1)), None)
    out.append(("files-after-denied-saves", "ok", len(files())))
    v1 = meta_port.versions(asset_id, viewer)["items"][0]["version_id"]
    step("version2", lambda: port.save_version(asset_id, editor, "a2.png", png2, val(png2)),
         lambda r: (keys(r), r["version_number"], r["checksum_sha256"] == sha(png2), r["original_filename"], len(files())))
    step("version-viewer", lambda: port.save_version(asset_id, viewer, "x.png", png2, val(png2)))
    step("version-outsider", lambda: port.save_version(asset_id, outsider, "x.png", png2, val(png2)))
    step("version-missing", lambda: port.save_version("ast_missing", editor, "x.png", png2, val(png2)))
    step("versions", lambda: meta_port.versions(asset_id, viewer),
         lambda r: [(i["version_number"], i["is_current"]) for i in r["items"]])
    step("restore-viewer", lambda: port.restore(asset_id, viewer, v1))
    step("restore-outsider", lambda: port.restore(asset_id, outsider, v1))
    step("restore-missing-version", lambda: port.restore(asset_id, editor, "av_missing"))
    step("restore-missing-asset", lambda: port.restore("ast_missing", editor, v1))
    step("restore", lambda: port.restore(asset_id, editor, v1),
         lambda r: (keys(r), r["version_number"], r["restored_from_version_id"] == v1, r["checksum_sha256"] == sha(png1), len(files())))
    step("versions-after-restore", lambda: meta_port.versions(asset_id, viewer),
         lambda r: [(i["version_number"], i["is_current"]) for i in r["items"]])
    step("provenance-events", lambda: meta_port.provenance(asset_id, viewer, 100, 0),
         lambda r: sorted((i["event_type"], i["version_number"], tuple(sorted(k for k in i["details"] if k not in ("version_id", "restored_from_version_id")))) for i in r["items"]))
    step("audit-ok", lambda: port.audit(ws, viewer, 100, 0), lambda r: (r["counts"], r["total"], r["checked"], r["limit"], r["offset"]))
    step("audit-outsider", lambda: port.audit(ws, outsider, 100, 0))
    step("file-lookup", lambda: port.current_file(asset_id) is not None, lambda r: r)
    step("file-lookup-missing", lambda: port.current_file("ast_missing") is None, lambda r: r)
    # corrupt the historical file: restore must refuse, and must not leave a new file behind
    before = files()
    record = port.version_record(asset_id, ws, v1)
    (storage_dir / record["storage_key"]).write_bytes(png1 + b"x")
    step("restore-corrupt", lambda: port.restore(asset_id, editor, v1))
    out.append(("no-new-file-on-refused-restore", "ok", files() == before))
    (storage_dir / record["storage_key"]).write_bytes(png2[:-3] + b"abc")  # same size, different bytes
    step("restore-checksum", lambda: port.restore(asset_id, editor, v1))
    (storage_dir / record["storage_key"]).unlink()
    step("restore-missing-file", lambda: port.restore(asset_id, editor, v1))
    # audit sees a corrupted / missing CURRENT file
    current_key = [k for k in files() if k != record["storage_key"]][-1]
    cur = meta_port.versions(asset_id, viewer)["items"][0]["version_id"]
    cur_key = port.version_record(asset_id, ws, cur)["storage_key"]
    size_now = (storage_dir / cur_key).stat().st_size
    (storage_dir / cur_key).write_bytes(b"z" * size_now)  # same size, different content
    step("audit-checksum", lambda: port.audit(ws, viewer, 100, 0), lambda r: r["counts"])
    (storage_dir / cur_key).write_bytes(b"short")
    step("audit-size", lambda: port.audit(ws, viewer, 100, 0), lambda r: r["counts"])
    (storage_dir / cur_key).unlink()
    step("audit-missing", lambda: port.audit(ws, viewer, 100, 0), lambda r: r["counts"])
    # delete removes every file of the asset
    step("delete", lambda: meta_port.delete(asset_id, editor))
    out.append(("files-after-delete", "ok", files()))
    step("file-lookup-after-delete", lambda: port.current_file(asset_id) is None, lambda r: r)
    return out


def test_asset_bytes_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.assets import PostgreSQLAssetMetadataPort, SQLiteAssetMetadataPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-bytes.sqlite3")
    store.initialize()
    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-bytes", sq[0])
    store.add_workspace_member("parity-bytes", sq[1], "editor")
    store.add_workspace_member("parity-bytes", sq[2], "viewer")
    wsp = SQLiteWorkspacePort()
    sqlite_out = _asset_bytes_scenario(SQLiteAssetBytesPort(wsp), SQLiteAssetMetadataPort(wsp), "parity-bytes", *sq, sq_dir)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_out = _asset_bytes_scenario(PostgreSQLAssetBytesPort(repos["assets"]), PostgreSQLAssetMetadataPort(repos["assets"]),
                                   ws, owner, editor, viewer, outsider, pg_dir)

    def normalise(row, mapping):
        text = repr(row)
        for a, b in mapping.items():
            text = text.replace(a, b)
        return text

    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:230])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out)
            if normalise(a, {"parity-bytes": "WS"}) != normalise(b, {ws: "WS"})]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={m[1]}\n   pg    ={m[2]}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["save-viewer"][0] == 403 and shown["save-outsider"][0] == 404 and shown["files-after-denied-saves"] == ("ok", 1)
    assert shown["version-missing"] == (404, "Asset not found") and shown["restore-missing-version"] == (404, "Asset version not found")
    assert shown["restore"][1][1] == 3 and shown["restore"][1][-1] == 3   # v3 created; three files on disk
    assert shown["restore-corrupt"][0] == 409 and shown["restore-checksum"][0] == 409 and shown["restore-missing-file"][0] == 409
    assert shown["no-new-file-on-refused-restore"] == ("ok", True)
    assert shown["audit-checksum"][1] == {"ok": 0, "missing": 0, "size_mismatch": 0, "checksum_mismatch": 1}
    assert shown["audit-size"][1] == {"ok": 0, "missing": 0, "size_mismatch": 1, "checksum_mismatch": 0}
    assert shown["audit-missing"][1]["missing"] == 1 and shown["files-after-delete"] == ("ok", [])
    assert shown["file-lookup"] == ("ok", True) and shown["file-lookup-missing"] == ("ok", True)
    assert shown["file-lookup-after-delete"] == ("ok", True)


class _GrantEditor:
    """Workspace port that grants a role the backend itself will refuse: the failure happens AFTER the file write."""
    def role(self, workspace_id, user_id):
        return "editor"


def test_failed_metadata_write_never_leaves_an_orphan_file(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.assets.validation import validate_image_upload
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort

    val = lambda data: validate_image_upload("a.png", data, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    png1, png2 = _png(11), _png(99)

    # --- SQLite (legacy implementation): upload by a non-member fails after the file was written
    sq_dir = tmp_path / "sq"; sq_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "orphans.sqlite3")
    store.initialize(); store.create_workspace("orphans", "owner_o")
    with pytest.raises(Exception):
        SQLiteAssetBytesPort(_GrantEditor()).save("orphans", "ghost", "a.png", png1, val(png1))
    assert list(sq_dir.iterdir()) == []

    # --- PostgreSQL: save, save_version and restore all clean up their object when the metadata write fails
    pg_dir = tmp_path / "pg"; pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    real = PostgreSQLAssetBytesPort(repos["assets"])
    ghosted = PostgreSQLAssetBytesPort(repos["assets"], workspaces=_GrantEditor())
    with pytest.raises(Exception):
        ghosted.save(ws, "ghost", "a.png", png1, val(png1))
    assert list(pg_dir.iterdir()) == []
    asset_id = real.save(ws, editor, "a.png", png1, val(png1))["asset_id"]
    assert len(list(pg_dir.iterdir())) == 1
    with pytest.raises(Exception):
        ghosted.save_version(asset_id, "ghost", "b.png", png2, val(png2))
    assert len(list(pg_dir.iterdir())) == 1
    first_version = repos["assets"].list_asset_versions(asset_id, ws)[0]["version_id"]
    with pytest.raises(Exception):
        ghosted.restore(asset_id, "ghost", first_version)
    assert len(list(pg_dir.iterdir())) == 1
    # rows were not changed either: still exactly one version
    assert len(repos["assets"].list_asset_versions(asset_id, ws)) == 1


def _photo_draft_scenario(port, ws, imgs, foreign_img, owner, editor, viewer, outsider):
    from app.photo_engine import PhotoDraftInput

    out = []

    def body(op="ENHANCE", src="src", **extra):
        data = {"workspace_id": ws, "source_asset_id": imgs[src], "operation": op, **extra}
        return PhotoDraftInput(**data)

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    shape = lambda d: (sorted(d), d["status"], sorted(d["input"]), d["input"]["operation"],  # noqa: E731
                       bool(d["input"]["source_version_id"]), len(d["input"]["source_checksum_sha256"]))
    created = step("create", lambda: port.create(ws, editor, body(reference_asset_ids=[imgs["ref"]], prompt="p")), shape)
    did = created[1]["draft_id"]
    other = step("create-2", lambda: port.create(ws, owner, body("LIGHTING")), shape)[1]["draft_id"]
    step("create-viewer", lambda: port.create(ws, viewer, body()))
    step("create-outsider", lambda: port.create(ws, outsider, body()))
    step("create-foreign-asset", lambda: port.create(ws, editor, body(reference_asset_ids=[foreign_img])))
    step("create-duplicate-role", lambda: port.create(ws, editor, body(reference_asset_ids=[imgs["src"]])))
    step("create-non-image", lambda: port.create(ws, editor, body(src="doc")))
    step("get-viewer", lambda: port.get(did, ws, viewer), shape)
    step("get-outsider", lambda: port.get(did, ws, outsider))
    step("get-missing", lambda: port.get("phd_missing", ws, viewer))
    step("get-other-workspace-id", lambda: port.get(did, "ws-other-not-member", editor))
    step("update-viewer", lambda: port.update(did, ws, viewer, body("RETOUCH")))
    step("update-outsider", lambda: port.update(did, ws, outsider, body("RETOUCH")))
    step("update-missing", lambda: port.update("phd_missing", ws, editor, body("RETOUCH")))
    step("update-foreign-asset", lambda: port.update(did, ws, editor, body(reference_asset_ids=[foreign_img])))
    step("update", lambda: port.update(did, ws, editor, body("RETOUCH", prompt="q")), lambda d: (d["input"]["operation"], d["input"]["prompt"]))
    step("list-viewer", lambda: port.list(ws, viewer, False, 50, 0), lambda r: (r["total"], r["limit"], r["offset"], [i["input"]["operation"] for i in r["items"]]))
    step("list-page", lambda: port.list(ws, viewer, False, 1, 1), lambda r: (r["total"], len(r["items"])))
    step("list-outsider", lambda: port.list(ws, outsider, False, 50, 0))
    step("archive-viewer", lambda: port.archive(did, ws, viewer))
    step("archive-outsider", lambda: port.archive(did, ws, outsider))
    step("archive-missing", lambda: port.archive("phd_missing", ws, editor))
    step("archive", lambda: port.archive(did, ws, editor), lambda d: (d["status"], bool(d["archived_at"])))
    step("archive-twice", lambda: port.archive(did, ws, editor))
    step("update-archived", lambda: port.update(did, ws, editor, body("RETOUCH")))
    step("get-archived", lambda: port.get(did, ws, viewer), lambda d: d["status"])
    step("list-after-archive", lambda: port.list(ws, viewer, False, 50, 0), lambda r: r["total"])
    step("list-include-archived", lambda: port.list(ws, viewer, True, 50, 0), lambda r: (r["total"], sorted(i["status"] for i in r["items"])))
    step("events", lambda: port.events(did, ws, viewer, 100, 0),
         lambda r: (r["total"], r["limit"], [(e["event_type"], e["details"]) for e in r["items"]]))
    step("events-page", lambda: port.events(did, ws, viewer, 1, 1), lambda r: (r["total"], [e["event_type"] for e in r["items"]]))
    step("events-max-limit", lambda: port.events(did, ws, viewer, 500, 0), lambda r: r["total"])
    step("events-outsider", lambda: port.events(did, ws, outsider, 100, 0))
    step("events-missing-draft", lambda: port.events("phd_missing", ws, viewer, 100, 0))
    step("runs-empty", lambda: port.runs(other, ws, viewer, 50, 0), lambda r: (r["total"], r["items"]))
    step("runs-outsider", lambda: port.runs(other, ws, outsider, 50, 0))
    step("runs-missing-draft", lambda: port.runs("phd_missing", ws, viewer, 50, 0))
    step("run-events-missing-run", lambda: port.run_events(other, "phr_missing", ws, viewer, 100, 0))
    step("run-events-missing-draft", lambda: port.run_events("phd_missing", "phr_missing", ws, viewer, 100, 0))
    step("run-events-outsider", lambda: port.run_events(other, "phr_missing", ws, outsider, 100, 0))
    return out, did, other


def _photo_runs_scenario(port, run_ids, ws, viewer, outsider, other):
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
    step("runs", lambda: port.runs(other, ws, viewer, 50, 0),
         lambda r: (r["total"], [(i["status"], i["attempts"], i.get("review_status"), sorted(i)) for i in r["items"]]))
    step("runs-page", lambda: port.runs(other, ws, viewer, 1, 0), lambda r: (r["total"], len(r["items"]), r["items"][0]["status"]))
    step("run-events", lambda: port.run_events(other, run_ids[0], ws, viewer, 100, 0),
         lambda r: (r["total"], [e["event_type"] for e in r["items"]]))
    step("run-events-page", lambda: port.run_events(other, run_ids[0], ws, viewer, 1, 1),
         lambda r: (r["total"], [e["event_type"] for e in r["items"]]))
    step("run-events-max-limit", lambda: port.run_events(other, run_ids[0], ws, viewer, 500, 0), lambda r: r["total"])
    step("run-events-wrong-draft", lambda: port.run_events(other, run_ids[1], ws, viewer, 100, 0))
    step("run-events-outsider", lambda: port.run_events(other, run_ids[0], ws, outsider, 100, 0))
    return out


def _non_image_asset_sqlite(ws, owner):
    from app.assets import store
    aid = "ast_" + uuid.uuid4().hex
    with store._connect() as db:
        db.execute("INSERT INTO assets(asset_id,owner_id,workspace_id,original_filename,storage_key,media_type,size_bytes,"
                   "checksum_sha256,gltf_version,embedded_binary,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                   (aid, owner, ws, "d.pdf", f"{ws}/{aid}.pdf", "application/pdf", 10, "b" * 64, "n/a", 0))
    return aid


def _photo_seed_runs_sqlite(ws, editor, other):
    from app.photo_engine import claim_local_run, complete_local_run, fail_local_run
    c = claim_local_run(other, ws, editor, "parity-key-1")
    fail_local_run(c["run_id"], c["claim_token"], editor, "boom")
    claim_local_run(other, ws, editor, "parity-key-1")   # retry -> processing, attempts 2
    return [c["run_id"]]


def test_photo_draft_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort, SQLitePhotoDraftPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-photo.sqlite3")
    store.initialize()
    from app.photo_engine import initialize as init_photo
    init_photo()
    from app.assets.validation import validate_image_upload

    def seed(bytes_port, ws, owner, other_ws, other_owner):
        png = _png(33)
        val = lambda n, d: validate_image_upload(n, d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
        imgs = {k: bytes_port.save(ws, owner, f"{k}.png", _png(20 + i), val("a.png", _png(20 + i)))["asset_id"]
                for i, k in enumerate(("src", "ref"))}
        foreign = bytes_port.save(other_ws, other_owner, "f.png", png, val("f.png", png))["asset_id"]
        return imgs, foreign

    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-photo", sq[0]); store.add_workspace_member("parity-photo", sq[1], "editor")
    store.add_workspace_member("parity-photo", sq[2], "viewer")
    store.create_workspace("parity-photo-2", "owner2_sq")
    wsp = SQLiteWorkspacePort()
    sq_imgs, sq_foreign = seed(SQLiteAssetBytesPort(wsp), "parity-photo", sq[0], "parity-photo-2", "owner2_sq")
    # a non-image asset (same on both backends: a document is rejected as source)
    sq_imgs["doc"] = _non_image_asset_sqlite("parity-photo", sq[0])
    sqlite_port = SQLitePhotoDraftPort(wsp)
    sqlite_out, sq_did, sq_other = _photo_draft_scenario(sqlite_port, "parity-photo", sq_imgs, sq_foreign, *sq)
    sqlite_out += _photo_runs_scenario(sqlite_port, _photo_seed_runs_sqlite("parity-photo", sq[1], sq_other) + [sq_did],
                                       "parity-photo", sq[2], sq[3], sq_other)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    ws2, owner2, *_ = _workspace(repos)
    pg_imgs, pg_foreign = seed(PostgreSQLAssetBytesPort(repos["assets"]), ws, owner, ws2, owner2)
    doc = "ast_" + uuid.uuid4().hex
    repos["assets"].register_asset(asset_id=doc, owner_id=owner, workspace_id=ws, original_filename="d.pdf",
                                   storage_key=f"{ws}/{doc}.pdf", media_type="application/pdf", size_bytes=10,
                                   checksum_sha256="b" * 64)
    pg_imgs["doc"] = doc
    pg_port = PostgreSQLPhotoDraftPort(repos["photos"])
    pg_out, pg_did, pg_other = _photo_draft_scenario(pg_port, ws, pg_imgs, pg_foreign, owner, editor, viewer, outsider)
    c = repos["photos"].claim_local_run(pg_other, ws, editor, "parity-key-1")
    repos["photos"].fail_local_run(c["run_id"], c["claim_token"], editor, "boom")
    repos["photos"].claim_local_run(pg_other, ws, editor, "parity-key-1")
    pg_out += _photo_runs_scenario(pg_port, [c["run_id"], pg_did], ws, viewer, outsider, pg_other)

    def norm(row, ws_name):
        return repr(row).replace(ws_name, "WS")
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:230])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-photo") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={m[1]}\n   pg    ={m[2]}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["create-viewer"][0] == 403 and shown["create-outsider"][0] == 404
    assert shown["create-foreign-asset"][0] == 422 and shown["create-non-image"][0] == 422
    assert shown["update-archived"][0] == 404 and shown["archive-twice"][0] == 404
    assert shown["events"][1][2][0][0] == "photo.draft_archived" and shown["events"][1][0] == 3
    assert shown["events-max-limit"][0] == "ok" and shown["run-events-missing-run"] == (404, "Photo processing run not found")
    assert shown["runs"][1][0] == 1 and shown["runs"][1][1][0][:2] == ("processing", 2)
    assert shown["run-events"][1][1][0] == "photo.local_run_retried" and shown["run-events-wrong-draft"][0] == 404


def _photo_review_scenario(port, make_run, corrupt, ws, owner, editor, viewer, outsider):
    """Runs the review/export contract against runs prepared by ``make_run`` (succeeded|failed|processing)."""
    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    view = lambda r: (r["status"], sorted(r["output"]), [(e["decision"], e["comment"], e["actor_id"]) for e in r["events"]])  # noqa: E731
    a_draft, a_run = make_run("succeeded", 1)
    b_draft, b_run = make_run("succeeded", 2)
    c_draft, c_run = make_run("succeeded", 3)
    d_draft, d_run = make_run("failed", 4)
    e_draft, e_run = make_run("processing", 5)
    step("review-pending", lambda: port.review(a_draft, a_run, ws, viewer), view)
    step("review-failed", lambda: port.review(d_draft, d_run, ws, viewer), lambda r: (r["status"], r["events"]))
    step("review-processing", lambda: port.review(e_draft, e_run, ws, viewer), lambda r: (r["status"], r["output"]["asset_id"]))
    step("review-outsider", lambda: port.review(a_draft, a_run, ws, outsider))
    step("review-missing-run", lambda: port.review(a_draft, "phr_missing", ws, viewer))
    step("review-wrong-draft", lambda: port.review(b_draft, a_run, ws, viewer))
    step("review-missing-draft", lambda: port.review("phd_missing", a_run, ws, viewer))
    step("decide-editor", lambda: port.decide(a_draft, a_run, ws, editor, "approved", ""))
    step("decide-viewer", lambda: port.decide(a_draft, a_run, ws, viewer, "approved", ""))
    step("decide-outsider", lambda: port.decide(a_draft, a_run, ws, outsider, "approved", ""))
    step("decide-viewer-missing-draft", lambda: port.decide("phd_missing", a_run, ws, viewer, "approved", ""))
    step("decide-missing-draft", lambda: port.decide("phd_missing", a_run, ws, owner, "approved", ""))
    step("decide-missing-run", lambda: port.decide(a_draft, "phr_missing", ws, owner, "approved", ""))
    step("decide-failed-run", lambda: port.decide(d_draft, d_run, ws, owner, "approved", ""))
    step("decide-processing-run", lambda: port.decide(e_draft, e_run, ws, owner, "approved", ""))
    step("changes-without-comment", lambda: port.decide(a_draft, a_run, ws, owner, "changes_requested", "   "))
    step("reject-without-comment", lambda: port.decide(a_draft, a_run, ws, owner, "rejected", ""))
    step("changes", lambda: port.decide(a_draft, a_run, ws, owner, "changes_requested", "  tone down  "), view)
    step("changes-again", lambda: port.decide(a_draft, a_run, ws, owner, "changes_requested", "again"))
    step("export-not-approved", lambda: port.export_manifest(a_draft, a_run, ws, editor))
    step("approve", lambda: port.decide(a_draft, a_run, ws, owner, "approved", ""), view)
    step("approve-again", lambda: port.decide(a_draft, a_run, ws, owner, "approved", ""))
    step("reject-after-approve", lambda: port.decide(a_draft, a_run, ws, owner, "rejected", "no"))
    step("review-after", lambda: port.review(a_draft, a_run, ws, viewer), view)
    step("export-viewer", lambda: port.export_manifest(a_draft, a_run, ws, viewer))
    step("export-outsider", lambda: port.export_manifest(a_draft, a_run, ws, outsider))
    step("export-missing-run", lambda: port.export_manifest(a_draft, "phr_missing", ws, editor))
    step("export-failed-run", lambda: port.export_manifest(d_draft, d_run, ws, editor))
    step("export-unreviewed", lambda: port.export_manifest(b_draft, b_run, ws, editor))
    exported = step("export", lambda: port.export_manifest(a_draft, a_run, ws, editor),
                    lambda r: (sorted(r), r["manifest"], len(r["manifest_sha256"]), bool(r["exported_at"])))
    import hashlib
    import json
    canonical = json.dumps(exported[1]["manifest"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    out.append(("export-sha-matches-manifest", "ok", hashlib.sha256(canonical.encode()).hexdigest() == exported[1]["manifest_sha256"]))
    step("export-twice", lambda: port.export_manifest(a_draft, a_run, ws, editor), lambda r: len(r["manifest_sha256"]))
    # integrity: bytes change after the run succeeded
    step("approve-c", lambda: port.decide(c_draft, c_run, ws, owner, "approved", ""), lambda r: r["status"])
    corrupt(c_run)
    step("review-corrupt", lambda: port.review(c_draft, c_run, ws, viewer), lambda r: (r["status"], len(r["events"])))
    step("export-corrupt", lambda: port.export_manifest(c_draft, c_run, ws, editor))
    step("decide-corrupt", lambda: port.decide(b_draft, b_run, ws, owner, "approved", ""), lambda r: r["status"])
    corrupt(b_run)
    step("decide-corrupt-2", lambda: port.decide(b_draft, b_run, ws, owner, "rejected", "bad"))
    step("review-corrupt-b", lambda: port.review(b_draft, b_run, ws, viewer), lambda r: r["status"])
    return out


def test_photo_review_export_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import re

    import app.config as config
    from app import photo_engine
    from app.assets import store
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort, SQLitePhotoDraftPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-review.sqlite3")
    store.initialize(); photo_engine.initialize()
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731

    def make_env(bytes_port, ws, owner, editor, claim, complete, fail, create_port):
        src = bytes_port.save(ws, owner, "s.png", _png(5), val(_png(5)))["asset_id"]
        versions = None

        def make_run(kind, n):
            draft = create_port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))
            did = draft["draft_id"]
            c = claim(did, ws, editor, f"review-key-{n}-{uuid.uuid4().hex[:6]}")
            if kind == "processing":
                return did, c["run_id"]
            if kind == "failed":
                fail(c["run_id"], c["claim_token"], editor, "boom")
                return did, c["run_id"]
            content = _png(100 + n)
            asset = bytes_port.save_derived(
                asset_id="ast_photo_" + c["run_id"].removeprefix("phr_"), owner_id=editor, workspace_id=ws,
                source_asset_id=src, source_version_id=draft["input"]["source_version_id"],
                source_checksum_sha256=draft["input"]["source_checksum_sha256"], filename="photo-enhance.png",
                content=content, validated=val(content), run_id=c["run_id"], operation="ENHANCE",
                processor_version="pillow-local-1.0")
            assert complete(c["run_id"], c["claim_token"], editor, asset_id=asset["asset_id"],
                            version_id=asset["version_id"], checksum=asset["checksum_sha256"], quality={}) is True
            return did, c["run_id"]
        return make_run

    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-review", sq[0]); store.add_workspace_member("parity-review", sq[1], "editor")
    store.add_workspace_member("parity-review", sq[2], "viewer")
    wsp = SQLiteWorkspacePort()
    sq_bytes = SQLiteAssetBytesPort(wsp)
    sq_port = SQLitePhotoDraftPort(wsp)
    sq_run = make_env(sq_bytes, "parity-review", sq[0], sq[1], photo_engine.claim_local_run,
                      photo_engine.complete_local_run, photo_engine.fail_local_run, sq_port)

    def corrupt_in(dir_, run_id, bytes_port):
        path = bytes_port.current_file("ast_photo_" + run_id.removeprefix("phr_"))
        path.write_bytes(path.read_bytes() + b"tamper")

    sqlite_out = _photo_review_scenario(sq_port, sq_run, lambda r: corrupt_in(sq_dir, r, sq_bytes), "parity-review", *sq)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_bytes = PostgreSQLAssetBytesPort(repos["assets"])
    pg_port = PostgreSQLPhotoDraftPort(repos["photos"])
    ph = repos["photos"]
    pg_run = make_env(pg_bytes, ws, owner, editor, ph.claim_local_run, ph.complete_local_run, ph.fail_local_run, pg_port)
    pg_out = _photo_review_scenario(pg_port, pg_run, lambda r: corrupt_in(pg_dir, r, pg_bytes), ws, owner, editor, viewer, outsider)

    def norm(row, ws_name):
        text = repr(row).replace(ws_name, "WS")
        for owner_name in (sq[0], owner):
            text = text.replace(owner_name, "OWNER")
        for editor_name in (sq[1], editor):
            text = text.replace(editor_name, "EDITOR")
        text = re.sub(r"(phd_|phr_|ast_photo_|av_photo_|ap_photo_|phrev_|av_)[0-9a-f]+", r"\1X", text)
        text = re.sub(r"\d{4}-\d\d-\d\dT[\d:.+\-]+", "TS", text)
        return re.sub(r"\b[0-9a-f]{64}\b", "H", text)
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:210])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-review") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={norm(m[1], 'parity-review')}\n   pg    ={norm(m[2], ws)}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["review-pending"][1][0] == "pending_review" and shown["review-failed"][1][0] == "failed"
    assert shown["decide-editor"][0] == 403 and shown["decide-outsider"][0] == 404 and shown["decide-viewer-missing-draft"][0] == 403
    assert shown["changes-without-comment"][0] == 409 and shown["approve-again"][0] == 409 and shown["reject-after-approve"][0] == 409
    assert shown["export-not-approved"][0] == 409 and shown["export-viewer"][0] == 403 and shown["export"][0] == "ok"
    assert shown["export-sha-matches-manifest"] == ("ok", True)
    assert shown["review-corrupt"][1][0] == "output_integrity_error" and shown["export-corrupt"][0] == 409
    assert shown["decide-corrupt-2"][0] == 409 and shown["review-after"][1][0] == "approved"


def test_photo_concurrent_review_decisions_are_serialised(repos, tmp_path, monkeypatch):
    import threading

    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort
    from app.repo_errors import RepositoryConflictError

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "race-private")
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, *_ = _workspace(repos)
    bytes_port = PostgreSQLAssetBytesPort(repos["assets"])
    port = PostgreSQLPhotoDraftPort(repos["photos"])
    src = bytes_port.save(ws, owner, "s.png", _png(1), val(_png(1)))["asset_id"]
    draft = port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))
    c = repos["photos"].claim_local_run(draft["draft_id"], ws, editor, "race-review-key")
    out = _png(2)
    asset = bytes_port.save_derived(
        asset_id="ast_photo_" + c["run_id"].removeprefix("phr_"), owner_id=editor, workspace_id=ws, source_asset_id=src,
        source_version_id=draft["input"]["source_version_id"], source_checksum_sha256=draft["input"]["source_checksum_sha256"],
        filename="o.png", content=out, validated=val(out), run_id=c["run_id"], operation="ENHANCE",
        processor_version="pillow-local-1.0")
    assert repos["photos"].complete_local_run(c["run_id"], c["claim_token"], editor, asset_id=asset["asset_id"],
                                              version_id=asset["version_id"], checksum=asset["checksum_sha256"], quality={})
    wins, losses, other = [], [], []

    def work():
        try:
            wins.append(port.decide(draft["draft_id"], c["run_id"], ws, owner, "approved", ""))
        except RepositoryConflictError as exc:
            losses.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            other.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not other and len(wins) == 1 and len(losses) == 7
    assert all("terminal" in m for m in losses)
    assert len(port.review(draft["draft_id"], c["run_id"], ws, owner)["events"]) == 1


def test_derived_photo_output_save_is_idempotent_and_cleans_up_on_failure(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "derived-private")
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, viewer, *_ = _workspace(repos)
    bp = PostgreSQLAssetBytesPort(repos["assets"])
    src_asset = bp.save(ws, owner, "s.png", _png(1), val(_png(1)))
    src_version = repos["assets"].list_asset_versions(src_asset["asset_id"], ws)[0]
    run = "phr_" + uuid.uuid4().hex
    out = _png(9)
    kw = dict(asset_id="ast_photo_" + run.removeprefix("phr_"), owner_id=editor, workspace_id=ws,
              source_asset_id=src_asset["asset_id"], source_version_id=src_version["version_id"],
              source_checksum_sha256=src_version["checksum_sha256"], filename="p.png", content=out,
              validated=val(out), run_id=run, operation="ENHANCE", processor_version="pillow-local-1.0")
    first = bp.save_derived(**kw)
    again = bp.save_derived(**kw)
    assert first["asset_id"] == again["asset_id"] and first["version_id"] == again["version_id"] == "av_photo_" + run[4:]
    assert len(repos["assets"].list_asset_versions(first["asset_id"], ws)) == 1
    files = sorted(p.name for p in (tmp_path / "derived-private").iterdir())
    assert len(files) == 2                                    # source + one derived file, retry added none
    rel = repos["assets"].list_asset_relations(first["asset_id"], ws)
    assert [(r["relation_type"], r["target_asset_id"]) for r in rel if r["source_asset_id"] == first["asset_id"]] == [
        ("derived_from", src_asset["asset_id"])]
    # different bytes under the same deterministic key are refused and change nothing
    with pytest.raises(ValueError):
        bp.save_derived(**{**kw, "content": _png(10), "validated": val(_png(10))})
    assert sorted(p.name for p in (tmp_path / "derived-private").iterdir()) == files
    # a failing metadata transaction (non-member owner) never leaves its new file behind
    run2 = "phr_" + uuid.uuid4().hex
    with pytest.raises(ValueError):
        bp.save_derived(**{**kw, "asset_id": "ast_photo_" + run2[4:], "run_id": run2, "owner_id": "intruder_x",
                           "content": _png(11), "validated": val(_png(11))})
    assert sorted(p.name for p in (tmp_path / "derived-private").iterdir()) == files
    # source version snapshot mismatch is refused
    run3 = "phr_" + uuid.uuid4().hex
    with pytest.raises(ValueError):
        bp.save_derived(**{**kw, "asset_id": "ast_photo_" + run3[4:], "run_id": run3,
                           "source_checksum_sha256": "f" * 64, "content": _png(12), "validated": val(_png(12))})
    assert sorted(p.name for p in (tmp_path / "derived-private").iterdir()) == files


def test_derived_save_refuses_a_leftover_file_with_different_bytes(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort

    root = tmp_path / "leftover-private"
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", root)
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, *_ = _workspace(repos)
    bp = PostgreSQLAssetBytesPort(repos["assets"])
    src = bp.save(ws, owner, "s.png", _png(1), val(_png(1)))
    ver = repos["assets"].list_asset_versions(src["asset_id"], ws)[0]
    run = "phr_" + uuid.uuid4().hex
    key_asset = "ast_photo_" + run[4:]
    (root / f"{key_asset}.png").write_bytes(b"crash leftover")          # file exists, no metadata
    out = _png(7)
    with pytest.raises(ValueError):
        bp.save_derived(asset_id=key_asset, owner_id=editor, workspace_id=ws, source_asset_id=src["asset_id"],
                        source_version_id=ver["version_id"], source_checksum_sha256=ver["checksum_sha256"],
                        filename="p.png", content=out, validated=val(out), run_id=run, operation="ENHANCE",
                        processor_version="pillow-local-1.0")
    assert (root / f"{key_asset}.png").read_bytes() == b"crash leftover"
    assert repos["assets"].get_asset(key_asset, ws) is None


def test_export_is_refused_when_provenance_changes_after_approval(repos, tmp_path, monkeypatch):
    import psycopg

    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort
    from app.repo_errors import RepositoryConflictError

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "snap-private")
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, *_ = _workspace(repos)
    bp = PostgreSQLAssetBytesPort(repos["assets"])
    port = PostgreSQLPhotoDraftPort(repos["photos"])
    src = bp.save(ws, owner, "s.png", _png(1), val(_png(1)))["asset_id"]
    draft = port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))
    c = repos["photos"].claim_local_run(draft["draft_id"], ws, editor, "snap-key")
    out = _png(3)
    asset = bp.save_derived(asset_id="ast_photo_" + c["run_id"][4:], owner_id=editor, workspace_id=ws, source_asset_id=src,
                            source_version_id=draft["input"]["source_version_id"],
                            source_checksum_sha256=draft["input"]["source_checksum_sha256"], filename="o.png",
                            content=out, validated=val(out), run_id=c["run_id"], operation="ENHANCE",
                            processor_version="pillow-local-1.0")
    assert repos["photos"].complete_local_run(c["run_id"], c["claim_token"], editor, asset_id=asset["asset_id"],
                                              version_id=asset["version_id"], checksum=asset["checksum_sha256"], quality={})
    port.decide(draft["draft_id"], c["run_id"], ws, owner, "approved", "")
    assert port.export_manifest(draft["draft_id"], c["run_id"], ws, editor)["manifest_sha256"]
    with psycopg.connect(DSN, autocommit=True) as conn:                  # a newer processing record appears
        conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,event_type,actor_id,created_at)
                        VALUES(%s,%s,%s,1,'asset.photo_processed',%s,now()+interval '1 minute')""",
                     ("ap_late_" + uuid.uuid4().hex, ws, asset["asset_id"], editor))
    with pytest.raises(RepositoryConflictError, match="snapshot no longer matches"):
        port.export_manifest(draft["draft_id"], c["run_id"], ws, editor)


def _photo_process_scenario(port, bytes_port, ws, owner, editor, viewer, outsider, root):
    """process-local through the port; ``_outcome`` also maps LocalProcessingFailed to its 422 body."""
    from app import config
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.photos import LocalProcessingFailed

    out = []
    val = lambda d: validate_image_upload("s.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    files = lambda: len([p for p in root.iterdir() if p.is_file()])  # noqa: E731

    def run(fn):
        try:
            return ("ok", fn())
        except LocalProcessingFailed as exc:
            return (422, {"code": "PHOTO_LOCAL_PROCESSING_FAILED", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            r = _outcome(lambda: (_ for _ in ()).throw(exc))
            return r

    def step(label, fn, show=None):
        r = run(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    def new_source(shade):
        data = _png(shade)
        return bytes_port.save(ws, owner, f"s{shade}.png", data, val(data))["asset_id"]

    def draft(src, op="ENHANCE", **extra):
        return port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation=op, **extra))["draft_id"]

    src = new_source(5)
    d1 = draft(src)
    shape = lambda r: (sorted(r), r["run"]["status"], r["run"]["attempts"], r["run"]["operation"],  # noqa: E731
                       r["run"]["processor_version"], r["run"]["output_checksum_sha256"],
                       sorted(r["output_asset"]), r["output_asset"]["media_type"], r["output_asset"]["checksum_sha256"],
                       r["run"]["quality"]["is_ai_generated"], r["run"]["quality"]["provider_dispatched"], files())
    step("process-viewer", lambda: port.process_local(d1, ws, viewer, "key-aaaaaaaa"))
    step("process-outsider", lambda: port.process_local(d1, ws, outsider, "key-aaaaaaaa"))
    step("process-missing-draft", lambda: port.process_local("phd_missing", ws, editor, "key-aaaaaaaa"))
    step("process-viewer-missing-draft", lambda: port.process_local("phd_missing", ws, viewer, "key-aaaaaaaa"))
    step("unsupported-operation", lambda: port.process_local(draft(src, "BACKGROUND"), ws, editor, "key-bbbbbbbb"))
    step("prompt-refused", lambda: port.process_local(draft(src, prompt="make it pop"), ws, editor, "key-cccccccc"))
    step("reference-refused", lambda: port.process_local(draft(src, reference_asset_ids=[new_source(6)]), ws, editor, "key-dddddddd"))
    step("many-outputs-refused", lambda: port.process_local(draft(src, output_count=2), ws, editor, "key-eeeeeeee"))
    out.append(("files-before-success", "ok", files()))
    first = step("process", lambda: port.process_local(d1, ws, editor, "key-aaaaaaaa"), shape)
    step("process-replay", lambda: port.process_local(d1, ws, editor, "key-aaaaaaaa"),
         lambda r: (r["run"]["status"], r["run"]["attempts"], r["output_asset"]["asset_id"] == first[1]["output_asset"]["asset_id"],
                    r["output_asset"]["version_id"] == first[1]["run"]["output_version_id"], files()))
    step("key-reused-other-draft", lambda: port.process_local(draft(src), ws, editor, "key-aaaaaaaa"))
    step("runs", lambda: port.runs(d1, ws, viewer, 50, 0), lambda r: [(i["status"], i["attempts"], i["review_status"]) for i in r["items"]])
    step("run-events", lambda: port.run_events(d1, first[1]["run"]["run_id"], ws, viewer, 100, 0),
         lambda r: [e["event_type"] for e in r["items"]])
    step("review", lambda: port.review(d1, first[1]["run"]["run_id"], ws, viewer), lambda r: (r["status"], r["output"]["checksum_sha256"]))
    step("approve", lambda: port.decide(d1, first[1]["run"]["run_id"], ws, owner, "approved", ""), lambda r: r["status"])
    step("export", lambda: port.export_manifest(d1, first[1]["run"]["run_id"], ws, editor), lambda r: r["manifest"]["output"]["review_status"])
    step("archived-draft", lambda: (port.archive(d1, ws, editor), port.process_local(d1, ws, editor, "key-ffffffff"))[1])
    # source bytes tampered after the draft snapshot: refused, run recorded as failed, nothing derived is left behind
    src2 = new_source(8)
    d2 = draft(src2)
    path = bytes_port.current_file(src2)
    path.write_bytes(path.read_bytes() + b"tamper")
    before = files()
    bad = step("tampered-source", lambda: port.process_local(d2, ws, editor, "key-gggggggg"))
    out.append(("no-file-for-failed-run", "ok", files() == before))
    step("failed-runs", lambda: port.runs(d2, ws, viewer, 50, 0), lambda r: [(i["status"], i["attempts"], i["error_message"]) for i in r["items"]])
    step("failed-run-events", lambda: port.run_events(d2, port.runs(d2, ws, viewer, 1, 0)["items"][0]["run_id"], ws, viewer, 100, 0),
         lambda r: [e["event_type"] for e in r["items"]])
    step("retry-still-failing", lambda: port.process_local(d2, ws, editor, "key-gggggggg"))
    step("failed-attempts", lambda: port.runs(d2, ws, viewer, 50, 0), lambda r: [(i["status"], i["attempts"]) for i in r["items"]])
    return out


def test_photo_process_local_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import re

    import app.config as config
    from app import photo_engine
    from app.assets import store
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort, SQLitePhotoDraftPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-process.sqlite3")
    store.initialize(); photo_engine.initialize()
    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-process", sq[0]); store.add_workspace_member("parity-process", sq[1], "editor")
    store.add_workspace_member("parity-process", sq[2], "viewer")
    wsp = SQLiteWorkspacePort()
    sqlite_out = _photo_process_scenario(SQLitePhotoDraftPort(wsp), SQLiteAssetBytesPort(wsp), "parity-process", *sq, sq_dir)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_out = _photo_process_scenario(PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"]),
                                     PostgreSQLAssetBytesPort(repos["assets"]), ws, owner, editor, viewer, outsider, pg_dir)

    def norm(row, ws_name):
        text = repr(row).replace(ws_name, "WS")
        text = re.sub(r"(phd_|phr_|ast_photo_|av_photo_|ap_photo_|phrev_|av_)[0-9a-f]+", r"\1X", text)
        return re.sub(r"\d{4}-\d\d-\d\dT[\d:.+\-]+", "TS", text)
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:230])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-process") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={norm(m[1], 'parity-process')}\n   pg    ={norm(m[2], ws)}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["process-viewer"][0] == 403 and shown["process-outsider"][0] == 404 and shown["process-viewer-missing-draft"][0] == 403
    assert shown["unsupported-operation"][0] == 409 and shown["prompt-refused"][0] == 409 and shown["key-reused-other-draft"][0] == 409
    assert shown["process"][1][1:4] == ("succeeded", 1, "ENHANCE") and shown["process-replay"][1][:3] == ("succeeded", 1, True)
    assert shown["process-replay"][1][4] == shown["process"][1][-1]                      # replay wrote no extra file
    assert shown["archived-draft"] == (404, "Photo Draft not found")
    assert shown["tampered-source"][0] == 422 and shown["tampered-source"][1]["code"] == "PHOTO_LOCAL_PROCESSING_FAILED"
    assert shown["no-file-for-failed-run"] == ("ok", True) and shown["failed-attempts"][1] == [("failed", 2)]
    assert shown["review"][1][0] == "pending_review" and shown["export"][1] == "approved"


def test_photo_process_local_failure_injection_leaves_no_orphans_and_retry_succeeds(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort
    from app.ports.photos import LocalProcessingFailed, PostgreSQLPhotoDraftPort

    root = tmp_path / "inject-private"
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", root)
    val = lambda d: validate_image_upload("s.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, *_ = _workspace(repos)
    bp = PostgreSQLAssetBytesPort(repos["assets"])
    port = PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"])
    src = bp.save(ws, owner, "s.png", _png(4), val(_png(4)))["asset_id"]
    did = port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="LIGHTING"))["draft_id"]
    files = lambda: sorted(p.name for p in root.iterdir())  # noqa: E731
    base = files()

    real = repos["assets"].save_derived_image_metadata

    def boom(**kw):
        raise RuntimeError("database went away")
    monkeypatch.setattr(repos["assets"], "save_derived_image_metadata", boom)
    with pytest.raises(LocalProcessingFailed, match="Local image processing failed"):
        port.process_local(did, ws, editor, "inject-key-1")
    assert files() == base                                               # derived file removed again
    run = port.runs(did, ws, editor, 10, 0)["items"][0]
    assert (run["status"], run["attempts"], run["error_message"]) == ("failed", 1, "Local image processing failed")
    assert run["output_asset_id"] is None

    monkeypatch.setattr(repos["assets"], "save_derived_image_metadata", real)   # service recovers; same key retried
    ok = port.process_local(did, ws, editor, "inject-key-1")
    assert ok["run"]["status"] == "succeeded" and ok["run"]["attempts"] == 2 and ok["run"]["run_id"] == run["run_id"]
    assert len(files()) == len(base) + 1
    events = [e["event_type"] for e in port.run_events(did, run["run_id"], ws, editor, 100, 0)["items"]]
    assert events == ["photo.local_run_succeeded", "photo.local_run_retried", "photo.local_run_failed", "photo.local_run_started"]
    assert repos["assets"].get_asset(ok["output_asset"]["asset_id"], ws) is not None


def test_photo_process_local_concurrent_same_key_runs_once(repos, tmp_path, monkeypatch):
    import threading

    import app.config as config
    from app.assets.validation import validate_image_upload
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort
    from app.ports.photos import PostgreSQLPhotoDraftPort
    from app.repo_errors import RepositoryConflictError

    root = tmp_path / "race-process-private"
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", root)
    val = lambda d: validate_image_upload("s.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    ws, owner, editor, *_ = _workspace(repos)
    bp = PostgreSQLAssetBytesPort(repos["assets"])
    port = PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"])
    src = bp.save(ws, owner, "s.png", _png(4), val(_png(4)))["asset_id"]
    did = port.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))["draft_id"]
    ok, conflicts, other = [], [], []

    def work():
        try:
            ok.append(port.process_local(did, ws, editor, "race-process-key"))
        except RepositoryConflictError:
            conflicts.append(1)
        except Exception as exc:  # noqa: BLE001
            other.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not other, other
    runs = port.runs(did, ws, editor, 10, 0)["items"]
    assert len(runs) == 1 and runs[0]["status"] == "succeeded" and runs[0]["attempts"] == 1
    assert len({r["output_asset"]["asset_id"] for r in ok}) == 1 and len(ok) >= 1
    assert len([p for p in root.iterdir()]) == 2                          # source + exactly one derived file


def _lookbook_draft_scenario(port, env, ws, owner, editor, viewer, outsider):
    """env: images (list of 3 usable image ids), foreign, doc, product, variant, archived_product,
    project, archived_project, character; every id is valid in ``ws`` for this backend."""
    from app.lookbook import LookbookDraftInput

    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    def body(title="Spring edit", **extra):
        data = {"workspace_id": ws, "title": title, "product_asset_ids": [env["images"][0]], **extra}
        return LookbookDraftInput(**data)

    shape = lambda d: (sorted(d), d["status"], d["workflow_status"], d["input"]["title"], d["input"]["output_count"])  # noqa: E731
    created = step("create", lambda: port.create(ws, editor, body(project_id=env["project"], character_id=env["character"],
                                                                 person_asset_id=env["images"][1], scene_preset="studio")), shape)
    did = created[1]["draft_id"]
    step("create-catalog", lambda: port.create(ws, owner, body("Catalog", product_asset_ids=[], product_ids=[env["product"]])), shape)
    step("create-variant", lambda: port.create(ws, owner, body("Variant", product_asset_ids=[], product_variant_ids=[env["variant"]])), shape)
    step("create-viewer", lambda: port.create(ws, viewer, body()))
    step("create-outsider", lambda: port.create(ws, outsider, body()))
    step("foreign-image", lambda: port.create(ws, editor, body(product_asset_ids=[env["foreign"]])))
    step("non-image", lambda: port.create(ws, editor, body(product_asset_ids=[env["doc"]])))
    step("archived-product", lambda: port.create(ws, editor, body(product_asset_ids=[], product_ids=[env["archived_product"]])))
    step("missing-product", lambda: port.create(ws, editor, body(product_asset_ids=[], product_ids=["prd_missing_x"])))
    step("missing-variant", lambda: port.create(ws, editor, body(product_asset_ids=[], product_variant_ids=["pvr_missing_x"])))
    step("archived-project", lambda: port.create(ws, editor, body(project_id=env["archived_project"])))
    step("foreign-project", lambda: port.create(ws, editor, body(project_id="prj_missing_xx")))
    step("missing-character", lambda: port.create(ws, editor, body(character_id="chr_missing_xx")))
    step("person-is-catalog-image", lambda: port.create(ws, editor, body(product_asset_ids=[], product_ids=[env["product"]], person_asset_id=env["catalog_image"])))
    step("get-viewer", lambda: port.get(did, ws, viewer), shape)
    step("get-outsider", lambda: port.get(did, ws, outsider))
    step("get-missing", lambda: port.get("lbd_missing", ws, viewer))
    step("list", lambda: port.list(ws, viewer, False, 50, 0), lambda r: (r["total"], r["limit"], sorted(i["input"]["title"] for i in r["items"])))
    step("list-page", lambda: port.list(ws, viewer, False, 1, 1), lambda r: (r["total"], len(r["items"])))
    step("list-outsider", lambda: port.list(ws, outsider, False, 50, 0))
    step("update-viewer", lambda: port.update(did, ws, viewer, body("X")))
    step("update-outsider", lambda: port.update(did, ws, outsider, body("X")))
    step("update-missing", lambda: port.update("lbd_missing", ws, editor, body("X")))
    step("update-viewer-missing", lambda: port.update("lbd_missing", ws, viewer, body("X")))
    step("update-bad-ref", lambda: port.update(did, ws, editor, body("X", product_asset_ids=[env["foreign"]])))
    step("update", lambda: port.update(did, ws, editor, body("Spring edit 2", output_count=3)), lambda d: (d["input"]["title"], d["input"]["output_count"], d["workflow_status"]))
    step("submit-viewer", lambda: port.submit(did, ws, viewer))
    step("submit-outsider", lambda: port.submit(did, ws, outsider))
    step("submit-missing", lambda: port.submit("lbd_missing", ws, editor))
    step("decide-not-in-review", lambda: port.decide(did, ws, owner, "APPROVED", None))
    step("submit", lambda: port.submit(did, ws, editor), lambda d: (d["workflow_status"], d["submitted_by"] == editor, d["reviewed_at"]))
    step("submit-again", lambda: port.submit(did, ws, editor))
    step("update-in-review", lambda: port.update(did, ws, editor, body("Z")))
    step("decide-editor", lambda: port.decide(did, ws, editor, "APPROVED", None))
    step("decide-outsider", lambda: port.decide(did, ws, outsider, "APPROVED", None))
    step("decide-missing", lambda: port.decide("lbd_missing", ws, owner, "APPROVED", None))
    step("decide-viewer-missing", lambda: port.decide("lbd_missing", ws, viewer, "APPROVED", None))
    step("changes-without-comment", lambda: port.decide(did, ws, owner, "CHANGES_REQUESTED", "   "))
    step("changes", lambda: port.decide(did, ws, owner, "CHANGES_REQUESTED", "  fix the pose  "),
         lambda d: (d["workflow_status"], d["review_comment"], d["reviewed_by"] == owner))
    step("manifest-unapproved", lambda: port.plan_manifest(did, ws, viewer))
    step("update-after-changes", lambda: port.update(did, ws, editor, body("Spring edit 3")), lambda d: (d["workflow_status"], d["input"]["title"]))
    step("resubmit", lambda: port.submit(did, ws, editor), lambda d: (d["workflow_status"], d["review_comment"]))
    step("approve", lambda: port.decide(did, ws, owner, "APPROVED", "ok"), lambda d: (d["workflow_status"], d["review_comment"]))
    step("approve-again", lambda: port.decide(did, ws, owner, "APPROVED", None))
    step("update-approved", lambda: port.update(did, ws, editor, body("Q")))
    step("manifest", lambda: port.plan_manifest(did, ws, viewer),
         lambda m: (sorted(m), m["manifest_type"], m["workflow_status"], m["approved_by"] == owner, m["input"]["title"],
                    [(a["role"]) for a in m["referenced_assets"]]))
    step("manifest-outsider", lambda: port.plan_manifest(did, ws, outsider))
    step("manifest-missing", lambda: port.plan_manifest("lbd_missing", ws, viewer))
    step("archive-viewer", lambda: port.archive(did, ws, viewer))
    step("archive-outsider", lambda: port.archive(did, ws, outsider))
    step("archive-missing", lambda: port.archive("lbd_missing", ws, editor))
    step("archive", lambda: port.archive(did, ws, editor), lambda d: (d["status"], bool(d["archived_at"])))
    step("archive-again", lambda: port.archive(did, ws, editor))
    step("update-archived", lambda: port.update(did, ws, editor, body("R")))
    step("submit-archived", lambda: port.submit(did, ws, editor))
    step("manifest-archived", lambda: port.plan_manifest(did, ws, viewer))
    step("get-archived", lambda: port.get(did, ws, viewer), lambda d: (d["status"], d["workflow_status"]))
    step("list-active", lambda: port.list(ws, viewer, False, 50, 0), lambda r: (r["total"], sorted(i["input"]["title"] for i in r["items"])))
    step("list-archived", lambda: port.list(ws, viewer, True, 50, 0), lambda r: r["total"])
    step("events", lambda: port.events(did, ws, viewer, 100, 0),
         lambda r: (r["total"], r["limit"], [e["event_type"] for e in r["items"]]))
    step("events-detail", lambda: port.events(did, ws, viewer, 100, 0),
         lambda r: [sorted(e["details"].items()) for e in r["items"] if e["event_type"] in {"lookbook.draft_created", "lookbook.changes_requested", "lookbook.submitted_for_review"}])  # JSONB does not keep key order
    step("events-page", lambda: port.events(did, ws, viewer, 2, 1), lambda r: (r["total"], len(r["items"])))
    step("events-max-limit", lambda: port.events(did, ws, viewer, 500, 0), lambda r: r["total"])
    step("events-outsider", lambda: port.events(did, ws, outsider, 100, 0))
    step("events-missing", lambda: port.events("lbd_missing", ws, viewer, 100, 0))
    return out


def test_lookbook_draft_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import re

    import app.config as config
    from app import lookbook
    from app.assets import store
    from app.assets.validation import validate_image_upload
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.characters import PostgreSQLCharacterPort, SQLiteCharacterPort
    from app.ports.lookbooks import PostgreSQLLookbookDraftPort, SQLiteLookbookDraftPort
    from app.ports.products import PostgreSQLProductPort, SQLiteProductPort
    from app.ports.projects import PostgreSQLProjectPort, SQLiteProjectPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-lookbook.sqlite3")
    store.initialize(); lookbook.initialize()
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731

    def seed(ws, owner, editor, other_ws, other_owner, bytes_port, products, projects, characters, doc_id):
        img = lambda w, o, shade: bytes_port.save(w, o, f"i{shade}.png", _png(shade), val(_png(shade)))["asset_id"]  # noqa: E731
        images = [img(ws, owner, 11), img(ws, owner, 12), img(ws, owner, 13)]
        catalog_image = img(ws, owner, 14)
        fields = lambda sku, imgs: {"workspace_id": ws, "sku": sku, "name": "Dress", "description": "d", "category": "apparel", "image_asset_ids": imgs}  # noqa: E731
        product = products.create(editor, fields("LB-1", [catalog_image]))["product_id"]
        variant = products.create_variant(product, editor, {"workspace_id": ws, "sku": "LB-1-M", "option_values": {"size": "M"}, "image_asset_ids": []})["variant_id"]
        archived = products.create(editor, fields("LB-3", [images[2]]))["product_id"]
        products.archive(ws, archived, editor)
        pf = {"name": "Spring", "project_type": "general", "description": "d", "external_reference": None}
        project = projects.create(ws, editor, pf)["project_id"]
        arch_project = projects.create(ws, editor, pf)["project_id"]
        projects.update(arch_project, editor, {**pf, "status": "ARCHIVED"})
        character = characters.create(ws, editor, {"identity": {"name": "Mina"}, "outfits": [{"id": "o1", "name": "Casual"}], "active_outfit_id": "o1"}, [])["character_id"]
        return {"images": images, "catalog_image": catalog_image, "foreign": img(other_ws, other_owner, 15), "doc": doc_id,
                "product": product, "variant": variant, "archived_product": archived,
                "project": project, "archived_project": arch_project, "character": character}

    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-lb", sq[0]); store.add_workspace_member("parity-lb", sq[1], "editor")
    store.add_workspace_member("parity-lb", sq[2], "viewer"); store.create_workspace("parity-lb-2", "owner2_sq")
    wsp = SQLiteWorkspacePort()
    sq_env = seed("parity-lb", sq[0], sq[1], "parity-lb-2", "owner2_sq", SQLiteAssetBytesPort(wsp), SQLiteProductPort(wsp),
                  SQLiteProjectPort(wsp), SQLiteCharacterPort(wsp), _non_image_asset_sqlite("parity-lb", sq[0]))
    sqlite_out = _lookbook_draft_scenario(SQLiteLookbookDraftPort(wsp), sq_env, "parity-lb", *sq)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    ws2, owner2, *_ = _workspace(repos)
    doc = "ast_" + uuid.uuid4().hex
    repos["assets"].register_asset(asset_id=doc, owner_id=owner, workspace_id=ws, original_filename="d.pdf",
                                   storage_key=f"{ws}/{doc}.pdf", media_type="application/pdf", size_bytes=10, checksum_sha256="b" * 64)
    pg_env = seed(ws, owner, editor, ws2, owner2, PostgreSQLAssetBytesPort(repos["assets"]), PostgreSQLProductPort(repos["products"]),
                  PostgreSQLProjectPort(repos["projects"]), PostgreSQLCharacterPort(repos["characters"]), doc)
    pg_out = _lookbook_draft_scenario(PostgreSQLLookbookDraftPort(repos["lookbooks"]), pg_env, ws, owner, editor, viewer, outsider)

    def norm(row, ws_name):
        text = repr(row).replace(ws_name, "WS")
        text = re.sub(r"\b[a-z]{2,4}_[0-9a-f]{12,}\b", "ID", text)
        return re.sub(r"\d{4}-\d\d-\d\dT[\d:.+\-]+", "TS", text)
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:210])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-lb") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={norm(m[1], 'parity-lb')}\n   pg    ={norm(m[2], ws)}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["create"][0] == "ok" and shown["create-viewer"][0] == 403 and shown["create-outsider"][0] == 404
    assert shown["non-image"][0] == 422 and shown["non-image"][1]["code"] == "LOOKBOOK_IMAGE_ASSET_REQUIRED"
    assert shown["archived-project"][0] == 409 and shown["decide-editor"][0] == 403 and shown["approve-again"][0] == 409
    assert shown["manifest-unapproved"][0] == 409 and shown["manifest"][0] == "ok" and shown["manifest-archived"][0] == 404
    assert shown["update-viewer-missing"][0] == 403 and shown["decide-viewer-missing"][0] == 403
    assert shown["events"][1][2][0] == "lookbook.draft_archived" and shown["events-max-limit"][0] == "ok"


def test_lookbook_concurrent_review_decisions_are_serialised(repos):
    import threading

    from app.repo_errors import RepositoryConflictError
    ws, owner, editor, *_ = _workspace(repos)
    lb = repos["lookbooks"]
    img = _image(repos, ws, owner, "lb-race")
    did = lb.create_draft(ws, editor, {"title": "Race", "product_asset_ids": [img], "output_count": 1})["draft_id"]
    lb.submit_for_review(did, ws, editor)
    wins, losses, other = [], [], []

    def work():
        try:
            wins.append(lb.decide_review(did, ws, owner, "APPROVED", "ok"))
        except RepositoryConflictError:
            losses.append(1)
        except Exception as exc:  # noqa: BLE001
            other.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not other, other
    assert len(wins) == 1 and len(losses) == 7
    approvals = [e for e in lb.list_events(did, ws, owner)["items"] if e["event_type"] == "lookbook.approved"]
    assert len(approvals) == 1


def _lookbook_assembly_scenario(lb, mk_run, mk_draft, corrupt, env, ws, owner, editor, viewer, outsider):
    """mk_run(approve) -> run_id; mk_draft(approved) -> lookbook draft id; corrupt(run_id) tampers the output bytes."""
    from app.lookbook import LookbookOutputAttachInput

    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    def attach(d, run, order, user=None, **extra):
        return lambda: lb.attach_output(d, ws, user or editor, LookbookOutputAttachInput(photo_run_id=run, page_order=order, **extra))

    item = lambda r: (sorted(k for k in r if k not in {"output_item_id", "created_at"}), r["page_order"], r["product_sku"],  # noqa: E731
                      r["variant_sku"], r["variant_options"], r["caption"])
    review = lambda r: (r["status"], r["planning_status"], r["output_count"], [(e["decision"], e["comment"], e["output_count"]) for e in r["events"]])  # noqa: E731
    runs = [mk_run(True) for _ in range(4)]
    unapproved = mk_run(False)
    d = mk_draft(True)
    draft_unapproved = mk_draft(False)
    empty_d = mk_draft(True)
    step("outputs-empty", lambda: lb.outputs(d, ws, viewer), lambda r: (r["total"], r["items"]))
    step("outputs-outsider", lambda: lb.outputs(d, ws, outsider))
    step("outputs-missing", lambda: lb.outputs("lbd_missing", ws, viewer))
    step("attach-viewer", attach(d, runs[0], 1, viewer))
    step("attach-outsider", attach(d, runs[0], 1, outsider))
    step("attach-missing-draft", attach("lbd_missing", runs[0], 1))
    step("attach-viewer-missing", attach("lbd_missing", runs[0], 1, viewer))
    step("attach-unapproved-photo", attach(d, unapproved, 1))
    tampered = mk_run(True)
    corrupt(tampered)
    step("attach-tampered-output", attach(d, tampered, 1))
    step("attach-unknown-run", attach(d, "phr_missing_run", 1))
    step("attach-planning-unapproved", attach(draft_unapproved, runs[0], 1))
    step("attach-unapproved-photo-and-planning", attach(draft_unapproved, unapproved, 1))
    step("attach", attach(d, runs[0], 1, caption="Look 1"), item)
    step("attach-same-run", attach(d, runs[0], 2))
    step("attach-same-page", attach(d, runs[1], 1))
    step("attach-product-not-in-plan", attach(d, runs[1], 2, product_id="prd_" + "0" * 20))
    step("attach-variant-not-active", attach(d, runs[1], 2, product_variant_id="pvr_" + "0" * 20))
    step("attach-variant-wrong-product", attach(d, runs[1], 2, product_variant_id=env["variant"], product_id="prd_" + "1" * 20))
    step("attach-product", attach(d, runs[1], 2, product_id=env["product"]), item)
    step("attach-variant", attach(d, runs[2], 3, product_variant_id=env["variant"]), item)
    step("outputs", lambda: lb.outputs(d, ws, viewer), lambda r: (r["total"], [(i["page_order"], i["product_sku"], i["variant_sku"]) for i in r["items"]]))
    step("assembly-empty", lambda: lb.assembly_review(empty_d, ws, viewer), review)
    step("assembly-pending", lambda: lb.assembly_review(d, ws, viewer), review)
    step("assembly-outsider", lambda: lb.assembly_review(d, ws, outsider))
    step("assembly-missing", lambda: lb.assembly_review("lbd_missing", ws, viewer))
    step("submit-viewer", lambda: lb.submit_assembly(d, ws, viewer))
    step("submit-outsider", lambda: lb.submit_assembly(d, ws, outsider))
    step("submit-missing", lambda: lb.submit_assembly("lbd_missing", ws, editor))
    step("submit-no-outputs", lambda: lb.submit_assembly(empty_d, ws, editor))
    step("submit-planning-unapproved", lambda: lb.submit_assembly(draft_unapproved, ws, editor))
    step("decide-before-submit", lambda: lb.decide_assembly(d, ws, owner, "approved", ""))
    step("manifest-before-review", lambda: lb.output_manifest(d, ws, editor))
    step("submit", lambda: lb.submit_assembly(d, ws, editor), review)
    step("submit-again", lambda: lb.submit_assembly(d, ws, editor))
    step("attach-after-freeze", attach(d, runs[3], 4))
    step("decide-editor", lambda: lb.decide_assembly(d, ws, editor, "approved", ""))
    step("decide-outsider", lambda: lb.decide_assembly(d, ws, outsider, "approved", ""))
    step("decide-viewer-missing", lambda: lb.decide_assembly("lbd_missing", ws, viewer, "approved", ""))
    step("decide-missing", lambda: lb.decide_assembly("lbd_missing", ws, owner, "approved", ""))
    step("reject-without-comment", lambda: lb.decide_assembly(d, ws, owner, "rejected", "  "))
    step("reject", lambda: lb.decide_assembly(d, ws, owner, "rejected", " not this order "), review)
    step("decide-after-reject", lambda: lb.decide_assembly(d, ws, owner, "approved", ""))
    step("manifest-after-reject", lambda: lb.output_manifest(d, ws, editor))
    # a second lookbook is approved and exported
    r2 = [mk_run(True), mk_run(True)]
    d2 = mk_draft(True)
    step("d2-attach-1", attach(d2, r2[0], 1, product_id=env["product"]), item)
    step("d2-attach-2", attach(d2, r2[1], 2))
    step("d2-submit", lambda: lb.submit_assembly(d2, ws, editor), review)
    step("d2-approve", lambda: lb.decide_assembly(d2, ws, owner, "approved", "great"), review)
    step("d2-approve-again", lambda: lb.decide_assembly(d2, ws, owner, "approved", ""))
    step("d2-review", lambda: lb.assembly_review(d2, ws, viewer), review)
    step("manifest-viewer", lambda: lb.output_manifest(d2, ws, viewer))
    step("manifest-outsider", lambda: lb.output_manifest(d2, ws, outsider))
    step("manifest-missing", lambda: lb.output_manifest("lbd_missing", ws, editor))
    exported = step("manifest", lambda: lb.output_manifest(d2, ws, editor),
                    lambda r: (sorted(r), r["manifest"]["manifest_type"], r["manifest"]["output_assembly_approved"],
                               [(o["page_order"], o["product_sku"], o["photo_review_status"], sorted(o)) for o in r["manifest"]["outputs"]],
                               sorted(r["manifest"]), len(r["manifest_sha256"])))
    import hashlib
    import json
    canonical = json.dumps(exported[1]["manifest"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    out.append(("manifest-sha-matches", "ok", hashlib.sha256(canonical.encode()).hexdigest() == exported[1]["manifest_sha256"]))
    corrupt(r2[1])
    step("d2-review-corrupt", lambda: lb.assembly_review(d2, ws, viewer), lambda r: r["status"])
    step("manifest-corrupt", lambda: lb.output_manifest(d2, ws, editor))
    return out


def test_lookbook_outputs_and_assembly_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import re

    import app.config as config
    from app import lookbook, photo_engine
    from app.assets import store
    from app.assets.validation import validate_image_upload
    from app.lookbook import LookbookDraftInput
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.lookbooks import PostgreSQLLookbookDraftPort, SQLiteLookbookDraftPort
    from app.ports.photos import PostgreSQLPhotoDraftPort, SQLitePhotoDraftPort
    from app.ports.products import PostgreSQLProductPort, SQLiteProductPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-assembly.sqlite3")
    store.initialize(); photo_engine.initialize(); lookbook.initialize()
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731

    def build(ws, owner, editor, bytes_port, products, photos, lookbooks):
        src = bytes_port.save(ws, owner, "s.png", _png(21), val(_png(21)))["asset_id"]
        cat = bytes_port.save(ws, owner, "c.png", _png(22), val(_png(22)))["asset_id"]
        product = products.create(editor, {"workspace_id": ws, "sku": "AS-1", "name": "Dress", "description": "d",
                                           "category": "apparel", "image_asset_ids": [cat]})["product_id"]
        variant = products.create_variant(product, editor, {"workspace_id": ws, "sku": "AS-1-M", "option_values": {"size": "M"},
                                                            "image_asset_ids": []})["variant_id"]
        counter = {"n": 0}

        def mk_run(approve):
            counter["n"] += 1
            did = photos.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))["draft_id"]
            res = photos.process_local(did, ws, editor, f"assembly-key-{counter['n']}-{uuid.uuid4().hex[:6]}")
            if approve:
                photos.decide(did, res["run"]["run_id"], ws, owner, "approved", "")
            mk_run.draft[res["run"]["run_id"]] = (did, res["output_asset"]["asset_id"])
            return res["run"]["run_id"]
        mk_run.draft = {}

        def mk_draft(approved):
            d = lookbooks.create(ws, editor, LookbookDraftInput(workspace_id=ws, title="Assembly", product_ids=[product]))["draft_id"]
            if approved:
                lookbooks.submit(d, ws, editor)
                lookbooks.decide(d, ws, owner, "APPROVED", None)
            return d

        def corrupt(run_id):
            path = bytes_port.current_file(mk_run.draft[run_id][1])
            path.write_bytes(path.read_bytes() + b"tamper")
        return mk_run, mk_draft, corrupt, {"product": product, "variant": variant}

    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-asm", sq[0]); store.add_workspace_member("parity-asm", sq[1], "editor")
    store.add_workspace_member("parity-asm", sq[2], "viewer")
    wsp = SQLiteWorkspacePort()
    sq_lb = SQLiteLookbookDraftPort(wsp)
    mk_run, mk_draft, corrupt, env = build("parity-asm", sq[0], sq[1], SQLiteAssetBytesPort(wsp), SQLiteProductPort(wsp),
                                           SQLitePhotoDraftPort(wsp), sq_lb)
    sqlite_out = _lookbook_assembly_scenario(sq_lb, mk_run, mk_draft, corrupt, env, "parity-asm", *sq)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_lb = PostgreSQLLookbookDraftPort(repos["lookbooks"])
    mk_run, mk_draft, corrupt, env = build(ws, owner, editor, PostgreSQLAssetBytesPort(repos["assets"]), PostgreSQLProductPort(repos["products"]),
                                           PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"]), pg_lb)
    pg_out = _lookbook_assembly_scenario(pg_lb, mk_run, mk_draft, corrupt, env, ws, owner, editor, viewer, outsider)

    # PG-only: the order of an already-submitted/approved sequence is re-checked against its snapshot digest
    # (reachable only through direct SQL, so it cannot be a parity step)
    import psycopg
    from app.lookbook import LookbookOutputAttachInput as _Attach
    from app.repositories.postgres_lookbooks import LookbookStateError as _LSE
    for approve_first in (False, True):
        dd = mk_draft(True)
        rr = mk_run(True)
        pg_lb.attach_output(dd, ws, editor, _Attach(photo_run_id=rr, page_order=1))
        pg_lb.submit_assembly(dd, ws, editor)
        if approve_first:
            pg_lb.decide_assembly(dd, ws, owner, "approved", "")
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("ALTER TABLE lookbook_output_assets DISABLE TRIGGER trg_lookbook_outputs_immutable")
            conn.execute("UPDATE lookbook_output_assets SET page_order=7 WHERE draft_id=%s", (dd,))
            conn.execute("ALTER TABLE lookbook_output_assets ENABLE TRIGGER trg_lookbook_outputs_immutable")
        with pytest.raises(Exception) as ei:
            if approve_first:
                pg_lb.output_manifest(dd, ws, editor)
            else:
                pg_lb.decide_assembly(dd, ws, owner, "approved", "")
        assert isinstance(ei.value, _LSE), repr(ei.value)

    def norm(row, ws_name):
        text = repr(row).replace(ws_name, "WS")
        text = re.sub(r"\b[a-z]{2,4}_[0-9a-f]{12,}\b", "ID", text)
        text = re.sub(r"\d{4}-\d\d-\d\dT[\d:.+\-]+", "TS", text)
        return re.sub(r"\b[0-9a-f]{64}\b", "H", text)
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:200])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-asm") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={norm(m[1], 'parity-asm')}\n   pg    ={norm(m[2], ws)}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["attach"][0] == "ok" and shown["attach-viewer"][0] == 403 and shown["attach-outsider"][0] == 404
    assert shown["attach-unapproved-photo"][0] == 409 and shown["attach-same-run"][0] == 409 and shown["attach-same-page"][0] == 409
    assert shown["attach-after-freeze"][0] == 409 and shown["decide-editor"][0] == 403 and shown["decide-after-reject"][0] == 409
    assert shown["submit"][1][0] == "in_review" and shown["reject"][1][0] == "rejected" and shown["d2-approve"][1][0] == "approved"
    assert shown["manifest"][0] == "ok" and shown["manifest-after-reject"][0] == 409 and shown["manifest-sha-matches"] == ("ok", True)
    assert shown["d2-review-corrupt"][1] == "integrity_error" and shown["manifest-corrupt"][0] == 409


def test_lookbook_assembly_concurrent_attach_and_decide_are_serialised(repos, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    import threading

    from app.repo_errors import RepositoryConflictError
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    lb = _VerifiedLookbooks(repos["lookbooks"])
    did = lb.create_draft(ws, editor, {"title": "Race", "product_ids": [prod]})["draft_id"]
    lb.submit_for_review(did, ws, editor); lb.decide_review(did, ws, owner, "APPROVED")
    runs = [_real_approved_photo_output(repos, ws, owner, editor, f"c{i}" + uuid.uuid4().hex[:6]) for i in range(6)]

    def race(fn, n):
        wins, losses, other = [], [], []

        def work(i):
            try:
                wins.append(fn(i))
            except RepositoryConflictError:
                losses.append(i)
            except Exception as exc:  # noqa: BLE001
                other.append(repr(exc))
        ts = [threading.Thread(target=work, args=(i,)) for i in range(n)]
        [t.start() for t in ts]; [t.join() for t in ts]
        return wins, losses, other

    # six different runs competing for the same page: exactly one wins
    wins, losses, other = race(lambda i: (lb.attach_approved_photo_output(did, ws, editor, photo_run_id=runs[i], page_order=1), runs[i])[1], 6)
    assert not other, other
    assert len(wins) == 1 and len(losses) == 5
    assert lb.list_outputs(did, ws, viewer)["total"] == 1
    # one run attached concurrently to different pages: exactly one wins.
    # Use a run that did NOT win above (any run may win the first race; an already attached run loses every attempt).
    spare = next(r for r in runs if r != wins[0])
    wins, losses, other = race(lambda i: lb.attach_approved_photo_output(did, ws, editor, photo_run_id=spare, page_order=10 + i), 6)
    assert not other, other
    assert len(wins) == 1 and len(losses) == 5
    assert lb.list_outputs(did, ws, viewer)["total"] == 2
    # concurrent submit: exactly one submission event
    wins, losses, other = race(lambda i: lb.submit_assembly(did, ws, editor), 6)
    assert not other, other
    assert len(wins) == 1 and len(losses) == 5
    # concurrent approve/reject: exactly one decision
    wins, losses, other = race(lambda i: lb.decide_assembly(did, ws, owner, "approved" if i % 2 else "rejected", "c"), 6)
    assert not other, other
    assert len(wins) == 1 and len(losses) == 5
    events = lb.get_assembly_review(did, ws, viewer)["events"]
    assert len([e for e in events if e["decision"] == "submitted"]) == 1
    assert len([e for e in events if e["decision"] in ("approved", "rejected")]) == 1


def _lookbook_package_scenario(lb, mk_run, mk_draft, ws, owner, editor, viewer, outsider, storage_dir):
    import asyncio
    import io
    import json
    import re
    import time
    import zipfile
    from urllib.parse import parse_qs, urlparse

    from app.lookbook import LookbookOutputAttachInput

    out = []

    def step(label, fn, show=None):
        r = _outcome(fn)
        out.append((label, r[0], show(r[1]) if r[0] == "ok" and show else (None if r[0] == "ok" else r[1])))
        return r

    def attach(d, run, order):
        return lb.attach_output(d, ws, editor, LookbookOutputAttachInput(photo_run_id=run, page_order=order))

    def body(resp):
        async def collect():
            return b"".join([c async for c in resp.body_iterator])
        return asyncio.run(collect())

    def zip_view(data):
        z = zipfile.ZipFile(io.BytesIO(data))
        manifest = json.loads(z.read("manifest.json"))
        for key in ("planning_approved_at", "output_assembly_reviewed_at"):
            manifest[key] = "TS"
        for o in manifest["outputs"]:
            o["asset_id"] = o["asset_version_id"] = "ID"
            o["file"] = re.sub(r"_av_[a-z]+_[0-9a-f]{12,}", "_ID", o["file"])
        manifest["output_assembly_approved_by"] = manifest["planning_approved_by"] = "U"
        manifest["draft_id"] = manifest["workspace_id"] = "X"
        return (sorted(re.sub(r"_av_[a-z]+_[0-9a-f]{12,}", "_ID", n) for n in z.namelist()), manifest)

    d_plan = mk_draft(False)
    d_empty = mk_draft(True)
    d_unreviewed = mk_draft(True)
    d = mk_draft(True)
    runs = [mk_run(True) for _ in range(2)]
    attach(d_unreviewed, mk_run(True), 1)
    attach(d, runs[0], 1)
    attach(d, runs[1], 2)
    step("list-empty", lambda: lb.package_exports(d, ws, viewer), lambda r: r)
    step("list-outsider", lambda: lb.package_exports(d, ws, outsider))
    step("list-missing", lambda: lb.package_exports("lbd_missing", ws, viewer))
    step("create-viewer", lambda: lb.create_package(d, ws, viewer))
    step("create-outsider", lambda: lb.create_package(d, ws, outsider))
    step("create-missing", lambda: lb.create_package("lbd_missing", ws, editor))
    step("create-viewer-missing", lambda: lb.create_package("lbd_missing", ws, viewer))
    step("create-plan-unapproved", lambda: lb.create_package(d_plan, ws, editor))
    step("create-no-outputs", lambda: lb.create_package(d_empty, ws, editor))
    step("create-assembly-unreviewed", lambda: lb.create_package(d_unreviewed, ws, editor))
    lb.submit_assembly(d, ws, editor)
    step("create-assembly-in-review", lambda: lb.create_package(d, ws, editor))
    lb.decide_assembly(d, ws, owner, "approved", "ok")
    made = step("create", lambda: lb.create_package(d, ws, editor),
                lambda r: (sorted(r), r["output_count"], r["internal_use_only"], r["publication_authorized"],
                           r["commercial_rights_verified"], len(r["package_sha256"]), len(r["manifest_sha256"]),
                           r["download_url"].split("?")[0].rsplit("/", 2)[0]))
    first = made[1]
    step("list-after-one", lambda: lb.package_exports(d, ws, viewer),
         lambda r: (r["total"], [(sorted(i), i["status"], i["output_count"]) for i in r["items"]]))
    time.sleep(1.1)
    second = step("create-second", lambda: lb.create_package(d, ws, editor), lambda r: r["output_count"])[1]
    step("list-after-two", lambda: lb.package_exports(d, ws, viewer),
         lambda r: (r["total"], [i["status"] for i in r["items"]]))
    out.append(("list-order-newest-first", "ok", None))
    listed = lb.package_exports(d, ws, viewer)["items"]
    out[-1] = ("list-order-newest-first", "ok", [i["export_id"] for i in listed] == [second["export_id"], first["export_id"]])

    def parts(result):
        q = parse_qs(urlparse(result["download_url"]).query)
        return result["export_id"], int(q["expires"][0]), q["signature"][0]
    eid, exp, sig = parts(first)
    resp = {}

    def dl(user, e=eid, x=exp, s=sig):
        return lambda: lb.download_package(e, x, s, user)
    r = step("download-viewer", dl(viewer), lambda r: (r.status_code, r.media_type))
    data = body(r[1]) if r[0] == "ok" else b""
    out.append(("download-zip", "ok", zip_view(data)))
    out.append(("download-matches-recorded-hash", "ok",
                __import__("hashlib").sha256(data).hexdigest() == first["package_sha256"]))
    step("download-outsider", dl(outsider))
    step("download-bad-signature", dl(viewer, s="0" * 64))
    step("download-expired-url", dl(viewer, x=int(time.time()) - 5,
                                    s=__import__("app.lookbook", fromlist=["x"])._lookbook_package_signature(eid, int(time.time()) - 5)))
    step("download-far-future-url", dl(viewer, x=int(time.time()) + 5000,
                                       s=__import__("app.lookbook", fromlist=["x"])._lookbook_package_signature(eid, int(time.time()) + 5000)))
    from app.lookbook import _lookbook_package_signature as sign
    step("download-unknown-export", dl(viewer, e="lbx_" + "0" * 32, s=sign("lbx_" + "0" * 32, exp), x=exp))
    path = storage_dir / "lookbook_exports" / f"{second['export_id']}.zip"
    e2, x2, s2 = parts(second)
    original = path.read_bytes()
    path.write_bytes(original + b"x")
    step("download-tampered", lambda: lb.download_package(e2, x2, s2, viewer))
    step("list-tampered-still-available", lambda: lb.package_exports(d, ws, viewer), lambda r: [i["status"] for i in r["items"]])
    path.write_bytes(original)
    path.unlink()
    step("download-file-missing", lambda: lb.download_package(e2, x2, s2, viewer))
    step("list-file-missing", lambda: lb.package_exports(d, ws, viewer), lambda r: [i["status"] for i in r["items"]])
    return out


def test_lookbook_package_export_port_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import re

    import app.config as config
    from app import lookbook, photo_engine
    from app.assets import store
    from app.assets.validation import validate_image_upload
    from app.lookbook import LookbookDraftInput
    from app.photo_engine import PhotoDraftInput
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.lookbooks import PostgreSQLLookbookDraftPort, SQLiteLookbookDraftPort
    from app.ports.photos import PostgreSQLPhotoDraftPort, SQLitePhotoDraftPort
    from app.ports.products import PostgreSQLProductPort, SQLiteProductPort
    from app.ports.workspace import SQLiteWorkspacePort

    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-package.sqlite3")
    store.initialize(); photo_engine.initialize(); lookbook.initialize()
    val = lambda d: validate_image_upload("o.png", d, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731

    def build(ws, owner, editor, bytes_port, products, photos, lookbooks):
        src = bytes_port.save(ws, owner, "s.png", _png(41), val(_png(41)))["asset_id"]
        cat = bytes_port.save(ws, owner, "c.png", _png(42), val(_png(42)))["asset_id"]
        product = products.create(editor, {"workspace_id": ws, "sku": "PK-1", "name": "Coat", "description": "d",
                                           "category": "apparel", "image_asset_ids": [cat]})["product_id"]
        counter = {"n": 0}

        def mk_run(approve):
            counter["n"] += 1
            did = photos.create(ws, editor, PhotoDraftInput(workspace_id=ws, source_asset_id=src, operation="ENHANCE"))["draft_id"]
            res = photos.process_local(did, ws, editor, f"package-key-{counter['n']}-{uuid.uuid4().hex[:6]}")
            if approve:
                photos.decide(did, res["run"]["run_id"], ws, owner, "approved", "")
            return res["run"]["run_id"]

        def mk_draft(approved):
            d = lookbooks.create(ws, editor, LookbookDraftInput(workspace_id=ws, title="Package", product_ids=[product]))["draft_id"]
            if approved:
                lookbooks.submit(d, ws, editor)
                lookbooks.decide(d, ws, owner, "APPROVED", None)
            return d
        return mk_run, mk_draft

    sq = [f"{n}_sq" for n in ("owner", "editor", "viewer", "outsider")]
    store.create_workspace("parity-pkg", sq[0]); store.add_workspace_member("parity-pkg", sq[1], "editor")
    store.add_workspace_member("parity-pkg", sq[2], "viewer")
    wsp = SQLiteWorkspacePort()
    sq_lb = SQLiteLookbookDraftPort(wsp)
    mk_run, mk_draft = build("parity-pkg", sq[0], sq[1], SQLiteAssetBytesPort(wsp), SQLiteProductPort(wsp), SQLitePhotoDraftPort(wsp), sq_lb)
    sqlite_out = _lookbook_package_scenario(sq_lb, mk_run, mk_draft, "parity-pkg", *sq, sq_dir)

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, viewer, outsider, _ = _workspace(repos)
    pg_lb = PostgreSQLLookbookDraftPort(repos["lookbooks"])
    mk_run, mk_draft = build(ws, owner, editor, PostgreSQLAssetBytesPort(repos["assets"]), PostgreSQLProductPort(repos["products"]),
                             PostgreSQLPhotoDraftPort(repos["photos"], repos["assets"]), pg_lb)
    pg_out = _lookbook_package_scenario(pg_lb, mk_run, mk_draft, ws, owner, editor, viewer, outsider, pg_dir)

    # PG-only: the approved sequence is re-verified in the audit transaction. A change made while the file is being
    # written (simulated with direct SQL) must be refused, leave no audit row and remove the file.
    import psycopg
    import app.lookbook as lookbook_module
    from app.lookbook import LookbookOutputAttachInput as _Attach
    from app.repo_errors import RepositoryConflictError as _Conflict
    dd = mk_draft(True)
    pg_lb.attach_output(dd, ws, editor, _Attach(photo_run_id=mk_run(True), page_order=1))
    pg_lb.submit_assembly(dd, ws, editor)
    pg_lb.decide_assembly(dd, ws, owner, "approved", "")
    real_write = lookbook_module.write_lookbook_package

    def tampering_write(*a, **kw):
        result = real_write(*a, **kw)
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("ALTER TABLE lookbook_output_assets DISABLE TRIGGER trg_lookbook_outputs_immutable")
            conn.execute("UPDATE lookbook_output_assets SET page_order=9 WHERE draft_id=%s", (dd,))
            conn.execute("ALTER TABLE lookbook_output_assets ENABLE TRIGGER trg_lookbook_outputs_immutable")
        return result
    monkeypatch.setattr(lookbook_module, "write_lookbook_package", tampering_write)
    export_dir = pg_dir / "lookbook_exports"
    before = sorted(export_dir.glob("*.zip"))
    with pytest.raises(_Conflict) as raised:
        pg_lb.create_package(dd, ws, editor)
    assert "changed before package audit" in str(raised.value)
    assert sorted(export_dir.glob("*.zip")) == before and not list(export_dir.glob(".*.tmp"))
    monkeypatch.setattr(lookbook_module, "write_lookbook_package", real_write)
    # page limit (shrunk so the test does not need 101 Photo outputs)
    d3 = mk_draft(True)
    for order in (1, 2):
        pg_lb.attach_output(d3, ws, editor, _Attach(photo_run_id=mk_run(True), page_order=order))
    pg_lb.submit_assembly(d3, ws, editor)
    pg_lb.decide_assembly(d3, ws, owner, "approved", "")
    monkeypatch.setattr(type(repos["lookbooks"]), "PACKAGE_MAX_PAGES", 1)
    with pytest.raises(_Conflict, match="limited to 100"):
        pg_lb.create_package(d3, ws, editor)
    monkeypatch.setattr(type(repos["lookbooks"]), "PACKAGE_MAX_PAGES", 100)
    assert pg_lb.create_package(d3, ws, editor)["output_count"] == 2
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM lookbook_output_package_exports WHERE draft_id=%s", (dd,)).fetchone()[0] == 0

    def norm(row, ws_name):
        text = repr(row).replace(ws_name, "WS")
        text = re.sub(r"\b[a-z]{2,4}_[0-9a-f]{12,}\b", "ID", text)
        text = re.sub(r"\d{4}-\d\d-\d\dT[\d:.+\-]+", "TS", text)
        return re.sub(r"\b[0-9a-f]{64}\b", "H", text)
    import os
    if os.environ.get("DUMP_PARITY"):
        for row in sqlite_out:
            print("PARITY", str(row)[:230])
    assert [r[0] for r in pg_out] == [r[0] for r in sqlite_out]
    mism = [(a[0], a[1:], b[1:]) for a, b in zip(sqlite_out, pg_out) if norm(a, "parity-pkg") != norm(b, ws)]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={norm(m[1], 'parity-pkg')}\n   pg    ={norm(m[2], ws)}" for m in mism)
    shown = {label: (s_, d) for label, s_, d in sqlite_out}
    assert shown["create"][0] == "ok" and shown["create-viewer"][0] == 403 and shown["create-outsider"][0] == 404
    assert shown["create-plan-unapproved"][0] == 409 and shown["create-assembly-in-review"][0] == 409
    assert shown["download-viewer"][0] == "ok" and shown["download-zip"][0] == "ok"
    assert shown["download-matches-recorded-hash"] == ("ok", True) and shown["list-order-newest-first"] == ("ok", True)
    assert shown["download-tampered"][0] == 409 and shown["download-file-missing"][0] == 410
    assert shown["download-bad-signature"][0] == 403 and shown["download-expired-url"][0] == 403


def test_lookbook_package_concurrent_creation_and_approval_change(repos, tmp_path, monkeypatch):
    import threading

    import app.config as config
    from app.lookbook import LookbookOutputAttachInput
    from app.ports.lookbooks import PostgreSQLLookbookDraftPort
    from app.repo_errors import RepositoryConflictError

    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
    lb = _VerifiedLookbooks(repos["lookbooks"])
    port = PostgreSQLLookbookDraftPort(repos["lookbooks"])
    did = lb.create_draft(ws, editor, {"title": "Pkg race", "product_ids": [prod]})["draft_id"]
    lb.submit_for_review(did, ws, editor); lb.decide_review(did, ws, owner, "APPROVED")
    for order in (1, 2):
        port.attach_output(did, ws, editor, LookbookOutputAttachInput(
            photo_run_id=_real_approved_photo_output(repos, ws, owner, editor, f"p{order}" + uuid.uuid4().hex[:6]), page_order=order))
    port.submit_assembly(did, ws, editor); port.decide_assembly(did, ws, owner, "approved", "")
    results, errors = [], []

    def work():
        try:
            results.append(port.create_package(did, ws, editor))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not errors, errors
    ids = {r["export_id"] for r in results}
    assert len(ids) == 6
    listed = port.package_exports(did, ws, viewer)
    assert listed["total"] == 6 and {i["export_id"] for i in listed["items"]} == ids
    assert all(i["status"] == "available" for i in listed["items"])
    files = sorted((tmp_path / "private" / "lookbook_exports").glob("*.zip"))
    assert len(files) == 6 and not list((tmp_path / "private" / "lookbook_exports").glob(".*.tmp"))
    # the audit trail is append-only
    import psycopg
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM lookbook_output_package_exports WHERE draft_id=%s", (did,))


def test_asset_delete_vs_product_create_never_leaves_a_dangling_reference(repos):
    """Invariant under contention: an ACTIVE product never references a soft-deleted asset."""
    import psycopg
    import threading

    ws, owner, editor, *_ = _workspace(repos)
    violations, errors = [], []
    for i in range(25):
        asset = _image(repos, ws, owner, f"race-{i}")
        barrier = threading.Barrier(2)

        def create():
            try:
                barrier.wait()
                repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"RACE-{i}-{uuid.uuid4().hex[:5]}", name="n",
                                         description=None, category="c", image_asset_ids=[asset])
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in {"DetailedValueError", "ProductConflictError"}:
                    errors.append(repr(exc))

        def delete():
            try:
                barrier.wait()
                repos["assets"].soft_delete_asset(asset, ws, actor_id=owner)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in {"AssetConflictError", "RepositoryConflictError"} and "referenced" not in str(exc):
                    errors.append(repr(exc))

        ts = [threading.Thread(target=create), threading.Thread(target=delete)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with psycopg.connect(DSN) as conn:
            n = conn.execute(
                """SELECT count(*) FROM product_assets pa JOIN products p ON p.product_id=pa.product_id
                   JOIN assets a ON a.asset_id=pa.asset_id
                   WHERE pa.asset_id=%s AND p.status='ACTIVE' AND a.deleted_at IS NOT NULL""", (asset,)).fetchone()[0]
        if n:
            violations.append(i)
    assert not errors, errors
    assert not violations, f"dangling product->asset references in iterations {violations}"


def _asset_delete_race(repos, make_reference, dangling_sql, label, rounds=20):
    """Run `make_reference(asset_id)` against `soft_delete_asset` for fresh assets; return dangling rounds + errors."""
    import threading

    import psycopg
    ws, owner, editor, *_ = _workspace(repos)
    violations, errors = [], []
    for i in range(rounds):
        asset = _image(repos, ws, owner, f"{label}-{i}")
        barrier = threading.Barrier(2)

        def reference():
            try:
                barrier.wait()
                make_reference(ws, owner, editor, asset, i)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in {"DetailedValueError", "ProductConflictError", "PhotoSourceVersionError"} and not isinstance(exc, ValueError):
                    errors.append(repr(exc))

        def delete():
            try:
                barrier.wait()
                repos["assets"].soft_delete_asset(asset, ws, actor_id=owner)
            except Exception as exc:  # noqa: BLE001
                if "referenced" not in str(exc) and type(exc).__name__ not in {"AssetConflictError", "RepositoryConflictError"}:
                    errors.append(repr(exc))
        ts = [threading.Thread(target=reference), threading.Thread(target=delete)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with psycopg.connect(DSN) as conn:
            if conn.execute(dangling_sql, (asset,)).fetchone()[0]:
                violations.append(i)
    return violations, errors


def test_asset_delete_vs_variant_create_never_leaves_a_dangling_reference(repos):
    ws0, owner0, editor0, *_ = _workspace(repos)

    def make(ws, owner, editor, asset, i):
        cat = _image(repos, ws, owner, f"vcat-{i}")
        product = repos["products"].create(workspace_id=ws, actor_id=editor, sku=f"VR-{i}-{uuid.uuid4().hex[:5]}", name="n",
                                           description=None, category="c", image_asset_ids=[cat])["product_id"]
        repos["products"].create_variant(product_id=product, workspace_id=ws, actor_id=editor,
                                         sku=f"VRV-{i}-{uuid.uuid4().hex[:5]}", option_values={"size": "M"}, image_asset_ids=[asset])
    violations, errors = _asset_delete_race(repos, make, """SELECT count(*) FROM product_variant_assets pva
        JOIN product_variants pv ON pv.variant_id=pva.variant_id JOIN assets a ON a.asset_id=pva.asset_id
        WHERE pva.asset_id=%s AND pv.status='ACTIVE' AND a.deleted_at IS NOT NULL""", "vrace")
    assert not errors, errors
    assert not violations, violations


def test_asset_delete_vs_photo_draft_create_never_leaves_a_dangling_reference(repos):
    def make(ws, owner, editor, asset, i):
        repos["photos"].create_draft(ws, editor, _photo_payload(asset))
    violations, errors = _asset_delete_race(repos, make, """SELECT count(*) FROM photo_draft_assets l
        JOIN photo_drafts d ON d.draft_id=l.draft_id JOIN assets a ON a.asset_id=l.asset_id
        WHERE l.asset_id=%s AND d.archived_at IS NULL AND a.deleted_at IS NOT NULL""", "prace")
    assert not errors, errors
    assert not violations, violations


def test_asset_delete_vs_lookbook_draft_create_never_leaves_a_dangling_reference(repos):
    def make(ws, owner, editor, asset, i):
        repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_asset_ids": [asset], "output_count": 1})
    violations, errors = _asset_delete_race(repos, make, """SELECT count(*) FROM lookbook_draft_assets l
        JOIN lookbook_drafts d ON d.draft_id=l.draft_id JOIN assets a ON a.asset_id=l.asset_id
        WHERE l.asset_id=%s AND d.archived_at IS NULL AND a.deleted_at IS NOT NULL""", "lrace")
    assert not errors, errors
    assert not violations, violations


def _parent_race(repos, label, make_child, archive_parent, dangling_sql, rounds=20):
    import threading

    import psycopg
    violations, errors = [], []
    for i in range(rounds):
        ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
        barrier = threading.Barrier(2)

        def child():
            try:
                barrier.wait()
                make_child(ws, editor, prod, chr_)
            except Exception as exc:  # noqa: BLE001
                if not isinstance(exc, ValueError) and type(exc).__name__ not in {"LookbookStateError"}:
                    errors.append(repr(exc))

        def parent():
            try:
                barrier.wait()
                archive_parent(ws, editor, prod, chr_)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in {"ProductConflictError", "CharacterConflictError"} and not isinstance(exc, (ValueError, LookupError)):
                    errors.append(repr(exc))
        ts = [threading.Thread(target=child), threading.Thread(target=parent)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with psycopg.connect(DSN) as conn:
            if conn.execute(dangling_sql, (prod,)).fetchone()[0]:
                violations.append(i)
    return violations, errors


def test_product_archive_vs_lookbook_draft_create_never_leaves_an_archived_reference(repos):
    violations, errors = _parent_race(
        repos, "parch",
        lambda ws, editor, prod, chr_: repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_ids": [prod]}),
        lambda ws, editor, prod, chr_: repos["products"].archive(prod, ws, editor),
        """SELECT count(*) FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
           JOIN products p ON p.product_id=e.entity_id
           WHERE e.entity_type='product' AND e.entity_id=%s AND d.archived_at IS NULL AND p.status<>'ACTIVE'
""")
    assert not errors, errors
    assert not violations, violations


def test_character_delete_vs_lookbook_draft_create_never_leaves_a_deleted_reference(repos):
    import threading

    import psycopg
    violations, errors = [], []
    for i in range(20):
        ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
        barrier = threading.Barrier(2)

        def child():
            try:
                barrier.wait()
                repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_ids": [prod], "character_id": chr_})
            except Exception as exc:  # noqa: BLE001
                if not isinstance(exc, ValueError):
                    errors.append(repr(exc))

        def parent():
            try:
                barrier.wait()
                repos["characters"].soft_delete(chr_, ws, editor)
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ != "CharacterConflictError":
                    errors.append(repr(exc))
        ts = [threading.Thread(target=child), threading.Thread(target=parent)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with psycopg.connect(DSN) as conn:
            if conn.execute("""SELECT count(*) FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
                JOIN characters c ON c.character_id=e.entity_id WHERE e.entity_type='character' AND e.entity_id=%s
                AND d.archived_at IS NULL AND c.deleted_at IS NOT NULL""", (chr_,)).fetchone()[0]:
                violations.append(i)
    assert not errors, errors
    assert not violations, violations


def test_project_archive_vs_lookbook_draft_create_never_leaves_an_archived_reference(repos):
    import threading

    import psycopg
    violations, errors = [], []
    for i in range(20):
        ws, owner, editor, viewer, outsider, prod, proj, chr_ = _lookbook_world(repos)
        barrier = threading.Barrier(2)

        def child():
            try:
                barrier.wait()
                repos["lookbooks"].create_draft(ws, editor, {"title": "T", "product_ids": [prod], "project_id": proj})
            except Exception as exc:  # noqa: BLE001
                if not isinstance(exc, ValueError) and type(exc).__name__ != "LookbookStateError":
                    errors.append(repr(exc))

        def parent():
            try:
                barrier.wait()
                repos["projects"].update(proj, editor, name="Campaign", project_type="campaign", status="ARCHIVED")
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ != "ProjectConflictError":
                    errors.append(repr(exc))
        ts = [threading.Thread(target=child), threading.Thread(target=parent)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with psycopg.connect(DSN) as conn:
            if conn.execute("""SELECT count(*) FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
                JOIN projects p ON p.project_id=e.entity_id WHERE e.entity_type='project' AND e.entity_id=%s
                AND d.archived_at IS NULL AND p.status<>'ACTIVE'""", (proj,)).fetchone()[0]:
                violations.append(i)
    assert not errors, errors
    assert not violations, violations


_CHARACTER_DANGLING_SQL = """SELECT count(*) FROM character_assets ca JOIN characters c ON c.character_id=ca.character_id
    JOIN assets a ON a.asset_id=ca.asset_id WHERE ca.asset_id=%s AND c.deleted_at IS NULL AND a.deleted_at IS NOT NULL"""


def test_asset_delete_vs_character_create_never_leaves_a_dangling_reference(repos):
    def make(ws, owner, editor, asset, i):
        repos["characters"].create(workspace_id=ws, actor_id=editor, payload=_char(name=f"R{i}"), asset_ids=[asset])
    violations, errors = _asset_delete_race(repos, make, _CHARACTER_DANGLING_SQL, "crace")
    assert not errors, errors
    assert not violations, violations


def test_asset_delete_vs_character_update_never_leaves_a_dangling_reference(repos):
    def make(ws, owner, editor, asset, i):
        cid = repos["characters"].create(workspace_id=ws, actor_id=editor, payload=_char(name=f"U{i}"))["character_id"]
        repos["characters"].update(cid, ws, editor, payload=_char(name=f"U{i}b"), asset_ids=[asset])
    violations, errors = _asset_delete_race(repos, make, _CHARACTER_DANGLING_SQL, "curace")
    assert not errors, errors
    assert not violations, violations


def _job_repos():
    from app.repositories.postgres_job import PostgreSQLJobRepository
    from app.repositories.postgres_outbox import PostgreSQLOutboxRepository
    return PostgreSQLJobRepository(), PostgreSQLOutboxRepository()


def _job_payload(ws, owner, key=""):
    return {"job_id": "job_" + uuid.uuid4().hex, "workspace_id": ws, "owner_id": owner, "status": "queued",
            "provider": "mock", "payload_hash": "h" * 64 + key, "payload": {"prompt": "x"}}


def _race(n, fn):
    import threading
    barrier, results, errors = threading.Barrier(n), [], []

    def work(i):
        try:
            barrier.wait()
            results.append(fn(i))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
    ts = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return results, errors


def test_job_concurrent_idempotent_create_makes_one_job(repos):
    import psycopg
    ws, owner, *_ = _workspace(repos)
    jobs, _ = _job_repos()
    key = "idem-" + uuid.uuid4().hex
    shared_hash = "a" * 64
    results, errors = _race(8, lambda i: jobs.create({**_job_payload(ws, owner), "payload_hash": shared_hash}, key))
    assert not errors, errors
    assert sum(1 for _, created in results if created) == 1
    assert len({value["job_id"] for value, _ in results}) == 1
    with psycopg.connect(DSN) as conn:
        job_id = results[0][0]["job_id"]
        assert conn.execute("SELECT count(*) FROM generation_idempotency WHERE workspace_id=%s AND idempotency_key=%s", (ws, key)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM generation_outbox WHERE job_id=%s", (job_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM generation_executions WHERE job_id=%s", (job_id,)).fetchone()[0] == 1
    # same key, different payload is refused under contention too
    results, errors = _race(4, lambda i: jobs.create({**_job_payload(ws, owner), "payload_hash": "b" * 64}, key))
    assert not results and all(isinstance(e, ValueError) for e in errors)


def test_job_concurrent_transitions_have_one_winner(repos):
    import psycopg
    from app.job_state import InvalidJobTransition
    ws, owner, *_ = _workspace(repos)
    jobs, _ = _job_repos()
    job, _ = jobs.create(_job_payload(ws, owner))
    results, errors = _race(8, lambda i: jobs.transition(job["job_id"], "running", actor_id=owner,
                                                        updates={"provider_request_id": f"prov-{i}"}))
    assert len(results) == 1 and len(errors) == 7 and all(isinstance(e, InvalidJobTransition) for e in errors), errors
    final = jobs.get(job["job_id"])
    assert final["status"] == "running" and final["provider_request_id"] == results[0]["provider_request_id"]
    with psycopg.connect(DSN) as conn:
        events = conn.execute("SELECT to_status FROM generation_job_events WHERE job_id=%s ORDER BY event_id", (job["job_id"],)).fetchall()
        assert [e[0] for e in events] == ["queued", "running"]
        version = conn.execute("SELECT version FROM generation_jobs WHERE job_id=%s", (job["job_id"],)).fetchone()[0]
        assert version == 2


def test_job_cancel_vs_dispatch_completion_never_deadlocks_or_double_applies(repos):
    """cancel_queued locks job->outbox while complete_outbox_submission locks outbox->job."""
    import psycopg
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    bad, outcomes = [], {"cancelled": 0, "dispatched": 0}
    for i in range(25):
        job, _ = jobs.create(_job_payload(ws, owner))
        worker = f"worker-{uuid.uuid4().hex[:8]}"
        # claim only OUR job's outbox row: older pending rows from other tests would be claimed first
        _isolate_queue(job["job_id"])
        claimed = outbox.claim_next_outbox(worker, 60)
        if claimed is None or claimed["job_id"] != job["job_id"]:
            if claimed is not None:
                outbox.mark_outbox_unknown(claimed["event_id"], claimed["job_id"], "test cleanup", worker)
            continue

        def act(k):
            if k == 0:
                return ("dispatched", outbox.complete_outbox_submission(claimed["event_id"], job["job_id"], "prov-" + uuid.uuid4().hex[:6], worker))
            return ("cancelled", jobs.cancel_queued(job["job_id"], actor_id=owner, reason="race"))
        results, errors = _race(2, act)
        deadlocks = [e for e in errors if "deadlock" in repr(e).lower()]
        other = [e for e in errors if not isinstance(e, (ValueError, RuntimeError)) and "deadlock" not in repr(e).lower()]
        final = jobs.get(job["job_id"])
        winners = [r[0] for r in results]
        consistent = (len(winners) == 1 and ((winners == ["dispatched"] and final["status"] == "running")
                                              or (winners == ["cancelled"] and final["status"] == "failed")))
        if deadlocks or other or not consistent:
            bad.append((i, [repr(e)[:80] for e in errors], winners, final["status"]))
        else:
            outcomes[winners[0]] += 1
    assert not bad, bad
    assert sum(outcomes.values()) > 0


def _isolate_queue(job_id):
    """Shared test DB: park every other pending dispatch/poll row so claims below can only reach this job."""
    import psycopg
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_outbox SET available_at=now()+interval '100 years' WHERE status='pending' AND job_id<>%s", (job_id,))
        conn.execute("UPDATE generation_poll_tasks SET available_at=now()+interval '100 years' WHERE status='pending' AND job_id<>%s", (job_id,))


def _job_at_persist_output(repos, jobs, outbox, ws, owner):
    """Drive one job through dispatch and claim its poll task in the persist_output phase."""
    import psycopg
    job, _ = jobs.create(_job_payload(ws, owner))
    worker = f"worker-{uuid.uuid4().hex[:8]}"
    _isolate_queue(job["job_id"])
    claimed = outbox.claim_next_outbox(worker, 60)
    assert claimed is not None and claimed["job_id"] == job["job_id"], "test must claim its own outbox row"
    outbox.complete_outbox_submission(claimed["event_id"], job["job_id"], "prov-" + uuid.uuid4().hex[:6], worker)
    _isolate_queue(job["job_id"])
    from app.repositories.postgres_poll import PostgreSQLPollRepository
    poll = PostgreSQLPollRepository()
    task = poll.claim_next_poll_task(worker, 60)
    assert task is not None and task["job_id"] == job["job_id"], "test must claim its own poll task"
    poll.reschedule_poll_task(task["task_id"], worker, delay_seconds=0, phase="persist_output")
    _isolate_queue(job["job_id"])
    task = poll.claim_next_poll_task(worker, 60)
    assert task["job_id"] == job["job_id"] and task["phase"] == "persist_output"
    jobs.transition(job["job_id"], "post_processing", actor_id=owner)
    return job, task, worker, poll


def test_output_finalize_concurrent_duplicate_and_exhaust_apply_once(repos):
    import psycopg
    from app.repositories.postgres_output import PostgreSQLOutputRepository
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    outputs = PostgreSQLOutputRepository()
    bad = []
    for i in range(15):
        job, task, worker, poll = _job_at_persist_output(repos, jobs, outbox, ws, owner)
        jid = job["job_id"]
        url = f"/v1/generation-jobs/{jid}/output"

        def act(k):
            if k < 3:
                return ("finalize", outputs.finalize_success(task["task_id"], worker, jid, storage_key=f"{jid}.png",
                                                             media_type="image/png", size_bytes=10, output_url=url))
            return ("exhaust", poll.exhaust_poll_task(task["task_id"], worker, jid, phase="persist_output", error="boom"))
        results, errors = _race(4, act)
        wins = [r for r in results if r[1] is True]
        with psycopg.connect(DSN) as conn:
            n_out = conn.execute("SELECT count(*) FROM generation_outputs WHERE job_id=%s", (jid,)).fetchone()[0]
            n_link = conn.execute("SELECT count(*) FROM generation_output_asset_links WHERE job_id=%s", (jid,)).fetchone()[0]
            n_ev = conn.execute("SELECT count(*) FROM generation_job_events WHERE job_id=%s AND event_type='OUTPUT_PERSISTED'", (jid,)).fetchone()[0]
            task_status = conn.execute("SELECT status FROM generation_poll_tasks WHERE task_id=%s", (task["task_id"],)).fetchone()[0]
        final = jobs.get(jid)
        finalized = any(w[0] == "finalize" for w in wins)
        ok = (not errors and len(wins) == 1
              and ((finalized and (n_out, n_link, n_ev) == (1, 1, 1) and final["status"] == "succeeded" and task_status == "completed")
                   or (not finalized and (n_out, n_link, n_ev) == (0, 0, 0) and final["status"] == "post_processing"
                       and task_status == "needs_reconciliation")))
        if not ok:
            bad.append((i, [repr(e)[:90] for e in errors], [w[0] for w in wins], (n_out, n_link, n_ev), final["status"], task_status))
    assert not bad, bad


def test_expired_poll_lease_is_requeued_and_stale_worker_cannot_finalize(repos):
    import psycopg
    from app.repositories.postgres_output import PostgreSQLOutputRepository
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    outputs = PostgreSQLOutputRepository()
    job, task, worker, poll = _job_at_persist_output(repos, jobs, outbox, ws, owner)
    jid = job["job_id"]
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_poll_tasks SET lease_expires_at=now()-interval '1 second' WHERE task_id=%s", (task["task_id"],))
    url = f"/v1/generation-jobs/{jid}/output"
    assert outputs.finalize_success(task["task_id"], worker, jid, storage_key=f"{jid}.png", media_type="image/png",
                                    size_bytes=10, output_url=url) is False
    assert poll.complete_poll_task(task["task_id"], worker) is False
    assert poll.renew_poll_task_lease(task["task_id"], worker, 60) is False
    other = f"worker-{uuid.uuid4().hex[:8]}"
    again = poll.claim_next_poll_task(other, 60)
    assert again is not None and again["task_id"] == task["task_id"] and again["claimed_by"] == other
    # the stale worker still cannot finalize or exhaust, the new owner can
    assert outputs.finalize_success(task["task_id"], worker, jid, storage_key=f"{jid}.png", media_type="image/png",
                                    size_bytes=10, output_url=url) is False
    assert poll.exhaust_poll_task(task["task_id"], worker, jid, phase="persist_output", error="x") is False
    assert jobs.get(jid)["status"] == "post_processing"
    assert outputs.finalize_success(task["task_id"], other, jid, storage_key=f"{jid}.png", media_type="image/png",
                                    size_bytes=10, output_url=url) is True
    assert jobs.get(jid)["status"] == "succeeded"


def _seed_deliveries(count, tag):
    """Insert one alert with `count` pending deliveries; created far in the past so claims reach them first."""
    import psycopg
    alert = "alert_" + uuid.uuid4().hex
    ids = []
    with psycopg.connect(DSN, autocommit=True) as conn:
        # park every other pending delivery so other tests' leftovers cannot be claimed here
        conn.execute("UPDATE generation_ops_alert_deliveries SET available_at=now()+interval '100 years' WHERE status='pending'")
        conn.execute("""INSERT INTO generation_ops_alerts(alert_id,fingerprint,alert_type,severity,status,title,first_seen_at,last_seen_at)
                        VALUES(%s,%s,'t','warning','active','t',now(),now())""", (alert, alert))
        for i in range(count):
            d = f"del_{tag}_{uuid.uuid4().hex[:10]}"
            ids.append(d)
            conn.execute("""INSERT INTO generation_ops_alert_deliveries(delivery_id,alert_id,destination,status,available_at,created_at)
                            VALUES(%s,%s,%s,'pending',now()-interval '1 hour',now()-interval '1 hour')""", (d, alert, f"dest-{i}"))
    return ids


def test_alert_delivery_claims_are_exclusive_under_contention(repos):
    from app.repositories.postgres_operations import PostgreSQLOperationsRepository
    ops = PostgreSQLOperationsRepository()
    ids = _seed_deliveries(10, "claim")
    workers = [f"worker-{i}-{uuid.uuid4().hex[:6]}" for i in range(6)]
    claimed, errors = [], []
    import threading

    def run(w):
        try:
            while True:
                row = ops.claim_alert_delivery(w, 60)
                if row is None:
                    return
                claimed.append((row["delivery_id"], w))
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))
    ts = [threading.Thread(target=run, args=(w,)) for w in workers]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors, errors
    mine = [c for c in claimed if c[0] in ids]
    assert sorted(d for d, _ in mine) == sorted(ids), "every delivery claimed exactly once"


def test_alert_delivery_finish_is_fenced_by_owner_and_lease(repos):
    import psycopg
    from app.repositories.postgres_operations import PostgreSQLOperationsRepository
    ops = PostgreSQLOperationsRepository()
    ids = _seed_deliveries(1, "fence")
    first = f"worker-a-{uuid.uuid4().hex[:6]}"
    other = f"worker-b-{uuid.uuid4().hex[:6]}"
    row = ops.claim_alert_delivery(first, 60)
    assert row["delivery_id"] == ids[0]
    assert ops.finish_alert_delivery(ids[0], worker_id=other, delivered=True) is False
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_ops_alert_deliveries SET lease_expires_at=now()-interval '1 second' WHERE delivery_id=%s", (ids[0],))
    assert ops.finish_alert_delivery(ids[0], worker_id=first, delivered=True) is False  # lease lost
    again = ops.claim_alert_delivery(other, 60)
    assert again["delivery_id"] == ids[0] and again["claimed_by"] == other and again["attempts"] == 2
    assert ops.finish_alert_delivery(ids[0], worker_id=first, delivered=True) is False  # stale owner
    # concurrent finish by the owner: delivered and a retry race, exactly one applies
    results, errors = _race(4, lambda i: ops.finish_alert_delivery(ids[0], worker_id=other, delivered=(i % 2 == 0), error="e"))
    assert not errors, errors
    assert sum(1 for r in results if r) == 1
    with psycopg.connect(DSN) as conn:
        status = conn.execute("SELECT status FROM generation_ops_alert_deliveries WHERE delivery_id=%s", (ids[0],)).fetchone()[0]
    assert status in {"delivered", "pending"}


def test_outbox_dispatch_complete_vs_unknown_vs_lease_expiry_apply_once(repos):
    import psycopg
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    bad, seen = [], {"complete": 0, "unknown": 0}
    for i in range(20):
        job, _ = jobs.create(_job_payload(ws, owner))
        jid = job["job_id"]
        worker = f"worker-{uuid.uuid4().hex[:8]}"
        _isolate_queue(jid)
        claimed = outbox.claim_next_outbox(worker, 60)
        assert claimed is not None and claimed["job_id"] == jid

        def act(k):
            if k == 0:
                return ("complete", outbox.complete_outbox_submission(claimed["event_id"], jid, "prov-" + uuid.uuid4().hex[:6], worker))
            if k == 1:
                return ("unknown", outbox.mark_outbox_unknown(claimed["event_id"], jid, "timeout", worker))
            return ("noop", outbox.claim_next_outbox(f"worker-x{k}-{uuid.uuid4().hex[:5]}", 60))
        results, errors = _race(3, act)
        wins = [r[0] for r in results if (r[0] == "complete" and r[1] is not None) or (r[0] == "unknown" and r[1] is True)]
        with psycopg.connect(DSN) as conn:
            ob = conn.execute("SELECT status FROM generation_outbox WHERE event_id=%s", (claimed["event_id"],)).fetchone()[0]
            ex = conn.execute("SELECT status FROM generation_executions WHERE job_id=%s", (jid,)).fetchone()[0]
            ev = [r[0] for r in conn.execute("SELECT event_type FROM generation_job_events WHERE job_id=%s ORDER BY event_id", (jid,)).fetchall()]
        final = jobs.get(jid)
        unexpected = [e for e in errors if not isinstance(e, RuntimeError)]
        ok = (not unexpected and len(wins) == 1 and (
            (wins == ["complete"] and (ob, final["status"], ex) == ("processed", "running", "running") and ev == ["JOB_CREATED", "PROVIDER_SUBMITTED"])
            or (wins == ["unknown"] and (ob, final["status"], ex) == ("needs_reconciliation", "queued", "unknown")
                and ev == ["JOB_CREATED", "PROVIDER_START_UNKNOWN"])))
        if not ok:
            bad.append((i, [repr(e)[:80] for e in errors], wins, ob, final["status"], ex, ev))
        else:
            seen[wins[0]] += 1
    assert not bad, bad
    assert seen["complete"] and seen["unknown"], seen


def test_outbox_expired_lease_is_quarantined_and_stale_worker_cannot_complete(repos):
    import psycopg
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    job, _ = jobs.create(_job_payload(ws, owner))
    jid = job["job_id"]
    stale = f"worker-{uuid.uuid4().hex[:8]}"
    _isolate_queue(jid)
    claimed = outbox.claim_next_outbox(stale, 60)
    assert claimed["job_id"] == jid
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_outbox SET lease_expires_at=now()-interval '1 second' WHERE event_id=%s", (claimed["event_id"],))
    outbox.claim_next_outbox(f"worker-{uuid.uuid4().hex[:8]}", 60)  # this call quarantines the expired claim
    with pytest.raises(RuntimeError):
        outbox.complete_outbox_submission(claimed["event_id"], jid, "prov-late", stale)
    assert outbox.mark_outbox_unknown(claimed["event_id"], jid, "late", stale) is False
    with psycopg.connect(DSN) as conn:
        status = conn.execute("SELECT status FROM generation_outbox WHERE event_id=%s", (claimed["event_id"],)).fetchone()[0]
    assert status == "needs_reconciliation"
    final = jobs.get(jid)
    assert final["status"] == "queued" and final["error_code"] == "PROVIDER_START_UNKNOWN"


def test_job_list_pagination_is_total_ordered_and_workspace_scoped(repos):
    """Stable data: pages are disjoint, cover every job, newest first, ties broken by job_id DESC."""
    import psycopg
    ws, owner, *_ = _workspace(repos)
    other_ws, other_owner, *_ = _workspace(repos)
    jobs, _ = _job_repos()
    mine = [jobs.create(_job_payload(ws, owner))[0]["job_id"] for _ in range(23)]
    for _ in range(5):
        jobs.create(_job_payload(other_ws, other_owner))
    with psycopg.connect(DSN, autocommit=True) as conn:  # force created_at ties on 10 jobs
        conn.execute("UPDATE generation_jobs SET created_at=now()+interval '1 hour' WHERE job_id = ANY(%s)", (mine[:10],))
    seen = []
    for offset in range(0, 30, 7):
        page = jobs.list_for_workspace(ws, limit=7, offset=offset)
        assert len(page) <= 7
        seen.extend(page)
    ids = [j["job_id"] for j in seen]
    assert sorted(ids) == sorted(mine) and len(set(ids)) == len(ids)
    keys = [(j["created_at"], j["job_id"]) for j in seen]
    assert keys == sorted(keys, reverse=True)
    assert jobs.list_for_workspace(ws, limit=7, offset=23) == []
    for bad in ({"limit": 0}, {"limit": 201}, {"offset": -1}):
        with pytest.raises(ValueError):
            jobs.list_for_workspace(ws, **bad)


def test_asset_delete_is_refused_while_an_active_character_links_it(repos):
    ws, owner, editor, *_ = _workspace(repos)
    img = _image(repos, ws, owner, "chr-link")
    chr_ = repos["characters"].create(workspace_id=ws, actor_id=editor, payload=_char(), asset_ids=[img])["character_id"]
    with pytest.raises(Exception) as err:
        repos["assets"].soft_delete_asset(img, ws, actor_id=owner)
    assert type(err.value).__name__ == "AssetConflictError" and "Character" in str(err.value)
    repos["characters"].soft_delete(chr_, ws, editor)
    assert repos["assets"].soft_delete_asset(img, ws, actor_id=owner) is True


def test_job_list_pagination_under_concurrent_creates_never_skips_existing_jobs(repos):
    """Offset paging may repeat a job when new jobs land at the head, but must never skip an existing one."""
    import threading
    ws, owner, *_ = _workspace(repos)
    jobs, _ = _job_repos()
    existing = {jobs.create(_job_payload(ws, owner))[0]["job_id"] for _ in range(30)}
    stop, errors, created = threading.Event(), [], []

    def writer():
        try:
            while not stop.is_set():
                created.append(jobs.create(_job_payload(ws, owner))[0]["job_id"])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
    t = threading.Thread(target=writer); t.start()
    try:
        for _ in range(10):
            seen, offset = [], 0
            for _ in range(200):  # bound: a broken offset must fail the test, not loop forever
                page = jobs.list_for_workspace(ws, limit=5, offset=offset)
                assert len(page) <= 5 and len({j["job_id"] for j in page}) == len(page)
                keys = [(j["created_at"], j["job_id"]) for j in page]
                assert keys == sorted(keys, reverse=True)
                seen.extend(j["job_id"] for j in page)
                if len(page) < 5:
                    break
                offset += 5
            else:
                raise AssertionError("pagination did not terminate")
            assert existing <= set(seen), existing - set(seen)
    finally:
        stop.set(); t.join()
    assert not errors, errors
    assert created


def test_job_execution_cursor_is_stable_while_new_attempts_arrive(repos):
    """Keyset cursor on attempt_no: attempts that existed at the first page appear exactly once, in order."""
    import psycopg, threading
    ws, owner, *_ = _workspace(repos)
    jobs, _ = _job_repos()
    job, _ = jobs.create(_job_payload(ws, owner))
    jid = job["job_id"]

    def add_attempt(n):
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute("""INSERT INTO generation_executions (execution_id,job_id,attempt_no,status,provider,started_at,finished_at)
                VALUES (%s,%s,%s,'failed','mock',now(),now())""", ("exec_" + uuid.uuid4().hex, jid, n))
    for n in range(2, 13):
        add_attempt(n)
    first = jobs.list_executions(jid, limit=4)
    assert [e["attempt_number"] for e in first["data"]] == [12, 11, 10, 9]
    stop, errors, nxt = threading.Event(), [], [100]

    def writer():
        try:
            while not stop.is_set():
                add_attempt(nxt[0]); nxt[0] += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
    t = threading.Thread(target=writer); t.start()
    try:
        got, cursor = [e["attempt_number"] for e in first["data"]], first["meta"]["next_cursor"]
        while cursor:
            page = jobs.list_executions(jid, limit=4, cursor=cursor)
            got.extend(e["attempt_number"] for e in page["data"])
            cursor = page["meta"]["next_cursor"]
    finally:
        stop.set(); t.join()
    assert not errors, errors
    assert got == list(range(12, 0, -1)), got
    for bad in ("garbage", "ZXhlYzow"):
        with pytest.raises(ValueError):
            jobs.list_executions(jid, cursor=bad)


def _claimed_outbox(repos):
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    job, _ = jobs.create(_job_payload(ws, owner))
    _isolate_queue(job["job_id"])
    owner_worker = f"worker-{uuid.uuid4().hex[:8]}"
    claimed = outbox.claim_next_outbox(owner_worker, 60)
    assert claimed["job_id"] == job["job_id"]
    return jobs, outbox, job["job_id"], claimed["event_id"], owner_worker


def _park_job_rows(job_id):
    """Leave no claimable dispatch/poll row behind for tests that share this database."""
    import psycopg
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_outbox SET available_at=now()+interval '100 years' WHERE status='pending' AND job_id=%s", (job_id,))
        conn.execute("UPDATE generation_poll_tasks SET available_at=now()+interval '100 years' WHERE status='pending' AND job_id=%s", (job_id,))


def _outbox_row(event_id):
    import psycopg
    with psycopg.connect(DSN) as conn:
        return conn.execute("SELECT status, claimed_by FROM generation_outbox WHERE event_id=%s", (event_id,)).fetchone()


def test_outbox_completion_and_unknown_are_fenced_to_the_claiming_worker(repos):
    """A different worker with its own valid claim elsewhere must not finish an event it does not hold."""
    jobs, outbox, jid, event_id, holder = _claimed_outbox(repos)
    intruder = f"worker-{uuid.uuid4().hex[:8]}"
    with pytest.raises(RuntimeError):
        outbox.complete_outbox_submission(event_id, jid, "prov-intruder", intruder)
    assert outbox.mark_outbox_unknown(event_id, jid, "intruder", intruder) is False
    assert tuple(_outbox_row(event_id)) == ("processing", holder) and jobs.get(jid)["status"] == "queued"
    try:
        assert outbox.complete_outbox_submission(event_id, jid, "prov-holder", holder)["status"] == "running"
        assert tuple(_outbox_row(event_id))[0] == "processed"
    finally:
        _park_job_rows(jid)


def test_outbox_expired_but_unreclaimed_lease_cannot_complete_or_mark_unknown(repos):
    """Expiry alone (no later claim has quarantined the row yet) must already fence the old owner."""
    import psycopg
    jobs, outbox, jid, event_id, holder = _claimed_outbox(repos)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE generation_outbox SET lease_expires_at=now()-interval '1 second' WHERE event_id=%s", (event_id,))
    with pytest.raises(RuntimeError):
        outbox.complete_outbox_submission(event_id, jid, "prov-late", holder)
    assert outbox.mark_outbox_unknown(event_id, jid, "late", holder) is False
    assert tuple(_outbox_row(event_id)) == ("processing", holder) and jobs.get(jid)["status"] == "queued"
    with psycopg.connect(DSN, autocommit=True) as conn:  # settle the row so no later claim has to quarantine it
        conn.execute("UPDATE generation_outbox SET status='needs_reconciliation', claimed_by=NULL, lease_expires_at=NULL WHERE event_id=%s", (event_id,))



def _glb(extra: str = "") -> bytes:
    import json
    import struct
    doc = json.dumps({"asset": {"version": "2.0", "generator": extra}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


def _version_metadata_scenario(bytes_port, meta_port, ws, editor):
    """New-version metadata: asset row, filename normalisation, version rows and provenance values."""
    import hashlib

    from app import config
    from app.assets.validation import validate_asset_upload

    out = []
    sha = lambda data: hashlib.sha256(data).hexdigest()  # noqa: E731
    val = lambda name, data: validate_asset_upload(name, data, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)  # noqa: E731
    asset_fields = ("original_filename", "media_type", "size_bytes", "gltf_version", "embedded_binary", "asset_kind")

    def show_asset(asset_id, data):
        row = meta_port.get(asset_id, editor)
        return tuple((k, row.get(k)) for k in asset_fields) + (("checksum_ok", row.get("checksum_sha256") == sha(data)),)

    def prov(asset_id):
        items = meta_port.provenance(asset_id, editor, 100, 0)["items"]
        return sorted((i["event_type"], i["version_number"], i["details"].get("previous_version")) for i in items)

    v1, v2, v3 = _glb("one"), _glb("two"), _glb("three")
    saved = bytes_port.save(ws, editor, "model-one.glb", v1, val("model-one.glb", v1))
    aid = saved["asset_id"]
    out.append(("after-save", show_asset(aid, v1)))
    bytes_port.save_version(aid, editor, "../up/dir/model-two.glb", v2, val("model-two.glb", v2))
    out.append(("after-version2-path-stripped", show_asset(aid, v2)))
    long_name = "n" * 300 + ".glb"
    bytes_port.save_version(aid, editor, long_name, v3, val("x.glb", v3))
    row = meta_port.get(aid, editor)
    out.append(("after-version3-long-name", (len(row["original_filename"]), row["original_filename"] == long_name[:255],
                                             show_asset(aid, v3)[1:])))
    versions = meta_port.versions(aid, editor)["items"]
    out.append(("versions", [(v["version_number"], v["is_current"], v["size_bytes"], v["media_type"]) for v in versions]))
    out.append(("version-checksums", sorted(sha(d) for d in (v1, v2, v3)) == sorted(v["checksum_sha256"] for v in versions)))
    out.append(("provenance-previous-version", prov(aid)))
    return out


def test_asset_version_metadata_parity_sqlite_vs_postgresql(repos, tmp_path, monkeypatch):
    import app.config as config
    from app.assets import store
    from app.ports.asset_bytes import PostgreSQLAssetBytesPort, SQLiteAssetBytesPort
    from app.ports.assets import PostgreSQLAssetMetadataPort, SQLiteAssetMetadataPort
    from app.ports.workspace import SQLiteWorkspacePort

    sq_dir, pg_dir = tmp_path / "sq-private", tmp_path / "pg-private"
    sq_dir.mkdir(); pg_dir.mkdir()
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", sq_dir)
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "parity-version.sqlite3")
    store.initialize()
    store.create_workspace("parity-ver", "owner_sq")
    store.add_workspace_member("parity-ver", "editor_sq", "editor")
    wsp = SQLiteWorkspacePort()
    sqlite_out = _version_metadata_scenario(SQLiteAssetBytesPort(wsp), SQLiteAssetMetadataPort(wsp), "parity-ver", "editor_sq")

    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", pg_dir)
    ws, owner, editor, *_ = _workspace(repos)
    pg_out = _version_metadata_scenario(PostgreSQLAssetBytesPort(repos["assets"]), PostgreSQLAssetMetadataPort(repos["assets"]), ws, editor)
    mism = [(a[0], a[1], b[1]) for a, b in zip(sqlite_out, pg_out) if a != b]
    assert [r[0] for r in sqlite_out] == [r[0] for r in pg_out]
    assert not mism, "\n" + "\n".join(f"{m[0]}\n   sqlite={m[1]}\n   pg    ={m[2]}" for m in mism)
    shown = dict(sqlite_out)
    assert shown["after-version2-path-stripped"][0] == ("original_filename", "model-two.glb")
    assert shown["after-version3-long-name"][:2] == (255, True)
    assert [v[0] for v in shown["versions"]] == [3, 2, 1] and [v[1] for v in shown["versions"]] == [True, False, False]
    created = [e for e in shown["provenance-previous-version"] if e[0] == "asset.version_created"]
    assert created == [("asset.version_created", 2, 1), ("asset.version_created", 3, 2)]


def test_job_get_idempotent_returns_the_job_and_payload_hash_scoped_to_the_workspace(repos):
    jobs, _outbox = _job_repos()
    ws, owner, *_ = _workspace(repos)
    other_ws, other_owner, *_ = _workspace(repos)
    key = "idem-" + uuid.uuid4().hex[:8]
    payload = _job_payload(ws, owner, key="k1")
    job, created = jobs.create(payload, idempotency_key=key)
    assert created is True
    found = jobs.get_idempotent(ws, key)
    assert found is not None and found[0]["job_id"] == job["job_id"] and found[1] == payload["payload_hash"]
    assert jobs.get_idempotent(ws, "no-such-key") is None
    assert jobs.get_idempotent(other_ws, key) is None  # same key in another workspace is a different key


def test_outbox_get_job_reads_the_job_aggregate(repos):
    jobs, outbox = _job_repos()
    ws, owner, *_ = _workspace(repos)
    job, _ = jobs.create(_job_payload(ws, owner))
    got = outbox.get_job(job["job_id"])
    assert got is not None and got["job_id"] == job["job_id"] and got["status"] == "queued"
    assert outbox.get_job("job_missing_" + uuid.uuid4().hex) is None


def _heartbeat_rows(worker_id):
    import psycopg
    with psycopg.connect(DSN) as conn:
        return conn.execute("SELECT started_at, last_seen_at, state, metadata_json FROM generation_worker_heartbeats WHERE worker_id=%s",
                            (worker_id,)).fetchall()


@pytest.mark.parametrize("which", ["outbox", "operations"])
def test_worker_heartbeat_upserts_without_resetting_started_at(repos, which):
    import time

    from app.repositories.postgres_operations import PostgreSQLOperationsRepository
    repo = _job_repos()[1] if which == "outbox" else PostgreSQLOperationsRepository()
    beat = repo.heartbeat_worker if which == "outbox" else repo.heartbeat
    worker = f"worker-{uuid.uuid4().hex[:8]}"
    beat(worker, "idle", {"n": 1})
    first = _heartbeat_rows(worker)
    assert len(first) == 1 and first[0][2] == "idle" and first[0][3] == {"n": 1}
    time.sleep(0.02)
    beat(worker, "busy", {"n": 2})
    second = _heartbeat_rows(worker)
    assert len(second) == 1, "a second heartbeat must update the row, not add one"
    assert second[0][0] == first[0][0], "started_at must not be reset by later heartbeats"
    assert second[0][1] > first[0][1] and second[0][2] == "busy" and second[0][3] == {"n": 2}
    beat(worker, "idle")  # metadata defaults to {}
    assert _heartbeat_rows(worker)[0][3] == {}
    for bad_worker, bad_state in (("", "idle"), (worker, ""), (worker, "   ")):
        with pytest.raises(ValueError):
            beat(bad_worker, bad_state)


def test_output_record_get_and_storage_key_listing(repos):
    from app.repositories.postgres_output import PostgreSQLOutputRepository
    jobs, _outbox = _job_repos()
    outputs = PostgreSQLOutputRepository()
    ws, owner, *_ = _workspace(repos)
    job1, _ = jobs.create(_job_payload(ws, owner, key="o1"))
    job2, _ = jobs.create(_job_payload(ws, owner, key="o2"))
    k1, k2, k3 = (f"out_{uuid.uuid4().hex}.png" for _ in range(3))
    assert outputs.get(job1["job_id"]) is None
    rec = outputs.record(job1["job_id"], k1, "image/png", 123)
    assert (rec["job_id"], rec["storage_key"], rec["media_type"], rec["size_bytes"]) == (job1["job_id"], k1, "image/png", 123)
    assert outputs.get(job1["job_id"])["storage_key"] == k1
    outputs.record(job2["job_id"], k2, "image/webp", 5)
    keys = outputs.list_storage_keys()
    assert {k1, k2} <= keys and k3 not in keys
    # recording again for the same job replaces its output; the old key is no longer listed
    again = outputs.record(job1["job_id"], k3, "image/jpeg", 7)
    assert again["storage_key"] == k3 and again["media_type"] == "image/jpeg" and again["size_bytes"] == 7
    keys = outputs.list_storage_keys()
    assert k3 in keys and k1 not in keys and k2 in keys
    for args in (("../evil.png", "image/png", 1), ("a/b.png", "image/png", 1), ("", "image/png", 1),
                 (k1, "application/pdf", 1), (k1, "image/png", -1), (k1, "image/png", True)):
        with pytest.raises(ValueError):
            outputs.record(job2["job_id"], *args)
    from app import config
    with pytest.raises(ValueError):
        outputs.record(job2["job_id"], k1, "image/png", config.MAX_OUTPUT_BYTES + 1)
    assert outputs.get(job2["job_id"])["storage_key"] == k2, "rejected records must not change the stored output"


def test_job_update_applies_allowed_fields_bumps_version_and_records_an_event(repos):
    import psycopg
    jobs, _outbox = _job_repos()
    ws, owner, *_ = _workspace(repos)
    job, _ = jobs.create(_job_payload(ws, owner))
    jid = job["job_id"]
    before = jobs.get(jid)
    updated = jobs.update(jid, {"message": "hello"}, event_type="TEST_UPDATED")
    assert updated["message"] == "hello" and updated["status"] == before["status"] and updated["version"] == before["version"] + 1
    with psycopg.connect(DSN) as conn:
        events = conn.execute("SELECT event_type, from_status, to_status FROM generation_job_events WHERE job_id=%s ORDER BY event_id", (jid,)).fetchall()
    assert events[-1] == ("TEST_UPDATED", before["status"], before["status"])
    default = jobs.update(jid, {"message": "again"})
    assert default["version"] == before["version"] + 2
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT event_type FROM generation_job_events WHERE job_id=%s ORDER BY event_id DESC LIMIT 1", (jid,)).fetchone()[0] == "JOB_UPDATED"
    with pytest.raises(ValueError):
        jobs.update(jid, {"status": "succeeded"})  # status changes go through transition(), never update()
    with pytest.raises(KeyError):
        jobs.update("job_missing_" + uuid.uuid4().hex, {"message": "x"})
    assert jobs.get(jid)["message"] == "again" and jobs.get(jid)["status"] == before["status"]


def test_job_list_outputs_reports_recorded_outputs_and_not_queued_link_status(repos):
    from app.repositories.postgres_output import PostgreSQLOutputRepository
    jobs, _outbox = _job_repos()
    ws, owner, *_ = _workspace(repos)
    job, _ = jobs.create(_job_payload(ws, owner))
    assert jobs.list_outputs(job["job_id"]) == {"data": [], "meta": {}}
    key = f"out_{uuid.uuid4().hex}.png"
    PostgreSQLOutputRepository().record(job["job_id"], key, "image/png", 42)
    data = jobs.list_outputs(job["job_id"])["data"]
    assert len(data) == 1
    assert (data[0]["job_id"], data[0]["mime_type"], data[0]["size_bytes"], data[0]["asset_link_status"]) == (job["job_id"], "image/png", 42, "not_queued")
    assert data[0]["asset_id"] is None and data[0]["provenance_record_id"] is None
    other, _ = jobs.create(_job_payload(ws, owner, key="other"))
    assert jobs.list_outputs(other["job_id"])["data"] == [], "outputs of another job must not appear"


def test_poll_lease_renewal_extends_only_the_owner_before_expiry(repos):
    import psycopg
    ws, owner, *_ = _workspace(repos)
    jobs, outbox = _job_repos()
    job, task, worker, poll = _job_at_persist_output(repos, jobs, outbox, ws, owner)

    def lease():
        with psycopg.connect(DSN) as conn:
            return conn.execute("SELECT lease_expires_at FROM generation_poll_tasks WHERE task_id=%s", (task["task_id"],)).fetchone()[0]
    before = lease()
    assert poll.renew_poll_task_lease(task["task_id"], worker, 600) is True
    assert lease() > before, "renewal must extend the lease"
    stranger = f"worker-{uuid.uuid4().hex[:8]}"
    after = lease()
    assert poll.renew_poll_task_lease(task["task_id"], stranger, 6000) is False
    assert lease() == after, "a non-owner must not change the lease"
    with pytest.raises(ValueError):
        poll.renew_poll_task_lease("", worker, 60)
    _park_job_rows(job["job_id"])
