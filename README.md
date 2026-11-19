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

## Background backtest và M0–M4

Migration `0004` tạo `model_runs` và `backtest_folds`; migration `0005` bổ sung
vòng đời `queued → running → succeeded/failed`, RQ job và lỗi fold. Migration
`0006` thêm `experiment_key` để request cùng dataset/model/config có tính
idempotent; run thất bại hoặc quá timeout được phép chạy lại. Endpoint
`POST /api/v1/models/backtests` trả `202` rồi đưa M0–M4 vào Redis queue;
service `worker` chạy model tương ứng ở nền. Endpoint
`GET /api/v1/models/runs/{id}` đọc lại đầy đủ run/fold và
`GET /api/v1/models/runs/latest?model_code=M0|M1|M2|M3|M4` nhận thêm fingerprint,
horizon, cấu hình fold và hyperparameter riêng của model để chỉ lấy run cùng
experiment signature. Backtest dùng expanding window và mô phỏng as-of: tại mỗi
origin chỉ dùng đơn đã giao trước origin, train kết thúc tại
`origin - maturity_days`; holdout cuối 90 ngày không tham gia tuning. Worker dùng
JSON serializer; Redis chỉ bind localhost trong môi trường phát triển.

Frontend `/model-lab` cho phép admin/analyst cấu hình và chạy M0–M3, polling
trạng thái worker, hiển thị lỗi fold, fingerprint, MAE/RMSE/WAPE, biểu đồ
actual–prediction, decomposition Orders/AOV của M3, metric từng fold và bảng so
sánh. Manager chỉ được xem.

Benchmark leakage-safe cập nhật ngày 18/11/2026 dùng horizon/step 30 ngày, maturity 30
ngày và 8 fold, cùng giữ kín holdout 01/06–29/08/2018:

- M0 run #11: MAE `9.000,79`, RMSE `11.869,12`, WAPE `31,17%`;
- M1 run #12: MAE `10.981,88`, RMSE `13.623,32`, WAPE `38,90%`;
- M2 v1 run #13: MAE `10.897,54`, RMSE `13.656,38`, WAPE `36,79%`;
- M2.1 run #15: MAE `7.183,13`, RMSE `10.129,61`, WAPE `24,34%`.
- M3 run #17: MAE `6.539,74`, RMSE `9.285,26`, WAPE `22,15%`.
- M4 run #19: chọn `alpha=0`, MAE `6.539,74`, RMSE `9.285,26`, WAPE `22,15%`.

M2 v1 dùng feature lịch, `lead_day`, lag 1/7/14/28 và rolling mean/std 7/14/28
được chụp tại origin. Phân tích fold cho thấy model bị underprediction khi mức
doanh thu tăng. M2.1 run #15 chuẩn hóa target theo rolling mean 28 ngày tại
origin, thêm feature scale/growth và Black Friday; quality gate yêu cầu tối thiểu
21/28 ngày có revenue và cap target ratio ở `10×`. Kết quả mới: MAE `7.183,13`,
RMSE `10.129,61`, WAPE `24,34%`, thắng M0 ở 6/8 fold validation. Model/version,
seed, chính sách feature và `feature_schema_hash` đều tham gia experiment key.
Holdout chưa được đánh giá. Import thành công cũng chủ động xóa cache Analytics;
lỗi Redis không làm hỏng transaction import.

M3 tách hai LightGBM: Orders dùng objective Poisson, AOV dùng L1 và bỏ ngày AOV
null khỏi train; revenue luôn reconcile bằng `Orders × AOV`. Trên 240 prediction
validation, không thiếu component và sai số reconciliation tối đa khoảng `1e-11`.
Orders đạt MAE `48,06`, WAPE `22,62%`; AOV đạt MAE `16,94`, WAPE `12,36%`.
M3 thắng M2.1 ở 5/8 fold. M4 thử lưới alpha `0,0–1,0` trên prediction
validation ngoài mẫu và chọn `alpha=0`, tức không cải thiện so với M3. Theo quy
tắc ưu tiên model đơn giản khi metric bằng nhau, M3 vẫn là ứng viên được chọn;
holdout tiếp tục khóa.

## Kế hoạch phát triển tiếp theo

1. Persist quyết định chọn M3, tạo artifact tái lập và chỉ sau đó mở holdout 90 ngày.
2. Thêm train final, quantile, Forecast API và Forecast Center.
3. Bổ sung explain/monitoring, E2E và báo cáo thực nghiệm.

Chi tiết và trạng thái từng gate nằm trong `docs/TECH_PLAN_CODE.md`. Quy tắc bắt
buộc về cấu trúc module, an toàn dữ liệu/job, ML leakage và verification nằm trong
`AGENTS.md`.

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
