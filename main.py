from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
from typing import Optional

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

# What the request looks like
class ExtractRequest(BaseModel):
    text: str

# What the response MUST look like
class ExtractResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str

# Helper: Extract amount from text
def extract_amount(text: str) -> Optional[float]:
    """Extract the first dollar/euro/pound amount"""
    patterns = [
        r'\$\s*([\d,]+\.?\d*)',  # $123.45
        r'€\s*([\d,]+\.?\d*)',   # €123.45
        r'£\s*([\d,]+\.?\d*)',   # £123.45
        r'([\d,]+\.\d{2})',      # 123.45
        r'([\d,]+\.?\d*)',       # 123 or 123.45
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Remove commas and convert to float
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except:
                continue
    return None

# Helper: Extract currency from text
def extract_currency(text: str) -> str:
    """Extract currency code"""
    if '$' in text or 'USD' in text:
        return 'USD'
    if '€' in text or 'EUR' in text:
        return 'EUR'
    if '£' in text or 'GBP' in text:
        return 'GBP'
    return 'USD'  # Default

# Helper: Extract date from text
def extract_date(text: str) -> Optional[str]:
    """Extract YYYY-MM-DD date"""
    # Look for YYYY-MM-DD
    date_pattern = r'(\d{4}-\d{2}-\d{2})'
    match = re.search(date_pattern, text)
    if match:
        return match.group(1)
    
    # Try other date formats
    patterns = [
        r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
        r'(\d{1,2}-\d{1,2}-\d{4})',  # MM-DD-YYYY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                from datetime import datetime
                # Try different formats
                for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except:
                        continue
            except:
                continue
    return None

# Helper: Extract vendor from text
def extract_vendor(text: str) -> str:
    """Extract vendor name"""
    patterns = [
        r'(?:Vendor|Company|From|Seller|Supplier)[:\s]+([^\n,]+)',
        r'(?:Bill from|Invoice from)[:\s]+([^\n,]+)',
        r'^([^\n,]+)',  # First line
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            if len(vendor) > 2:
                return vendor
    return "Unknown Vendor"

# THE MAIN ENDPOINT
@app.post("/extract")
async def extract_invoice(request: ExtractRequest):
    try:
        text = request.text.strip()
        
        # Handle empty or very short text
        if not text or len(text) < 5:
            return ExtractResponse(
                vendor="Unknown",
                amount=0.0,
                currency="USD",
                date="2026-01-01"
            )
        
        # Extract fields
        vendor = extract_vendor(text)
        amount = extract_amount(text) or 0.0
        currency = extract_currency(text)
        date = extract_date(text) or "2026-01-01"
        
        # Round amount to 2 decimal places
        amount = round(amount, 2)
        
        return ExtractResponse(
            vendor=vendor,
            amount=amount,
            currency=currency,
            date=date
        )
        
    except Exception as e:
        # Never crash on bad input
        print(f"Error processing request: {e}")
        return ExtractResponse(
            vendor="Error",
            amount=0.0,
            currency="USD",
            date="2026-01-01"
        )

@app.get("/")
async def root():
    return {
        "message": "Invoice Extractor API",
        "endpoint": "POST /extract",
        "email": EMAIL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)