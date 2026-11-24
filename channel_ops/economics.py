"""Two independent USD models. No external calls, credentials or storage."""

from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_HALF_UP

ZERO = Decimal(0)
HUNDRED = Decimal(100)
CENT = Decimal("0.01")
SIXTY = Decimal(60)

SAAS_EXAMPLE = {
    "monthly_price_usd": 19,
    "refund_percent": 3,
    "processing_percent": 3,
    "processing_fixed_usd": 0.30,
    "compute_storage_usd": 1.20,
    "model_api_usd": 1.50,
    "other_service_usd": 0.50,
    "support_minutes": 10,
    "loaded_support_hourly_usd": 30,
    "acquisition_cash_spend_usd": 180,
    "acquisition_hours": 8,
    "loaded_acquisition_hourly_usd": 30,
    "new_paying_channels": 12,
    "monthly_churn_percent": 5,
    "monthly_fixed_costs_usd": 300,
}

CAMPAIGN_FIELDS = {
    "production_cash_usd", "production_hours", "loaded_production_hourly_usd",
    "promotion_cash_usd", "distribution_and_sales_hours",
    "loaded_distribution_and_sales_hourly_usd", "tools_allocated_usd", "weeks",
}

WEEK_FIELDS = {
    "confirmed_orders", "confirmed_new_customers", "sales_collected_usd",
    "refunds_usd", "fulfillment_and_fees_usd", "other_net_income_usd",
}


def example_saas_inputs() -> dict:
    """Illustrative assumptions for a one-channel monthly subscription."""
    return dict(SAAS_EXAMPLE)


def example_campaign_inputs() -> dict:
    """Illustrative two-week campaign with one new customer and one repeat sale."""
    return {
        "production_cash_usd": 15, "production_hours": 2,
        "loaded_production_hourly_usd": 30, "promotion_cash_usd": 15,
        "distribution_and_sales_hours": 1, "loaded_distribution_and_sales_hourly_usd": 30,
        "tools_allocated_usd": 5,
        "weeks": [
            {"confirmed_orders": 1, "confirmed_new_customers": 1, "sales_collected_usd": 100,
             "refunds_usd": 0, "fulfillment_and_fees_usd": 25, "other_net_income_usd": 0},
            {"confirmed_orders": 1, "confirmed_new_customers": 0, "sales_collected_usd": 100,
             "refunds_usd": 0, "fulfillment_and_fees_usd": 25, "other_net_income_usd": 0},
        ],
    }


def _check_keys(data: dict, fields: set, metadata: bool = False) -> None:
    if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
        raise ValueError("Inputs must be a JSON object with string keys.")
    missing = sorted(fields - data.keys())
    known = fields | ({"measured_fields", "evidence_refs"} if metadata else set())
    extra = sorted(data.keys() - known)
    if missing or extra:
        raise ValueError(f"Missing fields: {missing}. Unexpected fields: {extra}.")


def _value(data: dict, field: str, *, count: bool = False) -> Decimal:
    value = data[field]
    if isinstance(value, bool) or not isinstance(value, (float, int, Decimal)):
        raise ValueError(f"{field} must be a JSON number.")
    number = Decimal(str(value))
    if not number.is_finite() or not ZERO <= number <= Decimal("1e12"):
        raise ValueError(f"{field} must be finite and between 0 and 1 trillion.")
    if number != ZERO and number.normalize().as_tuple().exponent < -6:
        raise ValueError(f"{field} supports up to six decimal places.")
    if field.endswith("_percent") and number > HUNDRED:
        raise ValueError(f"{field} must be at most 100.")
    if count and number != number.to_integral_value():
        raise ValueError(f"{field} must be a whole number.")
    return number


def _basis(data: dict, fields: set) -> dict:
    _check_keys(data, fields, metadata=True)
    measured = data.get("measured_fields", [])
    refs = data.get("evidence_refs", {})
    if not isinstance(measured, list) or not all(isinstance(x, str) and x in fields for x in measured):
        raise ValueError("measured_fields must list known input fields.")
    if len(measured) != len(set(measured)):
        raise ValueError("measured_fields contains duplicates.")
    if not isinstance(refs, dict) or set(refs) != set(measured):
        raise ValueError("Provide one evidence reference for each measured field.")
    if not all(isinstance(ref, str) and 0 < len(ref.strip()) <= 256 for ref in refs.values()):
        raise ValueError("Each evidence reference must be a short document or observation reference.")
    assumed = sorted(fields - set(measured))
    status = "assumptions_only" if not measured else ("mixed" if assumed else "measured_inputs")
    return {"status": status, "measured_fields": sorted(measured), "assumed_fields": assumed,
            "evidence_refs": dict(refs)}


def _rounded(number: Decimal | None) -> float | None:
    if number is None:
        return None
    with localcontext() as context:
        context.prec = max(28, number.adjusted() + 4)
        return float(number.quantize(CENT, rounding=ROUND_HALF_UP))


def _divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return numerator / denominator if denominator > ZERO else None


def _break_even(cost: Decimal, contribution: Decimal | None) -> int | None:
    if cost <= ZERO:
        return 0
    if contribution is None or contribution <= ZERO:
        return None
    return int((cost / contribution).to_integral_value(rounding=ROUND_CEILING))


def saas_unit_economics(inputs: dict) -> dict:
    """Per paying channel/month plus steady-state break-even including churn replacement."""
    fields = set(SAAS_EXAMPLE)
    basis = _basis(inputs, fields)
    x = {f: _value(inputs, f, count=(f == "new_paying_channels")) for f in fields}
    price = x["monthly_price_usd"]
    net_revenue = price * (1 - x["refund_percent"] / HUNDRED)
    processing = price * x["processing_percent"] / HUNDRED + x["processing_fixed_usd"]
    support = x["support_minutes"] * x["loaded_support_hourly_usd"] / SIXTY
    service = processing + support + x["compute_storage_usd"] + x["model_api_usd"] + x["other_service_usd"]
    contribution = net_revenue - service
    acquisition = x["acquisition_cash_spend_usd"] + x["acquisition_hours"] * x["loaded_acquisition_hourly_usd"]
    cac = _divide(acquisition, x["new_paying_channels"])
    churn = x["monthly_churn_percent"] / HUNDRED
    ltv = _divide(contribution, churn)
    replacement = ZERO if churn == ZERO else (None if cac is None else churn * cac)
    steady = None if replacement is None else contribution - replacement
    return {
        "currency": "USD", "scope": "per_paying_channel_month", "basis": basis,
        "net_revenue_usd": _rounded(net_revenue), "processing_usd": _rounded(processing),
        "support_usd": _rounded(support), "variable_cost_usd": _rounded(service),
        "monthly_contribution_usd": _rounded(contribution),
        "contribution_margin_percent": _rounded(_divide(contribution * HUNDRED, net_revenue)),
        "cohort_acquisition_cost_usd": _rounded(acquisition), "cac_usd": _rounded(cac),
        "simple_payback_months": _rounded(_divide(cac, contribution)) if cac is not None else None,
        "modeled_lifetime_contribution_usd": _rounded(ltv),
        "modeled_ltv_to_cac": _rounded(_divide(ltv, cac)) if ltv is not None and cac is not None else None,
        "monthly_replacement_acquisition_usd": _rounded(replacement),
        "steady_monthly_contribution_usd": _rounded(steady),
        "steady_break_even_active_channels": _break_even(x["monthly_fixed_costs_usd"], steady),
    }


def campaign_unit_economics(inputs: dict) -> dict:
    """Realized ticket-level cash totals in chronological weeks, with upfront campaign spend."""
    basis = _basis(inputs, CAMPAIGN_FIELDS)
    x = {f: _value(inputs, f) for f in CAMPAIGN_FIELDS - {"weeks"}}
    weeks = inputs["weeks"]
    if not isinstance(weeks, list) or not 1 <= len(weeks) <= 104:
        raise ValueError("weeks must contain 1 to 104 consecutive weekly summaries.")
    totals = {f: ZERO for f in WEEK_FIELDS}
    production = x["production_cash_usd"] + x["production_hours"] * x["loaded_production_hourly_usd"]
    distribution = x["promotion_cash_usd"] + x["distribution_and_sales_hours"] * x["loaded_distribution_and_sales_hourly_usd"]
    spend = production + distribution + x["tools_allocated_usd"]
    balance = -spend
    payback = 0 if balance == ZERO else None
    for index, week in enumerate(weeks, 1):
        _check_keys(week, WEEK_FIELDS)
        w = {f: _value(week, f, count=f.startswith("confirmed_")) for f in WEEK_FIELDS}
        if w["confirmed_new_customers"] > w["confirmed_orders"]:
            raise ValueError("Confirmed new customers cannot exceed confirmed orders in the week.")
        for field in WEEK_FIELDS:
            totals[field] += w[field]
        balance += w["sales_collected_usd"] - w["refunds_usd"] - w["fulfillment_and_fees_usd"] + w["other_net_income_usd"]
        if balance < ZERO:
            payback = None
        elif payback is None:
            payback = index
    sales_margin = totals["sales_collected_usd"] - totals["refunds_usd"] - totals["fulfillment_and_fees_usd"]
    per_order = _divide(sales_margin, totals["confirmed_orders"])
    return {
        "currency": "USD", "scope": "one_attributed_campaign", "basis": basis, "weeks_observed": len(weeks),
        "production_usd": _rounded(production), "distribution_and_sales_usd": _rounded(distribution),
        "total_campaign_cost_usd": _rounded(spend), "confirmed_orders": int(totals["confirmed_orders"]),
        "confirmed_new_customers": int(totals["confirmed_new_customers"]),
        "order_contribution_before_campaign_cost_usd": _rounded(sales_margin),
        "other_net_income_usd": _rounded(totals["other_net_income_usd"]),
        "campaign_contribution_usd": _rounded(balance), "return_on_campaign_spend_percent": _rounded(_divide(balance * HUNDRED, spend)),
        "blended_cac_usd": _rounded(_divide(spend, totals["confirmed_new_customers"])),
        "order_contribution_per_order_usd": _rounded(per_order),
        "modeled_break_even_orders": _break_even(spend - totals["other_net_income_usd"], per_order),
        "payback_week_through_observed_window": payback,
    }
