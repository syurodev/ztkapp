#!/usr/bin/env python3
"""
Test script to verify all imports work before building with PyInstaller
Run this before build_backend.bat to catch import errors early
"""

import sys
import os

# Add src directory to path (same as service_app.py does)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("="*50)
print("Testing Python Module Imports")
print("="*50)
print()

def test_import(module_name, display_name=None):
    """Test if a module can be imported"""
    if display_name is None:
        display_name = module_name

    try:
        __import__(module_name)
        print(f"OK {display_name}")
        return True
    except ImportError as e:
        print(f"✗ {display_name}: {e}")
        return False
    except Exception as e:
        print(f"✗ {display_name}: {e}")
        return False

# Track results
success = 0
failed = 0

print("Core Python modules:")
if test_import("sys"): success += 1
else: failed += 1
if test_import("os"): success += 1
else: failed += 1
if test_import("signal"): success += 1
else: failed += 1
if test_import("sqlite3"): success += 1
else: failed += 1

print()
print("Third-party dependencies:")
if test_import("flask", "Flask"): success += 1
else: failed += 1
if test_import("requests", "Requests"): success += 1
else: failed += 1
if test_import("psutil", "PSUtil"): success += 1
else: failed += 1
if test_import("dotenv", "Python-dotenv"): success += 1
else: failed += 1
if test_import("zk", "PyZK"): success += 1
else: failed += 1

print()
print("Application modules:")
if test_import("app", "app (main module)"): success += 1
else: failed += 1
if test_import("app.config.config_manager", "app.config.config_manager"): success += 1
else: failed += 1
if test_import("app.shared.logger", "app.shared.logger"): success += 1
else: failed += 1

print()
print("="*50)
print(f"Results: {success} passed, {failed} failed")
print("="*50)

if failed > 0:
    print()
    print("⚠️  Some imports failed!")
    print("Fix these errors before running build_backend.bat")
    sys.exit(1)
else:
    print()
    print("OK All imports successful!")
    print("Ready to build with PyInstaller")
    sys.exit(0)
