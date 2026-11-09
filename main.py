import os
import math
from fastapi import FastAPI, HTTPException, Query
import duckdb

app = FastAPI(title="Simple Search API")

# ---------------- YOUR SINGLE KEY ----------------
MASTER_KEY = "my_secret_key_123"  # Change this to your desired secret key

# Target the 7 files in the bucket
BUCKET_PATH = "hf://buckets/secrethure/aadhar-family-bucket/idx_aadhar.*.parquet"

# ---------------- HELPERS ----------------
def clean_records(df):
    """Cleans pandas NaN and numpy types for JSON serialization."""
    records = df.to_dict(orient="records")
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                clean[k] = None
            elif hasattr(v, "item"):  # numpy scalar -> python native
                clean[k] = v.item()
            else:
                clean[k] = v
        out.append(clean)
    return out

# ---------------- PUBLIC SEARCH ----------------
@app.get("/search")
async def dynamic_search(
    field: str = Query(..., description="Column to search (e.g., aadharNumber, phoneNumber)"),
    value: str = Query(..., description="The value to search for"),
    key: str = Query(..., description="Your API key"),
):
    if key != MASTER_KEY:
        raise HTTPException(status_code=401, detail="ACCESS_DENIED: Invalid API key")

    allowed_fields = [
        "name", "fathersName", "phoneNumber", "aadharNumber", 
        "otherNumber", "address", "district", "pincode", 
        "state", "town", "source"
    ]
    
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid field name.")

    con = None
    try:
        # Render has a normal home directory, but /tmp is still safe for temp files
        con = duckdb.connect()
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        
        # Using ILIKE for partial/case-insensitive matching (except for exact IDs)
        if field == "aadharNumber":
            query = f"SELECT * FROM read_parquet('{BUCKET_PATH}') WHERE {field} = ? LIMIT 10"
            df = con.execute(query, [value]).fetchdf()
        else:
            query = f"SELECT * FROM read_parquet('{BUCKET_PATH}') WHERE {field} ILIKE ? LIMIT 10"
            df = con.execute(query, [f"%{value}%"]).fetchdf()
        
        if df.empty:
            return {"message": "NO_DATA_FOUND", "field": field, "value": value}
        return clean_records(df)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QUERY_FAILED: {str(e)}")
        
    finally:
        if con is not None:
            con.close()

@app.get("/")
async def root():
    return {"status": "ONLINE", "message": "Use /search?field=...&value=...&key=..."}
