from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import func

from app.db import SessionLocal
from app.models import InventoryLot, InventoryStockMovement, ShopeeListing, ShopeeListingVariant, ShopeeOrder, ShopeeOrderItem


def _sum_int(value) -> int:
    return int(value or 0)


def reconcile_run(run_id: int, user_id: int, *, dry_run: bool) -> None:
    with SessionLocal() as db:
        purchase_rows = (
            db.query(
                InventoryStockMovement.product_id,
                func.coalesce(func.sum(InventoryStockMovement.qty_delta_on_hand), 0),
            )
            .filter(
                InventoryStockMovement.run_id == run_id,
                InventoryStockMovement.user_id == user_id,
                InventoryStockMovement.movement_type == "purchase_in",
                InventoryStockMovement.product_id.isnot(None),
            )
            .group_by(InventoryStockMovement.product_id)
            .all()
        )
        purchase_by_product = {int(pid): _sum_int(qty) for pid, qty in purchase_rows if pid is not None}

        sold_rows = (
            db.query(
                ShopeeListing.product_id,
                func.coalesce(func.sum(ShopeeOrderItem.quantity), 0),
            )
            .join(ShopeeOrder, ShopeeOrder.id == ShopeeOrderItem.order_id)
            .join(ShopeeListing, ShopeeListing.id == ShopeeOrder.listing_id)
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.type_bucket.in_(("shipping", "completed")),
                ShopeeListing.product_id.isnot(None),
            )
            .group_by(ShopeeListing.product_id)
            .all()
        )
        sold_by_product = {int(pid): _sum_int(qty) for pid, qty in sold_rows if pid is not None}

        lot_rows = (
            db.query(
                InventoryLot.product_id,
                func.coalesce(func.sum(InventoryLot.quantity_available), 0),
                func.coalesce(func.sum(InventoryLot.reserved_qty), 0),
            )
            .filter(InventoryLot.run_id == run_id)
            .group_by(InventoryLot.product_id)
            .all()
        )
        current_inv_by_product = {
            int(pid): _sum_int(avail) + _sum_int(reserved) for pid, avail, reserved in lot_rows if pid is not None
        }

        all_products = sorted(set(purchase_by_product.keys()) | set(current_inv_by_product.keys()) | set(sold_by_product.keys()))
        if not all_products:
            print("No product-level data found; nothing to reconcile.")
            return

        listing_rows = (
            db.query(ShopeeListing)
            .filter(
                ShopeeListing.run_id == run_id,
                ShopeeListing.user_id == user_id,
                ShopeeListing.product_id.in_(all_products),
            )
            .all()
        )
        listings_by_product: dict[int, list[ShopeeListing]] = defaultdict(list)
        for listing in listing_rows:
            if listing.product_id is not None:
                listings_by_product[int(listing.product_id)].append(listing)

        total_adjusted = 0
        for product_id in all_products:
            purchased = int(purchase_by_product.get(product_id, 0))
            sold = int(sold_by_product.get(product_id, 0))
            target_inventory_total = max(0, purchased - sold)
            current_inventory_total = int(current_inv_by_product.get(product_id, 0))
            delta = target_inventory_total - current_inventory_total

            lots = (
                db.query(InventoryLot)
                .filter(InventoryLot.run_id == run_id, InventoryLot.product_id == product_id)
                .order_by(InventoryLot.id.asc())
                .all()
            )
            if not lots:
                continue

            if delta > 0:
                # Add to earliest lot available.
                lots[0].quantity_available = max(0, int(lots[0].quantity_available or 0) + delta)
            elif delta < 0:
                need = -delta
                for lot in lots:
                    if need <= 0:
                        break
                    can_take = min(need, max(0, int(lot.quantity_available or 0)))
                    if can_take <= 0:
                        continue
                    lot.quantity_available = max(0, int(lot.quantity_available or 0) - can_take)
                    need -= can_take
                if need > 0:
                    print(f"product_id={product_id} cannot reduce enough available inventory, remaining={need}")
                    delta = -(abs(delta) - need)

            # Keep listing/variant stock_available aligned with lot-layer correction.
            applied = delta
            related_listings = listings_by_product.get(product_id, [])
            if related_listings:
                # First apply delta shift.
                if applied != 0:
                    if applied > 0:
                        listing = related_listings[0]
                        if listing.variants:
                            first_variant = sorted(list(listing.variants), key=lambda v: (int(v.sort_order or 0), int(v.id)))[0]
                            first_variant.stock = max(0, int(first_variant.stock or 0) + applied)
                        else:
                            listing.stock_available = max(0, int(listing.stock_available or 0) + applied)
                    else:
                        need = -applied
                        for listing in related_listings:
                            variants = sorted(list(listing.variants or []), key=lambda v: int(v.id), reverse=True)
                            for variant in variants:
                                if need <= 0:
                                    break
                                can_take = min(need, max(0, int(variant.stock or 0)))
                                if can_take <= 0:
                                    continue
                                variant.stock = max(0, int(variant.stock or 0) - can_take)
                                need -= can_take
                            if need <= 0:
                                break

                # Then force-align variant/listing available with lot quantity_available.
                desired_available = int(
                    db.query(func.coalesce(func.sum(InventoryLot.quantity_available), 0))
                    .filter(InventoryLot.run_id == run_id, InventoryLot.product_id == product_id)
                    .scalar()
                    or 0
                )
                current_variant_sum = int(
                    db.query(func.coalesce(func.sum(ShopeeListingVariant.stock), 0))
                    .join(ShopeeListing, ShopeeListing.id == ShopeeListingVariant.listing_id)
                    .filter(
                        ShopeeListing.run_id == run_id,
                        ShopeeListing.user_id == user_id,
                        ShopeeListing.product_id == product_id,
                    )
                    .scalar()
                    or 0
                )
                align_delta = desired_available - current_variant_sum
                if align_delta != 0:
                    if align_delta > 0:
                        listing = related_listings[0]
                        if listing.variants:
                            first_variant = sorted(list(listing.variants), key=lambda v: (int(v.sort_order or 0), int(v.id)))[0]
                            first_variant.stock = max(0, int(first_variant.stock or 0) + align_delta)
                    else:
                        need = -align_delta
                        for listing in related_listings:
                            variants = sorted(list(listing.variants or []), key=lambda v: int(v.id), reverse=True)
                            for variant in variants:
                                if need <= 0:
                                    break
                                can_take = min(need, max(0, int(variant.stock or 0)))
                                if can_take <= 0:
                                    continue
                                variant.stock = max(0, int(variant.stock or 0) - can_take)
                                need -= can_take
                            if need <= 0:
                                break
                    db.add(
                        InventoryStockMovement(
                            run_id=run_id,
                            user_id=user_id,
                            product_id=product_id,
                            movement_type="drift_reconcile",
                            qty_delta_on_hand=0,
                            qty_delta_reserved=0,
                            qty_delta_backorder=0,
                            biz_ref=f"run-{run_id}",
                            remark=f"商品可售库存对齐（目标可售={desired_available}, 当前可售={current_variant_sum}）",
                        )
                    )

                for listing in related_listings:
                    if listing.variants:
                        listing.stock_available = int(sum(max(0, int(v.stock or 0)) for v in list(listing.variants or [])))

            if delta != 0:
                db.add(
                    InventoryStockMovement(
                        run_id=run_id,
                        user_id=user_id,
                        product_id=product_id,
                        movement_type="drift_reconcile",
                        qty_delta_on_hand=int(delta),
                        qty_delta_reserved=0,
                        qty_delta_backorder=0,
                        biz_ref=f"run-{run_id}",
                        remark=f"库存守恒对账修复（目标={target_inventory_total}, 当前={current_inventory_total}）",
                    )
                )
                total_adjusted += int(delta)
                print(
                    f"product_id={product_id} purchased={purchased} sold={sold} "
                    f"current={current_inventory_total} target={target_inventory_total} delta={delta}"
                )

        if dry_run:
            db.rollback()
            print(f"DRY-RUN done, total_adjusted={total_adjusted}")
        else:
            db.commit()
            print(f"APPLIED done, total_adjusted={total_adjusted}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile inventory to conservation baseline per product.")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    reconcile_run(args.run_id, args.user_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
