# 🚗 Car Market Analysis & Data Pipeline

This project focuses on collecting, processing, and analyzing automotive market data in Azerbaijan using a full end-to-end data pipeline.

---

## 📊 Project Overview

The project combines web scraping, survey-based data collection, data transformation, and analytical modeling to understand car market trends and customer behavior.

---

## 📋 Survey Data Collection (Primary Data)

In addition to web scraping, real-world data was collected directly from users through a structured survey.

🔗 Survey link:  
https://docs.google.com/forms/d/1EUVOUHeK0k25SbuQb0_VyW6gpRNjtwx2vyHPeu-xeZk

### 🎯 Purpose
- Understand customer preferences in the car market  
- Analyze budget expectations  
- Measure electric vehicle (EV) adoption readiness  
- Identify key decision-making factors  

### 📊 Usage
- Cleaned and processed using Python  
- Used to build scoring models and customer segmentation  
- Integrated into Power BI dashboard  

---

## ⚙️ Data Collection (Web Scraping)

Multiple real-world sources were used:

- Turbo.az → large-scale listing scraping  
- Mashin.al → detailed listing extraction  
- Changan.az → official model and pricing data  
- Mercedes-Benz Azerbaijan → model and color data  
- BYD → structured product data  
- Autonet API → vehicle data collection  

---

## 🧹 Data Processing

- Data cleaning and normalization  
- Handling missing and inconsistent values  
- Structuring data into analysis-ready format  
- Feature engineering for analytics  

---

## 🗄️ Data Storage (SQL)

Structured data was stored in SQL Server:

- Cars  
- CarsMarket  
- City  

This enables efficient querying and analysis.

---

## 📈 Advanced Analytics

### 🔋 EV Readiness Score (0–100)

A custom scoring model was built based on:

- Purchase intention  
- Budget level  
- Market barriers (charging, cost, service)  
- Decision criteria (fuel efficiency, safety, etc.)

### 👥 Customer Segmentation

Users were divided into:

- Car owners  
- Potential buyers  
- High EV adoption segment  

---

## 📊 Visualization (Power BI)

An interactive dashboard was built to present insights:

- Price distribution  
- Brand trends  
- Regional analysis  
- Customer behavior patterns  

---

## 📁 Project Structure

```
car-market-analysis-dashboard/
│
├── scripts/        # Python scraping & data processing scripts
├── sql/            # SQL queries and database scripts
├── README.md       # Project documentation
```


---

## 🛠️ Technologies Used

- Python (requests, BeautifulSoup, Selenium, pandas)  
- SQL Server  
- Power BI  
- Excel  

---

## 🚀 Key Outcome

This project transforms raw data into a structured analytical system that enables data-driven insights into the automotive market.

---

📬 Feedback is welcome!

