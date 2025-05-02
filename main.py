from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import uuid
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory setup
DOWNLOAD_DIR = "downloads"
COOKIE_PATH = "cookies.txt"
STATUS_MAP = {}

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")

class VideoRequest(BaseModel):
    url: str

def download_video(url: str, video_id: str):
    STATUS_MAP[video_id] = "in_progress"
    output_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'quiet': True,
    }

    if os.path.exists(COOKIE_PATH):
        ydl_opts['cookiefile'] = COOKIE_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            real_path = ydl.prepare_filename(info)
            final_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
            os.rename(real_path, final_path)
        STATUS_MAP[video_id] = "done"
    except Exception as e:
        print("Download error:", str(e))
        STATUS_MAP[video_id] = "failed"

@app.post("/download")
async def download_video_endpoint(req: VideoRequest, background_tasks: BackgroundTasks):
    video_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(download_video, req.url, video_id)
    return {"video_id": video_id, "status_url": f"/status/{video_id}", "file_url": f"/file/{video_id}"}

@app.get("/status/{video_id}")
async def check_status(video_id: str):
    status = STATUS_MAP.get(video_id)
    if not status:
        raise HTTPException(status_code=404, detail="Video not found.")
    return {"status": status}

@app.get("/file/{video_id}")
async def get_file(video_id: str):
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not available yet.")
    return FileResponse(file_path, media_type="video/mp4", filename=f"{video_id}.mp4")

@app.post("/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt cookie files are supported.")
    with open(COOKIE_PATH, "wb") as f:
        f.write(await file.read())
    return {"message": "Cookies updated successfully."}
