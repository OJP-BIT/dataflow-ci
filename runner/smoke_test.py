from checks.structural import run_structural_checks
from checks.statistical import run_statistical_checks
from checks.referential import run_referential_checks

repo = '../tests/sample_pipeline'
s = run_structural_checks(repo)
st = run_statistical_checks(repo)
r = run_referential_checks(repo)

all_checks = s + st + r
passed = sum(1 for c in all_checks if c['passed'])
failed = sum(1 for c in all_checks if not c['passed'])

print(f'Total checks: {len(all_checks)}')
print(f'Passed: {passed}')
print(f'Failed: {failed}')

for c in all_checks:
    if not c['passed']:
        print(f"  FAIL [{c['category']}] {c['check']}: {c['message']}")