import os
import sys

# Add the project root to the Python path to allow for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from pyzatt.pyzatt import ZKSS


def test_pyzatt_connection():
    """Tests connection and user fetching with pyzatt library."""

    print("--- Starting pyzatt test ---", flush=True)

    ip = "192.168.8.100"

    port = 4370

    print(f"Using hardcoded IP={ip}, Port={port}", flush=True)

    z = ZKSS()
    try:
        print("Executing z.connect_net(...)", flush=True)
        z.connect_net(ip, dev_port=port)
        print("Connection successful!", flush=True)

        print("Executing z.read_all_user_id()...", flush=True)
        z.read_all_user_id()
        users = list(z.users.values())
        print("User data processing complete.", flush=True)

        print(f"Successfully fetched {len(users)} users.", flush=True)

        # Print details of first 5 users for verification
        for i, user in enumerate(users[:5]):
            print(
                f"  - User {i + 1}: UID={user.user_sn}, Name={user.user_name}, UserID={user.user_id}",
                flush=True,
            )

    except Exception as e:
        print(f"AN ERROR OCCURRED: {e}", flush=True)
        import traceback

        traceback.print_exc()

    finally:
        if hasattr(z, "connected_flg") and z.connected_flg:
            print("Disconnecting...", flush=True)
            z.disconnect()
            print("Disconnected.", flush=True)
        print("--- Test finished ---", flush=True)


if __name__ == "__main__":
    test_pyzatt_connection()
