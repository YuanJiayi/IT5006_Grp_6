#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [[ ! -x it5006-proj/bin/streamlit ]]; then
  python3 -m venv it5006-proj
  it5006-proj/bin/pip install -r requirements.txt
fi

exec it5006-proj/bin/streamlit run app.py
