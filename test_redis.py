#!/usr/bin/env python
"""Quick script to test Redis connection"""
import redis

try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    result = r.ping()
    print("✅ Redis is running! Connection successful.")
    print(f"Ping response: {result}")
except redis.exceptions.ConnectionError as e:
    print("❌ Redis is NOT running!")
    print(f"Error: {e}")
    print("\nPlease start Redis using one of the methods above.")
