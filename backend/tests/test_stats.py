from jobbr.models import Company, Job, Profile
from jobbr.repo import JobRow
from jobbr.stats import compute


def test_salary_median_uses_usd_and_both_middle_values():
    company = Company(id=1, name="Test employer")
    rows = [
        JobRow(
            Job(company_id=1, title="Role", comp_min=low, comp_max=high, comp_currency=currency),
            company,
            None,
            None,
        )
        for low, high, currency in [
            (100, 200, "USD"),
            (300, 400, "USD"),
            (10000, 20000, "EUR"),
            (None, 500, "USD"),
        ]
    ]
    assert compute(rows, Profile(), 0)["totals"]["median_comp"] == 250
    assert compute(rows[2:], Profile(), 0)["totals"]["median_comp"] is None
