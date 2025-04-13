from fastapi import APIRouter

from .dynamic_policies import router as dynamic_policies_router
from .networks import router as networks_router
from .policies import router as policies_router
from .publishers import router as publishers_router
from .revisions import router as revisions_router
from .services import router as services_router
from .targets import router as targets_router
from .tests import router as tests_router

router = APIRouter(prefix="/v1")
router.include_router(dynamic_policies_router)
router.include_router(networks_router)
router.include_router(policies_router)
router.include_router(publishers_router)
router.include_router(revisions_router)
router.include_router(services_router)
router.include_router(targets_router)
router.include_router(tests_router)