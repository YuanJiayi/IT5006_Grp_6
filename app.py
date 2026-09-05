"""Streamlit layout for the IT5006 Olist dashboard."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import (
    build_commercial_series,
    build_delivery_experience_series,
    build_delivery_review_analysis,
    build_delivery_series,
    build_growth_series,
    build_retention_series,
    build_review_series,
    eligible_deliveries,
    latest_reviews as select_latest_reviews,
    load_customer_ids,
    load_data,
    load_reviews,
)

DATA_PATH = Path("data/smartcommerce_consolidated.csv")
CUSTOMERS_PATH = Path("data/olist_customers_dataset.csv")
REVIEWS_PATH = Path("data/olist_order_reviews_dataset.csv")

st.set_page_config(page_title="IT5006 Olist Dashboard", layout="wide")
st.title("Olist E-Commerce Dashboard")

overview_tab, delivery_tab = st.tabs(["Overview", "Delivery"])

with overview_tab:
    required_paths = [DATA_PATH, CUSTOMERS_PATH, REVIEWS_PATH]
    if not all(path.exists() for path in required_paths):
        st.error("Required dashboard data files could not be found in the `data` folder.")
        st.stop()

    line_items = load_data(DATA_PATH)
    customer_ids = load_customer_ids(CUSTOMERS_PATH)
    reviews = load_reviews(REVIEWS_PATH)
    order_data = (
        line_items.drop_duplicates("order_id")
        .merge(customer_ids, on="customer_id", how="left", validate="one_to_one")
    )

    purchase_time = line_items["order_purchase_timestamp"]
    order_count = line_items["order_id"].nunique()
    product_revenue = line_items["price"].sum()
    items_sold = len(line_items)
    seller_count = line_items["seller_id"].nunique()

    st.caption(
        f"Purchase-date coverage: {purchase_time.min():%d %b %Y} – "
        f"{purchase_time.max():%d %b %Y}"
    )
    st.caption("Trend charts show January 2017 to August 2018, excluding launch and partial boundary periods.")
    sales_metric, orders_metric, items_metric, sellers_metric = st.columns(4)
    sales_metric.metric("Product sales", f"R$ {product_revenue:,.0f}")
    orders_metric.metric("Total orders", f"{order_count:,}")
    items_metric.metric("Items sold", f"{items_sold:,}")
    sellers_metric.metric("Number of sellers", f"{seller_count:,}")

    st.subheader("Dataset composition")
    state_orders = (
        line_items.groupby("customer_state")["order_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    top_states = state_orders.head(15)
    other_state_orders = state_orders.iloc[15:].sum()
    state_composition = top_states.rename_axis("Customer state").reset_index(name="Orders")
    if other_state_orders:
        state_composition = pd.concat(
            [
                state_composition,
                pd.DataFrame({"Customer state": ["Other"], "Orders": [other_state_orders]}),
            ],
            ignore_index=True,
        ).sort_values("Orders", ascending=False)
    state_composition["Order share (%)"] = state_composition["Orders"] / order_count * 100

    category_composition = (
        line_items.assign(
            product_category_name_english=line_items[
                "product_category_name_english"
            ].fillna("Unknown")
        )
        .groupby("product_category_name_english")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .rename_axis("Product category")
        .reset_index(name="Items sold")
    )
    category_composition["Item share (%)"] = (
        category_composition["Items sold"] / items_sold * 100
    )
    state_chart, category_chart = st.columns(2)
    with state_chart:
        st.markdown("#### Top customer states by orders")
        state_bars = alt.Chart(state_composition).mark_bar(color="#003D7C").encode(
            y=alt.Y(
                "Customer state:N",
                title=None,
                sort=state_composition["Customer state"].tolist(),
                axis=alt.Axis(labelOverlap=False),
            ),
            x=alt.X("Orders:Q", title="Orders"),
            tooltip=[
                alt.Tooltip("Customer state:N", title="Customer state"),
                alt.Tooltip("Orders:Q", title="Orders", format=","),
                alt.Tooltip("Order share (%):Q", title="Share of orders", format=".1f"),
            ],
        )
        st.altair_chart(
            state_bars.properties(height=360), use_container_width=True
        )
    with category_chart:
        st.markdown("#### Top product categories")
        category_bars = alt.Chart(category_composition).mark_bar(color="#EF7C00").encode(
            y=alt.Y(
                "Product category:N",
                title=None,
                sort=category_composition["Product category"].tolist(),
                axis=alt.Axis(labelOverlap=False),
            ),
            x=alt.X("Items sold:Q", title="Items sold"),
            tooltip=[
                alt.Tooltip("Product category:N", title="Product category"),
                alt.Tooltip("Items sold:Q", title="Items sold", format=","),
                alt.Tooltip("Item share (%):Q", title="Share of items sold", format=".1f"),
            ],
        )
        st.altair_chart(
            category_bars.properties(height=360),
            use_container_width=True,
        )

    granularity = st.selectbox("Time granularity", ["Day", "Month", "Year"], index=1)
    growth_series = build_growth_series(line_items, granularity)

    st.subheader("Growth over time")
    growth_metric = st.selectbox("Metric", ["Product sales", "Total orders", "Items sold"])
    growth_columns = {
        "Total orders": "Total orders",
        "Product sales": "Product sales",
        "Items sold": "Items sold",
    }
    growth_display = growth_series.rename(
        columns={
            "orders": "Total orders",
            "product_revenue": "Product sales",
            "items_sold": "Items sold",
        }
    )
    st.line_chart(growth_display, x="period", y=growth_columns[growth_metric])
    st.caption("Product sales exclude freight.")

    st.subheader("Commercial performance")
    commercial_series = build_commercial_series(line_items, granularity)
    aov_metric, basket_metric = st.columns(2)
    aov_metric.metric("Average order value", f"R$ {product_revenue / order_count:,.2f}")
    basket_metric.metric("Items per order", f"{items_sold / order_count:.2f}")
    commercial_metric = st.selectbox("Commercial metric", ["Average order value", "Items per order"])
    commercial_columns = {
        "Average order value": "Average order value",
        "Items per order": "Items per order",
    }
    commercial_display = commercial_series.rename(
        columns={
            "average_order_value": "Average order value",
            "items_per_order": "Items per order",
        }
    )
    st.line_chart(commercial_display, x="period", y=commercial_columns[commercial_metric])

    st.subheader("Customer experience")
    order_reviews = select_latest_reviews(reviews)
    average_score = order_reviews["review_score"].mean()
    low_rating_rate = order_reviews["review_score"].le(2).mean()
    satisfaction_proxy = (
        order_reviews["review_score"].eq(5).mean() - low_rating_rate
    ) * 100
    score_metric, low_rating_metric, proxy_metric = st.columns(3)
    score_metric.metric("Average review score", f"{average_score:.2f} / 5")
    low_rating_metric.metric("Low-rating rate", f"{low_rating_rate:.1%}")
    proxy_metric.metric("NPS proxy", f"{satisfaction_proxy:.1f}")
    experience_series = build_review_series(order_data, reviews, granularity)
    experience_metric = st.selectbox(
        "Customer-experience metric",
        ["Average review score", "Low-rating rate", "NPS proxy"],
    )
    experience_columns = {
        "Average review score": "Average review score",
        "Low-rating rate": "Low-rating rate (%)",
        "NPS proxy": "NPS proxy",
    }
    experience_display = experience_series.rename(
        columns={
            "average_review_score": "Average review score",
            "low_rating_rate": "Low-rating rate (%)",
            "satisfaction_proxy": "NPS proxy",
        }
    )
    st.line_chart(experience_display, x="period", y=experience_columns[experience_metric])
    st.caption(
        "Low rating: 1–2 stars · NPS proxy: 5-star rate − low-rating rate."
    )

    st.subheader("Customer retention")
    retention_series, repeat_customer_rate = build_retention_series(order_data, granularity)
    retention_metric = st.columns(1)[0]
    retention_metric.metric("Customers with a repeat order", f"{repeat_customer_rate:.1%}")
    retention_display = retention_series.rename(
        columns={"returning_customer_share": "Returning-customer share (%)"}
    )
    st.line_chart(retention_display, x="period", y="Returning-customer share (%)")
    st.caption("Share of customers purchasing in each period who had ordered previously.")

with delivery_tab:
    if not DATA_PATH.exists():
        st.error(f"Dataset not found: `{DATA_PATH}`")
        st.stop()

    delivery_line_items = load_data(DATA_PATH)
    delivery_orders = delivery_line_items.drop_duplicates("order_id")
    st.caption("Trend charts show January 2017 to August 2018, excluding launch and partial boundary periods.")
    delivery_series = build_delivery_series(delivery_orders, granularity)
    eligible_delivery_orders = eligible_deliveries(delivery_orders)
    delivery_days = (
        eligible_delivery_orders["order_delivered_customer_date"]
        - eligible_delivery_orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 86_400
    median_delivery_days = delivery_days.median()
    late_delivery_rate = (
        eligible_delivery_orders["order_delivered_customer_date"]
        > eligible_delivery_orders["order_estimated_delivery_date"]
    ).mean() * 100

    st.subheader("Delivery performance")
    median_metric, late_metric = st.columns(2)
    median_metric.metric("Median delivery time", f"{median_delivery_days:.1f} days")
    late_metric.metric("Late-delivery rate", f"{late_delivery_rate:.1f}%")

    delivery_metric = st.selectbox("Delivery metric", ["Median delivery time", "Late-delivery rate"])
    delivery_columns = {
        "Median delivery time": "Median delivery time (days)",
        "Late-delivery rate": "Late-delivery rate (%)",
    }
    delivery_display = delivery_series.rename(
        columns={
            "median_delivery_days": "Median delivery time (days)",
            "late_delivery_rate": "Late-delivery rate (%)",
        }
    )
    st.line_chart(delivery_display, x="period", y=delivery_columns[delivery_metric])
    st.caption("Late = delivered after estimated delivery date.")

    delivery_reviews = load_reviews(REVIEWS_PATH)
    st.subheader("Late-delivery rate and low-rating rate over time")
    delivery_experience_series = build_delivery_experience_series(
        delivery_orders, delivery_reviews
    )
    st.line_chart(
        delivery_experience_series,
        x="period",
        y=["Late-delivery rate (%)", "Low-rating rate (%)"],
    )
    st.caption(
        "Monthly rates for delivered orders with a review. Low rating: 1–2 stars."
    )

    st.subheader("Late delivery vs. low ratings")
    comparison, severity, risk_ratio = build_delivery_review_analysis(
        delivery_orders, delivery_reviews
    )
    on_time_low_rate = comparison.loc[
        comparison["delivery_timing"].eq("On time or early"), "low_rating_rate"
    ].iloc[0]
    late_low_rate = comparison.loc[
        comparison["delivery_timing"].eq("Late"), "low_rating_rate"
    ].iloc[0]
    on_time_metric, late_review_metric, risk_metric = st.columns(3)
    on_time_metric.metric("On-time low-rating rate", f"{on_time_low_rate:.1f}%")
    late_review_metric.metric("Late-order low-rating rate", f"{late_low_rate:.1f}%")
    risk_metric.metric("Late-order risk ratio", f"{risk_ratio:.2f}×")

    comparison_chart, severity_chart = st.columns(2)
    with comparison_chart:
        st.markdown("#### On-time versus late orders")
        comparison["low_rating_label"] = comparison["low_rating_rate"].map(
            lambda rate: f"{rate:.1f}%"
        )
        bars = alt.Chart(comparison).mark_bar().encode(
            x=alt.X("delivery_timing:N", title=None),
            y=alt.Y(
                "low_rating_rate:Q",
                title="Low-rating rate (%)",
                scale=alt.Scale(domain=[0, 80]),
            ),
            color=alt.Color("delivery_timing:N", legend=None),
            tooltip=[
                alt.Tooltip("delivery_timing:N", title="Delivery timing"),
                alt.Tooltip("low_rating_rate:Q", title="Low-rating rate", format=".1f"),
            ],
        )
        labels = bars.mark_text(dy=-8, color="#003D7C").encode(
            text="low_rating_label:N"
        )
        st.altair_chart((bars + labels).properties(height=280), use_container_width=True)
    with severity_chart:
        st.markdown("#### Low ratings by lateness severity")
        severity_display = severity.rename(
            columns={"low_rating_rate": "Low-rating rate (%)"}
        )
        severity_display["low_rating_label"] = severity_display["Low-rating rate (%)"].map(
            lambda rate: f"{rate:.1f}%"
        )
        severity_bars = alt.Chart(severity_display).mark_bar().encode(
            x=alt.X(
                "lateness_band:N",
                title=None,
                sort=["On time or early", "1–3 days late", "4–7 days late", "8+ days late"],
            ),
            y=alt.Y(
                "Low-rating rate (%):Q",
                title="Low-rating rate (%)",
                scale=alt.Scale(domain=[0, 80]),
            ),
            color=alt.Color("lateness_band:N", legend=None),
            tooltip=[
                alt.Tooltip("lateness_band:N", title="Lateness"),
                alt.Tooltip("Low-rating rate (%):Q", title="Low-rating rate", format=".1f"),
            ],
        )
        severity_labels = severity_bars.mark_text(dy=-8, color="#003D7C").encode(
            text="low_rating_label:N"
        )
        st.altair_chart(
            (severity_bars + severity_labels).properties(height=280),
            use_container_width=True,
        )
    st.caption("Low rating: 1–2 stars. Each order uses its latest review record.")
