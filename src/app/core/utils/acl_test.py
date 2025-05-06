from typing import List

from aerleon.lib.aclcheck import AclCheck
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import PolicyTerm


def run_tests(
    policy_dict: dict,
    definitions,
    terms: List[PolicyTerm],
    expected_action: str,
    src="any",
    dst="any",
    sport="any",
    dport="any",
    proto="any",
) -> PolicyTerm | None:
    # Add temporary target to make FromPolicyDict work
    policy_dict["filters"][0]["header"]["targets"] = {"cisco": "test-filter"}

    check = AclCheck.FromPolicyDict(policy_dict, definitions, src, dst, sport, dport, proto)

    match = next(iter(check.ExactMatches()), None)

    if not match:
        return False, None

    if match.action == expected_action:
        # Locate exact matched term.

        matched_term = next(iter([term for term in terms if match.term.startswith(term.valid_name)]), None)

        return True, matched_term

    return False, None
