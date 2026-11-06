# E-commerce Sales Analytics & Revenue Forecasting

Hệ thống phân tích dữ liệu bán hàng và dự báo doanh thu thương mại điện tử.

## Docker development foundation

### Yêu cầu

- Docker Engine 28+
- Docker Compose v2.34+

### Khởi động

Từ thư mục gốc của dự án:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Các địa chỉ phát triển:

- Frontend: http://localhost:5173
- API health: http://localhost:8000/health
- OpenAPI/Swagger: http://localhost:8000/docs
- phpMyAdmin: http://localhost:8080
- MySQL: `localhost:3306`
- Redis: `localhost:6379`

### Xem log

```bash
docker compose logs -f
docker compose logs -f api
docker compose logs -f web
```

### Dừng hệ thống

```bash
docker compose down
```

Lệnh trên giữ nguyên dữ liệu trong named volumes. Chỉ dùng `down -v` khi thực sự muốn xóa dữ liệu MySQL, Redis và dependencies volume của frontend.

## Database migrations

Sau khi MySQL và API đã chạy:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

Kiểm tra các bảng trong MySQL:

```bash
docker compose exec mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SHOW TABLES;"'
```

Chạy kiểm thử backend:

```bash
docker compose exec api pytest -q
```

## Olist database schema

Migration `0002` tạo schema phân tích cho toàn bộ Brazilian E-Commerce Public
Dataset by Olist:

- `customers` và `orders`: khách hàng cùng vòng đời đơn hàng.
- `order_items`, `products`, `product_categories`, `sellers`: chi tiết sản phẩm,
  giá, phí vận chuyển, danh mục và người bán.
- `order_payments` và `order_reviews`: thanh toán và đánh giá.
- `geolocations`: nhiều tọa độ có thể cùng thuộc một ZIP prefix, vì vậy bảng dùng
  khóa chính nội bộ và không tạo quan hệ một-một với customer/seller.
- `import_batches` và `import_errors`: lịch sử file CSV, checksum, trạng thái,
  thống kê số dòng và lỗi theo dòng.

Thứ tự import bảo đảm khóa ngoại:

1. Product category translation, customers và sellers.
2. Products và orders.
3. Order items, payments và reviews.
4. Geolocations có thể import độc lập.

Áp dụng và kiểm tra migration:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic check
```

## Authentication

Sau khi migration đã chạy, tạo tài khoản admin từ `ADMIN_EMAIL` và
`ADMIN_PASSWORD` trong file `.env`:

```bash
docker compose exec api python -m app.scripts.seed_admin
```

Lệnh seed có thể chạy lại an toàn và không tạo tài khoản trùng. Kiểm thử API tại
http://localhost:8000/docs với các endpoint:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

Giao diện đăng nhập tại http://localhost:5173. Sử dụng `ADMIN_EMAIL` và
`ADMIN_PASSWORD` trong `.env` sau khi đã chạy lệnh seed. Access token chỉ được
lưu trong `sessionStorage`; mật khẩu không được lưu trên trình duyệt.

Kiểm tra frontend trong Docker:

```bash
docker compose run --rm --no-deps web npm run typecheck
docker compose run --rm --no-deps web npm test
docker compose run --rm --no-deps web npm run build
docker compose run --rm --no-deps web npm audit
```
