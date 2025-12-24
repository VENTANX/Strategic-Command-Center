# Project: Strategic Command and Analysis Center (v5.0 - Final)
> **By OUSSAMA ASLOUJ** (Artificial Intelligence Track - AI 104)

![Main Dashboard](Screenshot%202025-12-24%20235534.png)

## About the Project

This project is an advanced simulation of a **Strategic Command Center** designed for real-time global threat surveillance and analysis. It demonstrates the power of Artificial Intelligence applied to crisis management, integrating real-time data feeds and predictive models.

**Developed under the supervision of Mr. EL MOUDEN ABDELAZIZ.**

---

## 🚀 Key Features

### 1. 🌍 Seismic & Nuclear Surveillance
Real-time detection and classification of global seismic events.
*   **Anomaly Detection AI**: `IsolationForest` model to identify suspicious seismic signatures (e.g., underground nuclear tests).
*   **Tsunami Prediction**: `RandomForest` model evaluating tsunami risk based on magnitude and depth.
*   **Yield Estimation**: Estimated yield calculation (kilotons) for artificial events.
*   **Interactive Mapping**: Visualization of risk zones (known test sites) and impact radii.

### 2. ☀️ Solar Activity Analysis
Space weather monitoring to protect critical infrastructure.
*   **Flare Tracking**: Detection of M-class and X-class solar flares.
*   **CME Alerts**: Coronal Mass Ejection (CME) analysis and Earth-impact estimation (Geo-effectiveness).
*   **Unified Dashboard**: Probability gauges and threat summaries at a glance.

![Interactive Map](Screenshot%202025-12-25%20000113.png)

### 3. ☄️ Orbital Threats (NEO)
Tracking of potentially hazardous Near-Earth Objects.
*   **Risk Calculation**: Automatic danger assessment based on approach distance and asteroid diameter.
*   **NASA/JPL Data**: Live synchronization with the Scout/Sentry database.

### 4. 🚨 Disaster Alerts (GDACS)
Global overview of humanitarian and natural crises.
*   **Live RSS Feed**: Aggregation of cyclone, flood, and earthquake alerts from the GDACS system (UN/EU).

---

## 🛠️ Installation and Startup

### Prerequisites
*   Python 3.8+
*   Internet Connection (for live API data feeds)

### Installation
1.  **Clone the project** or extract the archive.
2.  **Install dependencies**:
    ```bash
    pip install -r Requirements.txt
    ```

### Quick Start
To launch the main application directly (pre-trained models are included):

```bash
python "ultimate final app.py"
```

> **Note**: If you wish to retrain the models yourself, you can run `1_train_model.py` followed by `2_train_tsunami_model.py` before launching the application.

---

## 🏗️ Technical Architecture
*   **GUI**: `CustomTkinter` for a modern dark UI, suitable for control environments.
*   **Mapping**: `TkinterMapView` (Google Satellite Tiles).
*   **Machine Learning**: `Scikit-Learn` (Isolation Forest, Random Forest).
*   **Data Processing**: `Pandas`, `NumPy`.
*   **Visualization**: `Matplotlib` integrated into Tkinter.

---
*This project was realized as part of the Artificial Intelligence training program.*
