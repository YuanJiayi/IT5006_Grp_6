"""Streamlit layout for the IT5006 Olist dashboard."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_data import (
    build_category_cuts,
    build_commercial_series,
    build_delivery_experience_series,
    build_delivery_review_analysis,
    build_delivery_series,
    build_distance_buckets,
    build_distance_table,
    build_growth_series,
    build_leadtime_decomposition,
    build_retention_series,
    build_review_series,
    build_seller_cuts,
    eligible_deliveries,
    latest_reviews as select_latest_reviews,
    load_customer_ids,
    load_data,
    load_reviews,
)

DATA_PATH = Path("data/smartcommerce_consolidated.csv")
CUSTOMERS_PATH = Path("data/olist_customers_dataset.csv")
REVIEWS_PATH = Path("data/olist_order_reviews_dataset.csv")
ORDERS_PATH = Path("data/olist_orders_dataset.csv")
SELLERS_PATH = Path("data/olist_sellers_dataset.csv")
GEOLOCATION_PATH = Path("data/olist_geolocation_dataset.csv")

st.set_page_config(page_title="IT5006 Olist Dashboard", layout="wide")
st.title("Olist E-Commerce Dashboard")

overview_tab, delivery_tab, delivery_correlations_tab = st.tabs(
    ["Overview", "Delivery", "Delivery correlations"]
)

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

def boxed_label(text: str) -> None:
    """Render a filled label chip that captions the chart directly below it."""
    st.markdown(
        "<span style='display:inline-block;background:#003D7C;color:#FFFFFF;"
        "font-weight:600;font-size:0.85rem;letter-spacing:0.03em;"
        "text-transform:uppercase;padding:3px 12px;border-radius:4px;"
        f"margin-bottom:10px;'>{text}</span>",
        unsafe_allow_html=True,
    )


with delivery_correlations_tab:
    corr_required = [DATA_PATH, ORDERS_PATH, CUSTOMERS_PATH, SELLERS_PATH, GEOLOCATION_PATH, REVIEWS_PATH]
    if not all(path.exists() for path in corr_required):
        st.error("Required data files for this tab could not be found in the `data` folder.")
        st.stop()

    st.caption(
        "Order-level view. `order_approved_at` / `order_delivered_carrier_date` are "
        "read from `olist_orders_dataset.csv` (absent from the consolidated file) and "
        "merged on `order_id`."
    )

    (
        stage_summary,
        shipping_review,
        excluded_share,
        total_lead_mean,
    ) = build_leadtime_decomposition(ORDERS_PATH, REVIEWS_PATH)
    distance_table, dropped_share = build_distance_table(
        DATA_PATH, CUSTOMERS_PATH, SELLERS_PATH, GEOLOCATION_PATH, REVIEWS_PATH
    )
    distance_buckets = build_distance_buckets(distance_table)
    category_cuts = build_category_cuts(DATA_PATH, REVIEWS_PATH, min_orders=100)
    top_categories = category_cuts.head(13)
    category_order = top_categories["product_category_name_english"].tolist()
    seller_cuts = build_seller_cuts(DATA_PATH, REVIEWS_PATH, min_orders=20)
    volume_threshold = float(seller_cuts["orders"].quantile(0.90))
    seller_cuts = seller_cuts.assign(
        volume_band=lambda frame: frame["orders"]
        .ge(volume_threshold)
        .map({True: "Top-decile volume", False: "Other sellers"})
    )

    # Processing is a tiny slice, so it gets the high-contrast orange to pop;
    # handling takes the dark blue, shipping the lighter blue.
    STAGE_COLORS = ["#EF7C00", "#003D7C", "#7FA9D0"]

    row1_left, row1_right = st.columns(2)

    with row1_left:
        with st.container(border=True):
            boxed_label("Decomposition")
            stat_choice = st.radio(
                "Value used for the breakdown",
                ["Mean", "Median"],
                horizontal=True,
                key="leadtime_stat",
            )
            value_column = {"Mean": "mean_days", "Median": "median_days"}[stat_choice]
            stage_order = stage_summary["stage"].tolist()
            stage_share = stage_summary[["stage", value_column]].rename(columns={value_column: "days"})
            stage_share["share_pct"] = stage_share["days"] / stage_share["days"].sum() * 100
            stage_share["slice_label"] = stage_share.apply(
                lambda row: f"{row['days']:.1f}d ({row['share_pct']:.0f}%)", axis=1
            )

            stage_base = alt.Chart(stage_share).encode(
                theta=alt.Theta("days:Q", stack=True),
                color=alt.Color(
                    "stage:N",
                    title=None,
                    sort=stage_order,
                    scale=alt.Scale(domain=stage_order, range=STAGE_COLORS),
                    legend=alt.Legend(orient="bottom", columns=1),
                ),
                order=alt.Order("stage:N", sort="ascending"),
                tooltip=[
                    alt.Tooltip("stage:N", title="Stage"),
                    alt.Tooltip("days:Q", title=f"{stat_choice} days", format=".2f"),
                    alt.Tooltip("share_pct:Q", title="Share of shipping time", format=".1f"),
                ],
            )
            stage_pie = stage_base.mark_arc(outerRadius=88, stroke="#FFFFFF", strokeWidth=2)
            stage_pie_labels = stage_base.mark_text(radius=112, fontSize=12, fontWeight="bold").encode(
                text="slice_label:N", color=alt.value("#31333F")
            )
            st.altair_chart(
                (stage_pie + stage_pie_labels).properties(height=340),
                use_container_width=True,
            )
            total_selected = stage_share["days"].sum()
            st.caption(
                f"Slices show each stage's {stat_choice.lower()} duration as a share of "
                f"the three stages combined ({total_selected:.1f} days; mean total "
                f"shipping time {total_lead_mean:.1f} days). Shipping (carrier → "
                "customer) is the dominant stage. Toggle switches every slice between "
                f"the mean and the median stage duration. Excluded {excluded_share:.1f}% "
                "of orders with a negative stage duration (inconsistent timestamps) and "
                "any order missing one of the four timestamps."
            )

    with row1_right:
        with st.container(border=True):
            boxed_label("Mean review score")
            shipping_review_display = shipping_review.assign(
                shipping_bucket=shipping_review["shipping_bucket"].astype(str)
            )
            shipping_line = alt.Chart(shipping_review_display).mark_line(
                point=True, color="#EF7C00"
            ).encode(
                x=alt.X(
                    "shipping_bucket:N",
                    title="Shipping time (days, carrier → customer)",
                    sort=["0–3", "3–7", "7–14", "14–21", "21–30", "30+"],
                ),
                y=alt.Y("mean_review_score:Q", title="Mean review score", scale=alt.Scale(domain=[1, 5])),
                tooltip=[
                    alt.Tooltip("shipping_bucket:N", title="Shipping days"),
                    alt.Tooltip("mean_review_score:Q", title="Mean review score", format=".2f"),
                    alt.Tooltip("orders:Q", title="Orders", format=","),
                ],
            )
            st.altair_chart(shipping_line.properties(height=340), use_container_width=True)
            st.caption(
                f"Delivered orders with a review; negative-duration rows already excluded "
                f"({excluded_share:.1f}%). Buckets are days, right-open."
            )

    with st.container(border=True):
        boxed_label("Geographic distance")
        dist_left, dist_right = st.columns(2)
        with dist_left:
            st.markdown("###### Mean delivery days by customer–seller distance")
            dist_days = alt.Chart(distance_buckets).mark_bar(color="#003D7C").encode(
                x=alt.X(
                    "distance_label:N",
                    title="Distance (km)",
                    sort=distance_buckets["distance_label"].tolist(),
                ),
                y=alt.Y("mean_delivery_days:Q", title="Mean delivery days"),
                tooltip=[
                    alt.Tooltip("distance_label:N", title="Distance (km)"),
                    alt.Tooltip("mean_delivery_days:Q", title="Mean delivery days", format=".1f"),
                    alt.Tooltip("orders:Q", title="Orders", format=","),
                ],
            )
            st.altair_chart(dist_days.properties(height=300), use_container_width=True)
        with dist_right:
            st.markdown("###### Mean review score & late-rate by distance")
            base = alt.Chart(distance_buckets).encode(
                x=alt.X(
                    "distance_label:N",
                    title="Distance (km)",
                    sort=distance_buckets["distance_label"].tolist(),
                )
            )
            score_line = base.mark_line(point=True, color="#EF7C00").encode(
                y=alt.Y("mean_review_score:Q", title="Mean review score", scale=alt.Scale(domain=[1, 5])),
                tooltip=[
                    alt.Tooltip("distance_label:N", title="Distance (km)"),
                    alt.Tooltip("mean_review_score:Q", title="Mean review score", format=".2f"),
                    alt.Tooltip("late_rate:Q", title="Late rate (%)", format=".1f"),
                ],
            )
            late_line = base.mark_line(point=True, color="#003D7C", strokeDash=[4, 3]).encode(
                y=alt.Y("late_rate:Q", title="Late rate (%)"),
            )
            st.altair_chart(
                alt.layer(score_line, late_line).resolve_scale(y="independent").properties(height=300),
                use_container_width=True,
            )
        st.caption(
            "Distance is a haversine km between customer and seller zip-prefix "
            f"centroids (mean lat/lng per prefix from the geolocation table), not exact "
            f"addresses. Dropped {dropped_share:.1f}% of delivered orders whose customer "
            "or seller zip prefix is absent from the geolocation table. Buckets are "
            "sextiles of distance. Orange = review score (left axis), dashed blue = "
            "late rate (right axis)."
        )

    with st.container(border=True):
        boxed_label("Category")
        cat_left, cat_right = st.columns(2)
        with cat_left:
            st.markdown("###### Mean delivery days")
            cat_days = alt.Chart(top_categories).mark_bar(color="#003D7C").encode(
                y=alt.Y("product_category_name_english:N", title=None, sort=category_order),
                x=alt.X("mean_delivery_days:Q", title="Mean delivery days"),
                tooltip=[
                    alt.Tooltip("product_category_name_english:N", title="Category"),
                    alt.Tooltip("mean_delivery_days:Q", title="Mean delivery days", format=".1f"),
                    alt.Tooltip("orders:Q", title="Orders", format=","),
                ],
            )
            st.altair_chart(cat_days.properties(height=380), use_container_width=True)
        with cat_right:
            st.markdown("###### Mean review score")
            cat_score = alt.Chart(top_categories).mark_bar(color="#EF7C00").encode(
                y=alt.Y(
                    "product_category_name_english:N",
                    title=None,
                    sort=category_order,
                    axis=alt.Axis(labels=False),
                ),
                x=alt.X("mean_review_score:Q", title="Mean review score", scale=alt.Scale(domain=[1, 5])),
                tooltip=[
                    alt.Tooltip("product_category_name_english:N", title="Category"),
                    alt.Tooltip("mean_review_score:Q", title="Mean review score", format=".2f"),
                    alt.Tooltip("late_rate:Q", title="Late rate (%)", format=".1f"),
                ],
            )
            st.altair_chart(cat_score.properties(height=380), use_container_width=True)
        st.caption(
            "Categories with ≥100 delivered orders, top 13 by mean delivery time. Same "
            "row order in both charts. Late rate = share delivered after the estimated "
            "date (`is_on_time` from the consolidated file). One row per (order, category)."
        )

    with st.container(border=True):
        boxed_label("Seller volume size")
        seller_scatter = alt.Chart(seller_cuts).mark_circle(opacity=0.55).encode(
            x=alt.X("orders:Q", title="Delivered orders", scale=alt.Scale(type="log")),
            y=alt.Y("late_rate:Q", title="Late rate (%)"),
            size=alt.Size("orders:Q", title="Orders", legend=None),
            color=alt.Color(
                "volume_band:N",
                title=None,
                scale=alt.Scale(
                    domain=["Top-decile volume", "Other sellers"],
                    range=["#EF7C00", "#003D7C"],
                ),
            ),
            tooltip=[
                alt.Tooltip("seller_id:N", title="Seller"),
                alt.Tooltip("orders:Q", title="Orders", format=","),
                alt.Tooltip("late_rate:Q", title="Late rate (%)", format=".1f"),
                alt.Tooltip("mean_delivery_days:Q", title="Mean delivery days", format=".1f"),
                alt.Tooltip("mean_review_score:Q", title="Mean review score", format=".2f"),
            ],
        )
        st.altair_chart(seller_scatter.properties(height=340), use_container_width=True)
        st.caption(
            f"Sellers with ≥20 delivered orders. Orange = top-decile volume "
            f"(≥{volume_threshold:.0f} orders); x-axis log-scaled. Marker size also "
            "encodes order volume. Late rate from `is_on_time` in the consolidated "
            "file. One row per (order, seller)."
        )
