# Project Context: Blinkit Review Analyzer

This document outlines the context, goals, and key components of the **Blinkit Review Analyzer** system.

## Goal
The Blinkit Review Analyzer is designed to collect, process, and analyze customer feedback and product reviews from Blinkit (a leading quick-commerce platform). By leveraging natural language processing (NLP) and sentiment analysis, the system aims to provide actionable insights into product quality, delivery performance, and overall customer satisfaction.

## Key Components

### 1. Ingestion Pipeline
* **Sources**: Scraped product reviews, customer feedback forms, or delivery partner feedback.
* **Fields**: Review Text, Rating, Timestamp, Product Category, Delivery Time, Store Location.

### 2. Sentiment & Theme Analysis
* **Sentiment Classification**: Categorizing reviews into Positive, Neutral, and Negative.
* **Aspect-Based Sentiment**: Extracting sentiment on specific attributes:
  * Delivery Speed / Delay
  * Product Freshness / Expiry
  * Packaging Quality (damaged/spilled items)
  * Price / Value
  * Missing Items

### 3. Analytics & Dashboard
* **Metrics**: Average rating trends, sentiment distribution, key complaint categories, store-wise performance.
* **Insights**: Automated summaries of why ratings for specific categories (e.g., Fresh Fruits & Vegetables) dropped or spiked.
