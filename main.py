from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import uuid
import os
from mimetypes import guess_type

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

@app.post("/download")
async def download_video(req: VideoRequest):
    try:
        # Create a unique ID and output directory for each video download
        video_id = str(uuid.uuid4())[:8]
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{video_id}.%(ext)s")

        # yt-dlp options to download the best quality video
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': False,
            'cookiesfrombrowser': 'chrome',  # Extract cookies from Chrome
            # Optional: Specify custom profile path
            # 'cookiesfrombrowser': 'chrome:~/.var/app/com.google.Chrome'  # For Flatpak Chrome
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading video from {req.url}...")
            try:
                info = ydl.extract_info(req.url, download=True)
                filename = ydl.prepare_filename(info)
            except yt_dlp.utils.DownloadError as de:
                if "Sign in to confirm" in str(de):
                    raise HTTPException(
                        status_code=400,
                        detail="This video requires authentication. Please ensure the browser has valid YouTube cookies."
                    )
                raise HTTPException(status_code=400, detail=f"Download failed: {str(de)}")

        # Ensure the file exists before returning it
        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="File not found after download.")

        # Determine the media type dynamically
        media_type = guess_type(filename)[0] or "video/mp4"
        return FileResponse(
            filename,
            media_type=media_type,
            filename=os.path.basename(filename)
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(carstatus_code=500, detail=f"Error: {str(e)}")