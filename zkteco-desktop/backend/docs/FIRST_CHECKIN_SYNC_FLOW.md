# First Checkin Sync Cron - Luồng Xử Lý Chi Tiết

> **Version**: 1.0
> **Last Updated**: 2025-10-19
> **Status**: ✅ Active sau refactor pyzatt

---

## 📋 Tổng Quan

### Thông Tin Cơ Bản

| Thuộc tính | Giá trị |
|------------|---------|
| **Tên Cron** | First Checkin Sync |
| **Job ID** | `first_checkin_sync` |
| **Tần suất** | **Mỗi 30 giây** |
| **File** | `scheduler_service.py:204-264` |
| **Mục đích** | Đồng bộ nhanh users và first check-ins từ DB → External API |
| **Trigger** | `IntervalTrigger(seconds=30)` |
| **Max Instances** | 1 (không chạy đồng thời) |

### Đặc Điểm

- ✅ **Real-time sync**: Độ trễ tối đa 30 giây
- ✅ **Compatible với pyzatt**: Không gọi device trực tiếp
- ✅ **Pull & Push devices**: Hoạt động với cả 2 loại
- ✅ **Anti-duplicate**: Logic phòng ngừa trùng lặp
- ✅ **Error recovery**: Retry tối đa 100 lần/record

---

## 🔄 Luồng Xử Lý Tổng Quát

```
┌─────────────────────────────────────────────┐
│   First Checkin Sync Cron (Every 30s)      │
└─────────────────────────────────────────────┘
                    ↓
        ┌──────────────────────┐
        │   STEP 1: User Sync  │
        │  (DB → External API) │
        └──────────────────────┘
                    ↓
        Sync unsynced users từ DB
        sang External API
                    ↓
        Mark users as synced
                    ↓
        ┌──────────────────────────────┐
        │   STEP 2: Attendance Sync    │
        │   (DB → External API)        │
        └──────────────────────────────┘
                    ↓
        Query PENDING attendance từ DB
                    ↓
        Calculate first checkins
                    ↓
        Apply anti-duplicate logic
                    ↓
        Filter by external_user_id
                    ↓
        Batch processing (100/batch)
                    ↓
        Send to External API
                    ↓
        Process API response
                    ↓
        Update DB status (SYNCED/ERROR/SKIPPED)
                    ↓
                Complete
```

---

## 📊 STEP 1: User Sync (DB → External API)

### Flow Diagram

```
scheduler_service._run_first_checkin_sync()
    │
    ├─→ zk_service.sync_employee()  ✅ [RESTORED]
    │       │
    │       ├─→ 1. Get Unsynced Users
    │       │      user_repo.get_unsynced_users(device_id)
    │       │      Query: SELECT * FROM users WHERE is_synced = FALSE
    │       │      ↓
    │       │      Returns: List[User]
    │       │
    │       ├─→ 2. Get Device Config
    │       │      config_manager.get_device(device_id)
    │       │      ↓
    │       │      Extract: device_serial, device_id
    │       │
    │       ├─→ 3. Prepare Employee Data
    │       │      For each user:
    │       │      {
    │       │        'userId': user.user_id,
    │       │        'name': user.name,
    │       │        'card': user.card,
    │       │        'privilege': user.privilege,
    │       │        'password': user.password
    │       │      }
    │       │
    │       ├─→ 4. Call External API
    │       │      external_api_service.sync_employees(employees, serial_number)
    │       │      ↓
    │       │      POST /time-clock-employees/sync
    │       │      Headers:
    │       │        - x-api-key: {api_key}
    │       │        - x-device-sync: {serial_number}
    │       │        - x-branch-id: {branch_id}
    │       │        - ProjectId: {project_id}
    │       │      Body:
    │       │      {
    │       │        "timestamp": 1697712000,
    │       │        "employees": [...]
    │       │      }
    │       │
    │       └─→ 5. Mark as Synced (if success)
    │              If response.status == 200:
    │                  For each user:
    │                      user_repo.mark_as_synced(user.id)
    │                      → UPDATE users
    │                        SET is_synced = TRUE, synced_at = NOW()
    │                        WHERE id = ?
    │
    └─→ Return Result
           {
             'success': True,
             'synced_users_count': 5,
             'employees_count': 5,
             'message': 'Synced 5 users to external API'
           }
```

### Code Reference

**File**: `device_service.py:227-306`

```python
def sync_employee(self, device_id: str = None):
    """
    Sync unsynced users from local DB to external API
    NOTE: This does NOT fetch from device - it syncs DB users to external API
    Works for both pull and push devices
    """
    # 1. Get unsynced users
    unsynced_users = user_repo.get_unsynced_users(target_device_id)

    # 2. Get device config
    device_config = config_manager.get_device(target_device_id)
    device_serial = device_config.get('serial_number', target_device_id)

    # 3. Prepare employee data
    employees = []
    for user in unsynced_users:
        employee_data = {
            'userId': user.user_id,
            'name': user.name,
            'card': user.card or '',
            'privilege': user.privilege,
            'password': user.password or '',
        }
        employees.append(employee_data)

    # 4. Sync to external API
    sync_result = external_api_service.sync_employees(employees, device_serial)

    # 5. Mark as synced if successful
    if sync_result.get('status') == 200:
        for user in unsynced_users:
            user_repo.mark_as_synced(user.id)
```

### Return Formats

#### Success (có users cần sync)
```json
{
  "success": true,
  "message": "Synced 5 users to external API",
  "synced_users_count": 5,
  "employees_count": 5,
  "response": {
    "status": 200,
    "data": {...}
  }
}
```

#### Success (không có users)
```json
{
  "success": true,
  "message": "No unsynced users to sync",
  "synced_users_count": 0,
  "employees_count": 0
}
```

#### Error
```json
{
  "success": false,
  "error": "No device configuration found",
  "synced_users_count": 0,
  "employees_count": 0
}
```

### Logging

```
User sync to external API: 5/5 users synced              # INFO
User sync: no unsynced users to process                  # DEBUG
User sync to external API failed: Connection timeout     # WARNING
Error syncing users to external API: ValueError(...)     # ERROR
```

---

## 📊 STEP 2: Attendance Sync (DB → External API)

### Flow Diagram

```
attendance_sync_service.sync_first_checkins()
    │
    ├─→ 1. Determine Sync Date
    │      sync_date = target_date or date.today()
    │      → Default: ngày hôm nay
    │
    ├─→ 2. Calculate Daily Attendance with Dedup
    │      │
    │      ├─→ 2.1: Calculate with IDs
    │      │      _calculate_daily_attendance_with_ids(sync_date, device_id)
    │      │      │
    │      │      ├─→ Query Attendance Logs
    │      │      │      start_datetime = sync_date 00:00:00
    │      │      │      end_datetime = sync_date 23:59:59
    │      │      │
    │      │      │      Query:
    │      │      │      SELECT * FROM attendance_logs
    │      │      │      WHERE timestamp BETWEEN ? AND ?
    │      │      │        AND sync_status IN ('pending', 'error')
    │      │      │        AND COALESCE(error_count, 0) < 100
    │      │      │        [AND device_id = ?]
    │      │      │      ORDER BY user_id, timestamp
    │      │      │
    │      │      ├─→ Group by user_id
    │      │      │      user_logs = defaultdict(list)
    │      │      │      for log in logs:
    │      │      │          user_logs[log['user_id']].append(log)
    │      │      │
    │      │      ├─→ Separate Checkins/Checkouts
    │      │      │      For each user_id:
    │      │      │          checkins = [log WHERE action=0]
    │      │      │          checkouts = [log WHERE action=1]
    │      │      │
    │      │      ├─→ Calculate First/Last
    │      │      │      first_checkin_log = MIN(checkins by timestamp)
    │      │      │      first_checkin = first_checkin_log.timestamp
    │      │      │      first_checkin_id = first_checkin_log.id
    │      │      │
    │      │      │      last_checkout_log = MAX(checkouts by timestamp)
    │      │      │      last_checkout = last_checkout_log.timestamp
    │      │      │      last_checkout_id = last_checkout_log.id
    │      │      │
    │      │      ├─→ Get User Mappings
    │      │      │      users = user_repo.get_all(device_id)
    │      │      │      user_name_map = {user.user_id: user.name}
    │      │      │      user_external_id_map = {user.user_id: user.external_user_id}
    │      │      │
    │      │      └─→ Build Summary
    │      │             attendance_summary = [
    │      │               {
    │      │                 'user_id': '001',
    │      │                 'name': 'John Doe',
    │      │                 'external_user_id': 123,
    │      │                 'first_checkin': '2025-10-19 08:00:00',
    │      │                 'first_checkin_id': 456,
    │      │                 'last_checkout': '2025-10-19 17:30:00',
    │      │                 'last_checkout_id': 789,
    │      │                 'total_checkins': 2,
    │      │                 'total_checkouts': 1
    │      │               },
    │      │               ...
    │      │             ]
    │      │
    │      └─→ 2.2: Apply Anti-Duplicate Logic
    │             _calculate_daily_attendance_with_dedup()
    │             │
    │             For each user_summary:
    │                 │
    │                 ├─→ Check Synced Checkin
    │                 │      has_synced_checkin = attendance_repo.has_synced_record_for_date_action(
    │                 │          user_id, sync_date, action=0  # 0 = checkin
    │                 │      )
    │                 │
    │                 │      Query:
    │                 │      SELECT COUNT(*) FROM attendance_logs
    │                 │      WHERE user_id = ?
    │                 │        AND DATE(timestamp) = ?
    │                 │        AND action = 0
    │                 │        AND sync_status = 'synced'
    │                 │
    │                 │      If has_synced_checkin == True:
    │                 │          user_summary['first_checkin'] = None
    │                 │          user_summary['first_checkin_id'] = None
    │                 │
    │                 ├─→ Check Synced Checkout
    │                 │      has_synced_checkout = attendance_repo.has_synced_record_for_date_action(
    │                 │          user_id, sync_date, action=1  # 1 = checkout
    │                 │      )
    │                 │
    │                 │      If has_synced_checkout == True:
    │                 │          user_summary['last_checkout'] = None
    │                 │          user_summary['last_checkout_id'] = None
    │                 │
    │                 └─→ Filter
    │                        Only include if:
    │                            first_checkin OR last_checkout exists
    │
    │             Return: final_summary (deduplicated)
    │
    ├─→ 3. Prepare for API (ONLY Checkins)
    │      │
    │      ├─→ Get Device Serial
    │      │      device = config_manager.get_device(device_id)
    │      │      serial_number = device.get('serial_number', device_id)
    │      │
    │      ├─→ Add Metadata to Each Summary
    │      │      For each user_summary:
    │      │          user_summary['date'] = str(sync_date)
    │      │          user_summary['device_id'] = device_id
    │      │          user_summary['device_serial'] = serial_number
    │      │          user_summary['last_checkout'] = None       ⚠️ FORCE NULL
    │      │          user_summary['last_checkout_id'] = None    ⚠️ FORCE NULL
    │      │
    │      └─→ Filter Valid Summaries
    │             valid_summaries = [
    │                 summary
    │                 for summary in attendance_summary
    │                 if summary.get('first_checkin')                    # Has checkin
    │                    AND (summary.get('external_user_id') or 0) > 0  # Has external ID
    │             ]
    │
    ├─→ 4. Batch Processing
    │      │
    │      MAX_RECORDS_PER_REQUEST = 100
    │      total_batches = ceil(len(valid_summaries) / 100)
    │      │
    │      For batch_index, batch in enumerate(batches):
    │          │
    │          ├─→ Send to External API
    │          │      _send_to_external_api(batch, sync_date, device_id)
    │          │      │
    │          │      ├─→ Prepare Payload
    │          │      │      sync_data = {
    │          │      │          'timestamp': int(time.time()),
    │          │      │          'date': str(sync_date),
    │          │      │          'device_id': device_id,
    │          │      │          'device_serial': serial_number,
    │          │      │          'checkin_data_list': batch
    │          │      │      }
    │          │      │
    │          │      ├─→ Call API
    │          │      │      external_api_service.sync_checkin_data(sync_data, serial_number)
    │          │      │
    │          │      │      POST /time-clock-employees/sync-checkin-data
    │          │      │      Headers:
    │          │      │        - x-api-key: {api_key}
    │          │      │        - x-device-sync: {serial_number}
    │          │      │        - x-branch-id: {branch_id}
    │          │      │        - ProjectId: {project_id}
    │          │      │      Body:
    │          │      │      {
    │          │      │        "timestamp": 1697712000,
    │          │      │        "date": "2025-10-19",
    │          │      │        "device_serial": "ABC12345",
    │          │      │        "checkin_data_list": [
    │          │      │          {
    │          │      │            "user_id": "001",
    │          │      │            "name": "John Doe",
    │          │      │            "external_user_id": 123,
    │          │      │            "first_checkin": "2025-10-19 08:00:00",
    │          │      │            "first_checkin_id": 456,
    │          │      │            "last_checkout": null,
    │          │      │            "last_checkout_id": null,
    │          │      │            "total_checkins": 2,
    │          │      │            "total_checkouts": 0
    │          │      │          }
    │          │      │        ]
    │          │      │      }
    │          │      │
    │          │      └─→ Return
    │          │             {
    │          │               'status_code': 200,
    │          │               'response_data': {...},
    │          │               'sent_count': len(batch)
    │          │             }
    │          │
    │          ├─→ Check Response Status
    │          │      If sync_result.get('error'):
    │          │          → Stop processing
    │          │          → Return error
    │          │
    │          │      response_data = sync_result.get('response_data')
    │          │      status = response_data.get('status')
    │          │
    │          │      If status not in (200, 201):
    │          │          → Process partial response
    │          │          → Return error
    │          │
    │          └─→ Process API Response
    │                 _process_api_response(response_data, batch)
    │                 │
    │                 ├─→ Process Success Operations
    │                 │      success_operations = response_data['data']['successOperations']
    │                 │
    │                 │      For each success:
    │                 │          operation_id = success['operationId']  # first_checkin_id
    │                 │
    │                 │          attendance_repo.update_sync_status(
    │                 │              operation_id,
    │                 │              SyncStatus.SYNCED
    │                 │          )
    │                 │
    │                 │          UPDATE attendance_logs
    │                 │          SET sync_status = 'synced',
    │                 │              is_synced = TRUE,
    │                 │              synced_at = NOW()
    │                 │          WHERE id = ?
    │                 │
    │                 ├─→ Process Errors
    │                 │      errors = response_data['data']['errors']
    │                 │
    │                 │      For each error:
    │                 │          user_id = error['userId']
    │                 │          operation = error['operation']  # 'CHECKIN' or 'CHECKOUT'
    │                 │          record_id = error['firstCheckinId'] or error['lastCheckoutId']
    │                 │          error_code = error['errorCode']
    │                 │          error_message = error['errorMessage']
    │                 │
    │                 │          attendance_repo.update_sync_error(
    │                 │              record_id,
    │                 │              error_code,
    │                 │              error_message,
    │                 │              increment=True  # error_count++
    │                 │          )
    │                 │
    │                 │          UPDATE attendance_logs
    │                 │          SET sync_status = 'error',
    │                 │              error_code = ?,
    │                 │              error_message = ?,
    │                 │              error_count = COALESCE(error_count, 0) + 1
    │                 │          WHERE id = ?
    │                 │
    │                 └─→ Mark Other Records as Skipped
    │                        For each user_summary in batch:
    │                            user_id = user_summary['user_id']
    │                            date = user_summary['date']
    │
    │                            If first_checkin_id was processed:
    │                                first_checkin_id = user_summary['first_checkin_id']
    │
    │                                # Get other checkin records for same user/date
    │                                other_record_ids = attendance_repo.get_other_records_for_date_action(
    │                                    user_id,
    │                                    date,
    │                                    action=0,  # checkin
    │                                    exclude_id=first_checkin_id
    │                                )
    │
    │                                Query:
    │                                SELECT id FROM attendance_logs
    │                                WHERE user_id = ?
    │                                  AND DATE(timestamp) = ?
    │                                  AND action = 0
    │                                  AND id != ?
    │
    │                                # Mark as skipped
    │                                attendance_repo.mark_records_as_skipped(other_record_ids)
    │
    │                                UPDATE attendance_logs
    │                                SET sync_status = 'skipped'
    │                                WHERE id IN (...)
    │
    └─→ 5. Return Result
           {
             'success': True,
             'date': '2025-10-19',
             'count': 15,
             'synced_records': 15
           }
```

### Code Reference

**File**: `attendance_sync_service.py:185-305`

```python
def sync_first_checkins(self, target_date: Optional[str] = None, device_id: Optional[str] = None):
    """Sync only first check-ins for the target date (defaults to today)."""
    # 1. Determine target date
    sync_date = datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else date.today()

    # 2. Calculate with dedup
    attendance_summary = self._calculate_daily_attendance_with_dedup(sync_date, device_id)

    # 3. Prepare for API (only checkins)
    for user_summary in attendance_summary:
        user_summary['date'] = str(sync_date)
        user_summary['device_serial'] = serial_number
        user_summary['last_checkout'] = None  # ⚠️ FORCE NULL
        user_summary['last_checkout_id'] = None

    # 4. Filter valid
    valid_summaries = [
        summary for summary in attendance_summary
        if summary.get('first_checkin') and (summary.get('external_user_id') or 0) > 0
    ]

    # 5. Batch processing
    for batch in self._iter_record_batches(valid_summaries, 100):
        sync_result = self._send_to_external_api(batch, sync_date, device_id)
        self._process_api_response(sync_result['response_data'], batch)
```

### Return Formats

#### Success (có attendance)
```json
{
  "success": true,
  "date": "2025-10-19",
  "count": 15,
  "synced_records": 15
}
```

#### Success (không có attendance)
```json
{
  "success": true,
  "message": "No pending first checkins found",
  "date": "2025-10-19",
  "count": 0,
  "synced_records": 0
}
```

#### Error
```json
{
  "success": false,
  "error": "External API returned status 500",
  "date": "2025-10-19",
  "count": 15,
  "synced_records": 5
}
```

---

## 🎯 Điểm Quan Trọng

### 1. Chỉ Sync First Check-ins

**Code**: `attendance_sync_service.py:242-244`

```python
user_summary['last_checkout'] = None
user_summary['last_checkout_id'] = None
```

**Lý do**:
- ⚡ Real-time sync cho check-in (mỗi 30s)
- ⏰ Check-out sẽ được sync trong daily sync (23:59)
- 🚫 Tránh sync checkout chưa hoàn chỉnh (user chưa checkout cuối ngày)

### 2. Filter External User ID

**Code**: `attendance_sync_service.py:247-251`

```python
valid_summaries = [
    summary for summary in attendance_summary
    if summary.get('first_checkin')
       AND (summary.get('external_user_id') or 0) > 0
]
```

**Lý do**:
- 🔑 External API cần `external_user_id` để map user
- ❌ Users chưa có `external_user_id` → chưa được sync sang external system
- ✅ Tránh gửi data không hợp lệ sang API

### 3. Anti-Duplicate Protection (3 Layers)

#### Layer 1: Database Constraint
```sql
-- attendance_logs table
UNIQUE CONSTRAINT (user_id, device_id, timestamp, method, action)
```

#### Layer 2: Dedup Before Sync
```python
has_synced_checkin = attendance_repo.has_synced_record_for_date_action(
    user_id, target_date, action=0
)
if has_synced_checkin:
    user_summary['first_checkin'] = None  # Skip
```

#### Layer 3: Mark Others as Skipped
```python
# After syncing first checkin
other_record_ids = attendance_repo.get_other_records_for_date_action(
    user_id, date, action=0, exclude_id=first_checkin_id
)
attendance_repo.mark_records_as_skipped(other_record_ids)
```

**Kết quả**:
- ✅ Mỗi user chỉ có **1 checkin/ngày** được sync
- ✅ Các checkin khác → `sync_status = 'skipped'`
- ✅ Không duplicate trên external API

### 4. Error Handling & Retry

**Query Condition**:
```sql
WHERE sync_status IN ('pending', 'error')
  AND COALESCE(error_count, 0) < 100
```

**On Error**:
```python
attendance_repo.update_sync_error(
    record_id,
    error_code,
    error_message,
    increment=True  # error_count++
)
```

**Behavior**:
- ✅ Error count 1-99: Vẫn retry trong lần sync tiếp theo
- ❌ Error count ≥100: **Dừng retry**, bỏ qua record
- 🔍 Admin cần check error summary để fix manual

### 5. Batch Processing

```python
MAX_RECORDS_PER_REQUEST = 100

for batch in _iter_record_batches(valid_summaries, 100):
    _send_to_external_api(batch, ...)
```

**Lý do**:
- 📦 API có giới hạn request size
- ⏱️ Tránh timeout cho request lớn
- 🛡️ Better error handling (fail 1 batch không ảnh hưởng batch khác)

---

## 📊 Data Flow: Pull vs Push Devices

### Pull Devices (Manual Sync)

```
┌──────────────────────────────────────────┐
│  User triggers manual sync               │
└──────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────┐
│  API: POST /devices/{id}/sync-attendance │
└──────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────┐
│  device_service.get_attendance()         │
│  ✅ Đã refactor pyzatt                   │
└──────────────────────────────────────────┘
                ↓
        z.connect_net(ip, port)  ← pyzatt ZKSS
        z.read_att_log()
                ↓
        pyzatt_logs = z.att_log  ← List[ATTen]
                ↓
┌──────────────────────────────────────────┐
│  Convert to PyzkAttendance (compat)      │
└──────────────────────────────────────────┘
                ↓
        adapted_log = PyzkAttendance(
            user_id=log.user_id,
            timestamp=log.att_time,
            status=log.ver_state,
            punch=log.ver_type,
            uid=log.user_sn
        )
                ↓
┌──────────────────────────────────────────┐
│  Create AttendanceLog objects            │
└──────────────────────────────────────────┘
                ↓
        AttendanceLog(
            user_id=str(record.user_id),
            timestamp=record.timestamp,
            method=record.status,
            action=record.punch,
            device_id=target_device_id,
            sync_status=SyncStatus.PENDING,  ← ⚠️
            is_synced=False,
            raw_data={'sync_source': 'pyzatt_sync'}
        )
                ↓
┌──────────────────────────────────────────┐
│  attendance_repo.bulk_insert_ignore()    │
└──────────────────────────────────────────┘
                ↓
        INSERT OR IGNORE INTO attendance_logs
        (unique constraint prevents duplicates)
                ↓
┌──────────────────────────────────────────┐
│  Records in DB with PENDING status       │
└──────────────────────────────────────────┘
                ↓
        [After 30s]
                ↓
┌──────────────────────────────────────────┐
│  First Checkin Sync Cron                 │
└──────────────────────────────────────────┘
                ↓
        Query PENDING records
                ↓
        Sync to External API
                ↓
        Update status: SYNCED/ERROR/SKIPPED
```

### Push Devices (Auto Push)

```
┌──────────────────────────────────────────┐
│  Device sends event automatically        │
└──────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────┐
│  Push Protocol Service receives event    │
└──────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────┐
│  Create AttendanceLog                    │
└──────────────────────────────────────────┘
                ↓
        AttendanceLog(
            user_id=event.user_id,
            timestamp=event.timestamp,
            method=event.method,
            action=event.action,
            sync_status=SyncStatus.PENDING,  ← ⚠️
            raw_data={'sync_source': 'push_protocol'}
        )
                ↓
┌──────────────────────────────────────────┐
│  attendance_repo.add_attendance(log)     │
└──────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────┐
│  Records in DB with PENDING status       │
└──────────────────────────────────────────┘
                ↓
        [After 30s]
                ↓
┌──────────────────────────────────────────┐
│  First Checkin Sync Cron                 │
└──────────────────────────────────────────┘
                ↓
        Query PENDING records
                ↓
        Sync to External API
                ↓
        Update status: SYNCED/ERROR/SKIPPED
```

### Kết Luận

✅ **Cả 2 loại device đều đổ data vào DB với PENDING status**
✅ **Cron không phân biệt nguồn, chỉ sync PENDING records**
✅ **Compatible với pyzatt vì không gọi device trong cron**

---

## 🚨 Edge Cases & Error Scenarios

### Case 1: No Unsynced Users

**Flow**:
```
sync_employee()
    ↓
user_repo.get_unsynced_users() → []
    ↓
Return: {
  'success': True,
  'synced_users_count': 0,
  'employees_count': 0
}
    ↓
Cron log: "User sync: no unsynced users to process" (DEBUG)
    ↓
✅ Continue to Step 2
```

### Case 2: No Pending Attendance

**Flow**:
```
sync_first_checkins()
    ↓
_calculate_daily_attendance_with_dedup() → []
    ↓
Return: {
  'success': True,
  'message': 'No pending first checkins found',
  'count': 0
}
    ↓
Cron log: "First checkin sync: no pending attendance records" (DEBUG)
    ↓
✅ Cron complete successfully
```

### Case 3: User Has No external_user_id

**Flow**:
```
attendance_summary has users
    ↓
Filter: (summary.get('external_user_id') or 0) > 0
    ↓
All filtered out
    ↓
valid_summaries = []
    ↓
Return: {
  'success': True,
  'count': 0,
  'synced_records': 0,
  'message': 'No valid first checkins to sync'
}
    ↓
Cron log: "No first checkin records available after filtering, skipping sync"
```

**Fix**: User cần được sync từ device → DB → External API để có `external_user_id`

### Case 4: External API Returns Error

**Flow**:
```
_send_to_external_api()
    ↓
Response: {"status": 500, "message": "Internal server error"}
    ↓
sync_first_checkins() returns:
{
  'success': False,
  'error': 'External API returned status 500',
  'synced_records': 0
}
    ↓
_process_api_response() still called
    ↓
Records marked as ERROR
error_count incremented
    ↓
Cron log: "First checkin sync returned error: ..." (WARNING)
    ↓
✅ Next cron (after 30s) will retry
```

### Case 5: Partial Batch Failure

**Flow**:
```
Batch 1/3: Success → 50 records synced
    ↓
Batch 2/3: API Error 500
    ↓
Stop processing remaining batches
    ↓
Return: {
  'success': False,
  'error': 'External API returned status 500',
  'synced_records': 50,
  'count': 150
}
```

**Result**:
- ✅ Batch 1 records: SYNCED
- ❌ Batch 2 records: ERROR
- ⏸️ Batch 3 records: PENDING (retry next cron)

### Case 6: Device Not Configured

**Flow**:
```
sync_employee()
    ↓
config_manager.get_device(device_id) → None
    ↓
Return: {
  'success': False,
  'error': 'No device configuration found'
}
    ↓
Cron logs warning
    ↓
✅ Continue to Step 2 (attendance sync)
```

### Case 7: Record Error Count = 100

**Flow**:
```
Query attendance_logs:
WHERE sync_status IN ('pending', 'error')
  AND COALESCE(error_count, 0) < 100
    ↓
Record with error_count=100 is EXCLUDED
    ↓
⚠️ Record will NOT be retried
    ↓
Admin needs to check error_summary and fix manually
```

---

## 📊 Database Schema

### attendance_logs Table

```sql
CREATE TABLE attendance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    method INTEGER,           -- verification method (fingerprint, face, etc)
    action INTEGER,           -- 0=checkin, 1=checkout
    sync_status TEXT DEFAULT 'pending',  -- pending, synced, error, skipped
    is_synced BOOLEAN DEFAULT 0,
    synced_at DATETIME,
    error_code TEXT,
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    serial_number TEXT,
    raw_data TEXT,           -- JSON string
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint prevents duplicates
    UNIQUE(user_id, device_id, timestamp, method, action),

    FOREIGN KEY (device_id) REFERENCES devices(id)
);

-- Indexes for performance
CREATE INDEX idx_attendance_sync_status ON attendance_logs(sync_status);
CREATE INDEX idx_attendance_timestamp ON attendance_logs(timestamp);
CREATE INDEX idx_attendance_user_id ON attendance_logs(user_id);
CREATE INDEX idx_attendance_device_id ON attendance_logs(device_id);
```

### SyncStatus Enum

```python
class SyncStatus:
    PENDING = 'pending'    # Chưa sync
    SYNCED = 'synced'      # Đã sync thành công
    ERROR = 'error'        # Sync lỗi
    SKIPPED = 'skipped'    # Bị bỏ qua (duplicate)
```

---

## 🔍 Verification Checklist

### Sau Refactor pyzatt

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| `sync_employee()` | ✅ **FIXED** | `device_service.py:227` | Restored implementation |
| `get_attendance()` | ✅ **REFACTORED** | `device_service.py:79` | Using pyzatt ZKSS |
| `sync_first_checkins()` | ✅ **OK** | `attendance_sync_service.py:185` | No changes needed |
| `_calculate_daily_attendance_with_dedup()` | ✅ **OK** | `attendance_sync_service.py:436` | DB operations only |
| `_send_to_external_api()` | ✅ **OK** | `attendance_sync_service.py:703` | API calls only |
| `_process_api_response()` | ✅ **OK** | `attendance_sync_service.py:550` | DB operations only |
| Anti-duplicate logic | ✅ **OK** | `attendance_sync_service.py:476` | DB queries only |
| Batch processing | ✅ **OK** | `attendance_sync_service.py:685` | No device dependency |
| Error handling | ✅ **OK** | Throughout | No device dependency |

---

## 📝 Logging Examples

### Successful Run (có data)

```log
------------------------------------------------------------
CRON JOB STARTED: First Checkin Sync at 2025-10-19 10:00:30
------------------------------------------------------------
User sync to external API: 3/3 users synced
[First Checkin Sync] Sending batch 1/1 with 15 records
First checkin sync completed: processed 15 users, synced 15 records to external API
------------------------------------------------------------
CRON JOB COMPLETED: First Checkin Sync in 0:00:02.345
------------------------------------------------------------
```

### Successful Run (no data)

```log
------------------------------------------------------------
CRON JOB STARTED: First Checkin Sync at 2025-10-19 10:01:00
------------------------------------------------------------
User sync: no unsynced users to process
First checkin sync: no pending attendance records
------------------------------------------------------------
CRON JOB COMPLETED: First Checkin Sync in 0:00:00.123
------------------------------------------------------------
```

### Error Run

```log
------------------------------------------------------------
CRON JOB STARTED: First Checkin Sync at 2025-10-19 10:02:00
------------------------------------------------------------
User sync to external API: 5/5 users synced
[First Checkin Sync] Sending batch 1/2 with 100 records
[First Checkin Sync] Stopping due to error: External API returned status 500
First checkin sync returned error: External API returned status 500
------------------------------------------------------------
CRON JOB COMPLETED: First Checkin Sync in 0:00:01.567
------------------------------------------------------------
```

---

## 🎯 Kết Luận

### ✅ First Checkin Sync Cron HOẠT ĐỘNG HOÀN TOÀN SAU REFACTOR

**Lý do**:
1. ✅ `sync_employee()` đã được restore - chỉ xử lý DB ↔ API
2. ✅ `sync_first_checkins()` không thay đổi - chỉ xử lý DB ↔ API
3. ✅ Data vào DB qua `get_attendance()` đã refactor pyzatt
4. ✅ Cron **KHÔNG GỌI DEVICE** - chỉ xử lý PENDING records trong DB

### 🔄 Data Flow Complete

```
Device (pyzatt) → DB [PENDING] → Cron (30s) → External API → DB [SYNCED/ERROR/SKIPPED]
```

### ⚡ Performance

- **Real-time**: Chạy mỗi 30s → max delay 30s
- **Efficient**: Batch 100 records/request
- **Resilient**: Anti-duplicate + Error retry (max 100 times)
- **Compatible**: Hoạt động với cả pull và push devices

---

## 📚 Related Documentation

- [Daily Attendance Sync Flow](./DAILY_ATTENDANCE_SYNC_FLOW.md)
- [Periodic User Sync Flow](./PERIODIC_USER_SYNC_FLOW.md)
- [Pyzatt Migration Guide](./PYZATT_MIGRATION_GUIDE.md)
- [Error Handling Guide](./ERROR_HANDLING_GUIDE.md)

---

**Maintainer**: Backend Team
**Contact**: backend-team@company.com
**Last Review**: 2025-10-19
