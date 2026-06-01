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

INSERT INTO products (sku, name, brand, size_kg, price, stock_quantity, description, safety_info)
VALUES
  ('PETROLIMEX-12KG', 'Bình gas Petrolimex 12kg', 'Petrolimex', 12, 440000, 40, 'Bình gas gia đình phổ biến, phù hợp nấu ăn hằng ngày.', 'Đặt bình nơi thoáng khí, khóa van sau khi sử dụng.'),
  ('PETROLIMEX-45KG', 'Bình gas Petrolimex 45kg', 'Petrolimex', 45, 1650000, 15, 'Bình gas dung tích lớn cho nhà hàng và bếp công nghiệp.', 'Cần kỹ thuật viên kiểm tra van và dây dẫn định kỳ.'),
  ('SAIGONPETRO-6KG', 'Bình gas Saigon Petro 6kg', 'Saigon Petro', 6, 220000, 30, 'Bình nhỏ gọn cho hộ gia đình ít sử dụng.', 'Không đặt gần nguồn nhiệt hoặc ổ điện.'),
  ('SAIGONPETRO-12KG', 'Bình gas Saigon Petro 12kg', 'Saigon Petro', 12, 430000, 35, 'Bình gas gia đình giá tốt, dễ đổi bình.', 'Kiểm tra mùi gas trước và sau khi thay bình.'),
  ('TOTAL-12KG', 'Bình gas Total 12kg', 'Total Gas', 12, 445000, 25, 'Sản phẩm gas chất lượng cao cho gia đình.', 'Dùng van điều áp chính hãng và dây dẫn còn hạn.'),
  ('TOTAL-45KG', 'Bình gas Total 45kg', 'Total Gas', 45, 1680000, 10, 'Bình dung tích lớn cho nhu cầu sử dụng cao.', 'Lắp đặt tại khu vực thông thoáng, có biển cảnh báo.'),
  ('ELF-12KG', 'Bình gas Elf 12kg', 'Elf Gas', 12, 435000, 28, 'Gas gia đình ổn định, dễ sử dụng.', 'Không tự ý sửa van hoặc thay dây dẫn khi có nghi ngờ rò rỉ.'),
  ('VTGAS-12KG', 'Bình gas VT Gas 12kg', 'VT Gas', 12, 425000, 26, 'Lựa chọn tiết kiệm cho gia đình.', 'Luôn khóa van bình khi không sử dụng.'),
  ('SHELL-12KG', 'Bình gas Shell 12kg', 'Shell Gas', 12, 450000, 20, 'Thương hiệu quen thuộc, chất lượng ổn định.', 'Nếu ngửi thấy mùi gas, mở cửa và gọi hotline ngay.'),
  ('MTGAS-12KG', 'Bình gas MT Gas 12kg', 'MT Gas', 12, 420000, 22, 'Sản phẩm phù hợp nhu cầu nấu ăn hằng ngày.', 'Không để bình gas trong phòng kín.')
ON CONFLICT (sku) DO NOTHING;

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
  'Gas Quốc Cường cung cấp các thương hiệu gas phổ biến như Petrolimex, Saigon Petro, Total Gas, Elf Gas, VT Gas, Shell Gas và MT Gas. Bình 6kg phù hợp nhu cầu nhỏ, bình 12kg phù hợp gia đình, bình 45kg phù hợp nhà hàng hoặc bếp công nghiệp.',
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
