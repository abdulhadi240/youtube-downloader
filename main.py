from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from yt_dlp import YoutubeDL
from yt_dlp.utils import load_cookies_from_browser
import uuid
import os

app = FastAPI()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

STATUS_MAP = {}  # video_id -> status
# Possible values: in_progress, published, failed

class VideoRequest(BaseModel):
    url: str

def download_video_in_background(url: str, video_id: str):
    try:
        STATUS_MAP[video_id] = "in_progress"

        file_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")

        # Load cookies from Chrome (adjust path if needed)
        cookies = load_cookies_from_browser('chrome')  # or 'chrome', '/custom/path'

        ydl_opts = {
            'format': 'best',
            'outtmpl': file_template,
            'cookies': cookies
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            final_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

        if os.path.exists(final_file):
            STATUS_MAP[video_id] = "published"
            STATUS_MAP[f"{video_id}_file"] = final_file
        else:
            STATUS_MAP[video_id] = "failed"

    except Exception as e:
        print(f"Download failed for {video_id}: {e}")
        STATUS_MAP[video_id] = "failed"

@app.post("/download")
async def start_download(req: VideoRequest, background_tasks: BackgroundTasks):
    video_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(download_video_in_background, req.url, video_id)

    return JSONResponse({
        "video_id": video_id,
        "status": "in_progress"
    })

@app.get("/status/{video_id}")
async def check_status(video_id: str):
    status = STATUS_MAP.get(video_id)
    if not status:
        raise HTTPException(status_code=404, detail="Video ID not found")

    if status == "published":
        file_path = STATUS_MAP.get(f"{video_id}_file")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail="File missing after publishing")
        return FileResponse(file_path, filename=os.path.basename(file_path))

    return {"video_id": video_id, "status": status}
