"""API v1 module."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    archive,
    audit,
    auth,
    customers,
    lab_test_aliases,
    lab_test_types,
    lots,
    products,
    release,
    result_imports,
    retest,
    settings,
    test_results,
    uploads,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(
    lab_test_types.router, prefix="/lab-test-types", tags=["Lab Test Types"]
)
api_router.include_router(
    lab_test_aliases.router, prefix="/lab-test-aliases", tags=["Lab Test Aliases"]
)
api_router.include_router(lots.router, prefix="/lots", tags=["Lots"])
api_router.include_router(
    test_results.router, prefix="/test-results", tags=["Test Results"]
)
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(release.router, prefix="/release", tags=["COA Release"])
api_router.include_router(archive.router, prefix="/archive", tags=["Archive"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(retest.router, prefix="/retest", tags=["Retest"])
api_router.include_router(
    result_imports.router, prefix="/result-imports", tags=["Result Imports"]
)
