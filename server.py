import asyncio
import json
import pathlib
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from agent import run_pipeline

app = FastAPI(
    title="CoralDebug Enterprise Webhook Server",
    description="Microservice to autonomously trigger CoralDebug multi-agent triage pipeline.",
    version="2.0.0"
)

def trigger_triage_pipeline():
    """Wrapper to run the pipeline synchronously in the background."""
    print("[Server] Triggering autonomous CoralDebug pipeline...")
    try:
        run_pipeline()
        print("[Server] Autonomous pipeline completed successfully.")
    except Exception as e:
        print(f"[Server] Pipeline failed: {e}")

@app.post("/api/webhooks/sentry")
async def sentry_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Sentry to hit when a new issue is created or unresolved.
    We return 202 Accepted immediately so Sentry doesn't timeout,
    and we run the heavy multi-agent pipeline in the background.
    """
    # In a real enterprise app, we'd validate the Sentry HMAC signature here.
    payload = await request.json()
    
    event_id = payload.get("id", "unknown")
    project = payload.get("project_name", "unknown")
    
    print(f"\n--- Sentry Webhook Received ---")
    print(f"Event ID: {event_id} | Project: {project}")
    
    # Send the heavy lifting to the background
    background_tasks.add_task(trigger_triage_pipeline)
    
    return {
        "status": "accepted",
        "message": "Webhook received. Triage agents have been deployed in the background."
    }

@app.get("/api/report")
def get_report():
    """Returns the latest generated report.json"""
    report_path = pathlib.Path(__file__).parent / "report.json"
    if report_path.exists():
        with open(report_path, "r") as f:
            return JSONResponse(content=json.load(f))
    return JSONResponse(content={"error": "No report generated yet."}, status_code=404)

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the live dashboard UI."""
    index_path = pathlib.Path(__file__).parent / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Dashboard not found."

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "coraldebug-agents"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
