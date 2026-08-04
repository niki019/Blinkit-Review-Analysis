# 🛍️ Blinkit Review Analyzer & AI Agent

An automated, AI-driven pipeline for analyzing customer reviews, extracting high-level themes, and streamlining the product research validation process. This repository acts as both a **Serverless AI Backend** and an **Interactive Data Dashboard**.

## 🚀 Live Deployments (For Mentors & Reviewers)

### 1. Interactive Web Dashboard (Streamlit)
> **🔗 [View the Live Dashboard Here](https://blinkit-review-analysis-a295hhi3qmcxcqvvhg3g.streamlit.app/)**

The dashboard allows researchers to:
* **View Raw Data**: Browse a paginated database of user reviews from App Store, Play Store, and social media.
* **Analyze AI Themes**: Visualize NLP-extracted problem themes, ranked dynamically by Frequency × Source Diversity.
* **Validation Workspace**: Select themes, draft formal problem statements, attach interview quotes, and save them.
* **Google Workspace Export**: Push finalized insights directly into Google Docs via a single button click.

*(Note: The Streamlit dashboard connects to a pre-seeded SQLite database so mentors can view the visualizations immediately without running the ingestion pipelines).*

---

### 2. Headless Backend API (Vercel Serverless)
> **🔗 [View API Health Check](https://blinkit-pulse.vercel.app/)**

The backend is built with **FastAPI** and is designed to act as an MCP (Model Context Protocol) Server. It exposes endpoints that can be plugged directly into LLMs (like Claude Desktop) or Automation Tools (like n8n) so that the AI can act as your interface. 

---

## 🏗️ Technical Architecture
* **Frontend**: Streamlit, Plotly, Pandas
* **Backend API**: FastAPI, Uvicorn, SQLAlchemy
* **LLM Engine**: Groq API (`llama-3.1-8b-instant`)
* **Integrations**: Google Workspace APIs (Docs & Gmail), n8n Webhooks

## 📚 Project Documentation
For a deep dive into the architecture, edge cases, and implementation phases, refer to the documentation files in this repository:
* [`architecture.md`](./architecture.md) - System design and data flows.
* [`context.md`](./context.md) - Product goals and ingestion parameters.
* [`edge_case.md`](./edge_case.md) - Failure modes and mitigation strategies.
* [`implementation_plan.md`](./implementation_plan.md) - Development phases.
