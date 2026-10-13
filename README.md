# Erick Omondi — Data Analytics and Security Portfolio

A responsive static website showcasing **six technical projects** in data analytics, business intelligence, and security intelligence, plus **two deployed Streamlit dashboards**. The portfolio website itself is a separate GitHub Pages project.

## Live website

https://erick1679.github.io/data-analyst-portfolio/

## Featured projects

1. [Business Performance Analyzer](https://github.com/Erick1679/business-performance-analyzer) — business revenue and margin analysis.
2. [Data Cleaning Analyzer](https://github.com/Erick1679/data-cleaning-analyzer) — validation, quality classification, EDA, and CSV reports.
3. [Customer Analytics and Segmentation](https://github.com/Erick1679/customer-analytics-segmentation) — RFM segmentation and retention.
4. [Business Intelligence Dashboard](https://github.com/Erick1679/business-intelligence-dashboard) — interactive business reporting. [Launch live dashboard](https://business-intelligence-dashboard-ezx2j4jrjmckjbdvd6uzkz.streamlit.app/).
5. [Security Log Analyzer](https://github.com/Erick1679/security-log-analyzer) — explainable SSH log detections and audit reporting.
6. [End-to-End Analytics and Security](https://github.com/Erick1679/end-to-end-analytics-security) — cross-source event analytics, risk scoring, and interactive investigation. [Launch live security dashboard](https://end-to-end-analytics-security-viz5xshvrmhgfjhhzu6zim.streamlit.app/).

Security detections are **signals for investigation, not proof of compromise**. The sample project datasets are synthetic, and the deployed security dashboard displays demonstration data rather than monitoring live systems.

## Skills featured

- **Analytics:** Python, pandas, NumPy, Microsoft Excel, data cleaning, exploratory analysis, customer segmentation.
- **Business intelligence:** Streamlit, Plotly, Matplotlib, Microsoft Power BI, Tableau.
- **Statistics:** Stata, JASP, IBM SPSS Statistics.
- **Security analytics:** authentication log parsing, anomaly indicators, risk scoring, reporting.
- **Testing and delivery:** pytest, Git, GitHub, HTML, CSS, reproducible documentation.

## Run locally

```bash
python3 -m http.server 8000
```

Open http://localhost:8000 and use **Control + C** to stop the local server. This site uses plain HTML and CSS with a minimal JavaScript year update; it has no package dependencies or build step.

## Publish updates on GitHub Pages

From an existing local clone of `Erick1679/data-analyst-portfolio`:

```bash
git add index.html README.md
git commit -m "Add security analytics projects and live dashboard"
git push origin main
```

GitHub Pages is already configured on the repository to deploy the root of the `main` branch. Updated commits are published through the existing Pages configuration.

## Author

Erick Omondi
