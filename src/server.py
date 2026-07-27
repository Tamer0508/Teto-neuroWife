from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
import os

app = FastAPI()

# папка, где лежит этот файл -> оттуда берём index.html
HERE = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
async def index():
    return FileResponse(os.path.join(HERE, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)