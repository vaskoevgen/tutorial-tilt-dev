from fastapi import FastAPI
from redis import Redis
import os

app = FastAPI(title="Tilt Tutorial App")
redis = Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)

@app.get("/")
def root():
    return {"message": "Hello from Tilt tutorial!", "status": "ok"}

@app.get("/count")
def get_count():
    count = redis.get("counter") or 0
    return {"count": int(count)}

@app.post("/count/increment")
def increment():
    count = redis.incr("counter")
    return {"count": count}

@app.post("/count/reset")
def reset():
    redis.set("counter", 0)
    return {"count": 0}

@app.get("/health")
def health():
    try:
        redis.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "degraded", "redis": str(e)}
