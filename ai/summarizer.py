"""Generate plain-English AI signal summaries using Claude API."""

import anthropic

from config import Config
from data.corporate_actions import get_upcoming_dividends, get_recent_splits


SUMMARY_PROMPT = """You are an ASX stock analysis assistant for a personal learning tool.
A signal has fired for a stock on the user's watchlist. Your job is to explain what the
signal means in plain English, provide recent price context, and flag anything worth
considering. You do NOT recommend buying or selling.

Your summary should include:
- Which signal(s) fired and a plain-English explanation
- Recent price context (last 5-10 trading days)
- Current indicator values (RSI, MA levels, volume vs average)
- Any corporate action flags (upcoming dividend, recent split)
- A neutral "things to consider" note
- End with: "This is a signal, not a recommendation. Review the chart on TradingView before acting."

Keep it concise — 150-250 words."""


def generate_signal_summary(
    ticker: str,
    signal_name: str,
    indicators: dict,
    stock_name: str = "",
) -> str:
    """Call Claude API to generate a plain-English signal summary."""
    if not Config.ANTHROPIC_API_KEY:
        return f"[AI summary unavailable — set ANTHROPIC_API_KEY in .env]\n{signal_name} fired for {ticker}"

    # Check for nearby corporate actions
    upcoming_divs = get_upcoming_dividends(days_ahead=14)
    recent_splits = get_recent_splits(days_back=30)

    ticker_divs = [d for d in upcoming_divs if d["ticker"] == ticker]
    ticker_splits = [s for s in recent_splits if s["ticker"] == ticker]

    corporate_context = ""
    if ticker_divs:
        d = ticker_divs[0]
        corporate_context += f"\nUpcoming dividend: ${d['value']} on {d['date']}"
    if ticker_splits:
        s = ticker_splits[0]
        corporate_context += f"\nRecent split: {s.get('raw_ratio', s['value'])} on {s['date']}"

    user_message = f"""Stock: {ticker} ({stock_name})
Signal fired: {signal_name}

Current indicators:
- Price: ${indicators.get('current_price', 'N/A')}
- Daily change: {indicators.get('daily_change_pct', 'N/A')}%
- RSI (14): {indicators.get('rsi', 'N/A')}
- 50-day MA: ${indicators.get('sma_50', 'N/A')}
- 200-day MA: ${indicators.get('sma_200', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')} (Signal: {indicators.get('macd_signal', 'N/A')})
- Volume ratio (vs 20d avg): {indicators.get('volume_ratio', 'N/A')}x
- 52-week high: ${indicators.get('high_52w', 'N/A')}
- 52-week low: ${indicators.get('low_52w', 'N/A')}
- Bollinger upper: ${indicators.get('bb_upper', 'N/A')}
- Bollinger lower: ${indicators.get('bb_lower', 'N/A')}
{corporate_context}

Please provide a plain-English summary of this signal."""

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=Config.CLAUDE_MODEL,
        max_tokens=500,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
