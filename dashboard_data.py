"""Data loading and aggregation helpers for the Olist dashboard."""

from pathlib import Path

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


def build_retention_series(order_data: pd.DataFrame, granularity: str) -> tuple[pd.DataFrame, float]:
    customers = order_data.sort_values(["customer_unique_id", "order_purchase_timestamp", "order_id"]).copy()
    repeat_rate = customers.groupby("customer_unique_id")["order_id"].nunique().gt(1).mean()
    customers["returning_customer"] = customers.groupby("customer_unique_id").cumcount().gt(0)
    customers = trim_trend_window(customers, "order_purchase_timestamp")
    series = add_period(customers, "order_purchase_timestamp", granularity).groupby(["period", "returning_customer"], as_index=False)["customer_unique_id"].nunique().pivot(index="period", columns="returning_customer", values="customer_unique_id").fillna(0).rename(columns={False: "new_customers", True: "returning_customers"}).reset_index()
    series = complete_periods(series, granularity)
    series["returning_customer_share"] = series["returning_customers"] / (series["new_customers"] + series["returning_customers"]).replace(0, pd.NA) * 100
    return series, repeat_rate
