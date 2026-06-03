from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
def get_cv_tracker_status():
    return {"status": "CV Tracker endpoint is active."}

@router.post("/process-frame")
async def process_frame(request: Request):
    data = await request.json()
    # Placeholder for actual OpenCV frame processing logic
    return {"message": "Frame processed successfully", "objects_detected": []}
