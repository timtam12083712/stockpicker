"""Fundamental signal evaluation for ASX stocks.

Fetches fundamental data from yfinance and generates structured signal cards
covering Quality, Growth, Valuation, and Momentum categories.
"""

import time
import json
import threading
import yfinance as yf
from datetime import date

# Cache fundamental data per ticker (refreshes every 4 hours)
_fund_cache = {}
_fund_lock = threading.Lock()
_CACHE_TTL = 14400  # 4 hours


def _fetch_fundamental_data(ticker):
    """Fetch fundamental data from yfinance for a single ticker."""
    t = yf.Ticker(ticker)

    try:
        info = t.info or {}
    except Exception:
        info = {}

    try:
        hist_1y = t.history(period="1y")
    except Exception:
        hist_1y = None

    try:
        hist_6m = t.history(period="6mo")
    except Exception:
        hist_6m = None

    try:
        hist_3m = t.history(period="3mo")
    except Exception:
        hist_3m = None

    # Extract key fundamentals from info dict
    data = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),

        # Quality
        "roe": info.get("returnOnEquity"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "gross_margin": info.get("grossMargins"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),

        # Growth
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
        "revenue_per_share": info.get("revenuePerShare"),

        # Valuation
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        # yfinance returns dividendYield inconsistently — sometimes as 0.028, sometimes as 2.8
        # Use trailingAnnualDividendYield (always decimal) or normalise dividendYield
        "dividend_yield": info.get("trailingAnnualDividendYield") or (
            info.get("dividendYield") / 100 if info.get("dividendYield") and info["dividendYield"] > 1 else info.get("dividendYield")
        ),
        "payout_ratio": info.get("payoutRatio"),
        "free_cashflow": info.get("freeCashflow"),
        "market_cap": info.get("marketCap"),

        # Earnings dates
        "earnings_date": None,

        # Recommendation
        "analyst_target": info.get("targetMeanPrice"),
        "analyst_recommendation": info.get("recommendationKey"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),

        # 52-week
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_avg": info.get("fiftyDayAverage"),
        "two_hundred_day_avg": info.get("twoHundredDayAverage"),
    }

    # Calculate FCF yield
    if data["free_cashflow"] and data["market_cap"] and data["market_cap"] > 0:
        data["fcf_yield"] = data["free_cashflow"] / data["market_cap"]
    else:
        data["fcf_yield"] = None

    # Momentum: calculate returns from history
    if hist_3m is not None and len(hist_3m) >= 2:
        data["return_3m"] = (hist_3m["Close"].iloc[-1] / hist_3m["Close"].iloc[0] - 1)
    else:
        data["return_3m"] = None

    if hist_6m is not None and len(hist_6m) >= 2:
        data["return_6m"] = (hist_6m["Close"].iloc[-1] / hist_6m["Close"].iloc[0] - 1)
    else:
        data["return_6m"] = None

    # ASX200 relative strength (compare vs ^AXJO)
    try:
        axjo = yf.Ticker("^AXJO")
        axjo_3m = axjo.history(period="3mo")
        if axjo_3m is not None and len(axjo_3m) >= 2 and data["return_3m"] is not None:
            axjo_return = axjo_3m["Close"].iloc[-1] / axjo_3m["Close"].iloc[0] - 1
            data["relative_strength_3m"] = data["return_3m"] - axjo_return
        else:
            data["relative_strength_3m"] = None
    except Exception:
        data["relative_strength_3m"] = None

    # PE vs 5-year average — use forward vs trailing as proxy
    if data["pe_trailing"] and data["pe_forward"]:
        data["pe_vs_history"] = "cheap" if data["pe_forward"] < data["pe_trailing"] * 0.85 else \
                                "expensive" if data["pe_forward"] > data["pe_trailing"] * 1.15 else "fair"
    else:
        data["pe_vs_history"] = None

    return data


def get_fundamental_data(ticker):
    """Get fundamental data with caching."""
    with _fund_lock:
        cached = _fund_cache.get(ticker)
        if cached and time.time() - cached["ts"] < _CACHE_TTL:
            return cached["data"]

    data = _fetch_fundamental_data(ticker)

    with _fund_lock:
        _fund_cache[ticker] = {"data": data, "ts": time.time()}
    return data


def _evaluate_quality(data):
    """Evaluate quality signals."""
    tags = []
    details = {}

    # ROE
    roe = data.get("roe")
    if roe is not None:
        roe_pct = roe * 100
        details["roe"] = round(roe_pct, 1)
        if roe_pct >= 15:
            tags.append({"label": f"High ROE ({roe_pct:.0f}%)", "type": "bullish"})
        elif roe_pct >= 8:
            tags.append({"label": f"Moderate ROE ({roe_pct:.0f}%)", "type": "neutral"})
        elif roe_pct > 0:
            tags.append({"label": f"Low ROE ({roe_pct:.0f}%)", "type": "bearish"})
        else:
            tags.append({"label": f"Negative ROE ({roe_pct:.0f}%)", "type": "bearish"})

    # Profit margins
    margin = data.get("profit_margin")
    op_margin = data.get("operating_margin")
    if margin is not None:
        m_pct = margin * 100
        details["profit_margin"] = round(m_pct, 1)
        if m_pct >= 20:
            tags.append({"label": f"Strong Margins ({m_pct:.0f}%)", "type": "bullish"})
        elif m_pct >= 10:
            tags.append({"label": f"Healthy Margins ({m_pct:.0f}%)", "type": "neutral"})
        elif m_pct >= 0:
            tags.append({"label": f"Thin Margins ({m_pct:.0f}%)", "type": "bearish"})
        else:
            tags.append({"label": "Loss Making", "type": "bearish"})

    # Balance sheet — debt to equity
    dte = data.get("debt_to_equity")
    if dte is not None:
        details["debt_to_equity"] = round(dte, 1)
        if dte < 50:
            tags.append({"label": "Strong Balance Sheet", "type": "bullish"})
        elif dte < 100:
            tags.append({"label": "Moderate Debt", "type": "neutral"})
        elif dte < 200:
            tags.append({"label": "High Debt", "type": "bearish"})
        else:
            tags.append({"label": f"Very High Debt ({dte:.0f}%)", "type": "bearish"})

    # Current ratio
    cr = data.get("current_ratio")
    if cr is not None:
        details["current_ratio"] = round(cr, 2)
        if cr >= 2.0:
            tags.append({"label": "Strong Liquidity", "type": "bullish"})
        elif cr < 1.0:
            tags.append({"label": "Liquidity Risk", "type": "bearish"})

    return {"category": "Quality", "tags": tags, "details": details}


def _evaluate_growth(data):
    """Evaluate growth signals."""
    tags = []
    details = {}

    # Revenue growth
    rev_g = data.get("revenue_growth")
    if rev_g is not None:
        rg_pct = rev_g * 100
        details["revenue_growth"] = round(rg_pct, 1)
        if rg_pct >= 15:
            tags.append({"label": f"Strong Revenue Growth ({rg_pct:.0f}%)", "type": "bullish"})
        elif rg_pct >= 5:
            tags.append({"label": f"Steady Revenue Growth ({rg_pct:.0f}%)", "type": "neutral"})
        elif rg_pct >= 0:
            tags.append({"label": "Revenue Flat", "type": "neutral"})
        else:
            tags.append({"label": f"Revenue Declining ({rg_pct:.0f}%)", "type": "bearish"})

    # EPS / Earnings growth
    eps_g = data.get("earnings_growth")
    if eps_g is not None:
        eg_pct = eps_g * 100
        details["earnings_growth"] = round(eg_pct, 1)
        if eg_pct >= 20:
            tags.append({"label": f"Strong EPS Growth ({eg_pct:.0f}%)", "type": "bullish"})
        elif eg_pct >= 5:
            tags.append({"label": f"EPS Growing ({eg_pct:.0f}%)", "type": "neutral"})
        elif eg_pct >= -5:
            tags.append({"label": "EPS Flat", "type": "neutral"})
        else:
            tags.append({"label": f"EPS Declining ({eg_pct:.0f}%)", "type": "bearish"})

    # Earnings revisions proxy: forward PE vs trailing PE
    pe_t = data.get("pe_trailing")
    pe_f = data.get("pe_forward")
    if pe_t and pe_f and pe_t > 0 and pe_f > 0:
        if pe_f < pe_t * 0.85:
            tags.append({"label": "Earnings Upgrades", "type": "bullish"})
            details["earnings_revision"] = "upgrades"
        elif pe_f > pe_t * 1.15:
            tags.append({"label": "Earnings Downgrades", "type": "bearish"})
            details["earnings_revision"] = "downgrades"

    # Quarterly earnings growth
    q_g = data.get("earnings_quarterly_growth")
    if q_g is not None:
        qg_pct = q_g * 100
        details["quarterly_earnings_growth"] = round(qg_pct, 1)
        if qg_pct >= 25:
            tags.append({"label": f"Quarterly Beat ({qg_pct:.0f}%)", "type": "bullish"})
        elif qg_pct < -15:
            tags.append({"label": f"Quarterly Miss ({qg_pct:.0f}%)", "type": "bearish"})

    return {"category": "Growth", "tags": tags, "details": details}


def _evaluate_valuation(data):
    """Evaluate valuation signals."""
    tags = []
    details = {}

    # PE ratio
    pe = data.get("pe_trailing")
    pe_f = data.get("pe_forward")
    if pe is not None and pe > 0:
        details["pe_trailing"] = round(pe, 1)
        if pe < 12:
            tags.append({"label": f"Low PE ({pe:.0f}x)", "type": "bullish"})
        elif pe < 20:
            tags.append({"label": f"Moderate PE ({pe:.0f}x)", "type": "neutral"})
        elif pe < 30:
            tags.append({"label": f"High PE ({pe:.0f}x)", "type": "neutral"})
        else:
            tags.append({"label": f"Expensive PE ({pe:.0f}x)", "type": "bearish"})

    if pe_f is not None and pe_f > 0:
        details["pe_forward"] = round(pe_f, 1)

    # PE vs history
    pe_hist = data.get("pe_vs_history")
    if pe_hist == "cheap":
        tags.append({"label": "Undervalued vs History", "type": "bullish"})
    elif pe_hist == "expensive":
        tags.append({"label": "Expensive vs History", "type": "bearish"})

    # Dividend yield
    div_y = data.get("dividend_yield")
    if div_y is not None:
        dy_pct = div_y * 100
        details["dividend_yield"] = round(dy_pct, 2)
        if dy_pct >= 5:
            tags.append({"label": f"High Yield ({dy_pct:.1f}%)", "type": "bullish"})
        elif dy_pct >= 3:
            tags.append({"label": f"Solid Yield ({dy_pct:.1f}%)", "type": "neutral"})
        elif dy_pct > 0:
            tags.append({"label": f"Low Yield ({dy_pct:.1f}%)", "type": "neutral"})

    # Payout ratio
    payout = data.get("payout_ratio")
    if payout is not None:
        p_pct = payout * 100
        details["payout_ratio"] = round(p_pct, 0)
        if p_pct > 90:
            tags.append({"label": "Unsustainable Payout", "type": "bearish"})

    # FCF yield
    fcf_y = data.get("fcf_yield")
    if fcf_y is not None:
        fy_pct = fcf_y * 100
        details["fcf_yield"] = round(fy_pct, 1)
        if fy_pct >= 8:
            tags.append({"label": f"Strong FCF Yield ({fy_pct:.0f}%)", "type": "bullish"})
        elif fy_pct >= 4:
            tags.append({"label": f"Healthy FCF Yield ({fy_pct:.0f}%)", "type": "neutral"})
        elif fy_pct < 0:
            tags.append({"label": "Negative FCF", "type": "bearish"})

    # Price to book
    ptb = data.get("price_to_book")
    if ptb is not None and ptb > 0:
        details["price_to_book"] = round(ptb, 1)

    # Analyst target
    target = data.get("analyst_target")
    price = data.get("current_price")
    n_analysts = data.get("number_of_analysts")
    if target and price and price > 0 and n_analysts and n_analysts >= 3:
        upside = (target - price) / price * 100
        details["analyst_upside"] = round(upside, 1)
        details["analyst_target"] = round(target, 2)
        details["number_of_analysts"] = n_analysts
        if upside >= 15:
            tags.append({"label": f"Analyst Upside ({upside:.0f}%)", "type": "bullish"})
        elif upside <= -10:
            tags.append({"label": f"Analyst Downside ({upside:.0f}%)", "type": "bearish"})

    return {"category": "Valuation", "tags": tags, "details": details}


def _evaluate_momentum(data):
    """Evaluate momentum signals (fundamental + price combined)."""
    tags = []
    details = {}

    price = data.get("current_price")
    ma200 = data.get("two_hundred_day_avg")
    ma50 = data.get("fifty_day_avg")

    # Price vs 200DMA
    if price and ma200 and ma200 > 0:
        pct_vs_200 = (price - ma200) / ma200 * 100
        details["pct_vs_200dma"] = round(pct_vs_200, 1)
        if pct_vs_200 > 5:
            tags.append({"label": "Above 200DMA", "type": "bullish"})
        elif pct_vs_200 < -5:
            tags.append({"label": "Below 200DMA", "type": "bearish"})

    # 50MA vs 200MA trend
    if ma50 and ma200 and ma200 > 0:
        if ma50 > ma200:
            tags.append({"label": "Uptrend (50 > 200)", "type": "bullish"})
        else:
            tags.append({"label": "Downtrend (50 < 200)", "type": "bearish"})

    # Relative strength vs ASX200
    rs = data.get("relative_strength_3m")
    if rs is not None:
        rs_pct = rs * 100
        details["relative_strength_3m"] = round(rs_pct, 1)
        if rs_pct > 5:
            tags.append({"label": f"Outperforming Index (+{rs_pct:.0f}%)", "type": "bullish"})
        elif rs_pct < -5:
            tags.append({"label": f"Underperforming Index ({rs_pct:.0f}%)", "type": "bearish"})

    # 3M and 6M returns
    r3 = data.get("return_3m")
    if r3 is not None:
        r3_pct = r3 * 100
        details["return_3m"] = round(r3_pct, 1)
        if r3_pct > 10:
            tags.append({"label": f"Strong 3M ({r3_pct:+.0f}%)", "type": "bullish"})
        elif r3_pct < -10:
            tags.append({"label": f"Weak 3M ({r3_pct:+.0f}%)", "type": "bearish"})

    r6 = data.get("return_6m")
    if r6 is not None:
        r6_pct = r6 * 100
        details["return_6m"] = round(r6_pct, 1)

    # 52-week position
    h52 = data.get("fifty_two_week_high")
    l52 = data.get("fifty_two_week_low")
    if price and h52 and l52 and h52 > l52:
        pos = (price - l52) / (h52 - l52) * 100
        details["52w_position"] = round(pos, 0)
        if pos >= 90:
            tags.append({"label": "Near 52w High", "type": "neutral"})
        elif pos <= 10:
            tags.append({"label": "Near 52w Low", "type": "neutral"})

    return {"category": "Momentum", "tags": tags, "details": details}


def _evaluate_risks(data):
    """Identify key risk flags."""
    flags = []

    # High debt
    dte = data.get("debt_to_equity")
    if dte is not None and dte > 150:
        flags.append("High Debt")

    # Earnings downgrades
    pe_t = data.get("pe_trailing")
    pe_f = data.get("pe_forward")
    if pe_t and pe_f and pe_t > 0 and pe_f > pe_t * 1.15:
        flags.append("Earnings Downgrades")

    # Declining margins
    margin = data.get("profit_margin")
    if margin is not None and margin < 0.05:
        flags.append("Thin Margins")

    # Loss making
    if margin is not None and margin < 0:
        flags.append("Loss Making")

    # Overvaluation
    pe = data.get("pe_trailing")
    if pe is not None and pe > 35:
        flags.append("Expensive Valuation")

    # Negative FCF
    fcf = data.get("free_cashflow")
    if fcf is not None and fcf < 0:
        flags.append("Negative Free Cash Flow")

    # Unsustainable dividend
    payout = data.get("payout_ratio")
    if payout is not None and payout > 1.0:
        flags.append("Unsustainable Dividend")

    # Liquidity risk
    cr = data.get("current_ratio")
    if cr is not None and cr < 0.8:
        flags.append("Liquidity Risk")

    # Weak momentum
    r3 = data.get("return_3m")
    r6 = data.get("return_6m")
    if r3 is not None and r6 is not None and r3 < -0.15 and r6 < -0.15:
        flags.append("Sustained Decline")

    return flags


def _calculate_overall_rating(quality, growth, valuation, momentum, risks):
    """Calculate overall rating from signal categories."""
    score = 0

    for cat in [quality, growth, valuation, momentum]:
        for tag in cat["tags"]:
            if tag["type"] == "bullish":
                score += 1
            elif tag["type"] == "bearish":
                score -= 1

    # Risks weigh heavily
    score -= len(risks) * 0.5

    if score >= 3:
        return "bullish"
    elif score <= -2:
        return "bearish"
    else:
        return "neutral"


def _generate_summary(data, rating, quality, growth, valuation, momentum, risks):
    """Generate a 1-2 line plain English summary."""
    parts = []
    name = data.get("name", data["ticker"])

    # Quality summary
    roe = data.get("roe")
    margin = data.get("profit_margin")
    if roe and roe >= 0.15 and margin and margin >= 0.15:
        parts.append("high-quality compounder")
    elif roe and roe >= 0.10:
        parts.append("solid operator")
    elif margin and margin < 0:
        parts.append("loss-making business")

    # Growth
    rev_g = data.get("revenue_growth")
    eps_g = data.get("earnings_growth")
    if eps_g and eps_g >= 0.20:
        parts.append("with strong earnings momentum")
    elif rev_g and rev_g >= 0.10:
        parts.append("with healthy revenue growth")
    elif rev_g and rev_g < 0:
        parts.append("with declining revenue")
    elif eps_g and eps_g < -0.10:
        parts.append("with falling earnings")

    # Valuation
    pe = data.get("pe_trailing")
    if pe and pe > 30:
        parts.append("but trading at a premium valuation")
    elif pe and pe < 12:
        parts.append("at an attractive valuation")

    # Risks
    if len(risks) >= 3:
        parts.append("— multiple risk flags warrant caution")
    elif "High Debt" in risks:
        parts.append("— balance sheet leverage is a concern")
    elif "Earnings Downgrades" in risks:
        parts.append("— analyst estimates trending down")

    if parts:
        summary = " ".join(parts)
        # Capitalize first letter
        summary = summary[0].upper() + summary[1:]
        if not summary.endswith("."):
            summary += "."
        return summary

    if rating == "bullish":
        return "Fundamentals are solid with positive momentum."
    elif rating == "bearish":
        return "Weakening fundamentals suggest caution."
    return "Mixed signals — no strong conviction either way."


def _determine_action(rating, risks, data):
    """Determine action label: BUY CANDIDATE, WATCHLIST, or AVOID."""
    if rating == "bearish" or len(risks) >= 3:
        return "avoid"

    if rating == "bullish" and len(risks) <= 1:
        # Check valuation isn't extreme
        pe = data.get("pe_trailing")
        if pe and pe > 35:
            return "watchlist"
        return "buy_candidate"

    return "watchlist"


def generate_signal_card(ticker):
    """Generate a complete signal card for a stock.

    Returns a dict with all signal data ready for template rendering.
    """
    data = get_fundamental_data(ticker)

    if not data or not data.get("current_price"):
        return None

    quality = _evaluate_quality(data)
    growth = _evaluate_growth(data)
    valuation = _evaluate_valuation(data)
    momentum = _evaluate_momentum(data)
    risks = _evaluate_risks(data)
    rating = _calculate_overall_rating(quality, growth, valuation, momentum, risks)
    summary = _generate_summary(data, rating, quality, growth, valuation, momentum, risks)
    action = _determine_action(rating, risks, data)

    return {
        "ticker": ticker.replace(".AX", ""),
        "ticker_full": ticker,
        "name": data.get("name", ticker),
        "sector": data.get("sector", ""),
        "industry": data.get("industry", ""),
        "date": date.today().isoformat(),
        "current_price": data.get("current_price"),
        "rating": rating,
        "categories": [quality, growth, valuation, momentum],
        "risks": risks,
        "summary": summary,
        "action": action,
        "fundamentals": data,
    }


def generate_all_signal_cards(tickers):
    """Generate signal cards for a list of tickers."""
    cards = []
    for ticker in tickers:
        try:
            card = generate_signal_card(ticker)
            if card:
                cards.append(card)
        except Exception:
            continue
        time.sleep(0.5)  # Be kind to yfinance
    return cards
