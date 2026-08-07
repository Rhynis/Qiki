"""Code-track six extra-brand products that exist only on the production DB.

Revision ID: 025_seed_extra_brands
Revises: 024_seed_product_details
Create Date: 2026-08-07

Data-only migration (no schema change). Issue #343: the owner added six
brand/size variants directly on production (Saigon Petro 6kg, Petrolimex
45kg, Total 12kg/45kg, Shell 12kg, MT Gas 12kg) that were never committed to
``seed.sql``. This migration brings them into the codebase so the catalog is
fully code-tracked and reproducible:

* Insert each of the six SKUs (guarded by ``NOT EXISTS``; on production the
  rows already exist, so this is a no-op there).
* Ensure the Total Gas / Shell Gas / MT Gas parents exist (Saigon Petro and
  Petrolimex parents already exist from earlier seeded SKUs).
* Group all six under their brand parent and label their variant.
* Backfill ``long_description`` per SKU from the curated Vietnamese copy
  (issue #343, verbatim).

Idempotent: the product inserts are guarded by ``NOT EXISTS``, the parent
inserts by ``ON CONFLICT``, and each ``long_description`` update only touches
rows where the column is still NULL. Each statement is a separate
``op.execute()`` because asyncpg cannot run multi-statement SQL in one
execute. Downgrade deletes the six inserted SKUs.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "025_seed_extra_brands"
down_revision: str | None = "024_seed_product_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Insert the six extra-brand products, group them, and seed long_description."""
    # 1. Insert each of the six products if the DB does not already have it
    #    (production predates this migration; a fresh seed already includes them).
    #    Mirrors the seed rows so both sources produce identical products.
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'SAIGONPETRO-6KG',
               $nm$Bình gas Saigon Petro 6kg$nm$,
               'Saigon Petro', 6, 'gas', 'kg', 220000, 30,
               $ds$Bình nhỏ gọn cho hộ gia đình ít sử dụng.$ds$,
               $si$Không đặt gần nguồn nhiệt hoặc ổ điện.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'SAIGONPETRO-6KG')"""
    )
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'PETROLIMEX-45KG',
               $nm$Bình gas Petrolimex 45kg$nm$,
               'Petrolimex', 45, 'gas', 'kg', 1650000, 15,
               $ds$Bình gas dung tích lớn cho nhà hàng và bếp công nghiệp.$ds$,
               $si$Cần kỹ thuật viên kiểm tra van và dây dẫn định kỳ.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'PETROLIMEX-45KG')"""
    )
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'TOTAL-12KG',
               $nm$Bình gas Total 12kg$nm$,
               'Total Gas', 12, 'gas', 'kg', 445000, 25,
               $ds$Sản phẩm gas chất lượng cao cho gia đình.$ds$,
               $si$Dùng van điều áp chính hãng và dây dẫn còn hạn.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'TOTAL-12KG')"""
    )
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'TOTAL-45KG',
               $nm$Bình gas Total 45kg$nm$,
               'Total Gas', 45, 'gas', 'kg', 1680000, 10,
               $ds$Bình dung tích lớn cho nhu cầu sử dụng cao.$ds$,
               $si$Lắp đặt tại khu vực thông thoáng, có biển cảnh báo.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'TOTAL-45KG')"""
    )
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'SHELL-12KG',
               $nm$Bình gas Shell 12kg$nm$,
               'Shell Gas', 12, 'gas', 'kg', 450000, 20,
               $ds$Thương hiệu quen thuộc, chất lượng ổn định.$ds$,
               $si$Nếu ngửi thấy mùi gas, mở cửa và gọi hotline ngay.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'SHELL-12KG')"""
    )
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, safety_info, is_active)
        SELECT 'MTGAS-12KG',
               $nm$Bình gas MT Gas 12kg$nm$,
               'MT Gas', 12, 'gas', 'kg', 420000, 22,
               $ds$Sản phẩm phù hợp nhu cầu nấu ăn hằng ngày.$ds$,
               $si$Không để bình gas trong phòng kín.$si$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'MTGAS-12KG')"""
    )

    # 2. Ensure the new brand parents exist (Saigon Petro and Petrolimex parents
    #    already exist from earlier seeded SKUs). One parent per (brand, category).
    op.execute(
        """INSERT INTO product_parents (name, brand, category, is_active)
        VALUES ($pp$Bình gas Total$pp$, 'Total Gas', 'gas', TRUE)
        ON CONFLICT (brand, category) DO NOTHING"""
    )
    op.execute(
        """INSERT INTO product_parents (name, brand, category, is_active)
        VALUES ($pp$Bình gas Shell$pp$, 'Shell Gas', 'gas', TRUE)
        ON CONFLICT (brand, category) DO NOTHING"""
    )
    op.execute(
        """INSERT INTO product_parents (name, brand, category, is_active)
        VALUES ($pp$Bình gas MT Gas$pp$, 'MT Gas', 'gas', TRUE)
        ON CONFLICT (brand, category) DO NOTHING"""
    )

    # 3. Group each SKU under its brand parent (re-linking Saigon Petro / Petrolimex
    #    rows to their existing parent is a harmless no-op).
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'Saigon Petro' AND category = 'gas' LIMIT 1) WHERE sku = 'SAIGONPETRO-6KG'"
    )
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'Petrolimex' AND category = 'gas' LIMIT 1) WHERE sku = 'PETROLIMEX-45KG'"
    )
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'Total Gas' AND category = 'gas' LIMIT 1) WHERE sku = 'TOTAL-12KG'"
    )
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'Total Gas' AND category = 'gas' LIMIT 1) WHERE sku = 'TOTAL-45KG'"
    )
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'Shell Gas' AND category = 'gas' LIMIT 1) WHERE sku = 'SHELL-12KG'"
    )
    op.execute(
        "UPDATE products SET parent_id = (SELECT id FROM product_parents WHERE brand = 'MT Gas' AND category = 'gas' LIMIT 1) WHERE sku = 'MTGAS-12KG'"
    )

    # 4. Label each variant for the storefront selector.
    op.execute("UPDATE products SET variant_label = $v$6 kg$v$ WHERE sku = 'SAIGONPETRO-6KG'")
    op.execute("UPDATE products SET variant_label = $v$45 kg$v$ WHERE sku = 'PETROLIMEX-45KG'")
    op.execute("UPDATE products SET variant_label = $v$12 kg$v$ WHERE sku = 'TOTAL-12KG'")
    op.execute("UPDATE products SET variant_label = $v$45 kg$v$ WHERE sku = 'TOTAL-45KG'")
    op.execute("UPDATE products SET variant_label = $v$12 kg$v$ WHERE sku = 'SHELL-12KG'")
    op.execute("UPDATE products SET variant_label = $v$12 kg$v$ WHERE sku = 'MTGAS-12KG'")

    # 5. Backfill long_description per SKU from the curated copy (only where NULL).
    op.execute(
        """UPDATE products SET long_description = $ld$Saigon Petro là thương hiệu gas của Công ty TNHH MTV Dầu khí TP. Hồ Chí Minh — doanh nghiệp nhà nước, đưa sản phẩm gas ra thị trường từ năm 1993 và hiện chiếm khoảng 20% thị phần gas dân dụng khu vực phía Nam. Bình có độ ổn định cao, mạng lưới đổi vỏ rộng khắp nội thành nên rất dễ đổi bình, phù hợp cho bếp gia đình và căn hộ nấu ăn hằng ngày. Đây là một trong hai dòng chủ lực tại Gas Quốc Cường.$ld$
        WHERE sku = 'SAIGONPETRO-6KG' AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Petrolimex Gas (PGC) thuộc Tập đoàn Xăng dầu Việt Nam (Petrolimex) — doanh nghiệp nhà nước thành lập năm 1998, có hệ thống phân phối rộng khắp cả nước và tiêu chuẩn kiểm định rõ ràng. Bình 45kg dành cho nhà hàng, quán ăn và bếp công nghiệp nấu liên tục — cần đặt nơi riêng thoáng khí, có đường ống và van điều áp phù hợp công suất bếp. Khi nhận bình nên kiểm tra tem niêm phong và thông tin kiểm định trên vỏ.$ld$
        WHERE sku = 'PETROLIMEX-45KG' AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Total (Totalgaz) là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — cùng tập đoàn với Elf. Total gia nhập thị trường LPG Việt Nam từ năm 1992 và hiện là nhà cung cấp LPG lớn thứ hai cả nước, chất lượng ổn định, thương hiệu quốc tế uy tín. Loại 12kg phù hợp bếp gia đình, quán nhỏ và văn phòng nấu ăn hằng ngày. Khi nhận bình nên kiểm tra logo, tem niêm phong và hạn kiểm định trên vỏ.$ld$
        WHERE sku = 'TOTAL-12KG' AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Total (Totalgaz) là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — cùng tập đoàn với Elf, nhà cung cấp LPG lớn thứ hai tại Việt Nam với chất lượng ổn định. Bình 45kg dành cho nhà hàng, quán ăn và bếp công nghiệp nấu liên tục — cần không gian đặt riêng thoáng khí và van điều áp phù hợp công suất. Khi nhận bình nên kiểm tra logo, tem niêm phong và hạn kiểm định trên vỏ.$ld$
        WHERE sku = 'TOTAL-45KG' AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Shell Gas là thương hiệu gas quốc tế, dành cho khách quen dùng hàng thương hiệu lớn. Bình 12kg phù hợp bếp gia đình và nhu cầu nấu ăn vừa phải. Do nguồn hàng có thể thay đổi theo khu vực, bạn nên kiểm tra tình trạng sẵn hàng trước khi đặt; không nhận bình mất niêm phong, trầy xước bất thường hoặc có mùi gas quanh van.$ld$
        WHERE sku = 'SHELL-12KG' AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$MT Gas là dòng bình gas dân dụng được nhiều khách chọn nhờ mức giá hợp lý và nguồn cung ổn định. Bình 12kg phù hợp bếp gia đình, quán ăn nhỏ và khu nhà trọ. Khi đặt, bạn nên cung cấp thương hiệu bình cũ để nhân viên kiểm tra khả năng đổi vỏ; cửa hàng luôn kiểm tra vỏ bình, van và tem trước khi lắp.$ld$
        WHERE sku = 'MTGAS-12KG' AND long_description IS NULL"""
    )


def downgrade() -> None:
    """Remove the six inserted products (parents are left in place; harmless)."""
    op.execute("DELETE FROM products WHERE sku = 'MTGAS-12KG'")
    op.execute("DELETE FROM products WHERE sku = 'SHELL-12KG'")
    op.execute("DELETE FROM products WHERE sku = 'TOTAL-45KG'")
    op.execute("DELETE FROM products WHERE sku = 'TOTAL-12KG'")
    op.execute("DELETE FROM products WHERE sku = 'PETROLIMEX-45KG'")
    op.execute("DELETE FROM products WHERE sku = 'SAIGONPETRO-6KG'")
