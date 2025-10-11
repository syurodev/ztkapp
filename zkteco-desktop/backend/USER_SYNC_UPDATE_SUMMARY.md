# User Sync Update - Employee Object Mapping

## Tổng quan

Cập nhật mapping dữ liệu user từ external API để phù hợp với response format mới, bao gồm thêm field `employee_object` (Đối tượng).

## Response API Mới

```json
{
  "status": 200,
  "message": "OK",
  "data": [
    {
      "time_clock_user_id": "4",
      "employee_id": 5983,
      "employee_name": "Đại Hỷ",
      "employee_avatar": "tRbAnh3ujRYkWbmeqhjelDmjG1hxdL",
      "employee_role": "Giám đốc",
      "employee_object_text": "Giám đốc",
      "employee_user_name": "TR000001",
      "serial_number": "PYA8252300166"
    }
  ]
}
```

## Thay đổi

### 1. Database Schema

**File:** [connection.py:274-280](src/app/database/connection.py#L274-L280)

Thêm column mới `employee_object`:

```sql
ALTER TABLE users ADD COLUMN employee_object TEXT NULL
```

Migration tự động chạy khi app khởi động.

### 2. API Response Mapping

**File:** [device_service.py:487-498](src/app/services/device_service.py#L487-L498)

**Trước đây:** (mapping sai)
```python
'full_name': employee.get('full_name') or employee.get('employee_name') or '',
'employee_code': employee.get('employee_code') or employee.get('code') or '',
'position': employee.get('position') or employee.get('title') or '',
'department': employee.get('department') or employee.get('dept_name') or '',
```

**Bây giờ:** (mapping đúng theo API mới)
```python
'full_name': employee.get('employee_name') or '',
'employee_code': employee.get('employee_user_name') or '',
'position': employee.get('employee_role') or '',
'employee_object': employee.get('employee_object_text') or '',  # ← MỚI
'department': '',  # Để trống theo yêu cầu
'notes': ''  # API không trả về
```

### 3. Sync Update Logic

**File:** [device_service.py:641-646](src/app/services/device_service.py#L641-L646)

Thêm field mới vào updates:

```python
updates['full_name'] = details.get('full_name') or ''
updates['employee_code'] = details.get('employee_code') or ''
updates['position'] = details.get('position') or ''
updates['employee_object'] = details.get('employee_object') or ''  # ← MỚI
updates['department'] = details.get('department') or ''
updates['notes'] = details.get('notes') or ''
```

### 4. Logging Update

**File:** [device_service.py:648-652](src/app/services/device_service.py#L648-L652)

Cập nhật log để hiển thị `employee_object`:

```python
app_logger.info(
    f"User {user.user_id} ({user.name}): marked as synced + mapped to employee_id={details.get('employee_id')}, "
    f"full_name={details.get('full_name')}, code={details.get('employee_code')}, "
    f"position={details.get('position')}, object={details.get('employee_object')}"  # ← MỚI
)
```

## Kết quả Mapping

### Input (API Response):
```json
{
  "time_clock_user_id": "4",
  "employee_id": 5983,
  "employee_name": "Đại Hỷ",
  "employee_avatar": "tRbAnh3ujRYkWbmeqhjelDmjG1hxdL",
  "employee_role": "Giám đốc",
  "employee_object_text": "Giám đốc",
  "employee_user_name": "TR000001",
  "serial_number": "PYA8252300166"
}
```

### Output (Database users table):

| Column | Value | Source Field |
|--------|-------|--------------|
| `user_id` | "4" | `time_clock_user_id` |
| `external_user_id` | 5983 | `employee_id` |
| `name` | *(from device)* | - |
| `full_name` | "Đại Hỷ" | `employee_name` |
| `employee_code` | "TR000001" | `employee_user_name` |
| `position` | "Giám đốc" | `employee_role` |
| `employee_object` | "Giám đốc" | `employee_object_text` ✨ **MỚI** |
| `avatar_url` | "tRbAnh3ujRYkWbmeqhjelDmjG1hxdL" | `employee_avatar` |
| `department` | "" | *(để trống)* |
| `notes` | "" | *(để trống)* |
| `serial_number` | "PYA8252300166" | `serial_number` |

## Testing

### Kiểm tra migration:

```bash
# Restart backend để chạy migration
# Check logs để xem:
# "Adding employee_object column to users table..."
# "employee_object column added to users table successfully"
```

### Kiểm tra sync:

```bash
# Gọi API sync user
curl -X POST http://localhost:57575/sync-employee

# Check logs để xem mapping:
# "User 4 (Tên User): marked as synced + mapped to employee_id=5983,
#  full_name=Đại Hỷ, code=TR000001, position=Giám đốc, object=Giám đốc"
```

### Kiểm tra database:

```sql
-- Xem user data sau khi sync
SELECT
  user_id,
  name,
  full_name,
  employee_code,
  position,
  employee_object,  -- Column mới
  department,
  external_user_id,
  avatar_url
FROM users
WHERE user_id = '4';
```

Expected result:
```
user_id: 4
name: (original name from device)
full_name: Đại Hỷ
employee_code: TR000001
position: Giám đốc
employee_object: Giám đốc  ← MỚI
department: (empty)
external_user_id: 5983
avatar_url: tRbAnh3ujRYkWbmeqhjelDmjG1hxdL
```

## Files Modified

1. ✅ [src/app/database/connection.py](src/app/database/connection.py) - Migration
2. ✅ [src/app/services/device_service.py](src/app/services/device_service.py) - Mapping & Update logic

## Backward Compatibility

- ✅ Migration tự động thêm column nếu chưa có
- ✅ Không ảnh hưởng users hiện tại (column NULL)
- ✅ Code cũ vẫn hoạt động bình thường
- ✅ Response API cũ vẫn được xử lý (fallback to empty string)

## Next Steps

1. Restart backend service để chạy migration
2. Test user sync với API mới
3. Kiểm tra data trong database
4. Update frontend UI nếu cần hiển thị "Đối tượng"

---

**Generated:** 2025-10-11
**Status:** ✅ Completed
