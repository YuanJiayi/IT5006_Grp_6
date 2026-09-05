# IT5006 Milestone 1 — Working Report Notes

> This is a living working memory for the eventual report, not the final report. It records only work the team has completed or requirements taken directly from the course brief. Proposed work is labelled **Next**, and must not be presented as a result.

## Current project status — 5 September 2026

**Completed:** We have worked through `IT5006-Olist_Getting_Started.ipynb`. The notebook loads the nine supplied Olist CSV tables, explores their schema, constructs and saves `smartcommerce_consolidated.csv`, calculates starter KPI summaries, and displays basic exploratory charts.

**Dashboard work completed:** The Streamlit Overview tab displays purchase-date coverage, total orders, product sales excluding freight, and items sold, followed by selectable day/month/year trends for growth, commercial efficiency, customer experience, and retention. It uses the consolidated dataset plus the customers table for `customer_unique_id` and the reviews table for rating measures. The Delivery tab displays median delivery time and late-delivery rate with a selectable temporal chart.

**Current problem scope:** We have selected delivery performance as one problem with dual framing: delivery-lead-time regression and late-delivery classification. This satisfies the course requirement for regression and classification while retaining one operational stakeholder and one coherent data model.

**Not yet completed:** a saved model-ready preprocessing workflow beyond the starter notebook; EDA beyond the verified results below; model preparation, training, or evaluation; dashboard deployment; and literature review writing. None of these should currently be described as completed work in the final report.

## Course-brief reference

The [IT5006 project brief](https://prakashsukhwal.github.io/IT5006/IT5006_Project_Description_2026Aug_V2.html) specifies that Milestone 1 comprises a 4–5-page report (literature review and EDA), an interactive dashboard, and the code/notebooks repository. The final report must include the dashboard and repository links.

For later phases, the project must cover classification and regression, either as two problems or a dual-framed problem. The brief also warns to use `customer_unique_id`, rather than `customer_id`, for customer-level analysis; to avoid post-outcome fields as predictors; and to evaluate imbalanced classification targets with metrics beyond accuracy.

## Completed starter-notebook record

### Data assets loaded

The notebook loads the following supplied tables:

| Table | Rows shown by notebook | Purpose in starter workflow |
| --- | ---: | --- |
| Orders | 99,441 | Order status and timestamps |
| Order items | 112,650 | Item, seller, price, and freight data |
| Customers | 99,441 | Customer location and `customer_unique_id` |
| Products | 32,951 | Product attributes and category |
| Sellers | 3,095 | Seller location |
| Payments | 103,886 | Payment data |
| Reviews | 99,224 | Review score and comment data |
| Geolocation | 1,000,163 | Zip-code reference data |
| Category translation | 71 | Portuguese-to-English category translation |

### Consolidated dataset created by the starter notebook

The notebook starts with `order_items`, then left-joins:

1. products plus the English category translation on `product_id`;
2. selected order fields on `order_id`;
3. customer city and state on `customer_id`; and
4. seller state on `seller_id`.

It creates a **line-item-level** dataset with **112,650 rows and 25 columns**, saved as `smartcommerce_consolidated.csv`. It also creates these starter derived fields:

- purchase-date fields: `order_date`, `year_month`, `year`, `month`, `day_of_week`;
- `delivery_days` and `is_on_time`; and
- `item_revenue = price + freight_value`.

The consolidated file does **not** include payment or review columns. It is line-item grain, so raw row counts are not automatically order counts; the notebook uses distinct `order_id` when calculating its starter order KPI.

### Starter outputs retained for later verification

The following values are notebook outputs, not yet written up as interpreted EDA findings:

| Starter calculation | Notebook output |
| --- | ---: |
| Distinct orders | 98,666 |
| Product sales, excluding freight | R$13,591,643.70 |
| Sales including freight | R$15,843,553.24 |
| Mean order value, excluding freight | R$137.75 |
| Median order value, excluding freight | R$86.90 |
| Unique customers (`customer_unique_id`) | 96,096 |
| Repeat customers | 2,997 |
| Repeat rate | 3.12% |
| Delivered orders | 96,478 |
| Average delivery days | 12.0 |
| Median delivery days | 10.0 |
| On-time delivery rate | 92.1% |
| Average review score | 4.09 / 5 |

The notebook also displays starter charts for monthly orders, top-10 category sales, order-value distribution, top-10 customer states by orders, delivery-days distribution, review-score distribution, and payment value by payment type. Verified findings subsequently developed from the dashboard are drafted below.

2. Exploratory Data Analysis

2.1 Dataset overview

The Olist dataset contains Brazilian e-commerce transaction, product, customer, seller, delivery, and review information. The analytical dataset comprises 112,650 line-item records and 25 variables, representing 98,666 orders. Each record represents an item within an order. The marketplace connects 3,095 sellers across 72 product categories. São Paulo accounts for 41.9% of orders.

Data-quality checks found no duplicate records or material invalid fields. The main issue is incomplete delivery information: actual delivery dates are missing in 2,454 line-item records, mainly for orders that were not completed. These records are excluded, rather than imputed, when analysing delivery outcomes.

2.2 Temporal analysis

Purchase records span 4 September 2016 to 3 September 2018. Temporal charts use January 2017 to August 2018, excluding the launch period and partial boundary months.

Order volume and product sales rose steadily through 2017. In 2018, both more than doubled compared with the same January–August period the year before, then levelled off at this higher volume. November 2017 was a sharp one-month spike that aligns with Black Friday; no other clear seasonal pattern was observed.

This growth came from more orders rather than bigger ones. Average order value and items per order stayed broadly flat across the two comparable periods.

Growing order volume does not necessarily mean the business improved on every dimension. Customer experience held up well overall but dipped twice: in November 2017 and again in February–March 2018. Both dips coincided with longer delivery times and higher late-delivery rates.

Repeat purchasing told a different story. The monthly returning-customer share remained low and broadly stable despite substantial order growth; overall, only 3.1% of customers made a repeat purchase during the observed period. Delivery reliability and customer retention therefore stand out as two separate areas for further investigation.

2.3 Problems chosen

The selected analytics problem is delivery performance for the operations/fulfilment team, framed in two complementary ways.

Regression asks how long an order is expected to take from purchase to customer delivery. Its target is the number of days between the actual delivery timestamp and purchase timestamp. The eligible population contains 96,470 delivered orders with complete purchase, actual-delivery, and estimated-delivery dates. Performance will be assessed using MAE against a training-set median baseline, with RMSE as a secondary measure.

Classification asks whether an order will be delivered after its estimated delivery date. The same 96,470 orders are eligible; 7,826 are late (8.11%). Given this class imbalance, performance will be assessed using PR-AUC, precision, recall, F1, and balanced accuracy against a majority-class baseline.

This scope is operationally relevant because late delivery is strongly associated with poorer customer experience. Among 95,824 delivered orders with an order-level review, 54.1% of late orders received a low rating (1–2 stars), compared with 9.2% of on-time/early orders. The association becomes stronger as lateness increases. This does not imply that delivery is the only determinant of review score; it identifies delivery reliability as an actionable, high-priority factor for further segmentation by seller, geography, category, and order characteristics.

Prediction time is defined as order placement. Candidate features include purchase-calendar fields, customer and seller state, product category/weight, item count, price, and freight aggregates. Actual delivery dates, delivery_days, is_on_time, review scores, and review timestamps are outcome or post-outcome information and will not be used as predictors. Before modelling, the line-item dataset will be aggregated to one row per order so that targets and features share the same grain.

## Next — record only after the team does the work

- Build and save a one-row-per-order preprocessing workflow for the selected delivery problem.
- Continue EDA of seller, category, geography, and price/freight patterns associated with delivery performance.
- Deploy the dashboard and add its live link.
- Add literature-review sources and synthesis.

## Verified delivery–review finding

For completed orders with a delivery outcome and review, delivery and review records were reduced to one row per order. Where an order had multiple reviews, the latest review by `review_creation_date` was retained. A low rating is a score of 1–2.

Among **95,824** reviewed delivered orders, the low-rating rate was **54.1%** for late orders and **9.2%** for on-time/early orders: a **5.86×** late-to-on-time risk ratio. The relationship strengthens by lateness severity: 19.1% low rated at 1–3 days late, 61.3% at 4–7 days late, and 78.4% at 8+ days late. A chi-square test of late/on-time status and low/not-low rating gave χ² = 12,681.8, *p* < .001, with Cramér’s V = 0.364.

This is report-ready evidence of a substantial association between delivery lateness and low review scores. It does not establish delivery timing as the sole cause, so follow-up analysis should examine category, route, seller, and price/freight patterns before proposing interventions.

## Change log

| Date | Record |
| --- | --- |
| 2026-09-05 | Created this working record from the completed starter notebook and the course project brief. |
| 2026-09-05 | Added an initial Overview dashboard tab and a selectable growth chart using the consolidated starter dataset. |
| 2026-09-05 | Added commercial, customer-experience, retention, and delivery dashboard measures. Review metrics are labelled as review-record measures; NPS proxy is defined as the 5-star rate minus the low-rating rate. |
| 2026-09-05 | Verified the delivery–review association at one row per order and added it to the Delivery dashboard tab. |
