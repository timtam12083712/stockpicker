"""Macro sensitivity mappings for ASX sectors and industries.

Maps each sector/industry to:
- What drives the business
- Key macro sensitivities (positive and negative factors)
- Condition scoring based on current macro environment
"""

# Each sensitivity has:
#   factor: what to watch
#   direction: "positive" = this factor rising is GOOD for the stock
#              "negative" = this factor rising is BAD for the stock
#   weight: how important (1-3)

SECTOR_PROFILES = {
    "Financial Services": {
        "what_they_do": "Banks, insurers, and financial intermediaries. Revenue comes from net interest margins (lending vs borrowing rates), fees, wealth management, and insurance premiums.",
        "products": ["Mortgages & home loans", "Business lending", "Credit cards", "Wealth management", "Insurance", "Transaction banking"],
        "drivers": [
            "Net interest margin (spread between lending and deposit rates)",
            "Credit growth (demand for loans)",
            "Asset quality (bad debts and loan losses)",
            "Housing market health",
            "Regulatory environment (APRA capital requirements)",
        ],
        "sensitivities": [
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "positive", "weight": 3,
             "why": "Higher rates widen net interest margins — banks earn more on the spread between lending and deposit rates"},
            {"factor": "yield_curve", "label": "Yield Curve Steepness", "direction": "positive", "weight": 3,
             "why": "Banks borrow short (deposits) and lend long (mortgages) — a steep curve maximises this spread"},
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 2,
             "why": "Strong economy = more lending demand, fewer bad debts"},
            {"factor": "housing", "label": "Housing Market", "direction": "positive", "weight": 2,
             "why": "Mortgages are the biggest revenue driver for Aussie banks — housing downturn = credit stress"},
            {"factor": "unemployment", "label": "Unemployment", "direction": "negative", "weight": 2,
             "why": "Rising unemployment = more loan defaults and provisions for bad debts"},
        ],
        "risks": ["Housing market crash", "Rising bad debts", "Regulatory capital increases", "Fintech disruption", "Credit rating downgrades"],
    },

    "Basic Materials": {
        "what_they_do": "Mining, metals, and materials companies. Revenue depends on extracting and selling commodities (iron ore, copper, gold, lithium, etc.) at market prices.",
        "products": ["Iron ore", "Copper", "Gold", "Lithium", "Aluminium", "Coal", "Nickel", "Zinc"],
        "drivers": [
            "Commodity prices (set by global supply/demand)",
            "Production volumes and costs",
            "Chinese demand (largest buyer of Australian commodities)",
            "USD/AUD exchange rate (commodities priced in USD)",
            "Capex cycle and project pipeline",
        ],
        "sensitivities": [
            {"factor": "commodity_prices", "label": "Commodity Prices", "direction": "positive", "weight": 3,
             "why": "Revenue is directly tied to spot prices — a 10% rise in iron ore can mean a 20%+ rise in profits"},
            {"factor": "china_growth", "label": "China Growth", "direction": "positive", "weight": 3,
             "why": "China buys ~60% of global seaborne iron ore and is the dominant demand driver"},
            {"factor": "aud_usd", "label": "AUD/USD", "direction": "negative", "weight": 2,
             "why": "Commodities priced in USD but costs in AUD — weaker AUD means higher AUD revenue"},
            {"factor": "economic_growth", "label": "Global Growth", "direction": "positive", "weight": 2,
             "why": "Infrastructure and construction demand drives materials consumption"},
            {"factor": "inflation", "label": "Inflation", "direction": "positive", "weight": 1,
             "why": "Commodities are a natural inflation hedge — prices tend to rise with inflation"},
        ],
        "risks": ["Commodity price collapse", "China slowdown", "Rising production costs", "Environmental regulation", "Sovereign/political risk in operating regions"],
    },

    "Energy": {
        "what_they_do": "Oil, gas, and energy producers. Revenue tied to energy commodity prices and production volumes.",
        "products": ["Crude oil", "Natural gas (LNG)", "Thermal coal", "Petroleum products"],
        "drivers": [
            "Oil and gas prices (Brent crude, LNG spot)",
            "Production volumes and reserves",
            "OPEC supply decisions",
            "Energy transition and decarbonisation policy",
            "Capex and exploration success",
        ],
        "sensitivities": [
            {"factor": "oil_price", "label": "Oil Price", "direction": "positive", "weight": 3,
             "why": "Revenue scales directly with oil/gas prices — the single biggest driver"},
            {"factor": "economic_growth", "label": "Global Growth", "direction": "positive", "weight": 2,
             "why": "Growing economies consume more energy — recession = demand destruction"},
            {"factor": "aud_usd", "label": "AUD/USD", "direction": "negative", "weight": 2,
             "why": "Energy priced in USD — weaker AUD boosts reported revenue"},
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 1,
             "why": "Capital-intensive industry — higher rates increase project financing costs"},
            {"factor": "geopolitics", "label": "Geopolitical Risk", "direction": "positive", "weight": 2,
             "why": "Supply disruptions (wars, sanctions) push energy prices higher"},
        ],
        "risks": ["Oil price collapse", "Energy transition / stranded assets", "Carbon regulation", "Project cost blowouts", "LNG contract renegotiation"],
    },

    "Healthcare": {
        "what_they_do": "Pharmaceuticals, biotech, medical devices, and healthcare services. Revenue from selling treatments, devices, and services — often with pricing power.",
        "products": ["Pharmaceuticals", "Blood plasma products", "Medical devices", "Hearing implants", "Respiratory devices", "Healthcare services"],
        "drivers": [
            "R&D pipeline and drug approvals",
            "Patent life and generic competition",
            "Government healthcare spending and reimbursement",
            "Ageing population demographics",
            "USD revenue (many ASX healthcare firms earn in USD)",
        ],
        "sensitivities": [
            {"factor": "aud_usd", "label": "AUD/USD", "direction": "negative", "weight": 3,
             "why": "CSL, COH, RMD earn most revenue in USD — weaker AUD = higher AUD earnings"},
            {"factor": "economic_cycle", "label": "Economic Cycle", "direction": "neutral", "weight": 1,
             "why": "Healthcare demand is relatively inelastic — people need treatment regardless of the economy"},
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 2,
             "why": "Growth stocks with high PE multiples — rising rates compress valuations"},
            {"factor": "regulation", "label": "Regulatory Environment", "direction": "negative", "weight": 2,
             "why": "Drug pricing reforms, PBS changes, and FDA/TGA approval timelines directly impact revenue"},
        ],
        "risks": ["Patent cliffs", "Drug trial failures", "Regulatory/pricing reform", "AUD strength", "Competition from generics/biosimilars"],
    },

    "Technology": {
        "what_they_do": "Software, IT services, and tech platforms. Revenue typically from SaaS subscriptions, licensing, and professional services.",
        "products": ["Cloud software (SaaS)", "Enterprise solutions", "Payments technology", "Data analytics", "IT consulting"],
        "drivers": [
            "Recurring revenue growth and retention rates",
            "Business IT spending budgets",
            "Customer acquisition and churn",
            "R&D and product innovation",
            "Scalability of the platform",
        ],
        "sensitivities": [
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 3,
             "why": "High-PE growth stocks are most sensitive to rate changes — higher rates compress multiples significantly"},
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 2,
             "why": "Businesses invest more in technology during growth periods — IT budgets expand"},
            {"factor": "aud_usd", "label": "AUD/USD", "direction": "negative", "weight": 2,
             "why": "Many ASX tech firms (XRO, WTC) earn revenue globally in USD/GBP"},
            {"factor": "risk_appetite", "label": "Risk Appetite", "direction": "positive", "weight": 2,
             "why": "Growth stocks rally hardest in risk-on environments — VIX low, money flowing into equities"},
        ],
        "risks": ["Multiple compression from rising rates", "Customer churn in downturn", "Competition", "Key person risk", "Overvaluation"],
    },

    "Consumer Cyclical": {
        "what_they_do": "Retailers, consumer brands, and discretionary goods. Revenue depends on consumer spending, which rises and falls with the economic cycle.",
        "products": ["Hardware & home improvement (Bunnings)", "Department stores (Kmart, Target)", "Office supplies (Officeworks)", "Chemicals & fertilisers", "Automotive", "Travel & leisure"],
        "drivers": [
            "Consumer confidence and spending",
            "Employment and wage growth",
            "Housing market (renovation cycle)",
            "Interest rates (mortgage repayments affect disposable income)",
            "Population growth and immigration",
        ],
        "sensitivities": [
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 3,
             "why": "Higher mortgage rates leave less disposable income for discretionary spending — directly hits revenue"},
            {"factor": "consumer_confidence", "label": "Consumer Confidence", "direction": "positive", "weight": 3,
             "why": "People spend on non-essentials when they feel secure about jobs and finances"},
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 2,
             "why": "Strong economy = higher employment, wages, and spending"},
            {"factor": "housing", "label": "Housing Market", "direction": "positive", "weight": 2,
             "why": "Bunnings (Wesfarmers) revenue is closely tied to renovation and new home construction"},
            {"factor": "unemployment", "label": "Unemployment", "direction": "negative", "weight": 2,
             "why": "Rising joblessness = consumers cut discretionary spending first"},
        ],
        "risks": ["Consumer downturn", "Rising rates crushing spending", "Online competition (Amazon)", "Cost of living crisis", "Inventory buildup"],
    },

    "Consumer Defensive": {
        "what_they_do": "Supermarkets, food producers, and essential goods. Revenue is relatively stable because people buy groceries and essentials regardless of the economy.",
        "products": ["Groceries", "Liquor", "Personal care products", "Packaged food", "Agricultural products"],
        "drivers": [
            "Population growth",
            "Food price inflation (can be passed through)",
            "Market share battles (Woolworths vs Coles)",
            "Private label penetration",
            "Supply chain efficiency",
        ],
        "sensitivities": [
            {"factor": "economic_cycle", "label": "Economic Cycle", "direction": "neutral", "weight": 1,
             "why": "Defensive sector — demand is stable regardless of economic conditions. Outperforms in downturns."},
            {"factor": "inflation", "label": "Inflation", "direction": "mixed", "weight": 2,
             "why": "Moderate inflation can be passed through to consumers (good). But high inflation squeezes margins if costs rise faster than prices."},
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 1,
             "why": "Mild impact — higher rates reduce disposable income but grocery spending is the last thing consumers cut"},
            {"factor": "population_growth", "label": "Population Growth", "direction": "positive", "weight": 2,
             "why": "More people = more mouths to feed. Immigration is a direct demand driver for supermarkets."},
        ],
        "risks": ["Margin compression from price wars", "ACCC regulation", "Supply chain disruptions", "Private label cannibalisation"],
    },

    "Real Estate": {
        "what_they_do": "REITs (Real Estate Investment Trusts) that own and manage commercial, retail, industrial, or residential property. Revenue from rents and property valuations.",
        "products": ["Shopping centres", "Office buildings", "Industrial/logistics warehouses", "Residential developments"],
        "drivers": [
            "Interest rates (directly impacts property valuations and borrowing costs)",
            "Occupancy rates and lease terms",
            "Property valuations (cap rates)",
            "E-commerce growth (drives industrial, hurts retail)",
            "Work-from-home trends (impacts office demand)",
        ],
        "sensitivities": [
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 3,
             "why": "REITs are the most rate-sensitive sector — higher rates increase borrowing costs and compress property valuations (cap rates rise)"},
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 2,
             "why": "Strong economy = higher occupancy, rent growth, and property demand"},
            {"factor": "inflation", "label": "Inflation", "direction": "mixed", "weight": 2,
             "why": "Rents often have CPI escalators (good), but higher rates from inflation crush valuations (bad)"},
        ],
        "risks": ["Rising interest rates", "Vacancy increases", "E-commerce disruption (retail REITs)", "Work-from-home (office REITs)", "Tenant defaults"],
    },

    "Industrials": {
        "what_they_do": "Infrastructure, transport, engineering, and industrial services. Revenue tied to economic activity, construction, and trade volumes.",
        "products": ["Toll roads", "Airports", "Rail freight", "Engineering services", "Building materials", "Packaging"],
        "drivers": [
            "Infrastructure spending (government and private)",
            "Trade volumes and freight demand",
            "Construction activity",
            "Population growth and urbanisation",
            "Fuel costs (for transport companies)",
        ],
        "sensitivities": [
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 3,
             "why": "Industrial activity correlates directly with GDP — more economic activity = more freight, construction, and infrastructure use"},
            {"factor": "government_spending", "label": "Government Infrastructure Spending", "direction": "positive", "weight": 2,
             "why": "Major infrastructure projects (roads, rail, airports) are direct revenue drivers"},
            {"factor": "oil_price", "label": "Oil/Fuel Prices", "direction": "negative", "weight": 2,
             "why": "Transport and logistics companies face higher fuel costs — squeezes margins unless passed through"},
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 2,
             "why": "Capital-intensive businesses with high debt — rising rates increase financing costs"},
        ],
        "risks": ["Economic slowdown", "Rising fuel costs", "Regulatory changes (tolling)", "Construction downturn", "Supply chain disruptions"],
    },

    "Communication Services": {
        "what_they_do": "Telecoms, media, and communication platforms. Revenue from subscriptions, advertising, and data services.",
        "products": ["Mobile plans", "Broadband/NBN", "Media content", "Advertising platforms", "Data centres"],
        "drivers": [
            "Subscriber growth and ARPU (average revenue per user)",
            "Data consumption growth",
            "5G network investment",
            "Advertising market conditions",
            "Content costs and licensing",
        ],
        "sensitivities": [
            {"factor": "economic_growth", "label": "Economic Growth", "direction": "positive", "weight": 2,
             "why": "Advertising revenue is cyclical — businesses cut ad budgets in downturns"},
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 2,
             "why": "Telcos carry significant debt for network infrastructure — higher rates increase costs"},
            {"factor": "consumer_confidence", "label": "Consumer Spending", "direction": "positive", "weight": 1,
             "why": "Premium plans and add-ons are discretionary — consumers downgrade in tough times"},
        ],
        "risks": ["Network competition and price wars", "Rising content costs", "Regulatory (NBN pricing)", "Technology disruption", "High capex requirements"],
    },

    "Utilities": {
        "what_they_do": "Electricity, gas, and water providers. Revenue from regulated or contracted energy supply — often with predictable cash flows.",
        "products": ["Electricity generation", "Natural gas distribution", "Renewable energy", "Energy retail"],
        "drivers": [
            "Electricity demand and prices",
            "Renewable energy transition and subsidies",
            "Regulatory frameworks and price caps",
            "Weather patterns (extreme weather drives demand)",
            "Gas prices and input costs",
        ],
        "sensitivities": [
            {"factor": "interest_rates", "label": "Interest Rates", "direction": "negative", "weight": 2,
             "why": "Utilities are bond proxies — investors buy them for yield, so they compete with bond rates"},
            {"factor": "economic_cycle", "label": "Economic Cycle", "direction": "neutral", "weight": 1,
             "why": "Defensive — electricity demand is relatively stable. Outperforms in downturns."},
            {"factor": "regulation", "label": "Energy Regulation", "direction": "negative", "weight": 2,
             "why": "Government price caps and regulatory changes directly impact revenue and margins"},
            {"factor": "energy_transition", "label": "Energy Transition", "direction": "mixed", "weight": 2,
             "why": "Renewables investment is growth opportunity, but stranded fossil fuel assets are a risk"},
        ],
        "risks": ["Regulatory price caps", "Renewable transition costs", "Weather variability", "Carbon policy changes", "Grid reliability mandates"],
    },
}

# Aliases for common sector name variations (DB shorthand → profile key)
SECTOR_ALIASES = {
    "Mining": "Basic Materials",
    "Materials": "Basic Materials",
    "Financials": "Financial Services",
    "Finance": "Financial Services",
    "Banks": "Financial Services",
    "Consumer": "Consumer Cyclical",
    "Consumer Discretionary": "Consumer Cyclical",
    "Retail": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Property": "Real Estate",
    "REIT": "Real Estate",
    "Tech": "Technology",
    "Information Technology": "Technology",
    "Telecom": "Communication Services",
    "Telecommunications": "Communication Services",
}

# Fallback for sectors not explicitly mapped
DEFAULT_PROFILE = {
    "what_they_do": "Business details not yet mapped for this sector.",
    "products": [],
    "drivers": [],
    "sensitivities": [],
    "risks": [],
}


def get_sector_profile(sector):
    """Get the macro sensitivity profile for a sector."""
    # Try direct match first, then aliases
    if sector in SECTOR_PROFILES:
        return SECTOR_PROFILES[sector]
    canonical = SECTOR_ALIASES.get(sector, sector)
    return SECTOR_PROFILES.get(canonical, DEFAULT_PROFILE)


def score_macro_conditions(sector, macro_data, cycle_data):
    """Score current macro conditions for a given sector.

    Returns: {"score": -3 to +3, "label": str, "factors": [list of active factors]}
    """
    profile = get_sector_profile(sector)
    if not profile["sensitivities"]:
        return {"score": 0, "label": "Unknown", "color": "#8b8fa3", "factors": []}

    score = 0
    factors = []

    for sens in profile["sensitivities"]:
        factor = sens["factor"]
        weight = sens["weight"]
        direction = sens["direction"]

        # Score based on current macro data and cycle
        factor_score = 0

        if factor == "interest_rates":
            # High rates = positive score (we invert for negative direction)
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("contraction", "trough"):
                    factor_score = -1  # rates likely falling/low
                elif phase in ("late_expansion",):
                    factor_score = 1  # rates high/rising
                else:
                    factor_score = 0

        elif factor == "economic_growth":
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("early_expansion", "mid_expansion"):
                    factor_score = 1
                elif phase in ("contraction", "trough"):
                    factor_score = -1
                else:
                    factor_score = 0

        elif factor == "yield_curve":
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("early_expansion", "trough"):
                    factor_score = 1  # curve steepening
                elif phase in ("late_expansion", "contraction"):
                    factor_score = -1  # flat/inverted
                else:
                    factor_score = 0

        elif factor in ("commodity_prices", "oil_price"):
            # Check oil/gold from macro data
            if macro_data:
                for m in macro_data:
                    if m.get("label") == "Oil (WTI)" and m.get("change_pct", 0) > 2:
                        factor_score = 1
                    elif m.get("label") == "Oil (WTI)" and m.get("change_pct", 0) < -2:
                        factor_score = -1

        elif factor == "china_growth":
            # Use cycle as proxy
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("early_expansion", "mid_expansion"):
                    factor_score = 1
                elif phase in ("contraction", "trough"):
                    factor_score = -1

        elif factor == "aud_usd":
            if macro_data:
                for m in macro_data:
                    if m.get("label") == "AUD/USD":
                        chg = m.get("change_pct", 0)
                        if chg > 0.5:
                            factor_score = 1  # AUD rising
                        elif chg < -0.5:
                            factor_score = -1  # AUD falling

        elif factor == "consumer_confidence":
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("early_expansion", "mid_expansion"):
                    factor_score = 1
                elif phase in ("contraction", "trough"):
                    factor_score = -1

        elif factor == "unemployment":
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("contraction", "trough"):
                    factor_score = 1  # unemployment rising
                elif phase in ("mid_expansion",):
                    factor_score = -1  # unemployment low

        elif factor == "risk_appetite":
            # Use VIX as proxy
            if macro_data:
                for m in macro_data:
                    if m.get("label") == "VIX":
                        try:
                            vix_val = float(m.get("price", "20"))
                        except (ValueError, TypeError):
                            vix_val = 20
                        if vix_val < 16:
                            factor_score = 1  # risk on
                        elif vix_val > 25:
                            factor_score = -1  # risk off

        elif factor in ("inflation",):
            if cycle_data:
                phase = cycle_data.get("phase", "")
                if phase in ("late_expansion",):
                    factor_score = 1  # inflation elevated
                elif phase in ("contraction", "trough"):
                    factor_score = -1  # inflation falling

        elif factor == "economic_cycle":
            factor_score = 0  # neutral by definition for defensives

        # Apply direction
        if direction == "negative":
            factor_score = -factor_score
        elif direction in ("neutral", "mixed"):
            factor_score = 0

        weighted = factor_score * (weight / 3)  # normalise weight
        score += weighted

        if factor_score != 0:
            impact = "tailwind" if factor_score > 0 else "headwind"
            if direction == "negative":
                impact = "headwind" if factor_score > 0 else "tailwind"
            factors.append({
                "label": sens["label"],
                "impact": impact,
                "why": sens["why"],
            })

    # Normalise score to -3 to +3
    score = max(-3, min(3, round(score, 1)))

    if score >= 1.5:
        label = "Favourable"
        color = "#34d399"
    elif score >= 0.5:
        label = "Mildly Positive"
        color = "#6ee7b7"
    elif score > -0.5:
        label = "Neutral"
        color = "#fbbf24"
    elif score > -1.5:
        label = "Mildly Negative"
        color = "#fca5a5"
    else:
        label = "Unfavourable"
        color = "#f87171"

    return {"score": score, "label": label, "color": color, "factors": factors}
