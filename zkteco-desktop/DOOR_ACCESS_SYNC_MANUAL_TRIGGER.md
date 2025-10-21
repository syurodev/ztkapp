# 🔄 Manual Door Access Sync Feature

## 📋 Tổng quan

Đã thêm tính năng **sync thủ công log mở cửa** lên External API ngay từ giao diện người dùng.

---

## ✨ Tính năng mới

### 🎯 Chức năng

- **Sync logs thủ công** từ màn hình "Lịch sử mở cửa"
- **Chọn ngày** để sync (hoặc mặc định hôm nay)
- **Realtime feedback** với toast notifications
- **Loading states** để UX tốt hơn

---

## 🏗️ Kiến trúc

### Backend API

**Endpoint:** `POST /doors/access-logs/sync`

**Location:** `backend/src/app/api/doors.py:270-325`

**Request Body (Optional):**
```json
{
  "date": "2025-10-20"  // YYYY-MM-DD format, default: today
}
```

**Response Success:**
```json
{
  "success": true,
  "message": "Đã đồng bộ 15 log (5 records) cho ngày 2025-10-20",
  "data": {
    "synced_logs": 15,
    "aggregated_records": 5,
    "date": "2025-10-20"
  }
}
```

**Response Error:**
```json
{
  "success": false,
  "message": "Lỗi đồng bộ: No active device configured",
  "error": "No active device configured"
}
```

---

### Frontend API

**Location:** `frontend/src/lib/api.ts:1239-1257`

**Function:**
```typescript
doorAPI.syncDoorAccessLogs(date?: string): Promise<{
  success: boolean;
  message: string;
  data?: {
    synced_logs: number;
    aggregated_records: number;
    date: string;
  };
  error?: string;
}>
```

**Usage:**
```typescript
// Sync today
const result = await doorAPI.syncDoorAccessLogs();

// Sync specific date
const result = await doorAPI.syncDoorAccessLogs("2025-10-20");
```

---

### UI Component

**Location:** `frontend/src/components/features/DoorAccessHistory.tsx`

**Key Changes:**

1. **Import Upload icon** (line 48)
2. **Add state** `syncApiLoading` (line 88)
3. **Add handler** `handleSyncToExternalAPI()` (line 154-182)
4. **Add button** to UI (line 343-361)

---

## 🎨 UI Design

### Vị trí nút

```
┌────────────────────────────────────────────────────────────┐
│ Lịch sử mở cửa                                             │
├────────────────────────────────────────────────────────────┤
│ [Chọn cửa ▼] [Lọc theo ngày 📅] [Xóa lọc 🔍]              │
│ [Lấy lịch sử từ máy] [Đồng bộ ⬆️] [Refresh 🔄]    │
└────────────────────────────────────────────────────────────┘
```

### Button Properties

| Property | Value |
|----------|-------|
| **Variant** | `default` (primary blue) |
| **Size** | `sm` |
| **Icon** | `Upload` (⬆️) |
| **Label** | "Đồng bộ" |
| **Tooltip** | "Đồng bộ log hôm nay lên API" hoặc "Đồng bộ log cho ngày XX/XX/XXXX" |
| **Disabled** | Khi `syncApiLoading === true` |

---

## 🔄 Flow hoạt động

### 1. User clicks "Đồng bộ"

```typescript
handleSyncToExternalAPI() được gọi
  ↓
setSyncApiLoading(true)
  ↓
Lấy targetDate từ dateRange (nếu có)
  ↓
Gọi doorAPI.syncDoorAccessLogs(targetDate)
```

### 2. Backend xử lý

```python
POST /doors/access-logs/sync
  ↓
door_access_sync_service.sync_daily_door_access(target_date)
  ↓
- Get aggregated data (group by user_id, door_id, date)
- Filter valid records (có external_user_id)
- Build payload
- Send to external API
- Mark logs as synced (nếu success)
  ↓
Return result
```

### 3. Frontend nhận response

```typescript
if (response.success) {
  toast.success("Đã đồng bộ X log...")
  fetchLogs() // Refresh view
} else {
  toast.error("Lỗi đồng bộ...")
}
  ↓
setSyncApiLoading(false)
```

---

## 📊 Data Flow

### Aggregation Logic

Door access logs được **group** trước khi sync:

```sql
SELECT
    dal.user_id,
    dal.door_id,
    u.external_user_id,
    GROUP(TIME(dal.timestamp)) as timestamps,
    GROUP(dal.id) as log_ids
FROM door_access_logs dal
LEFT JOIN users u ON dal.user_id = u.id
WHERE DATE(dal.timestamp) = ?
  AND dal.is_synced = 0
GROUP BY dal.user_id, dal.door_id
```

**Example:**
```
Input: 15 individual logs
  User 1 + Door A: 08:30:00, 12:00:00, 18:00:00
  User 1 + Door B: 09:00:00
  User 2 + Door A: 10:00:00, 17:00:00
  ...

Output: 5 aggregated records
  {user_id: 1, door_id: A, data: ["08:30:00", "12:00:00", "18:00:00"]}
  {user_id: 1, door_id: B, data: ["09:00:00"]}
  {user_id: 2, door_id: A, data: ["10:00:00", "17:00:00"]}
  ...
```

### API Payload

```json
{
  "timestamp": 1729468800,
  "date": "2025-10-20",
  "device_serial": "PYA8252300166",
  "branch_id": "0",
  "door_access_data": [
    {
      "user_id": "1",
      "door_id": "2",
      "date": "2025-10-20",
      "external_user_id": "123",
      "data": ["08:30:00", "12:00:00", "18:00:00"]
    }
  ]
}
```

---

## ✅ Features

### 1. Smart Date Selection

- **Không chọn ngày:** Sync hôm nay
- **Chọn 1 ngày:** Sync ngày đó
- **Chọn range:** Sync ngày FROM

```typescript
const targetDate = dateRange?.from
  ? format(dateRange.from, "yyyy-MM-dd")
  : undefined; // Backend defaults to today
```

### 2. Visual Feedback

**Loading State:**
```tsx
{syncApiLoading ? (
  <Loader2 className="h-4 w-4 animate-spin" />
) : (
  <Upload className="h-4 w-4" />
)}
```

**Toast Notifications:**
```typescript
// Success
toast.success("Đã đồng bộ 15 log (5 records) cho ngày 2025-10-20")

// Error
toast.error("Không thể đồng bộ lên API")
```

### 3. Auto Refresh

Sau khi sync thành công, tự động refresh logs:
```typescript
if (response.success) {
  fetchLogs(); // Refresh view
}
```

---

## 🔧 Configuration

### Required Settings

1. **Active Device:** Phải có device active với serial_number
2. **Branch ID:** Setting `ACTIVE_BRANCH_ID` (default: "0")
3. **External User IDs:** Users phải có `external_user_id`

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "No active device configured" | Không có device active | Activate một device |
| "No valid records with external_user_id" | Users không có external_user_id | Map users với external API |
| "API returned status 4XX" | External API error | Check API credentials/endpoint |

---

## 🧪 Testing

### Manual Test Steps

1. **Tạo door access logs:**
   ```
   - Mở cửa từ UI hoặc từ device
   - Kiểm tra logs xuất hiện trong "Lịch sử mở cửa"
   - Verify is_synced = 0
   ```

2. **Test sync hôm nay:**
   ```
   - Không chọn filter ngày
   - Click "Đồng bộ"
   - Verify toast success
   - Check logs marked as synced (is_synced = 1)
   ```

3. **Test sync ngày cụ thể:**
   ```
   - Chọn một ngày trong quá khứ
   - Click "Đồng bộ"
   - Verify sync đúng ngày
   ```

4. **Test error cases:**
   ```
   - Deactivate tất cả devices → Expect error
   - User không có external_user_id → Expect warning
   ```

### Verify Database

```sql
-- Check synced logs
SELECT
    id,
    user_id,
    door_id,
    timestamp,
    is_synced,
    synced_at
FROM door_access_logs
WHERE DATE(timestamp) = '2025-10-20'
ORDER BY synced_at DESC;
```

---

## 📝 Logs

### Backend Logs

```
[INFO] Manual door access sync triggered for date: 2025-10-20
[INFO] Starting door access sync for date: 2025-10-20
[INFO] Sending 5 aggregated door access records (15 individual logs) to external API
[INFO] Door access sync completed: 5 aggregated records, 15 individual logs marked as synced
```

### Frontend Console

```
Making POST request to /doors/access-logs/sync
Response: {success: true, message: "Đã đồng bộ 15 log...", data: {...}}
```

---

## 🎯 Use Cases

### 1. Re-sync logs bị lỗi

Nếu cron job failed hoặc API down:
```
1. Check logs với is_synced = 0
2. Chọn ngày bị lỗi
3. Click "Đồng bộ"
4. Logs được re-sync
```

### 2. Sync on-demand

Không cần đợi cron 23:59:
```
1. User mở cửa
2. Admin muốn sync ngay
3. Click "Đồng bộ"
4. Logs được sync realtime
```

### 3. Debugging

Test external API integration:
```
1. Tạo test logs
2. Manual sync
3. Check API response
4. Debug nếu có lỗi
```

---

## 🚀 Deployment

### Checklist

- [x] Backend endpoint tested
- [x] Frontend API client added
- [x] UI button added
- [x] Error handling implemented
- [x] Toast notifications working
- [x] Loading states working
- [x] Documentation complete

### Next Steps

1. Test trên production data
2. Monitor API call success rate
3. Add retry logic nếu cần
4. Consider batch sync cho multiple dates

---

## 🔗 Related

- **Cron Sync:** `scheduler_service.py:100-110` (runs at 23:59 daily)
- **Sync Service:** `door_access_sync_service.py`
- **Repository:** `door_access_repository.py`
- **Migration Fix:** `MIGRATION_REFACTOR_SUMMARY.md`

---

## 📞 Support

Nếu gặp vấn đề:

1. Check backend logs: `backend/logs/`
2. Check browser console
3. Verify database: `door_access_logs` table
4. Check settings: device active, branch_id, external_user_ids

**Enjoy manual syncing! 🎉**
