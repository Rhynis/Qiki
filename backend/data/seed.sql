-- Seed data for Gas Quốc Cường local development.

INSERT INTO users (email, full_name, phone, role)
VALUES
  ('admin1@gasbot.vn', 'Nguyễn Minh Anh', '+84901234501', 'admin'),
  ('admin2@gasbot.vn', 'Trần Quốc Bảo', '+84901234502', 'admin'),
  ('admin3@gasbot.vn', 'Lê Hoàng Linh', '+84901234503', 'admin'),
  ('staff1@gasbot.vn', 'Phạm Thu Hà', '+84901234504', 'staff'),
  ('staff2@gasbot.vn', 'Võ Minh Khang', '+84901234505', 'staff'),
  ('staff3@gasbot.vn', 'Đặng Gia Huy', '+84901234506', 'staff'),
  ('staff4@gasbot.vn', 'Bùi Thanh Tâm', '+84901234507', 'staff'),
  ('staff5@gasbot.vn', 'Hoàng Ngọc Mai', '+84901234508', 'staff')
ON CONFLICT (email) DO NOTHING;

UPDATE products
SET is_active = false
WHERE category = 'gas'
  AND sku NOT IN (
    'SP-12KG-XAM',
    'SP-12KG-XANH',
    'SP-45KG-BO',
    'VT-12KG-XAM',
    'ELF-12KG-DO',
    'ELF-6KG-DO',
    'PLX-12KG-BIEN',
    'SAOMAI-12KG',
    'THUDUC-12KG',
    'THUDUC-6KG-NHUA'
  );

INSERT INTO products (
  sku,
  name,
  brand,
  size_kg,
  category,
  unit,
  price,
  stock_quantity,
  description,
  safety_info,
  pricing_note
)
VALUES
  ('SP-12KG-XAM', 'Bình gas Saigon Petro 12kg (xám)', 'Saigon Petro', 12, 'gas', 'kg', 605000, 50, 'Bình gas Saigon Petro vỏ xám 12kg cho gia đình.', NULL, NULL),
  ('SP-12KG-XANH', 'Bình gas Saigon Petro 12kg (xanh/vàng/biển)', 'Saigon Petro', 12, 'gas', 'kg', 665000, 50, 'Bình gas Saigon Petro vỏ xanh/vàng/biển 12kg.', NULL, NULL),
  ('SP-45KG-BO', 'Bình gas Saigon Petro 45kg (bò)', 'Saigon Petro', 45, 'gas', 'kg', 2250000, 20, 'Bình gas Saigon Petro 45kg cho nhà hàng, bếp công nghiệp.', NULL, NULL),
  ('VT-12KG-XAM', 'Bình gas VT 12kg (xám)', 'VT Gas', 12, 'gas', 'kg', 605000, 50, 'Bình gas VT vỏ xám 12kg cho gia đình.', NULL, NULL),
  ('ELF-12KG-DO', 'Bình gas Elf 12kg (đỏ)', 'Elf Gas', 12, 'gas', 'kg', 710000, 50, 'Bình gas Elf vỏ đỏ 12kg cho gia đình.', NULL, NULL),
  ('ELF-6KG-DO', 'Bình gas Elf 6kg (đỏ)', 'Elf Gas', 6, 'gas', 'kg', 350000, 50, 'Bình gas Elf 6kg nhỏ gọn cho hộ ít dùng.', NULL, NULL),
  ('PLX-12KG-BIEN', 'Bình gas Petrolimex 12kg (biển)', 'Petrolimex', 12, 'gas', 'kg', 675000, 50, 'Bình gas Petrolimex vỏ biển 12kg cho gia đình.', NULL, NULL),
  ('SAOMAI-12KG', 'Bình gas Sao Mai 12kg', 'Sao Mai', 12, 'gas', 'kg', 625000, 50, 'Bình gas Sao Mai 12kg cho gia đình.', NULL, NULL),
  ('THUDUC-12KG', 'Bình gas Thủ Đức 12kg', 'Gas Thủ Đức', 12, 'gas', 'kg', 625000, 50, 'Bình gas Thủ Đức 12kg cho gia đình.', NULL, NULL),
  ('THUDUC-6KG-NHUA', 'Bình gas Thủ Đức 6kg (vỏ nhựa)', 'Gas Thủ Đức', 6, 'gas', 'kg', 320000, 50, 'Bình gas Thủ Đức 6kg vỏ nhựa, nhỏ gọn.', NULL, NULL),
  ('SAIGONPETRO-6KG', 'Bình gas Saigon Petro 6kg', 'Saigon Petro', 6, 'gas', 'kg', 220000, 30, 'Bình nhỏ gọn cho hộ gia đình ít sử dụng.', 'Không đặt gần nguồn nhiệt hoặc ổ điện.', NULL),
  ('PETROLIMEX-45KG', 'Bình gas Petrolimex 45kg', 'Petrolimex', 45, 'gas', 'kg', 1650000, 15, 'Bình gas dung tích lớn cho nhà hàng và bếp công nghiệp.', 'Cần kỹ thuật viên kiểm tra van và dây dẫn định kỳ.', NULL),
  ('TOTAL-12KG', 'Bình gas Total 12kg', 'Total Gas', 12, 'gas', 'kg', 445000, 25, 'Sản phẩm gas chất lượng cao cho gia đình.', 'Dùng van điều áp chính hãng và dây dẫn còn hạn.', NULL),
  ('TOTAL-45KG', 'Bình gas Total 45kg', 'Total Gas', 45, 'gas', 'kg', 1680000, 10, 'Bình dung tích lớn cho nhu cầu sử dụng cao.', 'Lắp đặt tại khu vực thông thoáng, có biển cảnh báo.', NULL),
  ('SHELL-12KG', 'Bình gas Shell 12kg', 'Shell Gas', 12, 'gas', 'kg', 450000, 20, 'Thương hiệu quen thuộc, chất lượng ổn định.', 'Nếu ngửi thấy mùi gas, mở cửa và gọi hotline ngay.', NULL),
  ('MTGAS-12KG', 'Bình gas MT Gas 12kg', 'MT Gas', 12, 'gas', 'kg', 420000, 22, 'Sản phẩm phù hợp nhu cầu nấu ăn hằng ngày.', 'Không để bình gas trong phòng kín.', NULL),
  ('VIHAWA-20L', 'Nước Vihawa 20 lít', 'Vihawa', 20, 'nuoc_uong', 'lít', 55000, 50, 'Bình nước uống Vihawa 20 lít dùng cho gia đình và văn phòng.', NULL, 'Giá niêm yết là giá mua tại cửa hàng. Giao hàng tận nơi +5.000đ; lên lầu +5.000đ mỗi lầu.'),
  -- Vihawa also comes as a hot-cold ("bình nóng lạnh") bottle; the price here is a
  -- placeholder until the owner sets the real one.
  ('VIHAWA-20L-NL', 'Nước Vihawa 20 lít (bình nóng lạnh)', 'Vihawa', 20, 'nuoc_uong', 'lít', 55000, 50, 'Bình nước uống Vihawa 20 lít loại dùng cho máy nóng lạnh.', NULL, 'Giá niêm yết là giá mua tại cửa hàng. Giao hàng tận nơi +5.000đ; lên lầu +5.000đ mỗi lầu.'),
  ('HOANHAO-20L', 'Nước Hoàn Hảo 20 lít', 'Hoàn Hảo', 20, 'nuoc_uong', 'lít', 15000, 50, 'Bình nước uống Hoàn Hảo 20 lít tiện đổi bình định kỳ.', NULL, 'Giá niêm yết là giá mua tại cửa hàng. Giao hàng tận nơi +5.000đ; lên lầu +5.000đ mỗi lầu.')
ON CONFLICT (sku) DO UPDATE SET
  name = EXCLUDED.name,
  brand = EXCLUDED.brand,
  size_kg = EXCLUDED.size_kg,
  category = EXCLUDED.category,
  unit = EXCLUDED.unit,
  price = EXCLUDED.price,
  stock_quantity = EXCLUDED.stock_quantity,
  description = EXCLUDED.description,
  safety_info = EXCLUDED.safety_info,
  pricing_note = EXCLUDED.pricing_note,
  is_active = true;

-- Group seeded products under a parent per (brand, category) so the storefront
-- shows one card per brand with selectable colour/size variants. Mirrors the
-- 017_add_product_variants data migration for idempotent local re-seeds.
INSERT INTO product_parents (name, brand, category, description, image_url, is_active)
SELECT DISTINCT ON (p.brand, p.category)
    btrim(
        regexp_replace(
            regexp_replace(p.name, '\s*\([^)]*\)\s*$', ''),
            '\s*\d+([.,]\d+)?\s*(kg|lít|l)\y',
            '',
            'gi'
        )
    ) AS name,
    p.brand,
    p.category,
    p.description,
    p.image_url,
    TRUE
FROM products p
ORDER BY p.brand, p.category, p.created_at
ON CONFLICT (brand, category) DO NOTHING;

UPDATE products p
SET parent_id = pp.id
FROM product_parents pp
WHERE p.brand = pp.brand AND p.category = pp.category;

UPDATE products
SET colour = trim(substring(name FROM '\(([^)]*)\)\s*$'))
WHERE name ~ '\([^)]*\)\s*$';

UPDATE products
SET variant_label = trim(
    btrim(
        (rtrim(to_char(size_kg, 'FM999999990.99'), '.') || ' ' || unit)
        || CASE WHEN colour IS NOT NULL AND colour <> ''
                THEN ' (' || colour || ')' ELSE '' END
    )
);

-- Vihawa 20L is offered as a normal bottle and a hot-cold ("bình nóng lạnh") one;
-- label the two variants explicitly (the generic label above is size-only for water).
UPDATE products SET variant_label = 'Bình thường' WHERE sku = 'VIHAWA-20L';
UPDATE products SET variant_label = 'Bình nóng lạnh' WHERE sku = 'VIHAWA-20L-NL';

-- Detailed product descriptions (long_description). Kept in sync with data
-- migration 024_seed_product_details; a fresh seed sets the same copy.
UPDATE products SET long_description = $ld$Saigon Petro là thương hiệu gas của Công ty TNHH MTV Dầu khí TP. Hồ Chí Minh — doanh nghiệp nhà nước, đưa sản phẩm gas ra thị trường từ năm 1993 và hiện chiếm khoảng 20% thị phần gas dân dụng khu vực phía Nam. Bình có độ ổn định cao, mạng lưới đổi vỏ rộng khắp nội thành nên rất dễ đổi bình. Loại 12kg (vỏ xám hoặc xanh/vàng/biển) phù hợp cho bếp gia đình, căn hộ nấu ăn hằng ngày — một bình 12kg dùng trung bình khoảng 3–4 tuần cho hộ 4 người. Riêng bình 45kg (vỏ bò) dành cho nhà hàng, quán ăn, bếp công nghiệp nấu liên tục, cần đặt nơi riêng thoáng khí và có van điều áp phù hợp công suất. Đây là một trong hai dòng chủ lực tại Gas Quốc Cường.$ld$ WHERE sku IN ('SP-12KG-XAM', 'SP-12KG-XANH', 'SP-45KG-BO');
UPDATE products SET long_description = $ld$Bình gas VT 12kg (vỏ xám) là dòng gas dân dụng có mức giá cạnh tranh và nguồn cung ổn định, phù hợp với hộ gia đình, quán ăn nhỏ và khu nhà trọ muốn tiết kiệm chi phí. Dùng tốt cho bếp gia dụng thông thường; có thể đổi vỏ nếu cùng chuẩn và tình trạng vỏ đạt yêu cầu. Khi đặt, bạn nên hỏi rõ giá đổi bình và giá mua mới để chủ động ngân sách.$ld$ WHERE sku IN ('VT-12KG-XAM');
UPDATE products SET long_description = $ld$Elf là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — một trong những tập đoàn năng lượng lớn nhất thế giới. Total gia nhập thị trường LPG Việt Nam từ năm 1992 (công ty quốc tế đầu tiên tái giới thiệu gas tại Việt Nam) và hiện là nhà cung cấp LPG lớn thứ hai cả nước, vận hành song song hai thương hiệu Total và Elf. Bình Elf (vỏ đỏ) có chất lượng ổn định, được khách quen dùng tin tưởng. Loại 12kg phù hợp bếp gia đình nấu hằng ngày; loại 6kg nhỏ gọn cho phòng trọ, căn hộ nhỏ hoặc người ít nấu, dễ di chuyển. Nên lắp với van điều áp đúng chuẩn LPG và mua từ nhà phân phối uy tín để tránh bình sang chiết trái phép.$ld$ WHERE sku IN ('ELF-12KG-DO', 'ELF-6KG-DO');
UPDATE products SET long_description = $ld$Petrolimex Gas (PGC) thuộc Tập đoàn Xăng dầu Việt Nam (Petrolimex) — doanh nghiệp nhà nước thành lập năm 1998, có hệ thống phân phối rộng khắp cả nước và tiêu chuẩn kiểm định rõ ràng. Bình 12kg vỏ màu xanh biển đặc trưng, phù hợp hộ gia đình nấu ăn hằng ngày. Khi nhận bình nên kiểm tra tem niêm phong, màng co và thông tin kiểm định trên vỏ.$ld$ WHERE sku IN ('PLX-12KG-BIEN');
UPDATE products SET long_description = $ld$Bình gas Sao Mai 12kg (tại cửa hàng thường dùng loại vỏ xám) là dòng bình phổ biến, giá hợp lý và nguồn cung ổn định, phù hợp hộ gia đình nấu ăn hằng ngày. Đây là một trong hai dòng được Gas Quốc Cường dùng nhiều nhất nhờ cân bằng tốt giữa chất lượng, giá và khả năng giao nhanh trong khu vực.$ld$ WHERE sku IN ('SAOMAI-12KG');
UPDATE products SET long_description = $ld$Gas Thủ Đức là dòng bình dân dụng quen thuộc với khách khu vực Thủ Đức – Bình Thạnh, giá hợp lý, dễ đổi vỏ tại địa phương. Loại 12kg phù hợp bếp gia đình nấu hằng ngày; loại 6kg vỏ nhựa nhỏ gọn, nhẹ, dễ di chuyển, hợp phòng trọ và người ít nấu. Bình dùng tốt với bếp gia dụng và van điều áp thông dụng.$ld$ WHERE sku IN ('THUDUC-12KG', 'THUDUC-6KG-NHUA');
UPDATE products SET long_description = $ld$Nước uống đóng bình Vihawa 20 lít là lựa chọn quen thuộc cho gia đình, văn phòng và quán nhỏ. Bản bình thường có vòi, dùng với kệ úp bình hoặc bình bơm tay; bản dùng cho máy nóng lạnh không có vòi vì được úp trực tiếp lên cây nước nóng lạnh, giá giữ nguyên như bình thường. Giá niêm yết là giá mua tại cửa hàng; giao tận nơi và lên lầu có phụ phí, Qiki sẽ báo rõ khi đặt. Nên vệ sinh vòi và khay hứng của cây nước định kỳ để đảm bảo nước sạch.$ld$ WHERE sku IN ('VIHAWA-20L', 'VIHAWA-20L-NL');
UPDATE products SET long_description = $ld$Nước uống đóng bình Hoàn Hảo 20 lít là lựa chọn tiết kiệm, tiện đổi bình định kỳ cho gia đình và văn phòng. Giá niêm yết là giá mua tại cửa hàng; giao tận nơi và lên lầu có phụ phí. Dùng nước trong thời gian hợp lý sau khi mở bình và đổi bình định kỳ để đảm bảo chất lượng.$ld$ WHERE sku IN ('HOANHAO-20L');
UPDATE products SET long_description = $ld$Saigon Petro là thương hiệu gas của Công ty TNHH MTV Dầu khí TP. Hồ Chí Minh — doanh nghiệp nhà nước, đưa sản phẩm gas ra thị trường từ năm 1993 và hiện chiếm khoảng 20% thị phần gas dân dụng khu vực phía Nam. Bình có độ ổn định cao, mạng lưới đổi vỏ rộng khắp nội thành nên rất dễ đổi bình, phù hợp cho bếp gia đình và căn hộ nấu ăn hằng ngày. Đây là một trong hai dòng chủ lực tại Gas Quốc Cường.$ld$ WHERE sku IN ('SAIGONPETRO-6KG');
UPDATE products SET long_description = $ld$Petrolimex Gas (PGC) thuộc Tập đoàn Xăng dầu Việt Nam (Petrolimex) — doanh nghiệp nhà nước thành lập năm 1998, có hệ thống phân phối rộng khắp cả nước và tiêu chuẩn kiểm định rõ ràng. Bình 45kg dành cho nhà hàng, quán ăn và bếp công nghiệp nấu liên tục — cần đặt nơi riêng thoáng khí, có đường ống và van điều áp phù hợp công suất bếp. Khi nhận bình nên kiểm tra tem niêm phong và thông tin kiểm định trên vỏ.$ld$ WHERE sku IN ('PETROLIMEX-45KG');
UPDATE products SET long_description = $ld$Total (Totalgaz) là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — cùng tập đoàn với Elf. Total gia nhập thị trường LPG Việt Nam từ năm 1992 và hiện là nhà cung cấp LPG lớn thứ hai cả nước, chất lượng ổn định, thương hiệu quốc tế uy tín. Loại 12kg phù hợp bếp gia đình, quán nhỏ và văn phòng nấu ăn hằng ngày. Khi nhận bình nên kiểm tra logo, tem niêm phong và hạn kiểm định trên vỏ.$ld$ WHERE sku IN ('TOTAL-12KG');
UPDATE products SET long_description = $ld$Total (Totalgaz) là thương hiệu gas quốc tế thuộc tập đoàn TotalEnergies (Pháp) — cùng tập đoàn với Elf, nhà cung cấp LPG lớn thứ hai tại Việt Nam với chất lượng ổn định. Bình 45kg dành cho nhà hàng, quán ăn và bếp công nghiệp nấu liên tục — cần không gian đặt riêng thoáng khí và van điều áp phù hợp công suất. Khi nhận bình nên kiểm tra logo, tem niêm phong và hạn kiểm định trên vỏ.$ld$ WHERE sku IN ('TOTAL-45KG');
UPDATE products SET long_description = $ld$Shell Gas là thương hiệu gas quốc tế, dành cho khách quen dùng hàng thương hiệu lớn. Bình 12kg phù hợp bếp gia đình và nhu cầu nấu ăn vừa phải. Do nguồn hàng có thể thay đổi theo khu vực, bạn nên kiểm tra tình trạng sẵn hàng trước khi đặt; không nhận bình mất niêm phong, trầy xước bất thường hoặc có mùi gas quanh van.$ld$ WHERE sku IN ('SHELL-12KG');
UPDATE products SET long_description = $ld$MT Gas là dòng bình gas dân dụng được nhiều khách chọn nhờ mức giá hợp lý và nguồn cung ổn định. Bình 12kg phù hợp bếp gia đình, quán ăn nhỏ và khu nhà trọ. Khi đặt, bạn nên cung cấp thương hiệu bình cũ để nhân viên kiểm tra khả năng đổi vỏ; cửa hàng luôn kiểm tra vỏ bình, van và tem trước khi lắp.$ld$ WHERE sku IN ('MTGAS-12KG');

INSERT INTO knowledge_base (title, content, category, source, embedding)
SELECT
  'Hướng dẫn an toàn gas số ' || gs::text,
  'Khi sử dụng gas trong gia đình, khách hàng cần đặt bình ở nơi thông thoáng, khóa van sau khi dùng, kiểm tra dây dẫn định kỳ và liên hệ kỹ thuật viên khi nghi ngờ rò rỉ. Nếu ngửi thấy mùi gas, không bật tắt thiết bị điện, mở cửa thông gió, gọi 114 hoặc 115 trước, sau đó gọi hotline 090 3026306 nếu cần hỗ trợ từ cửa hàng.',
  'safety',
  'seed_data',
  array_fill(0.0::float8, ARRAY[768])::vector
FROM generate_series(1, 15) AS gs
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_base (title, content, category, source, embedding)
SELECT
  'Thông tin sản phẩm gas số ' || gs::text,
  'Gas Quốc Cường cung cấp các thương hiệu gas phổ biến như Saigon Petro, VT Gas, Elf Gas, Petrolimex, Sao Mai và Gas Thủ Đức. Bình 6kg phù hợp nhu cầu nhỏ, bình 12kg phù hợp gia đình, bình 45kg phù hợp nhà hàng hoặc bếp công nghiệp.',
  'product_info',
  'seed_data',
  array_fill(0.0::float8, ARRAY[768])::vector
FROM generate_series(1, 15) AS gs
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_base (title, content, category, source, embedding)
SELECT
  'Thông tin giao hàng số ' || gs::text,
  'Gas Quốc Cường hỗ trợ giao hàng tại Bình Thạnh và Thủ Đức. Thời gian giao hàng phụ thuộc vào phường, tuyến giao và tình trạng giao thông. Khách cần cung cấp số nhà, đường, phường và mốc gần nhà để điều phối chính xác.',
  'delivery',
  'seed_data',
  array_fill(0.0::float8, ARRAY[768])::vector
FROM generate_series(1, 10) AS gs
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_base (title, content, category, source, embedding)
SELECT
  'Câu hỏi thường gặp số ' || gs::text,
  'Khách hàng có thể đặt hàng không cần tài khoản, tra cứu đơn bằng mã đơn và số điện thoại, yêu cầu hóa đơn VAT khi thanh toán, và liên hệ hotline 090 3026306 để được hỗ trợ nhanh.',
  'faq',
  'seed_data',
  array_fill(0.0::float8, ARRAY[768])::vector
FROM generate_series(1, 5) AS gs
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_base (title, content, category, source, embedding)
SELECT
  'Thông tin công ty số ' || gs::text,
  'Cửa hàng Gas Quốc Cường là cửa hàng gas LPG tại TP. Hồ Chí Minh với trợ lý ảo Qiki hỗ trợ tư vấn sản phẩm, đặt hàng và cung cấp thông tin an toàn cho khách hàng.',
  'company',
  'seed_data',
  array_fill(0.0::float8, ARRAY[768])::vector
FROM generate_series(1, 5) AS gs
ON CONFLICT DO NOTHING;
