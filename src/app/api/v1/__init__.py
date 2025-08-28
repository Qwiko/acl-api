from fastapi import APIRouter

from app.api.v1.deployers import router as deployers_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.dynamic_policies import router as dynamic_policies_router
from app.api.v1.networks import router as networks_router
from app.api.v1.policies import router as policies_router
from app.api.v1.revisions import router as revisions_router
from app.api.v1.services import router as services_router
from app.api.v1.targets import router as targets_router
from app.api.v1.tests import router as tests_router
from app.api.v1.token import router as token_router

router = APIRouter(prefix="/v1")
router.include_router(token_router)
router.include_router(deployers_router)
router.include_router(deployments_router)
router.include_router(dynamic_policies_router)
router.include_router(networks_router)
router.include_router(policies_router)
router.include_router(revisions_router)
router.include_router(services_router)
router.include_router(targets_router)
router.include_router(tests_router)
