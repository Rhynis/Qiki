"""Seed detailed product descriptions and make the Vihawa hot-cold variant live.

Revision ID: 024_seed_product_details
Revises: 023_add_product_sale_price
Create Date: 2026-08-05

Data-only migration (no schema change):

* Ensure the Vihawa hot-cold variant row (``VIHAWA-20L-NL``) exists on the live
  DB, group it with ``VIHAWA-20L`` under the single Vihawa parent, and label the
  two ("Bình thường" / "Bình nóng lạnh").
* Backfill ``long_description`` for every seeded SKU from the curated Vietnamese
  copy (issue #339, verbatim).

Idempotent: the variant insert is guarded by ``NOT EXISTS``, the parent by
``ON CONFLICT``, and each ``long_description`` update only touches rows where the
column is still NULL, so an admin edit is never overwritten. Each statement is a
separate ``op.execute()`` because asyncpg cannot run multi-statement SQL in one
execute. Downgrade removes the inserted variant and nulls the seeded copy.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "024_seed_product_details"
down_revision: str | None = "023_add_product_sale_price"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Insert the hot-cold Vihawa variant, group it, and seed long_description."""
    # 1. Add the hot-cold Vihawa bottle if the live DB does not already have it
    #    (production predates it; a fresh seed already includes it). Mirrors the
    #    seed row so both sources produce an identical product.
    op.execute(
        """INSERT INTO products
            (sku, name, brand, size_kg, category, unit, price, stock_quantity,
             description, pricing_note, is_active)
        SELECT 'VIHAWA-20L-NL',
               $nm$Nước Vihawa 20 lít (bình nóng lạnh)$nm$,
               'Vihawa', 20, 'nuoc_uong', 'lít', 55000, 50,
               $ds$Bình nước uống Vihawa 20 lít loại dùng cho máy nóng lạnh.$ds$,
               $pn$Giá niêm yết là giá mua tại cửa hàng. Giao hàng tận nơi +5.000đ; lên lầu +5.000đ mỗi lầu.$pn$,
               TRUE
        WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'VIHAWA-20L-NL')"""
    )

    # 2. Ensure the Vihawa parent exists (created by 018 on seeded/live DBs;
    #    guard covers a migration-only database). One parent per (brand, category).
    op.execute(
        """INSERT INTO product_parents (name, brand, category, is_active)
        VALUES ($pp$Nước Vihawa$pp$, 'Vihawa', 'nuoc_uong', TRUE)
        ON CONFLICT (brand, category) DO NOTHING"""
    )

    # 3. Group both Vihawa bottles under that parent (re-linking VIHAWA-20L to its
    #    existing parent is a harmless no-op).
    op.execute(
        """UPDATE products
        SET parent_id = (
            SELECT id FROM product_parents
            WHERE brand = 'Vihawa' AND category = 'nuoc_uong' LIMIT 1
        )
        WHERE sku IN ('VIHAWA-20L', 'VIHAWA-20L-NL')"""
    )

    # 4. Label the two variants for the storefront selector.
    op.execute("UPDATE products SET variant_label = $v$Bình thường$v$ WHERE sku = 'VIHAWA-20L'")
    op.execute(
        "UPDATE products SET variant_label = $v$Bình nóng lạnh$v$ WHERE sku = 'VIHAWA-20L-NL'"
    )

    # 5. Backfill long_description per SKU from the curated copy (only where NULL).
    op.execute(
        """UPDATE products SET long_description = $ld$Saigon Petro là thương hiệu gas của Công ty TNHH MTV Dầu khí TP. Hồ Chí Minh — doanh nghiệp nhà nước, đưa sản phẩm gas ra thị trường từ năm 1993 và hiện chiếm khoảng 20% thị phần gas dân dụng khu vực phía Nam. Bình có độ ổn định cao, mạng lưới đổi vỏ rộng khắp nội thành nên rất dễ đổi bình. Loại 12kg (vỏ xám hoặc xanh/vàng/biển) phù hợp cho bếp gia đình, căn hộ nấu ăn hằng ngày — một bình 12kg dùng trung bình khoảng 3–4 tuần cho hộ 4 người. Riêng bình 45kg (vỏ bò) dành cho nhà hàng, quán ăn, bếp công nghiệp nấu liên tục, cần đặt nơi riêng thoáng khí và có van điều áp phù hợp công suất. Đây là một trong hai dòng chủ lực tại Gas Quốc Cường.$ld$
        WHERE sku IN ('SP-12KG-XAM', 'SP-12KG-XANH', 'SP-45KG-BO') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Bình gas VT 12kg (vỏ xám) là dòng gas dân dụng có mức giá cạnh tranh và nguồn cung ổn định, phù hợp với hộ gia đình, quán ăn nhỏ và khu nhà trọ muốn tiết kiệm chi phí. Dùng tốt cho bếp gia dụng thông thường; có thể đổi vỏ nếu cùng chuẩn và tình trạng vỏ đạt yêu cầu. Khi đặt, bạn nên hỏi rõ giá đổi bình và giá mua mới để chủ động ngân sách.$ld$
        WHERE sku IN ('VT-12KG-XAM') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Elf là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — một trong những tập đoàn năng lượng lớn nhất thế giới. Total gia nhập thị trường LPG Việt Nam từ năm 1992 (công ty quốc tế đầu tiên tái giới thiệu gas tại Việt Nam) và hiện là nhà cung cấp LPG lớn thứ hai cả nước, vận hành song song hai thương hiệu Total và Elf. Bình Elf (vỏ đỏ) có chất lượng ổn định, được khách quen dùng tin tưởng. Loại 12kg phù hợp bếp gia đình nấu hằng ngày; loại 6kg nhỏ gọn cho phòng trọ, căn hộ nhỏ hoặc người ít nấu, dễ di chuyển. Nên lắp với van điều áp đúng chuẩn LPG và mua từ nhà phân phối uy tín để tránh bình sang chiết trái phép.$ld$
        WHERE sku IN ('ELF-12KG-DO', 'ELF-6KG-DO') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Petrolimex Gas (PGC) thuộc Tập đoàn Xăng dầu Việt Nam (Petrolimex) — doanh nghiệp nhà nước thành lập năm 1998, có hệ thống phân phối rộng khắp cả nước và tiêu chuẩn kiểm định rõ ràng. Bình 12kg vỏ màu xanh biển đặc trưng, phù hợp hộ gia đình nấu ăn hằng ngày. Khi nhận bình nên kiểm tra tem niêm phong, màng co và thông tin kiểm định trên vỏ.$ld$
        WHERE sku IN ('PLX-12KG-BIEN') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Bình gas Sao Mai 12kg (tại cửa hàng thường dùng loại vỏ xám) là dòng bình phổ biến, giá hợp lý và nguồn cung ổn định, phù hợp hộ gia đình nấu ăn hằng ngày. Đây là một trong hai dòng được Gas Quốc Cường dùng nhiều nhất nhờ cân bằng tốt giữa chất lượng, giá và khả năng giao nhanh trong khu vực.$ld$
        WHERE sku IN ('SAOMAI-12KG') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Gas Thủ Đức là dòng bình dân dụng quen thuộc với khách khu vực Thủ Đức – Bình Thạnh, giá hợp lý, dễ đổi vỏ tại địa phương. Loại 12kg phù hợp bếp gia đình nấu hằng ngày; loại 6kg vỏ nhựa nhỏ gọn, nhẹ, dễ di chuyển, hợp phòng trọ và người ít nấu. Bình dùng tốt với bếp gia dụng và van điều áp thông dụng.$ld$
        WHERE sku IN ('THUDUC-12KG', 'THUDUC-6KG-NHUA') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Nước uống đóng bình Vihawa 20 lít là lựa chọn quen thuộc cho gia đình, văn phòng và quán nhỏ. Bản bình thường có vòi, dùng với kệ úp bình hoặc bình bơm tay; bản dùng cho máy nóng lạnh không có vòi vì được úp trực tiếp lên cây nước nóng lạnh, giá giữ nguyên như bình thường. Giá niêm yết là giá mua tại cửa hàng; giao tận nơi và lên lầu có phụ phí, Qiki sẽ báo rõ khi đặt. Nên vệ sinh vòi và khay hứng của cây nước định kỳ để đảm bảo nước sạch.$ld$
        WHERE sku IN ('VIHAWA-20L', 'VIHAWA-20L-NL') AND long_description IS NULL"""
    )
    op.execute(
        """UPDATE products SET long_description = $ld$Nước uống đóng bình Hoàn Hảo 20 lít là lựa chọn tiết kiệm, tiện đổi bình định kỳ cho gia đình và văn phòng. Giá niêm yết là giá mua tại cửa hàng; giao tận nơi và lên lầu có phụ phí. Dùng nước trong thời gian hợp lý sau khi mở bình và đổi bình định kỳ để đảm bảo chất lượng.$ld$
        WHERE sku IN ('HOANHAO-20L') AND long_description IS NULL"""
    )


def downgrade() -> None:
    """Null the seeded descriptions and remove the inserted hot-cold variant."""
    op.execute(
        "UPDATE products SET long_description = NULL WHERE sku IN ('SP-12KG-XAM', 'SP-12KG-XANH', 'SP-45KG-BO')"
    )
    op.execute("UPDATE products SET long_description = NULL WHERE sku IN ('VT-12KG-XAM')")
    op.execute(
        "UPDATE products SET long_description = NULL WHERE sku IN ('ELF-12KG-DO', 'ELF-6KG-DO')"
    )
    op.execute("UPDATE products SET long_description = NULL WHERE sku IN ('PLX-12KG-BIEN')")
    op.execute("UPDATE products SET long_description = NULL WHERE sku IN ('SAOMAI-12KG')")
    op.execute(
        "UPDATE products SET long_description = NULL WHERE sku IN ('THUDUC-12KG', 'THUDUC-6KG-NHUA')"
    )
    op.execute(
        "UPDATE products SET long_description = NULL WHERE sku IN ('VIHAWA-20L', 'VIHAWA-20L-NL')"
    )
    op.execute("UPDATE products SET long_description = NULL WHERE sku IN ('HOANHAO-20L')")
    op.execute("DELETE FROM products WHERE sku = 'VIHAWA-20L-NL'")
