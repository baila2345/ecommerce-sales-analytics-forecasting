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

### Import CSV: product categories

Luồng import đầu tiên hỗ trợ file `product_category_name_translation.csv` và chỉ
cho phép tài khoản `admin` hoặc `analyst` thực hiện:

1. `POST /api/v1/imports/product-categories/preview` nhận multipart field `file`,
   kiểm tra UTF-8, header, dữ liệu bắt buộc và dữ liệu trùng; kết quả trả tối đa 5
   dòng preview cùng `batch_id`.
2. `POST /api/v1/imports/product-categories/{batch_id}/commit` nhận lại cùng file
   và chỉ import khi SHA-256 khớp với file đã preview.

Nếu validation thất bại, batch và lỗi theo dòng vẫn được lưu vào `import_batches`
và `import_errors`. Giao diện thực hiện luồng này tại http://localhost:5173/imports.

Module import được tách theo trách nhiệm để mở rộng từng dataset:

- `domain.py`: các kiểu dữ liệu nghiệp vụ, không phụ thuộc database.
- `file_reader.py`: đọc upload, giới hạn kích thước và tạo checksum.
- `parsers/`: parse và validation riêng cho từng loại CSV.
- `repositories.py`: truy cập `ImportBatch`, audit event và bảng đích.
- `services/`: điều phối use case preview hoặc commit và quản lý transaction.
- `factory.py`: lắp các dependency; `router.py` chỉ xử lý HTTP.

### Các dataset được hỗ trợ

Trang http://localhost:5173/imports hỗ trợ đủ 9 file Olist. Import theo thứ tự để
bảo đảm khóa ngoại:

1. `product_category_name_translation.csv`
2. `olist_customers_dataset.csv`
3. `olist_sellers_dataset.csv`
4. `olist_products_dataset.csv`
5. `olist_orders_dataset.csv`
6. `olist_order_items_dataset.csv`
7. `olist_order_payments_dataset.csv`
8. `olist_order_reviews_dataset.csv`
9. `olist_geolocation_dataset.csv`

`GET /api/v1/imports/datasets` trả metadata của tất cả dataset. Tám dataset ngoài
product categories dùng hai endpoint tổng quát:

- `POST /api/v1/imports/{dataset_slug}/preview`
- `POST /api/v1/imports/{dataset_slug}/{batch_id}/commit`

Parser kiểm tra header, kiểu dữ liệu, giá trị bắt buộc, khóa trùng và constraint
theo từng dataset. Preview cũng kiểm tra customer/order/product/seller tham chiếu
đã tồn tại. Import sử dụng upsert theo batch; riêng geolocation thay thế snapshot
cũ trong cùng transaction. Các file nhỏ trong thư mục `samples/` có thể dùng để
test thủ công theo thứ tự trên.

File Products gốc của Olist dùng hai header bị viết sai chính tả
`product_name_lenght` và `product_description_lenght`. Importer nhận đúng header
nguồn này và ánh xạ sang các cột chuẩn `product_name_length` và
`product_description_length` trong MySQL.

## Analytics Dashboard

Dashboard tại http://localhost:5173/analytics dành cho `admin`, `analyst` và
`manager`. Báo cáo hỗ trợ lọc theo khoảng ngày mua hàng, bang khách hàng, danh
mục sản phẩm và seller; bộ lọc hiện tại được giữ nguyên khi export CSV.

Quy ước KPI:

- Doanh thu là tổng `order_items.price` của đơn có trạng thái `delivered`.
- Khách hàng được đếm theo `customer_unique_id`.
- Giá trị đơn trung bình bằng doanh thu chia số đơn đã giao.
- Thời gian giao hàng tính từ `order_purchase_timestamp` đến
  `order_delivered_customer_date`.

Các endpoint:

- `GET /api/v1/analytics/dashboard`: KPI, xu hướng, trạng thái đơn, sản phẩm,
  seller, khu vực và hiệu suất giao hàng.
- `GET /api/v1/analytics/filters`: miền giá trị cho bộ lọc.
- `GET /api/v1/analytics/export`: tải báo cáo CSV theo cùng bộ lọc.

Dashboard chỉ JOIN các bảng cần cho từng báo cáo và tính delivery aggregate trong
MySQL. Response Dashboard được cache trong Redis 60 giây theo bộ lọc; frontend
dùng chung request đang chờ để React `StrictMode` không gọi trùng endpoint. Nếu
Redis không khả dụng, Dashboard vẫn truy vấn database bình thường. Bước tiếp theo
là chủ động xóa cache sau commit import thay vì chỉ chờ TTL.

## Data Quality

Sau khi import đủ 9 file, tài khoản `admin`, `analyst` hoặc `manager` có thể gọi
`GET /api/v1/datasets/quality`. Báo cáo chỉ đọc dữ liệu và trả về:

- row count và khoảng thời gian của snapshot;
- kiểm tra bảng rỗng, khóa ngoại mồ côi và chuỗi timestamp đơn hàng;
- category/dimensions sản phẩm bị thiếu, giá trị tiền và tọa độ bất thường;
- đối soát tổng item, freight, payment và số đơn chênh lệch;
- trạng thái tổng `passed`, `warning` hoặc `failed`, kèm số dòng ảnh hưởng của
  từng check.

Snapshot Olist hiện tại có đủ 9 bảng và không có khóa ngoại mồ côi. Báo cáo phát
hiện 8 đơn `delivered` thiếu ngày giao hàng; đây là lỗi chặn cần có chính sách loại
khỏi chuỗi trưởng thành trước khi dựng `daily_sales`. Các thiếu hụt nguồn khác vẫn
được giữ dưới dạng warning để quá trình làm sạch có thể truy vết, không sửa dữ liệu
gốc im lặng.

Chính sách `olist-ml-quality-v1` giữ dữ liệu nguồn và tạo tập đủ điều kiện riêng:
chỉ nhận đơn `delivered` có item, có ngày giao và ngày giao không trước ngày mua.
Snapshot hiện giữ 96.470/96.478 đơn delivered; 8 đơn và 8 item, tương ứng
`1.249,18` doanh thu, bị loại khỏi ML. Có 197 đơn không được dùng cho feature thời
gian giao hàng; 610 sản phẩm thiếu category được chiếu thành `unknown`. API trả
`ready_for_daily_sales=true`, nên có thể dựng aggregate mà không cần sửa/xóa raw.

## Dataset fingerprint và daily sales

Migration `0003` tạo `dataset_snapshots` và `daily_sales`. Fingerprint SHA-256
được tính xác định từ checksum mới nhất của đủ 9 dataset, `daily-sales-v2`,
`olist-ml-quality-v1`, lịch nguồn, khoảng ngày và `maturity_days`. Timestamp chạy
job không tham gia fingerprint nên cùng input luôn sinh cùng ID dữ liệu.

Các endpoint dành cho `admin`/`analyst`; `manager` được quyền đọc:

- `GET /api/v1/datasets/fingerprint?maturity_days=30`: xem fingerprint trước khi
  build.
- `POST /api/v1/datasets/daily-sales/rebuild?maturity_days=30`: chạy quality gate,
  tạo/cập nhật snapshot và điền đủ lịch ngày.
- `GET /api/v1/datasets/snapshots/latest`: xem snapshot mới nhất cùng reconciliation.

Ngày không có đơn được lưu với revenue/orders/customer/items bằng `0`, AOV là
`null`. Snapshot mới sẽ là `ready`; khi bất kỳ nguồn nào được import lại, snapshot
`ready` tự chuyển thành `stale`. `daily-sales-v2` cũng chặn phần đuôi giả bằng
cách không cho mature cutoff vượt quá ngày mua cuối có đơn delivered hợp lệ.
Phân phối giao hàng hiện tại có P95 là 29 ngày, vì vậy snapshot dùng
`maturity_days=30` và cho kết quả:

- fingerprint `3f851c685e1c5f7bdd6ad779c133487c101aab0c0336fa7893e1ea9840718dec`;
- 774 ngày từ 04/09/2016 đến 17/10/2018, trong đó 725 ngày mature đến 29/08/2018;
- 96.470 order, 110.189 item và revenue `13.220.248,93`.

## Baseline M0

Migration `0004` tạo `model_runs` và `backtest_folds`. Endpoint
`POST /api/v1/models/backtests` chạy Seasonal Naive chu kỳ 7 ngày; endpoint
`GET /api/v1/models/runs/{id}` đọc lại đầy đủ run/fold và
`GET /api/v1/models/runs/latest` lấy run M0 mới nhất. Backtest dùng expanding
window, không đọc actual tương lai khi dự báo nhiều bước và không dùng holdout
cuối 90 ngày trong tuning.

Frontend `/model-lab` cho phép admin/analyst cấu hình và chạy M0, đồng thời hiển
thị fingerprint, quality policy, MAE/RMSE/WAPE, biểu đồ actual–prediction và
metric từng fold. Manager có quyền xem kết quả nhưng không được khởi chạy run.

Run M0 đầu tiên dùng horizon/step 30 ngày, có 9 fold và giữ kín holdout
01/06–29/08/2018. Kết quả validation: MAE trung bình `9.497,66`, RMSE
`12.441,22`, WAPE `34,75%`. Holdout chưa được đánh giá và chỉ mở sau khi đã so
sánh/chọn model. Import thành công cũng chủ động xóa cache Analytics; lỗi Redis
không làm hỏng transaction import.

## Kế hoạch phát triển tiếp theo

1. Thêm worker cho model job dài và mở rộng Model Lab với SARIMA M1 trên cùng fold.
2. Triển khai LightGBM direct, Orders × AOV và ensemble M2–M4.
3. So sánh M0–M4, chốt model trước khi mở holdout 90 ngày.
4. Thêm train final, quantile, Forecast API và Forecast Center.

Chi tiết và trạng thái từng gate nằm trong `docs/TECH_PLAN_CODE.md`.

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
