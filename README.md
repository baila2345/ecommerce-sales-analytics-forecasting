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
