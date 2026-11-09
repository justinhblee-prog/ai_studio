from __future__ import annotations

import sqlite3

from app.integrity_audit import audit_connection


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE assets(asset_id TEXT PRIMARY KEY, workspace_id TEXT, deleted_at TEXT, media_type TEXT);
    CREATE TABLE products(product_id TEXT PRIMARY KEY, workspace_id TEXT);
    CREATE TABLE product_assets(product_id TEXT, asset_id TEXT);
    CREATE TABLE product_variants(variant_id TEXT PRIMARY KEY, product_id TEXT, workspace_id TEXT);
    CREATE TABLE product_variant_assets(variant_id TEXT, asset_id TEXT);
    CREATE TABLE characters(character_id TEXT PRIMARY KEY, workspace_id TEXT);
    CREATE TABLE character_assets(character_id TEXT, asset_id TEXT);
    CREATE TABLE lookbook_drafts(draft_id TEXT PRIMARY KEY, workspace_id TEXT);
    CREATE TABLE lookbook_draft_assets(draft_id TEXT, asset_id TEXT);
    CREATE TABLE projects(project_id TEXT PRIMARY KEY, workspace_id TEXT);
    CREATE TABLE lookbook_draft_entities(draft_id TEXT, entity_type TEXT, entity_id TEXT);
    INSERT INTO assets VALUES('a1','w1',NULL,'image/png'),('a2','w2',NULL,'image/png'),('a3','w1','2026-01-01','application/octet-stream');
    INSERT INTO products VALUES('p1','w1');
    INSERT INTO product_assets VALUES('p1','a2');
    INSERT INTO product_variants VALUES('v1','p1','w2');
    INSERT INTO product_variant_assets VALUES('v1','a1');
    INSERT INTO characters VALUES('c1','w1');
    INSERT INTO character_assets VALUES('c1','a2');
    INSERT INTO lookbook_drafts VALUES('d1','w1');
    INSERT INTO lookbook_draft_assets VALUES('d1','a3');
    INSERT INTO projects VALUES('pr1','w2');
    INSERT INTO lookbook_draft_entities VALUES('d1','project','pr1'),('d1','character','missing');
    """)
    return db


def test_audit_detects_historical_cross_workspace_and_stale_references_without_mutation():
    db = _db()
    before = db.execute("SELECT COUNT(*) FROM product_assets").fetchone()[0]
    report = audit_connection(db)
    codes = {item["code"] for item in report["findings"]}
    assert report["mode"] == "read-only"
    assert "PRODUCT_ASSET_CROSS_WORKSPACE" in codes
    assert "VARIANT_PARENT_MISMATCH" in codes
    assert "VARIANT_ASSET_CROSS_WORKSPACE" in codes
    assert "CHARACTER_ASSET_CROSS_WORKSPACE" in codes
    assert "LOOKBOOK_ASSET_INVALID" in codes
    assert "LOOKBOOK_ENTITY_MISSING_OR_CROSS_WORKSPACE" in codes
    assert db.execute("SELECT COUNT(*) FROM product_assets").fetchone()[0] == before


def test_audit_clean_workspace_relations_have_no_findings():
    db = _db()
    db.executescript("""
    DELETE FROM product_assets; INSERT INTO product_assets VALUES('p1','a1');
    UPDATE product_variants SET workspace_id='w1';
    DELETE FROM product_variant_assets; INSERT INTO product_variant_assets VALUES('v1','a1');
    DELETE FROM character_assets; INSERT INTO character_assets VALUES('c1','a1');
    DELETE FROM lookbook_draft_assets; INSERT INTO lookbook_draft_assets VALUES('d1','a1');
    DELETE FROM lookbook_draft_entities;
    """)
    assert audit_connection(db)["finding_count"] == 0
