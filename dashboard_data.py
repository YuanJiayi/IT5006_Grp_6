"""Data loading and aggregation helpers for the Olist dashboard."""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


PERIOD_ALIASES = {"Day": "D", "Month": "M", "Year": "Y"}
DATE_FREQUENCIES = {"Day": "D", "Month": "MS", "Year": "YS"}
TREND_START = pd.Timestamp("2017-01-01")
TREND_END = pd.Timestamp("2018-09-01")


@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        parse_dates=[
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )


@st.cache_data
def load_customer_ids(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, usecols=["customer_id", "customer_unique_id"])


@st.cache_data
def load_reviews(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["review_creation_date"])


def latest_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    return reviews.sort_values(["order_id", "review_creation_date", "review_id"]).drop_duplicates(
        "order_id", keep="last"
    )


def add_period(data: pd.DataFrame, date_column: str, granularity: str) -> pd.DataFrame:
    return data.assign(
        period=data[date_column].dt.to_period(PERIOD_ALIASES[granularity]).dt.to_timestamp()
    )


def trim_trend_window(data: pd.DataFrame, date_column: str) -> pd.DataFrame:
    return data.loc[
        data[date_column].ge(TREND_START) & data[date_column].lt(TREND_END)
    ].copy()


def complete_periods(time_series: pd.DataFrame, granularity: str) -> pd.DataFrame:
    periods = pd.date_range(
        start=time_series["period"].min(), end=time_series["period"].max(), freq=DATE_FREQUENCIES[granularity]
    )
    return time_series.set_index("period").reindex(periods, fill_value=0).rename_axis("period").reset_index()


def build_growth_series(data: pd.DataFrame, granularity: str) -> pd.DataFrame:
    data = trim_trend_window(data, "order_purchase_timestamp")
    series = add_period(data, "order_purchase_timestamp", granularity).groupby("period", as_index=False).agg(
        orders=("order_id", "nunique"), product_revenue=("price", "sum"), items_sold=("order_item_id", "size")
    )
    return complete_periods(series, granularity)


def build_commercial_series(data: pd.DataFrame, granularity: str) -> pd.DataFrame:
    data = trim_trend_window(data, "order_purchase_timestamp")
    series = add_period(data, "order_purchase_timestamp", granularity).groupby("period", as_index=False).agg(
        orders=("order_id", "nunique"), product_revenue=("price", "sum"), items_sold=("order_item_id", "size")
    )
    series["average_order_value"] = series["product_revenue"] / series["orders"]
    series["items_per_order"] = series["items_sold"] / series["orders"]
    return series


def build_review_series(order_data: pd.DataFrame, reviews: pd.DataFrame, granularity: str) -> pd.DataFrame:
    review_data = order_data[["order_id", "order_purchase_timestamp"]].merge(
        latest_reviews(reviews)[["order_id", "review_score"]], on="order_id", how="inner", validate="one_to_one"
    )
    review_data = trim_trend_window(review_data, "order_purchase_timestamp").assign(
        low_rating=lambda data: data["review_score"].le(2), five_star=lambda data: data["review_score"].eq(5)
    )
    series = add_period(review_data, "order_purchase_timestamp", granularity).groupby("period", as_index=False).agg(
        average_review_score=("review_score", "mean"), low_rating_rate=("low_rating", "mean"), five_star_rate=("five_star", "mean")
    )
    series["satisfaction_proxy"] = (series["five_star_rate"] - series["low_rating_rate"]) * 100
    series["low_rating_rate"] *= 100
    return series


def eligible_deliveries(order_data: pd.DataFrame) -> pd.DataFrame:
    return order_data.loc[
        order_data["order_status"].eq("delivered")
        & order_data["order_delivered_customer_date"].notna()
        & order_data["order_estimated_delivery_date"].notna()
    ].copy()


def build_delivery_series(order_data: pd.DataFrame, granularity: str) -> pd.DataFrame:
    delivered = trim_trend_window(eligible_deliveries(order_data), "order_purchase_timestamp")
    delivered["delivery_days_exact"] = (
        delivered["order_delivered_customer_date"] - delivered["order_purchase_timestamp"]
    ).dt.total_seconds() / 86_400
    delivered["late_delivery"] = delivered["order_delivered_customer_date"] > delivered["order_estimated_delivery_date"]
    series = add_period(delivered, "order_purchase_timestamp", granularity).groupby("period", as_index=False).agg(
        median_delivery_days=("delivery_days_exact", "median"), late_delivery_rate=("late_delivery", "mean")
    )
    series["late_delivery_rate"] *= 100
    return series


def reviewed_deliveries(order_data: pd.DataFrame, reviews: pd.DataFrame, trim: bool = False) -> pd.DataFrame:
    data = eligible_deliveries(order_data).merge(
        latest_reviews(reviews)[["order_id", "review_score"]], on="order_id", how="inner", validate="one_to_one"
    )
    if trim:
        data = trim_trend_window(data, "order_purchase_timestamp")
    return data.assign(
        late_delivery=lambda frame: frame["order_delivered_customer_date"] > frame["order_estimated_delivery_date"],
        low_rating=lambda frame: frame["review_score"].le(2),
        days_late=lambda frame: (frame["order_delivered_customer_date"] - frame["order_estimated_delivery_date"]).dt.total_seconds() / 86_400,
    )


def build_delivery_experience_series(order_data: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    data = reviewed_deliveries(order_data, reviews, trim=True)
    series = add_period(data, "order_purchase_timestamp", "Month").groupby("period", as_index=False).agg(
        late_delivery_rate=("late_delivery", "mean"), low_rating_rate=("low_rating", "mean")
    )
    return series.assign(**{"Late-delivery rate (%)": series["late_delivery_rate"] * 100, "Low-rating rate (%)": series["low_rating_rate"] * 100})


def build_delivery_review_analysis(order_data: pd.DataFrame, reviews: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    data = reviewed_deliveries(order_data, reviews)
    comparison = data.groupby("late_delivery", as_index=False)["low_rating"].mean().assign(
        delivery_timing=lambda frame: frame["late_delivery"].map({False: "On time or early", True: "Late"}),
        low_rating_rate=lambda frame: frame["low_rating"] * 100,
    )
    risk_ratio = comparison.loc[comparison["late_delivery"], "low_rating_rate"].iloc[0] / comparison.loc[~comparison["late_delivery"], "low_rating_rate"].iloc[0]
    data["lateness_band"] = pd.cut(data["days_late"], [-float("inf"), 0, 3, 7, float("inf")], labels=["On time or early", "1–3 days late", "4–7 days late", "8+ days late"])
    severity = data.groupby("lateness_band", observed=True, as_index=False)["low_rating"].mean().assign(low_rating_rate=lambda frame: frame["low_rating"] * 100)
    return comparison, severity, risk_ratio


# ---------------------------------------------------------------------------
# Delivery correlations tab
# ---------------------------------------------------------------------------

LEAD_STAGES = ["processing_time", "handling_time", "shipping_time"]
LEAD_STAGE_LABELS = {
    "processing_time": "Processing (purchase → approval)",
    "handling_time": "Handling (approval → carrier)",
    "shipping_time": "Shipping (carrier → customer)",
}


@st.cache_data
def load_order_stage_timestamps(path: Path) -> pd.DataFrame:
    """Approval / carrier timestamps live only in the raw orders file, not the
    consolidated line-item CSV, so they are pulled straight from here."""
    return pd.read_csv(
        path,
        usecols=[
            "order_id",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
        ],
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
        ],
    )


def _order_review_scores(reviews_path: Path) -> pd.DataFrame:
    return latest_reviews(load_reviews(reviews_path))[["order_id", "review_score"]]


@st.cache_data
def build_leadtime_decomposition(
    orders_path: Path, reviews_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    stages = load_order_stage_timestamps(orders_path).dropna(
        subset=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
        ]
    )
    stages["processing_time"] = (
        stages["order_approved_at"] - stages["order_purchase_timestamp"]
    ).dt.total_seconds() / 86_400
    stages["handling_time"] = (
        stages["order_delivered_carrier_date"] - stages["order_approved_at"]
    ).dt.total_seconds() / 86_400
    stages["shipping_time"] = (
        stages["order_delivered_customer_date"] - stages["order_delivered_carrier_date"]
    ).dt.total_seconds() / 86_400

    valid = (stages[LEAD_STAGES] >= 0).all(axis=1)
    excluded_share = float((~valid).mean() * 100)
    clean = stages.loc[valid].copy()
    clean["total_time"] = clean[LEAD_STAGES].sum(axis=1)
    total_mean = float(clean["total_time"].mean())

    summary = pd.DataFrame(
        {
            "stage": [LEAD_STAGE_LABELS[key] for key in LEAD_STAGES],
            "stage_key": LEAD_STAGES,
            "mean_days": [clean[key].mean() for key in LEAD_STAGES],
            "median_days": [clean[key].median() for key in LEAD_STAGES],
        }
    )
    summary["share_pct"] = summary["mean_days"] / total_mean * 100

    scored = clean.merge(_order_review_scores(reviews_path), on="order_id", how="inner")
    scored["shipping_bucket"] = pd.cut(
        scored["shipping_time"],
        bins=[0, 3, 7, 14, 21, 30, float("inf")],
        labels=["0–3", "3–7", "7–14", "14–21", "21–30", "30+"],
        include_lowest=True,
    )
    shipping_review = (
        scored.groupby("shipping_bucket", observed=True, as_index=False)
        .agg(mean_review_score=("review_score", "mean"), orders=("order_id", "size"))
    )
    return summary, shipping_review, excluded_share, total_mean


@st.cache_data
def load_zip_centroids(path: Path) -> pd.DataFrame:
    geo = pd.read_csv(
        path,
        usecols=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
    )
    return geo.groupby("geolocation_zip_code_prefix", as_index=False).agg(
        lat=("geolocation_lat", "mean"), lng=("geolocation_lng", "mean")
    )


def _haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371.0
    lat1, lng1, lat2, lng2 = map(np.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    inner = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(inner))


@st.cache_data
def build_distance_table(
    consolidated_path: Path,
    customers_path: Path,
    sellers_path: Path,
    geo_path: Path,
    reviews_path: Path,
) -> tuple[pd.DataFrame, float]:
    orders = eligible_deliveries(load_data(consolidated_path).drop_duplicates("order_id"))[
        [
            "order_id",
            "customer_id",
            "seller_id",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
            "delivery_days",
        ]
    ]
    customers = pd.read_csv(
        customers_path, usecols=["customer_id", "customer_zip_code_prefix"]
    )
    sellers = pd.read_csv(sellers_path, usecols=["seller_id", "seller_zip_code_prefix"])
    centroids = load_zip_centroids(geo_path)

    merged = orders.merge(customers, on="customer_id", how="left").merge(
        sellers, on="seller_id", how="left"
    )
    total = len(merged)
    merged = merged.merge(
        centroids.rename(
            columns={
                "geolocation_zip_code_prefix": "customer_zip_code_prefix",
                "lat": "cust_lat",
                "lng": "cust_lng",
            }
        ),
        on="customer_zip_code_prefix",
        how="left",
    ).merge(
        centroids.rename(
            columns={
                "geolocation_zip_code_prefix": "seller_zip_code_prefix",
                "lat": "sell_lat",
                "lng": "sell_lng",
            }
        ),
        on="seller_zip_code_prefix",
        how="left",
    )
    located = merged.dropna(subset=["cust_lat", "sell_lat"]).copy()
    dropped_share = float((1 - len(located) / total) * 100) if total else 0.0
    located["distance_km"] = _haversine_km(
        located["cust_lat"], located["cust_lng"], located["sell_lat"], located["sell_lng"]
    )
    located["is_late"] = (
        located["order_delivered_customer_date"]
        > located["order_estimated_delivery_date"]
    )
    located = located.merge(_order_review_scores(reviews_path), on="order_id", how="left")
    return (
        located[["order_id", "distance_km", "delivery_days", "is_late", "review_score"]],
        dropped_share,
    )


def build_distance_buckets(distance_table: pd.DataFrame) -> pd.DataFrame:
    data = distance_table.dropna(subset=["distance_km", "delivery_days"]).copy()
    data["distance_bucket"] = pd.qcut(data["distance_km"], 6, duplicates="drop")
    grouped = (
        data.groupby("distance_bucket", observed=True)
        .agg(
            mean_delivery_days=("delivery_days", "mean"),
            mean_review_score=("review_score", "mean"),
            late_rate=("is_late", "mean"),
            orders=("order_id", "size"),
        )
        .reset_index()
    )
    grouped["late_rate"] *= 100
    grouped["distance_label"] = grouped["distance_bucket"].apply(
        lambda interval: f"{max(interval.left, 0):,.0f}–{interval.right:,.0f}"
    )
    return grouped


def _delivery_review_cut(
    consolidated_path: Path, reviews_path: Path, group_columns: list[str]
) -> pd.DataFrame:
    items = eligible_deliveries(load_data(consolidated_path))
    keep = list(dict.fromkeys([*group_columns, "order_id", "delivery_days", "is_on_time"]))
    pairs = items[keep].dropna(subset=group_columns).drop_duplicates(
        [*group_columns, "order_id"]
    )
    pairs = pairs.merge(_order_review_scores(reviews_path), on="order_id", how="left")
    pairs["is_late"] = ~pairs["is_on_time"].astype(bool)
    grouped = (
        pairs.groupby(group_columns)
        .agg(
            orders=("order_id", "nunique"),
            mean_delivery_days=("delivery_days", "mean"),
            mean_review_score=("review_score", "mean"),
            late_rate=("is_late", "mean"),
        )
        .reset_index()
    )
    grouped["late_rate"] *= 100
    return grouped


@st.cache_data
def build_category_cuts(
    consolidated_path: Path, reviews_path: Path, min_orders: int = 100
) -> pd.DataFrame:
    grouped = _delivery_review_cut(
        consolidated_path, reviews_path, ["product_category_name_english"]
    )
    return (
        grouped.loc[grouped["orders"] >= min_orders]
        .sort_values("mean_delivery_days", ascending=False)
        .reset_index(drop=True)
    )


@st.cache_data
def build_seller_cuts(
    consolidated_path: Path, reviews_path: Path, min_orders: int = 20
) -> pd.DataFrame:
    grouped = _delivery_review_cut(consolidated_path, reviews_path, ["seller_id"])
    return (
        grouped.loc[grouped["orders"] >= min_orders]
        .sort_values("orders", ascending=False)
        .reset_index(drop=True)
    )


def build_retention_series(order_data: pd.DataFrame, granularity: str) -> tuple[pd.DataFrame, float]:
    customers = order_data.sort_values(["customer_unique_id", "order_purchase_timestamp", "order_id"]).copy()
    repeat_rate = customers.groupby("customer_unique_id")["order_id"].nunique().gt(1).mean()
    customers["returning_customer"] = customers.groupby("customer_unique_id").cumcount().gt(0)
    customers = trim_trend_window(customers, "order_purchase_timestamp")
    series = add_period(customers, "order_purchase_timestamp", granularity).groupby(["period", "returning_customer"], as_index=False)["customer_unique_id"].nunique().pivot(index="period", columns="returning_customer", values="customer_unique_id").fillna(0).rename(columns={False: "new_customers", True: "returning_customers"}).reset_index()
    series = complete_periods(series, granularity)
    series["returning_customer_share"] = series["returning_customers"] / (series["new_customers"] + series["returning_customers"]).replace(0, pd.NA) * 100
    return series, repeat_rate
