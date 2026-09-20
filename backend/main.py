import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client, Client
from normalizer import normalize_node
from classifier import classify_tree
from validator import validate_classified_design
from renderer import render_dashboard_html
from Orchestrator import generate_dashboard_config

load_dotenv()


# -------------------------
# Supabase configuration
# -------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials are missing")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# -------------------------
# FastAPI
# -------------------------

app = FastAPI()


# -------------------------
# Request structure
# -------------------------

class DesignData(BaseModel):
    name: str
    figma_node_id: str
    design_json: dict


# -------------------------
# Static files
# -------------------------

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)


# -------------------------
# Dashboard UI  (GET /)
# -------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    html_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(html_path, media_type="text/html")


# -------------------------
# Health check
# -------------------------

@app.get("/health")
def health():
    return {"status": "ok", "message": "FastAPI is running"}


# -------------------------
# Save design
# -------------------------

@app.post("/designs")
def save_design(data: DesignData):

    try:

        record = {
            "name": data.name,
            "figma_node_id": data.figma_node_id,
            "design_json": data.design_json
        }

        response = (
            supabase
            .table("designs")
            .insert(record)
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# -------------------------
# Get saved design
# -------------------------

@app.get("/designs/{design_id}")
def get_design(design_id: str):

    try:

        response = (
            supabase
            .table("designs")
            .select("*")
            .eq("id", design_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Design not found"
            )

        return {
            "success": True,
            "data": response.data[0]
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# -------------------------
# Get all saved designs
# -------------------------

@app.get("/designs")
def get_all_designs():

    try:

        response = (
            supabase
            .table("designs")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/designs/{design_id}/normalize")
def normalize_design(design_id: str):

    try:

        # Get design from Supabase
        response = (
            supabase
            .table("designs")
            .select("*")
            .eq("id", design_id)
            .execute()
        )

        if not response.data:

            raise HTTPException(
                status_code=404,
                detail="Design not found"
            )

        design = response.data[0]

        # Get raw Figma JSON
        raw_json = design["design_json"]

        # Normalize
        normalized_json = normalize_node(
            raw_json
        )

        return {
            "success": True,
            "design_id": design_id,
            "normalized_design": normalized_json
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# -------------------------
# Classify design
# -------------------------

@app.post("/designs/{design_id}/classify")
def classify_design(design_id: str):
    try:
        response = (
            supabase
            .table("designs")
            .select("*")
            .eq("id", design_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Design not found"
            )

        raw_json = response.data[0]["design_json"]

        # Always re-normalize from raw Figma JSON so texts are
        # freshly aggregated — never use a cached normalized form
        normalized = normalize_node(raw_json)
        classified = classify_tree(normalized)

        return {
            "success":           True,
            "design_id":         design_id,
            "classified_design": classified,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Render design as an HTML preview
# -------------------------

@app.get("/designs/{design_id}/render", response_class=HTMLResponse)
def render_design(design_id: str):
    try:
        response = (
            supabase
            .table("designs")
            .select("*")
            .eq("id", design_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Design not found"
            )

        raw_json = response.data[0]["design_json"]

        # Same normalize -> classify path as /classify, plus a
        # validation pass so the preview can flag broken components
        # instead of you eyeballing the JSON against a screenshot.
        normalized = normalize_node(raw_json)
        classified = classify_tree(normalized)
        validation = validate_classified_design(classified)

        html = render_dashboard_html(classified, validation)

        return HTMLResponse(content=html)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Orchestrate design into a dashboard_config
# -------------------------

@app.post("/designs/{design_id}/orchestrate")
def orchestrate_design(design_id: str):
    try:
        response = (
            supabase
            .table("designs")
            .select("*")
            .eq("id", design_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Design not found"
            )

        raw_json = response.data[0]["design_json"]

        # Same normalize -> classify -> validate path as /render, then
        # hand off to the orchestrator: deterministic layout for every
        # component, plus a targeted LLM call for each validator-flagged
        # one (zero LLM calls if the design is already clean).
        normalized = normalize_node(raw_json)
        classified = classify_tree(normalized)
        validation = validate_classified_design(classified)
        dashboard_config = generate_dashboard_config(classified, validation)

        return {
            "success": True,
            "design_id": design_id,
            "validation": validation,
            "dashboard_config": dashboard_config,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))