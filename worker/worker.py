"""Background worker: every 10 seconds logs the current counter value from Redis."""
import time
import os
from redis import Redis

redis = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)

print("Worker started. Reporting counter every 10 seconds...", flush=True)

while True:
    count = redis.get("counter") or 0
    print(f"[worker] current counter = {count}", flush=True)
    time.sleep(10)
