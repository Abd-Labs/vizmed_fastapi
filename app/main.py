from fastapi import FastAPI, Depends
from app.core.security import api_key_authentication
from app.api.v1.endpoints import health_check,file_processing,classification

app = FastAPI()

# Include API routers
app.include_router(health_check.router, prefix="/api/v1")
app.include_router(file_processing.router, prefix="/api/v1")
app.include_router(classification.router, prefix="/api/v1")

# Default route for checking if the application is up
@app.get("/", dependencies=[Depends(api_key_authentication)])
async def root():
    return {"message": "Application is up and running"}
