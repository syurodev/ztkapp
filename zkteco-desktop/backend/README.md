# ZKTeco RESTful API

Một REST API để quản lý thiết bị ZKTeco, bao gồm quản lý người dùng và vân tay.

## Cài đặt và Chạy

### Chạy trực tiếp với Python

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Tạo file `.env` với các biến môi trường:
```
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=true
DEVICE_IP=192.168.3.18
DEVICE_PORT=4370
PASSWORD=0
USE_MOCK_DEVICE=true
```

3. Chạy ứng dụng:
```bash
python app.py
```

Server sẽ chạy tại: http://127.0.0.1:5001

### Chạy với Docker

1. Build Docker image:
```bash
docker build -t zkteco-restful-api-image .
```

2. Chạy container:
```bash
docker run -p 4000:80 --restart always zkteco-restful-api-image
```

## API Endpoints

### User Management

#### Tạo người dùng mới
```
POST /user
Content-Type: application/json

{
  "user_id": 1,
  "user_data": {
    "name": "John Doe",
    "privilege": 0,
    "password": "123456",
    "group_id": 0,
    "card": 0
  }
}
```

#### Lấy danh sách tất cả người dùng
```
GET /users
```

#### Xóa người dùng
```
DELETE /user/{user_id}
```

### Fingerprint Management

#### Tạo vân tay cho người dùng
```
POST /user/{user_id}/fingerprint
Content-Type: application/json

{
  "temp_id": 0
}
```

#### Lấy thông tin vân tay
```
GET /user/{user_id}/fingerprint/{temp_id}
```

#### Xóa vân tay
```
DELETE /user/{user_id}/fingerprint/{temp_id}
```

### Device Management

#### Kết nối thiết bị
```
GET /device/capture
```

## Cấu trúc dự án

```
zkteco-restful-api/
├── app.py                 # Entry point
├── requirements.txt       # Dependencies
├── .env                  # Environment variables
└── zkteco/
    ├── __init__.py       # Flask app factory
    ├── config/
    │   └── settings.py   # Configuration
    ├── controllers/
    │   ├── user_controller.py
    │   └── device_controller.py
    ├── services/
    │   └── zk_service.py # ZKTeco device service
    ├── validations/
    │   └── __init__.py   # Request validation schemas
    └── logger.py         # Logging configuration
```

## Các thay đổi đã thực hiện

1. **Sửa lỗi syntax**: Đã sửa trailing comma trong `zk_service.py`
2. **Lazy loading**: Implement lazy loading cho ZkService để tránh blocking khi khởi động
3. **Python 3.12+ compatibility**: Thay thế `distutils.util.strtobool` bằng custom function
4. **Error handling**: Cải thiện error handling và logging

## Lưu ý

- **Mock Mode**: Đặt `USE_MOCK_DEVICE=true` trong `.env` để test API mà không cần thiết bị ZKTeco thật
- **Real Device**: Đặt `USE_MOCK_DEVICE=false` và đảm bảo thiết bị ZKTeco được kết nối và có thể truy cập qua mạng
- **Password**: ZKTeco devices chỉ chấp nhận password dạng số nguyên (ví dụ: `PASSWORD=0`)
- API sử dụng lazy loading để tránh blocking khi khởi động
- Tất cả các endpoint đều có error handling và logging
- Sử dụng validation schemas cho request data

## Troubleshooting

1. **Lỗi kết nối thiết bị**: Kiểm tra IP và port trong file `.env`
2. **Import errors**: Đảm bảo đã cài đặt đúng Python version và dependencies
3. **Permission errors**: Kiểm tra quyền truy cập thiết bị ZKTeco
4. **Syntax errors**: Đảm bảo sử dụng Python 3.8+ và đã cài đặt đúng dependencies

## Bypass authorization on re-running subprocess
`<your_username>` ALL=(ALL) NOPASSWD: /usr/sbin/service `<service_name>`
