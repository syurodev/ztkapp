2025-10-20 16:47:46 - app.shared.logger - INFO - Performing a full sync of 6 users to external API for device PYA8252300166
2025-10-20 16:47:46 - app.shared.logger - INFO - External API Request -> Method: POST, URL: http://0.0.0.0:8095/api/v1/time-clock-employees/sync, Headers: {'Content-Type': 'application/json', 'x-api-key': '***', 'ProjectId': '1055', 'x-device-sync': 'PYA8252300166', 'x-branch-id': '***'}
2025-10-20 16:47:46 - app.shared.logger - DEBUG - Request Payload: {"timestamp": 1760953666, "employees": [{"userId": "7339", "name": "PALACE 2", "card": "", "privilege": 0, "password": "", "groupId": 1}, {"userId": "7297", "name": "Cung \u1ee9ng 2 test update", "card": "", "privilege": 0, "password": "", "groupId": 1}, {"userId": "7309", "name": "T\u1ed5ng qu\u1ea3n l\u00fd 2", "card": "", "privilege": 0, "password": "", "groupId": 1}, {"userId": "7325", "name": "anh quang qu\u00e2n", "card": "", "privilege": 0, "password": "", "groupId": 1}, {"userId": "7338", "name": "PALACE 1", "card": "", "privilege": 0, "password": "", "groupId": 1}, {"userId": "7300", "name": "ong", "card": "", "privilege": 0, "password": "", "groupId": 1}]}
2025-10-20 16:47:47 - app.shared.logger - INFO - External API Response <- Status: 200, Body: {"status":200,"message":"OK","data":"6 nhân viên đã được đồng bộ từ thiết bị PYA8252300166"}
2025-10-20 16:47:47 - app.shared.logger - INFO - Successfully completed full sync of 6 users to external API for device 23db1331-cf32-4864-a26a-6d379f765324
2025-10-20 16:47:47,261 - werkzeug - INFO - 127.0.0.1 - - [20/Oct/2025 16:47:47] "POST /device/sync-employee HTTP/1.1" 200 -
2025-10-20 16:47:47,269 - app - INFO - [DEBUG] Starting get_all_users API call with database sync
2025-10-20 16:47:47,270 - app - INFO - [DEBUG] Attempting to sync users from device...
2025-10-20 16:47:47,271 - app - INFO - Device 23db1331-cf32-4864-a26a-6d379f765324 is push type, skipping user sync from device (push devices send data automatically)
2025-10-20 16:47:47,271 - app - INFO - [DEBUG] Device sync completed in 0.00 seconds, synced 0 new users
2025-10-20 16:47:47,271 - app - INFO - [DEBUG] Retrieving users from database...
2025-10-20 16:47:47,272 - app - INFO - [DEBUG] Database query completed in 0.00 seconds
2025-10-20 16:47:47,272 - app - INFO - [DEBUG] Found 6 users in database, starting serialization
2025-10-20 16:47:47,272 - app - INFO - [DEBUG] Serialization completed in 0.00 seconds
2025-10-20 16:47:47,272 - app - INFO - [DEBUG] Total API call completed in 0.00 seconds
2025-10-20 16:47:47,273 - werkzeug - INFO - 127.0.0.1 - - [20/Oct/2025 16:47:47] "GET /users HTTP/1.1" 200 -
