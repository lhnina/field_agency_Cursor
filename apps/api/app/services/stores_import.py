"""Simple CSV store import (Q34) + zone ensure (Q05)."""

from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RetailChain, Store, Zone
from app.services.audit import write_audit


class ImportError_(Exception):
    pass


def ensure_zone(
    db: Session,
    *,
    organization_id: uuid.UUID,
    code: str,
    name: str | None = None,
) -> Zone:
    zone = db.scalar(
        select(Zone).where(Zone.organization_id == organization_id, Zone.code == code)
    )
    if zone:
        return zone
    zone = Zone(
        organization_id=organization_id,
        code=code,
        name=name or code,
        active=True,
    )
    db.add(zone)
    db.flush()
    return zone


def import_stores_csv(
    db: Session,
    *,
    organization_id: uuid.UUID,
    content: str,
    actor_user_id: uuid.UUID | None = None,
) -> dict:
    """
    Expected headers: chain,name,credential_name,address,zone_code
    Creates missing retail chains and zones.
    """
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ImportError_("CSV vazio")
    required = {"chain", "name", "zone_code"}
    fields = {f.strip().lower() for f in reader.fieldnames}
    if not required.issubset(fields):
        raise ImportError_("Cabeçalhos obrigatórios: chain,name,zone_code")

    created = 0
    skipped = 0
    chains_cache: dict[str, RetailChain] = {}

    for raw in reader:
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        chain_name = row.get("chain") or ""
        store_name = row.get("name") or ""
        zone_code = row.get("zone_code") or ""
        if not chain_name or not store_name or not zone_code:
            skipped += 1
            continue

        ensure_zone(db, organization_id=organization_id, code=zone_code, name=zone_code)
        if chain_name not in chains_cache:
            chain = db.scalar(
                select(RetailChain).where(
                    RetailChain.organization_id == organization_id,
                    RetailChain.name == chain_name,
                )
            )
            if not chain:
                chain = RetailChain(
                    organization_id=organization_id,
                    name=chain_name,
                    insignia=chain_name,
                )
                db.add(chain)
                db.flush()
            chains_cache[chain_name] = chain

        existing = db.scalar(
            select(Store).where(
                Store.organization_id == organization_id,
                Store.retail_chain_id == chains_cache[chain_name].id,
                Store.name == store_name,
            )
        )
        if existing:
            skipped += 1
            continue

        db.add(
            Store(
                organization_id=organization_id,
                retail_chain_id=chains_cache[chain_name].id,
                name=store_name,
                credential_name=row.get("credential_name") or store_name,
                address=row.get("address") or None,
                zone_code=zone_code,
            )
        )
        created += 1

    write_audit(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="STORES_CSV_IMPORT",
        entity_type="store",
        entity_id="bulk",
        after={"created": created, "skipped": skipped},
    )
    db.commit()
    return {"created": created, "skipped": skipped}
