import re

# Read the original file
with open("zkteco/services/zk_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the import
new_content = content.replace(
    "from distutils.util import strtobool",
    """# from distutils.util import strtobool - deprecated in Python 3.12+
def strtobool(val):
    \"\"\"Convert a string representation of truth to true (1) or false (0).\"\"\"
    val = val.lower()
    if val in (\"y\", \"yes\", \"t\", \"true\", \"on\", \"1\"):
        return 1
    elif val in (\"n\", \"no\", \"f\", \"false\", \"off\", \"0\"):
        return 0
    else:
        raise ValueError(f\"invalid truth value {val!r}\")"""
)

# Write the fixed content back
with open("zkteco/services/zk_service.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Fixed distutils import in zk_service.py")
