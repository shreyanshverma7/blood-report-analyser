# Security Policy

## Reporting a vulnerability

If you find a security vulnerability, please **do not open a public issue**.
Email shreyanshv97@gmail.com with a description of the issue and
steps to reproduce. You'll get a response within a few days.

## Sensitive health data

This app processes blood reports, which are sensitive personal health data.

- **Never include real blood report PDFs or patient data** in issues,
  discussions, pull requests, or test fixtures — use synthetic data only
- If you discover a way the app could leak one user's report data to another
  user, treat it as a security vulnerability and report it privately as above

## Scope

The live deployment at
[blood-report-analyser-agent.streamlit.app](https://blood-report-analyser-agent.streamlit.app/)
and the code in this repository are both in scope.
