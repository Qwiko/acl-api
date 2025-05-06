from fastapi import APIRouter

from .deployers import router as deployers_router
from .deployments import router as deployments_router
from .dynamic_policies import router as dynamic_policies_router
from .token import router as token_router
from .networks import router as networks_router
from .policies import router as policies_router
from .revisions import router as revisions_router
from .services import router as services_router
from .targets import router as targets_router
from .tests import router as tests_router

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
