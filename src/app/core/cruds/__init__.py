from app.core.utils.crud import BaseCRUD
from app.models import (
    Deployer,
    Deployment,
    DynamicPolicy,
    Network,
    NetworkAddress,
    Policy,
    PolicyTerm,
    Revision,
    Service,
    ServiceEntry,
    Target,
    Test,
    TestCase,
)

policy_crud = BaseCRUD(Policy)

term_crud = BaseCRUD(PolicyTerm)

revision_crud = BaseCRUD(Revision)

dynamic_policy_crud = BaseCRUD(DynamicPolicy)

network_crud = BaseCRUD(Network)
address_crud = BaseCRUD(NetworkAddress)

service_crud = BaseCRUD(Service)
entry_crud = BaseCRUD(ServiceEntry)

target_crud = BaseCRUD(Target)

test_crud = BaseCRUD(Test)
case_crud = BaseCRUD(TestCase)

deployer_crud = BaseCRUD(Deployer)
deployment_crud = BaseCRUD(Deployment)
