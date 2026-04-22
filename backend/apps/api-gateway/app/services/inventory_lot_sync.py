from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import InventoryLot


def get_lot_available_qty(
    db: Session,
    *,
    run_id: int,
    product_id: int,
) -> int:
    """Return total quantity_available across all lots for a product."""
    from sqlalchemy import func
    result = (
        db.query(func.coalesce(func.sum(InventoryLot.quantity_available), 0))
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
        )
        .scalar()
    )
    return max(0, int(result or 0))


def reserve_inventory_lots(
    db: Session,
    *,
    run_id: int,
    product_id: int,
    qty: int,
) -> int:
    """Move inventory from available -> reserved (FIFO by lot create order)."""
    need = max(0, int(qty or 0))
    if need <= 0:
        return 0

    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
            InventoryLot.quantity_available > 0,
        )
        .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
        .all()
    )
    moved = 0
    for lot in lots:
        if need <= 0:
            break
        can_take = min(need, max(0, int(lot.quantity_available or 0)))
        if can_take <= 0:
            continue
        lot.quantity_available = max(0, int(lot.quantity_available or 0) - can_take)
        lot.reserved_qty = max(0, int(lot.reserved_qty or 0) + can_take)
        moved += can_take
        need -= can_take
    return moved


def release_reserved_inventory_lots(
    db: Session,
    *,
    run_id: int,
    product_id: int,
    qty: int,
) -> int:
    """Release reserved inventory back to available."""
    need = max(0, int(qty or 0))
    if need <= 0:
        return 0

    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
            InventoryLot.reserved_qty > 0,
        )
        .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
        .all()
    )
    moved = 0
    for lot in lots:
        if need <= 0:
            break
        can_release = min(need, max(0, int(lot.reserved_qty or 0)))
        if can_release <= 0:
            continue
        lot.reserved_qty = max(0, int(lot.reserved_qty or 0) - can_release)
        lot.quantity_available = max(0, int(lot.quantity_available or 0) + can_release)
        moved += can_release
        need -= can_release

    # Backward compatibility:
    # For historical orders created before reserved_qty started维护，
    # 取消时需要把库存回补到可用库存，避免出现“无预占可释放但应回补”的情况。
    if need > 0:
        fallback_lot = (
            db.query(InventoryLot)
            .filter(
                InventoryLot.run_id == run_id,
                InventoryLot.product_id == product_id,
            )
            .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
            .first()
        )
        if fallback_lot:
            fallback_lot.quantity_available = max(0, int(fallback_lot.quantity_available or 0) + need)
    return moved


def consume_available_inventory_lots(
    db: Session,
    *,
    run_id: int,
    product_id: int,
    qty: int,
) -> int:
    """Directly consume quantity_available (for ship-time fallback when reserved was already consumed)."""
    need = max(0, int(qty or 0))
    if need <= 0:
        return 0
    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
            InventoryLot.quantity_available > 0,
        )
        .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
        .all()
    )
    consumed = 0
    for lot in lots:
        if need <= 0:
            break
        can_take = min(need, max(0, int(lot.quantity_available or 0)))
        if can_take <= 0:
            continue
        lot.quantity_available = max(0, int(lot.quantity_available or 0) - can_take)
        consumed += can_take
        need -= can_take
    return consumed


def consume_reserved_inventory_lots(
    db: Session,
    *,
    run_id: int,
    product_id: int,
    qty: int,
) -> int:
    """Consume reserved inventory when shipping out."""
    need = max(0, int(qty or 0))
    if need <= 0:
        return 0

    lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
            InventoryLot.reserved_qty > 0,
        )
        .order_by(InventoryLot.created_at.asc(), InventoryLot.id.asc())
        .all()
    )
    consumed = 0
    for lot in lots:
        if need <= 0:
            break
        can_consume = min(need, max(0, int(lot.reserved_qty or 0)))
        if can_consume <= 0:
            continue
        lot.reserved_qty = max(0, int(lot.reserved_qty or 0) - can_consume)
        consumed += can_consume
        need -= can_consume
    return consumed
