from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import case, func

from app.db import SessionLocal
from app.models import InventoryStockMovement, ShopeeListing, ShopeeListingVariant, ShopeeOrder
from app.services.inventory_lot_sync import consume_reserved_inventory_lots, reserve_inventory_lots


@dataclass
class DriftRow:
    order_id: int
    order_no: str
    listing_id: int | None
    variant_id: int | None
    product_id: int | None
    reserve_on_hand_abs: int
    release_on_hand: int
    excess: int


def _collect_drift_rows(run_id: int, user_id: int) -> list[DriftRow]:
    with SessionLocal() as db:
        rows = (
            db.query(
                ShopeeOrder.id.label("order_id"),
                ShopeeOrder.order_no.label("order_no"),
                ShopeeOrder.listing_id.label("listing_id"),
                ShopeeOrder.variant_id.label("variant_id"),
                ShopeeListing.product_id.label("product_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                InventoryStockMovement.movement_type == "order_reserve",
                                -InventoryStockMovement.qty_delta_on_hand,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("reserve_on_hand_abs"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                InventoryStockMovement.movement_type == "cancel_release",
                                InventoryStockMovement.qty_delta_on_hand,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("release_on_hand"),
            )
            .join(ShopeeListing, ShopeeListing.id == ShopeeOrder.listing_id, isouter=True)
            .join(
                InventoryStockMovement,
                (InventoryStockMovement.biz_order_id == ShopeeOrder.id)
                & (InventoryStockMovement.run_id == run_id)
                & (InventoryStockMovement.user_id == user_id),
                isouter=True,
            )
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.type_bucket == "cancelled",
            )
            .group_by(
                ShopeeOrder.id,
                ShopeeOrder.order_no,
                ShopeeOrder.listing_id,
                ShopeeOrder.variant_id,
                ShopeeListing.product_id,
            )
            .all()
        )
        result: list[DriftRow] = []
        for row in rows:
            reserve_abs = max(0, int(row.reserve_on_hand_abs or 0))
            release = max(0, int(row.release_on_hand or 0))
            excess = max(0, release - reserve_abs)
            if excess <= 0:
                continue
            result.append(
                DriftRow(
                    order_id=int(row.order_id),
                    order_no=str(row.order_no or f"order-{row.order_id}"),
                    listing_id=int(row.listing_id) if row.listing_id is not None else None,
                    variant_id=int(row.variant_id) if row.variant_id is not None else None,
                    product_id=int(row.product_id) if row.product_id is not None else None,
                    reserve_on_hand_abs=reserve_abs,
                    release_on_hand=release,
                    excess=excess,
                )
            )
        return result


def _apply_for_row(run_id: int, user_id: int, row: DriftRow, *, dry_run: bool) -> int:
    with SessionLocal() as db:
        reduce_qty = int(row.excess)
        if reduce_qty <= 0:
            return 0

        reduced_from_lot = 0
        if row.product_id and row.product_id > 0:
            reserved = reserve_inventory_lots(db, run_id=run_id, product_id=int(row.product_id), qty=reduce_qty)
            consumed = consume_reserved_inventory_lots(db, run_id=run_id, product_id=int(row.product_id), qty=reserved)
            reduced_from_lot = int(consumed)

        applied = reduced_from_lot if reduced_from_lot > 0 else reduce_qty

        listing: ShopeeListing | None = None
        if row.listing_id:
            listing = (
                db.query(ShopeeListing)
                .filter(
                    ShopeeListing.id == int(row.listing_id),
                    ShopeeListing.run_id == run_id,
                    ShopeeListing.user_id == user_id,
                )
                .first()
            )

        variant: ShopeeListingVariant | None = None
        if row.variant_id:
            variant = db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id == int(row.variant_id)).first()
            if variant:
                current_stock = max(0, int(variant.stock or 0))
                variant.stock = max(0, current_stock - applied)

        if listing:
            if listing.variants:
                listing.stock_available = int(sum(max(0, int(v.stock or 0)) for v in list(listing.variants or [])))
            else:
                listing.stock_available = max(0, int(listing.stock_available or 0) - applied)

        db.add(
            InventoryStockMovement(
                run_id=run_id,
                user_id=user_id,
                product_id=int(row.product_id) if row.product_id else None,
                listing_id=int(row.listing_id) if row.listing_id else None,
                variant_id=int(row.variant_id) if row.variant_id else None,
                biz_order_id=int(row.order_id),
                movement_type="drift_reconcile",
                qty_delta_on_hand=-int(applied),
                qty_delta_reserved=0,
                qty_delta_backorder=0,
                biz_ref=row.order_no,
                remark="修复重复取消释放导致的库存漂移",
            )
        )

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return int(applied)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile duplicated cancel_release drift for one run.")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    drift_rows = _collect_drift_rows(run_id=args.run_id, user_id=args.user_id)
    if not drift_rows:
        print("No drift rows found.")
        return

    total_excess = sum(r.excess for r in drift_rows)
    print(f"Found {len(drift_rows)} drift orders, total excess={total_excess}")
    total_applied = 0
    for row in drift_rows:
        applied = _apply_for_row(args.run_id, args.user_id, row, dry_run=args.dry_run)
        total_applied += applied
        print(
            f"order={row.order_no} excess={row.excess} applied={applied} "
            f"product_id={row.product_id} listing_id={row.listing_id} variant_id={row.variant_id}"
        )

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"{mode} total applied={total_applied}")


if __name__ == "__main__":
    main()

