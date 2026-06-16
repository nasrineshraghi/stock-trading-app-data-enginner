from __future__ import annotations

import pandas as pd
import streamlit as st

from stock_pipeline.config import get_settings
from stock_pipeline.dashboard.data import filter_tickers, list_tickers, load_dashboard_data


@st.cache_data(ttl=300, show_spinner="Loading market data…")
def cached_load(source: str) -> tuple:
    settings = get_settings()
    return load_dashboard_data(settings, source=source)


def _metric_columns(latest_row) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Latest close", f"${latest_row['close']:.2f}")
    daily_return = latest_row["daily_return_pct"]
    if pd.isna(daily_return):
        col2.metric("Daily return", "—")
    else:
        col2.metric("Daily return", f"{daily_return:+.2f}%")
    col3.metric("Volume", f"{latest_row['volume']:,.0f}")
    col4.metric("Last date", str(latest_row["date"].date()))


def _price_chart(df) -> None:
    import plotly.express as px

    fig = px.line(
        df,
        x="date",
        y="close",
        color="ticker",
        markers=True,
        title="Closing price",
        labels={"date": "Date", "close": "Close (USD)", "ticker": "Ticker"},
    )
    fig.update_layout(hovermode="x unified", height=420)
    st.plotly_chart(fig, use_container_width=True)


def _candlestick_chart(df, ticker: str) -> None:
    import plotly.graph_objects as go

    single = df[df["ticker"] == ticker]
    if single.empty:
        return

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=single["date"],
                open=single["open"],
                high=single["high"],
                low=single["low"],
                close=single["close"],
                name=ticker,
            )
        ]
    )
    fig.update_layout(title=f"{ticker} candlestick", xaxis_title="Date", height=420)
    st.plotly_chart(fig, use_container_width=True)


def _returns_chart(df) -> None:
    import plotly.express as px

    returns = df.dropna(subset=["daily_return_pct"])
    if returns.empty:
        st.info("Daily returns appear after the second trading day per ticker.")
        return

    fig = px.bar(
        returns,
        x="date",
        y="daily_return_pct",
        color="ticker",
        barmode="group",
        title="Daily return (%)",
        labels={"date": "Date", "daily_return_pct": "Return %", "ticker": "Ticker"},
    )
    fig.update_layout(height=360)
    st.plotly_chart(fig, use_container_width=True)


def _volume_chart(df) -> None:
    import plotly.express as px

    fig = px.bar(
        df,
        x="date",
        y="volume",
        color="ticker",
        barmode="group",
        title="Volume",
        labels={"date": "Date", "volume": "Shares", "ticker": "Ticker"},
    )
    fig.update_layout(height=360)
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Stock OHLCV Dashboard",
        page_icon="📈",
        layout="wide",
    )

    st.title("Stock OHLCV Dashboard")
    st.caption("Daily bars and returns from your Snowflake dbt mart or processed CSV files.")

    with st.sidebar:
        st.header("Settings")
        source = st.radio(
            "Data source",
            options=["auto", "snowflake", "csv"],
            format_func=lambda value: {
                "auto": "Auto (Snowflake → CSV)",
                "snowflake": "Snowflake mart only",
                "csv": "Processed CSV only",
            }[value],
        )
        if st.button("Refresh data", type="primary"):
            cached_load.clear()

    try:
        df, source_label = cached_load(source)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    if df.empty:
        st.warning(
            "No data yet. Run ingest-batch with --snowflake, then `make dbt-run`."
        )
        st.stop()

    tickers = list_tickers(df)
    with st.sidebar:
        default_tickers = tickers[: min(3, len(tickers))]
        selected = st.multiselect("Tickers", options=tickers, default=default_tickers)

    filtered = filter_tickers(df, selected)
    if filtered.empty:
        st.warning("Select at least one ticker.")
        st.stop()

    st.success(f"Loaded {len(filtered):,} rows from **{source_label}**.")

    latest = filtered.sort_values("date").groupby("ticker", as_index=False).tail(1)
    if len(selected) == 1:
        _metric_columns(latest.iloc[0])
    else:
        st.dataframe(
            latest[
                ["ticker", "date", "close", "daily_return_pct", "volume"]
            ].rename(columns={"daily_return_pct": "daily_return_%"}),
            use_container_width=True,
            hide_index=True,
        )

    tab_prices, tab_candles, tab_returns, tab_volume, tab_table = st.tabs(
        ["Prices", "Candlestick", "Returns", "Volume", "Table"]
    )

    with tab_prices:
        _price_chart(filtered)

    with tab_candles:
        if len(selected) == 1:
            _candlestick_chart(filtered, selected[0])
        else:
            pick = st.selectbox("Ticker for candlestick", options=selected)
            _candlestick_chart(filtered, pick)

    with tab_returns:
        _returns_chart(filtered)

    with tab_volume:
        _volume_chart(filtered)

    with tab_table:
        st.dataframe(
            filtered.sort_values(["ticker", "date"], ascending=[True, False]),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
