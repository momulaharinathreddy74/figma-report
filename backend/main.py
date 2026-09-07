

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from normalizer import normalize_node
from classifier import classify_tree

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
# Test endpoint
# -------------------------

@app.get("/")
def home():
    return {
        "message": "FastAPI is working"
    }


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
# Classify normalized design
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

        design = response.data[0]

        design_json = design["design_json"]

        # Check whether the data is already normalized
        if (
            "position" in design_json
            and "size" in design_json
            and "texts" in design_json
        ):
            normalized_json = design_json

        else:
            normalized_json = normalize_node(design_json)

        classified_json = classify_tree(normalized_json)

        return {
            "success": True,
            "design_id": design_id,
            "classified_design": classified_json
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )