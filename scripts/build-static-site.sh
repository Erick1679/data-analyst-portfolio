
#!/usr/bin/env bash
set -euo pipefail

# Build The Brights Analytics static website.
# Only explicitly approved public assets are deployed.

cd "$(dirname "$0")/.."

files=(
  "index.html"
  "insights.html"
  "project-global-analytics.html"
  "robots.txt"
  "sitemap.xml"
  "images/erick_omondi_data_insights_in_action.png"
  "images/brights/The_Brights_Analytics_Approved_Favicon.ico"
  "images/brights/The_Brights_Analytics_Approved_Header.webp"
  "reports/Global_Predictive_Business_Analytics_Executive_Report.pptx"
  "reports/Global_Predictive_Business_Analytics_Report.xlsx"
  "screenshots/01_executive_overview.png"
  "screenshots/02_revenue_forecasting.png"
  "screenshots/03_customer_intelligence.png"
  "screenshots/04_customer_lifetime_value.png"
  "screenshots/05_product_analytics.png"
  "screenshots/06_operations_inventory.png"
  "screenshots/07_model_performance.png"
  "screenshots/08_data_quality.png"
)

# Verify all required inputs before building.
for file in "${files[@]}"; do
  if [[ ! -f "$file" || -L "$file" ]]; then
    echo "ERROR: Missing or unsafe asset: $file" >&2
    exit 1
  fi
done

# Build a clean publish directory.
rm -rf -- dist
mkdir -p dist

for file in "${files[@]}"; do
  mkdir -p "dist/$(dirname "$file")"
  cp -- "$file" "dist/$file"
done

# Verify the published file count.
count=$(find dist -type f | wc -l | tr -d ' ')

if [[ "$count" -ne "${#files[@]}" ]]; then
  echo "ERROR: Unexpected published file count." >&2
  exit 1
fi

# Ensure application source directories are excluded.
for forbidden in backend .git .github scripts; do
  if [[ -e "dist/$forbidden" ]]; then
    echo "ERROR: Forbidden deployment path: $forbidden" >&2
    exit 1
  fi
done

echo "SUCCESS: ${#files[@]} approved public files prepared."
echo "Netlify publish directory: dist"
