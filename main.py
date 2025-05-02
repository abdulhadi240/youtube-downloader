from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import uuid
import os

app = FastAPI()

# Serve static files (optional)
DOWNLOAD_DIR = "downloads"
STATUS_MAP = {}  # Track download status
app.mount("/files", StaticFiles(directory=DOWNLOAD_DIR), name="files")

class VideoRequest(BaseModel):
    url: str

def download_video_in_background(url: str, video_id: str):
    file_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")
    try:
        STATUS_MAP[video_id] = "in_progress"
        ydl_opts = {
            'format': 'best',
            'outtmpl': file_template,
            'cookiefile': "cookies.txt"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            final_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
            if os.path.exists(final_file):
                STATUS_MAP[video_id] = "published"
                STATUS_MAP[f"{video_id}_file"] = final_file
            else:
                STATUS_MAP[video_id] = "failed"
    except Exception as e:
        print("Download error:", e)
        STATUS_MAP[video_id] = "failed"

@app.post("/download")
async def download(req: VideoRequest, background_tasks: BackgroundTasks):
    video_id = str(uuid.uuid4())[:8]
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    STATUS_MAP[video_id] = "queued"
    background_tasks.add_task(download_video_in_background, req.url, video_id)

    return JSONResponse({
        "message": "Download started",
        "video_id": video_id,
        "status_url": f"http://localhost:8000/status/{video_id}"
    })

@app.get("/status/{video_id}")
async def check_status(video_id: str):
    status = STATUS_MAP.get(video_id)
    if not status:
        raise HTTPException(status_code=404, detail="Invalid video ID")

    if status == "published":
        file_path = STATUS_MAP.get(f"{video_id}_file")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail="Downloaded file missing.")
        return FileResponse(file_path, media_type="video/mp4", filename=os.path.basename(file_path))

    return {"status": status}
