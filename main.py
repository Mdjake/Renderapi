import os
import math
import gc  # <--- Add this import at the top of your file
from fastapi import FastAPI, HTTPException, Query
import duckdb

app = FastAPI(title="Simple Search API")
MASTER_KEY = "my_secret_key_123"
BUCKET_PATH = "hf://buckets/secrethure/aadhar-family-bucket/idx_aadhar.*.parquet"

def clean_records(df):
    records = df.to_dict(orient="records")
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                clean[k] = None
            elif hasattr(v, "item"):
                clean[k] = v.item()
            else:
                clean[k] = v
        out.append(clean)
    return out

@app.get("/search")
async def dynamic_search(
    field: str = Query(...),
    value: str = Query(...),
    key: str = Query(...),
):
    if key != MASTER_KEY:
        raise HTTPException(status_code=401, detail="ACCESS_DENIED")

    allowed_fields = ["name", "fathersName", "phoneNumber", "aadharNumber", "otherNumber", "address", "district", "pincode", "state", "town", "source"]
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid field")

    con = None
    try:
        con = duckdb.connect()
        con.execute("SET home_directory = '/tmp';")
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        
        if field == "aadharNumber":
            query = f"SELECT * FROM read_parquet('{BUCKET_PATH}') WHERE {field} = ? LIMIT 10"
            df = con.execute(query, [value]).fetchdf()
        else:
            query = f"SELECT * FROM read_parquet('{BUCKET_PATH}') WHERE {field} ILIKE ? LIMIT 10"
            df = con.execute(query, [f"%{value}%"]).fetchdf()
        
        if df.empty:
            return {"message": "NO_DATA_FOUND"}
        return clean_records(df)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QUERY_FAILED: {str(e)}")
        
    finally:
        # --- FORCE MEMORY CLEANUP ---
        if con is not None:
            con.close()
        del con  # Delete the connection object
        gc.collect()  # Force Python to clean up RAM immediately
