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
