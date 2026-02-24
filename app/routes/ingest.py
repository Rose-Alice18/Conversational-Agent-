from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.routes.chat import reinit_agent
from app.services.ingest import ProductsNotEmptyError, run_ingest

router = APIRouter()


class IngestResponse(BaseModel):
    inventory_count: int
    business_info_count: int
    message: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest_excel(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx or .xls files are accepted.",
        )

    file_bytes = await file.read()

    try:
        result = await run_ingest(file_bytes)
    except ProductsNotEmptyError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Products table already contains data. "
                "Ingestion is only allowed on an empty database. "
                "Run DROP TABLE products; in Postgres to reset."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Hot-reload the agent with the newly built store context
    await reinit_agent(result["context_text"])

    return IngestResponse(
        inventory_count=result["inventory_count"],
        business_info_count=result["business_info_count"],
        message=(
            f"Successfully ingested {result['inventory_count']} products "
            f"and {result['business_info_count']} business info entries. "
            f"Agent reloaded with updated store context."
        ),
    )
