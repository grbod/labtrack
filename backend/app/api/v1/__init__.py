"""API v1 module."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, products, lab_test_types, lots, test_results, uploads, settings, customers, release, archive, audit, retest

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(lab_test_types.router, prefix="/lab-test-types", tags=["Lab Test Types"])
api_router.include_router(lots.router, prefix="/lots", tags=["Lots"])
api_router.include_router(test_results.router, prefix="/test-results", tags=["Test Results"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(release.router, prefix="/release", tags=["COA Release"])
api_router.include_router(archive.router, prefix="/archive", tags=["Archive"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(retest.router, prefix="/retest", tags=["Retest"])
