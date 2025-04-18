from ...models import (
    DynamicPolicy,
    Network,
    NetworkAddress,
    Policy,
    Revision,
    PolicyTerm,
    Deployer,
    Deployment,
    Service,
    ServiceEntry,
    Target,
    Test,
    TestCase,
)
from ..utils.crud import BaseCRUD

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
