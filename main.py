from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import uuid
from typing import Optional, List, Dict
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# YOUR EMAIL - CHANGE THIS!
EMAIL = "25ds1000078@ds.study.iitm.ac.in"  # ⚠️ CHANGE THIS!

# --- CONFIGURATION ---
TOTAL_ORDERS = 51
RATE_LIMIT = 16

# --- DATA STORES ---
idempotency_store = {}
rate_limit_store = defaultdict(list)

def get_order_by_id(order_id: int) -> dict:
    """Return order data for a given ID"""
    return {
        "id": order_id,
        "customer": f"Customer_{order_id % 10 + 1}",
        "amount": round(10.99 + (order_id * 7.77), 2),
        "status": "completed" if order_id % 3 != 0 else "pending",
        "created_at": (datetime.now() - timedelta(days=order_id)).isoformat()
    }

# --- ENDPOINT 1: IDEMPOTENT ORDER CREATION ---
@app.post("/orders")
async def create_order(request: Request):
    # Get idempotency key from header
    idempotency_key = request.headers.get("Idempotency-Key")
    
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    
    # Check if we've seen this key before
    if idempotency_key in idempotency_store:
        order_id = idempotency_store[idempotency_key]
        return get_order_by_id(order_id)
    
    # First time - create new order
    order_id = len(idempotency_store) + 1
    
    # Store the idempotency key
    idempotency_store[idempotency_key] = order_id
    
    # Return the created order
    return get_order_by_id(order_id)

# --- ENDPOINT 2: CURSOR PAGINATION ---
@app.get("/orders")
async def list_orders(limit: int = 10, cursor: Optional[str] = None):
    # Parse cursor
    if cursor:
        try:
            start_id = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor")
    else:
        start_id = 1
    
    # Calculate end_id
    end_id = min(start_id + limit - 1, TOTAL_ORDERS)
    
    # Get items
    items = []
    for order_id in range(start_id, end_id + 1):
        items.append(get_order_by_id(order_id))
    
    # Determine next cursor
    next_cursor = None
    if end_id < TOTAL_ORDERS:
        next_cursor = str(end_id + 1)
    
    return {
        "items": items,
        "next_cursor": next_cursor,
        "total": TOTAL_ORDERS
    }

# --- RATE LIMITING ---
def check_rate_limit(client_id: str) -> bool:
    now = time.time()
    window = 10
    
    timestamps = rate_limit_store[client_id]
    
    while timestamps and timestamps[0] < now - window:
        timestamps.pop(0)
    
    if len(timestamps) >= RATE_LIMIT:
        return False
    
    timestamps.append(now)
    return True

def get_retry_after(client_id: str) -> int:
    now = time.time()
    window = 10
    
    timestamps = rate_limit_store[client_id]
    if not timestamps:
        return 0
    
    oldest = timestamps[0]
    wait_time = max(0, int(window - (now - oldest)))
    return wait_time

# --- RATE LIMITING MIDDLEWARE ---
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id", "default")
    
    if not check_rate_limit(client_id):
        retry_after = get_retry_after(client_id)
        raise HTTPException(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            detail="Too many requests"
        )
    
    response = await call_next(request)
    return response

# --- HOMEPAGE ---
@app.get("/")
async def root():
    return {
        "message": "Orders API",
        "email": EMAIL,
        "total_orders": TOTAL_ORDERS,
        "rate_limit": RATE_LIMIT,
        "endpoints": {
            "POST /orders": "Create order (requires Idempotency-Key header)",
            "GET /orders?limit=P&cursor=C": "List orders with pagination"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)