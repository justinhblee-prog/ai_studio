"""Read-only historical workspace/reference integrity audit for SQLite metadata.

The auditor never initializes schema, opens a write transaction, or mutates rows.
It is intended for pre-migration inventory and production change planning.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _tables(db: sqlite3.Connection) -> set[str]:
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def audit_connection(db: sqlite3.Connection) -> dict[str, Any]:
    """Return deterministic findings; caller supplies a read-only connection."""
    db.row_factory = sqlite3.Row
    tables = _tables(db)
    findings: list[dict[str, str]] = []

    def scan(code: str, sql: str, columns: tuple[str, ...]) -> None:
        if not set(columns).issubset(tables):
            return
        for row in db.execute(sql):
            findings.append({"code": code, **{key: str(row[key]) for key in row.keys()}})

    scan("PRODUCT_ASSET_MISSING", """SELECT pa.product_id, pa.asset_id FROM product_assets pa
        LEFT JOIN products p ON p.product_id=pa.product_id LEFT JOIN assets a ON a.asset_id=pa.asset_id
        WHERE p.product_id IS NULL OR a.asset_id IS NULL""", ("product_assets", "products", "assets"))
    scan("PRODUCT_ASSET_CROSS_WORKSPACE", """SELECT p.product_id, a.asset_id, p.workspace_id AS product_workspace,
        a.workspace_id AS asset_workspace FROM product_assets pa JOIN products p ON p.product_id=pa.product_id
        JOIN assets a ON a.asset_id=pa.asset_id WHERE p.workspace_id<>a.workspace_id""", ("product_assets", "products", "assets"))
    scan("PRODUCT_ASSET_DELETED", """SELECT p.product_id, a.asset_id FROM product_assets pa
        JOIN products p ON p.product_id=pa.product_id JOIN assets a ON a.asset_id=pa.asset_id
        WHERE a.deleted_at IS NOT NULL""", ("product_assets", "products", "assets"))
    scan("VARIANT_PARENT_MISMATCH", """SELECT pv.variant_id, pv.product_id, pv.workspace_id AS variant_workspace,
        p.workspace_id AS product_workspace FROM product_variants pv LEFT JOIN products p ON p.product_id=pv.product_id
        WHERE p.product_id IS NULL OR pv.workspace_id<>p.workspace_id""", ("product_variants", "products"))
    scan("VARIANT_ASSET_MISSING", """SELECT pva.variant_id, pva.asset_id FROM product_variant_assets pva
        LEFT JOIN product_variants pv ON pv.variant_id=pva.variant_id LEFT JOIN assets a ON a.asset_id=pva.asset_id
        WHERE pv.variant_id IS NULL OR a.asset_id IS NULL""", ("product_variant_assets", "product_variants", "assets"))
    scan("VARIANT_ASSET_CROSS_WORKSPACE", """SELECT pv.variant_id, pv.workspace_id AS variant_workspace,
        a.asset_id, a.workspace_id AS asset_workspace FROM product_variant_assets pva
        JOIN product_variants pv ON pv.variant_id=pva.variant_id JOIN products p ON p.product_id=pv.product_id
        JOIN assets a ON a.asset_id=pva.asset_id
        WHERE pv.workspace_id<>p.workspace_id OR pv.workspace_id<>a.workspace_id""", ("product_variant_assets", "product_variants", "products", "assets"))
    scan("CHARACTER_ASSET_MISSING", """SELECT ca.character_id, ca.asset_id FROM character_assets ca
        LEFT JOIN characters c ON c.character_id=ca.character_id LEFT JOIN assets a ON a.asset_id=ca.asset_id
        WHERE c.character_id IS NULL OR a.asset_id IS NULL""", ("character_assets", "characters", "assets"))
    scan("CHARACTER_ASSET_CROSS_WORKSPACE", """SELECT c.character_id, c.workspace_id AS character_workspace,
        a.asset_id, a.workspace_id AS asset_workspace FROM character_assets ca
        JOIN characters c ON c.character_id=ca.character_id JOIN assets a ON a.asset_id=ca.asset_id
        WHERE c.workspace_id<>a.workspace_id""", ("character_assets", "characters", "assets"))
    scan("CHARACTER_ASSET_DELETED", """SELECT c.character_id, a.asset_id FROM character_assets ca
        JOIN characters c ON c.character_id=ca.character_id JOIN assets a ON a.asset_id=ca.asset_id
        WHERE a.deleted_at IS NOT NULL""", ("character_assets", "characters", "assets"))
    scan("LOOKBOOK_ASSET_MISSING", """SELECT la.draft_id, la.asset_id FROM lookbook_draft_assets la
        LEFT JOIN lookbook_drafts d ON d.draft_id=la.draft_id LEFT JOIN assets a ON a.asset_id=la.asset_id
        WHERE d.draft_id IS NULL OR a.asset_id IS NULL""", ("lookbook_draft_assets", "lookbook_drafts", "assets"))
    scan("LOOKBOOK_ASSET_INVALID", """SELECT d.draft_id, d.workspace_id AS draft_workspace, a.asset_id,
        a.workspace_id AS asset_workspace FROM lookbook_draft_assets la
        JOIN lookbook_drafts d ON d.draft_id=la.draft_id JOIN assets a ON a.asset_id=la.asset_id
        WHERE d.workspace_id<>a.workspace_id OR a.deleted_at IS NOT NULL OR a.media_type NOT LIKE 'image/%'""",
        ("lookbook_draft_assets", "lookbook_drafts", "assets"))
    entity_checks = {
        "project": ("projects", "project_id"), "character": ("characters", "character_id"),
        "product": ("products", "product_id"), "product_variant": ("product_variants", "variant_id"),
    }
    if {"lookbook_draft_entities", "lookbook_drafts"}.issubset(tables):
        for entity_type, (table, pk) in entity_checks.items():
            if table not in tables:
                continue
            sql = f"""SELECT d.draft_id, e.entity_id, e.entity_type FROM lookbook_draft_entities e
                JOIN lookbook_drafts d ON d.draft_id=e.draft_id LEFT JOIN {table} x ON x.{pk}=e.entity_id
                WHERE e.entity_type=? AND (x.{pk} IS NULL OR x.workspace_id<>d.workspace_id)"""
            for row in db.execute(sql, (entity_type,)):
                findings.append({"code": "LOOKBOOK_ENTITY_MISSING_OR_CROSS_WORKSPACE", **{k: str(row[k]) for k in row.keys()}})

    findings.sort(key=lambda item: (item["code"], *(item[k] for k in sorted(item) if k != "code")))
    counts: dict[str, int] = {}
    for item in findings:
        counts[item["code"]] = counts.get(item["code"], 0) + 1
    return {"audit": "workspace-reference-integrity", "mode": "read-only", "findings": findings,
            "finding_count": len(findings), "counts_by_code": dict(sorted(counts.items()))}


def audit_database(path: str | Path) -> dict[str, Any]:
    db_path = Path(path).expanduser().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        return audit_connection(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only workspace relation integrity audit")
    parser.add_argument("database", help="Existing SQLite metadata database (opened read-only)")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    report = audit_database(args.database)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
