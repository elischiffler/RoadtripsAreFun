from . import app  # Import the `app` from the `__init__.py`


@app.get("/")
async def root() -> str:
    return "Hello world"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
