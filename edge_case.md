# Edge Cases & Corner Cases: Blinkit Review Analyzer

This document outlines potential edge cases, failure modes, and mitigation strategies for the **Blinkit Review Analyzer** project.

---

## 1. Data Ingestion & n8n Integration Edge Cases

### 1.1 Duplicate Review Submissions
* **Scenario**: A user posts the exact same review text on Google Play Store, Apple App Store, and Trustpilot.
* **Impact**: Skews frequency metrics and artificially inflates "Source Diversity" since the same user feedback appears in $\ge 3$ platforms.
* **Mitigation**: Calculate a content hash of the cleaned text. If the same hash appears on multiple platforms within a 48-hour window from the same author name, flag them as likely cross-posts and reduce the diversity weighting.

### 1.2 Empty Review Text / Ratings Only
* **Scenario**: A customer leaves a 1-star rating on the App Store without any descriptive review text.
* **Impact**: The NLP pipeline cannot extract themes or sentiment triggers from empty strings.
* **Mitigation**: Filter out reviews with empty or extremely short (e.g. $< 3$ characters) text before NLP processing, but log the rating count to maintain accurate overall rating metrics.

### 1.3 n8n Webhook Payload Format Drift
* **Scenario**: The upstream scraper fields change, causing n8n to send a payload with missing parameters.
* **Impact**: Key columns like `timestamp` or `rating` are null, throwing database constraint errors.
* **Mitigation**: Implement robust schema validation (e.g., using `pydantic` in the FastAPI backend) with default values (e.g., current timestamp for missing dates, source classification based on URL structure).

### 1.4 Rate Limiting / Scraping Blocks
* **Scenario**: Google Play Store or Trustpilot blocks the scraping IP during a bulk query.
* **Impact**: Ingestion terminates mid-process, resulting in partial data and pipeline failure.
* **Mitigation**: The n8n workflow must support exponential backoff retries and log partial successes. The database transaction should commit incrementally rather than all-or-nothing.

---

## 2. NLP & Sentiment Analysis Edge Cases

### 2.1 Mixed Hinglish & Code-Switching
* **Scenario**: Reviews containing Hinglish/transliterated text (e.g., *"Blinkit delivery delayed hai par product bilkul fresh mila."*).
* **Impact**: Standard English sentiment tools (like VADER) may mistranslate or score it as completely neutral or negative based on words like *"delayed"*, ignoring the positive qualifier (*"fresh mila"*).
* **Mitigation**: Clean and pre-process reviews using Hinglish dictionary mappings, or use multilingual transformers (e.g., `xlm-roberta-base` fine-tuned on Hinglish sentiment).

### 2.2 Sarcasm and Irony
* **Scenario**: *"Blinkit delivered my ice cream so fast that it was hot tea by the time it arrived. Incredible service! 10/10."*
* **Impact**: Rule-based sentiment models score this as positive due to words like *"Incredible"*, *"service"*, and *"10/10"*.
* **Mitigation**: Leverage semantic embeddings or LLMs for topic/sentiment tagging instead of rule-based keyword matchers, as they capture semantic context better.

### 2.3 Emoji-Only Reviews
* **Scenario**: A customer reviews: *"😡👎🛒"*
* **Impact**: Traditional NLP parser strips these as special characters, leaving an empty string.
* **Mitigation**: Configure the text cleaning engine to translate emojis into descriptive text tags (e.g., `😡` $\rightarrow$ `[angry_face]`, `👎` $\rightarrow$ `[thumbs_down]`) before running sentiment analysis.

---

## 3. Database (SQLite) Storage Edge Cases

### 3.1 SQLite Database Locking (`database is locked`)
* **Scenario**: The n8n scraper tries to ingest 1,000 raw reviews at the exact same moment the researcher is saving interview validation results from the Streamlit UI.
* **Impact**: One of the writes fails with a transaction lock error.
* **Mitigation**: 
  * Enable Write-Ahead Logging (WAL) mode for SQLite: `PRAGMA journal_mode=WAL;`
  * Set a busy timeout of 5000ms: `PRAGMA busy_timeout = 5000;`

### 3.2 SQL Injection via Review Content
* **Scenario**: A malicious review contains SQL statements: *"Nice app'); DROP TABLE raw_reviews; --"*
* **Impact**: High risk of data loss or manipulation.
* **Mitigation**: Always use parameterized queries (ORM like SQLAlchemy/SQLModel handles this automatically). Do not use string formatting (`f"INSERT INTO..."`) to construct queries.

---

## 4. Theme Extraction & Triangulation Edge Cases

### 4.1 Low Frequency / High Diversity
* **Scenario**: A theme appears once on Quora, once on Reddit, and once on Trustpilot (frequency = 3, diversity = 3). The formula score is $3 \times 3 = 9$. Another theme has frequency = 9 but appears only on Play Store (diversity = 1), scoring $9 \times 1 = 9$.
* **Impact**: The triangulation weights them identically, but a theme appearing in 3 distinct platforms represents a more systemic issue than a loud pattern isolated to 1 store.
* **Mitigation**: Apply a non-linear scaling multiplier for source diversity, e.g., $\text{Rank Score} = \text{Frequency} \times \text{Source Diversity}^{1.5}$.

### 4.2 Generic Keywords Matching Taxonomy
* **Scenario**: Review contains: *"The app is nice"* $\rightarrow$ matched to `habit/convenience` because of the word *"app"*.
* **Impact**: Taxonomy matches are too broad, leading to noisy theme tagging.
* **Mitigation**: Match keyword patterns using part-of-speech (POS) tags or context rules rather than simple substring matching.

---

## 5. Dashboard Validation Edge Cases

### 5.1 Insufficient Primary Research Interviews
* **Scenario**: The researcher conducts only 2 interviews instead of the planned 5–6.
* **Impact**: The validation logic (`Confirmed` requires $\ge 4$ votes) can never be met.
* **Mitigation**: Adjust the confirmation threshold dynamically: if total interviews conducted is $N$, set the threshold to $\ge \text{ceil}(0.75 \times N)$.

### 5.2 Contradictory Interview Findings
* **Scenario**: Interviewee A says they don't explore categories because they *“don't trust product quality”*, but Interviewee B says they *“highly trust product quality but find the layout confusing”*.
* **Impact**: Contradictory inputs map to the same theme.
* **Mitigation**: Allow partial classifications (e.g., `Partially Confirmed`) and support logging multiple conflicting feedback entries.
