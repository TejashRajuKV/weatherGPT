# WeatherGPT: Conversational AI for Weather Forecasting, Alerts, and Climate Information

**Project Document**\
Version 1.0 | October 2026\
Technology Stack: HTML, CSS, JavaScript, Node.js, React.js, Python, MongoDB, Cloud

---

## 1. Executive Summary

WeatherGPT is an AI-powered conversational platform that gives people weather intelligence in plain, natural language. Instead of searching through multiple portals, bulletins, satellite products, and forecast systems, a user simply asks a question such as *"Will it rain in Nashik this weekend? Should I delay sowing?"* and receives an accurate, contextual, and actionable answer, by text or by voice, in their own language.

The platform integrates real-time meteorological data, numerical weather prediction (NWP) outputs such as GFS and WRF, historical climate records, and disaster warning feeds. A Large Language Model (LLM) based query-understanding engine converts user questions into structured data requests, and a response generator turns the results into clear advisories for farmers, pilots, disaster managers, city planners, and researchers.

---

## 2. Background and Problem Statement

Weather information today is scattered across many sources: national meteorological portals, satellite imagery products, radar feeds, NWP model outputs, bulletins in PDF form, and warning systems run by different agencies. This creates several problems:

- **Fragmentation:** Users must visit several websites and interpret technical products (charts, GRIB files, bulletins) themselves.
- **Technical language:** Forecasts are written for specialists. Common users, especially farmers and fishermen, struggle to turn them into decisions.
- **Language barrier:** Most products are in English, while a large share of the Indian population is more comfortable in regional languages.
- **Delayed dissemination:** Extreme weather warnings (cyclones, floods, heatwaves, lightning) may not reach people in remote areas in time.
- **Accessibility gap:** Low literacy and limited smartphone proficiency in rural areas make text-heavy portals hard to use.
- **Lack of decision support:** Raw forecast numbers do not tell a farmer whether to irrigate, a pilot whether a route is safe, or a city official whether to open drainage control rooms.

There is a clear need for an intelligent conversational platform that provides real-time weather information, forecasts, warnings, climate analysis, and decision support in natural language.

---

## 3. Objectives

### 3.1 Primary Objective

Develop **WeatherGPT**, an AI-powered chatbot platform that integrates meteorological datasets, forecasting models, and disaster warning systems to deliver accurate, contextual, and multilingual weather intelligence through conversational interfaces.

### 3.2 Specific Objectives

1. Provide real-time weather information for any location through natural language queries.
2. Integrate NWP model outputs (GFS, WRF) and weather APIs to generate location-specific forecasts.
3. Disseminate extreme weather alerts and early warnings quickly through push, SMS, and in-chat notifications.
4. Generate domain-specific advisories for agriculture, aviation, marine, and urban use cases.
5. Support multiple Indian languages in both text and voice.
6. Offer climate trend and historical analysis for researchers and planners.
7. Deliver a scalable, low-latency architecture capable of real-time data ingestion.

---

## 4. Scope

### 4.1 In Scope

- Web application (responsive and mobile-first) and Progressive Web App (PWA) for mobile use
- Conversational chat interface with text and voice input and output
- Backend services for data ingestion, query understanding, forecast retrieval, and alerting
- Integration with weather APIs, NWP model outputs, and public warning feeds
- Multilingual support for major Indian languages (Hindi, Marathi, Kannada, Tamil, Telugu, Bengali, Gujarati, Malayalam, Punjabi, Odia, plus English)
- Climate and historical analysis module with charts
- Admin dashboard for alert management and monitoring

### 4.2 Out of Scope (Version 1.0)

- Running a full in-house WRF model at national scale (WRF outputs will be consumed or run for a limited pilot region)
- Native iOS and Android apps (PWA is provided; native apps are a future enhancement)
- Hardware sensor deployment

---

## 5. Key Features

| # | Feature | Description |
| --- | --- | --- |
| 1 | Real-time weather retrieval | Current temperature, humidity, wind, rainfall, pressure, visibility, and UV index for any location |
| 2 | Natural language querying | Users ask free-form questions; the LLM identifies intent, location, time range, and parameters |
| 3 | NWP model integration | Ingests GFS and WRF outputs to produce short, medium, and extended range forecasts |
| 4 | Extreme weather alerts | Early warnings for cyclones, floods, heatwaves, cold waves, heavy rain, thunderstorms, and lightning |
| 5 | Location-based advisories | Uses GPS or typed location to generate hyperlocal forecasts and actionable advice |
| 6 | Multilingual support | Understands and responds in Indian languages, with automatic language detection |
| 7 | Climate and historical analysis | Trends, anomalies, rainfall totals, and comparisons against long-term normals |
| 8 | Voice-enabled interaction | Speech-to-text and text-to-speech for rural and low-literacy users |

---

## 6. Users and Use Cases

| User Group | Example Query | Value Delivered |
| --- | --- | --- |
| Farmers | "Should I spray pesticide on my cotton crop tomorrow?" | Crop-weather advisory based on wind, rain probability, and temperature |
| Aviation | "Give me a weather briefing for Bengaluru to Delhi." | Route weather, METAR/TAF-style summary, turbulence and visibility hazards |
| Disaster managers | "Which coastal districts are under cyclone warning?" | Warning status, expected landfall, and affected areas |
| Smart city operators | "Show waterlogging risk zones for tonight." | Rainfall intensity maps and risk alerts for wards |
| Fishermen and marine users | "Is it safe to go out to sea tomorrow?" | Wave height, wind speed, and sea state advisory |
| Researchers | "Compare monsoon rainfall in Pune for the last 20 years." | Historical datasets, trend charts, and anomaly analysis |
| General public | "Will it rain during my commute?" | Short, simple, location-aware answer |

---

## 7. Functional Requirements

### 7.1 Conversational Interface

- FR-1: The system shall accept text queries in English and supported Indian languages.
- FR-2: The system shall accept voice queries and convert them to text.
- FR-3: The system shall maintain conversation context so that follow-up questions work (for example, "And tomorrow?").
- FR-4: The system shall respond in the language of the user's query and optionally read answers aloud.

### 7.2 Query Understanding

- FR-5: The system shall extract intent, location, time period, and weather parameter from each query.
- FR-6: The system shall resolve place names to coordinates using geocoding, including villages and districts.
- FR-7: The system shall ask a clarifying question when a query is ambiguous.

### 7.3 Weather Data and Forecasting

- FR-8: The system shall retrieve current conditions and forecasts from weather APIs and NWP outputs.
- FR-9: The system shall display hourly, daily, and weekly forecasts with confidence indicators where available.
- FR-10: The system shall provide historical data and climate normals for analysis.

### 7.4 Alerts and Early Warning

- FR-11: The system shall ingest official warnings and detect threshold breaches from forecast data.
- FR-12: Users shall be able to subscribe to alerts for specific locations and hazard types.
- FR-13: The system shall dispatch alerts through web push, SMS, and in-chat messages within defined latency targets.

### 7.5 Advisory Generation

- FR-14: The system shall generate domain-specific advisories (agriculture, aviation, marine, urban) using forecast data and rule-based knowledge, expressed by the LLM in simple language.

### 7.6 Administration

- FR-15: Administrators shall be able to review, approve, and broadcast alerts, manage data sources, and view usage analytics.

---

## 8. Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| Performance | Typical chat response within 3 seconds for cached queries and within 6 seconds for complex queries |
| Scalability | Horizontal scaling to support at least 10,000 concurrent users; stateless backend services |
| Availability | 99.5% or higher uptime, with graceful degradation to cached data when sources fail |
| Accuracy | Forecast values must be traceable to a named source; the LLM must never invent numerical values |
| Security | HTTPS everywhere, JWT-based authentication, rate limiting, input sanitization, secrets in a vault |
| Accessibility | WCAG 2.1 AA, large touch targets, high contrast mode, voice-first option |
| Localization | UTF-8 and Indic font support, translation of UI strings and responses |
| Maintainability | Modular services, documented APIs, automated tests, CI/CD |

---

## 9. Technology Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | HTML5, CSS3, JavaScript (ES6+), React.js | Responsive chat UI, dashboards, charts, PWA |
| Backend API | Node.js (Express) | REST and WebSocket gateway, authentication, session handling, alert dispatch |
| AI and data services | Python (FastAPI) | LLM orchestration, NLP, data processing, NWP parsing, analytics |
| Database | MongoDB | Users, conversations, alerts, cached forecasts, locations, time-series observations |
| Real-time messaging | WebSocket, MQTT | Live chat streaming, alert push, ingestion of real-time feeds |
| AI models | LLM (OpenAI, Gemini, or Llama), speech-to-text, text-to-speech, translation models | Query understanding, response generation, multilingual and voice support |
| Weather data | Weather APIs, GFS, WRF, IMD and open data feeds, satellite and radar products | Forecast and observation sources |
| GIS | Leaflet or Mapbox, GeoJSON, GDAL, geocoding services | Maps, location resolution, spatial queries |
| Cloud and DevOps | Docker, Kubernetes, cloud provider (AWS, Azure, or GCP), CI/CD pipeline | Deployment, scaling, monitoring |
| Libraries | Chart.js or Recharts, xarray, cfgrib, pandas, NumPy | Visualization and meteorological data processing |

---

## 10. System Architecture

### 10.1 Architectural Overview

WeatherGPT follows a layered, microservice-oriented architecture. The React client communicates with a Node.js API gateway over HTTPS and WebSocket. The gateway routes requests to Python AI and data services, which read from and write to MongoDB and external meteorological sources.

```
+---------------------------------------------------------------+
|  CLIENT LAYER: React PWA (Chat, Voice, Maps, Dashboards)      |
+------------------------------+--------------------------------+
                               | HTTPS / WebSocket
+------------------------------v--------------------------------+
|  API GATEWAY (Node.js / Express)                              |
|  Auth, rate limiting, sessions, alert dispatch, WebSocket hub |
+--------+---------------------+----------------------+---------+
         |                     |                      |
+--------v-------+   +---------v--------+   +---------v--------+
| AI SERVICE     |   | WEATHER DATA     |   | ALERT SERVICE    |
| (Python)       |   | SERVICE (Python) |   | (Node/Python)    |
| LLM, NLU,      |   | API fetch, NWP   |   | Threshold rules, |
| translation,   |   | parsing, climate |   | CAP feeds, push, |
| STT / TTS      |   | analytics        |   | SMS              |
+--------+-------+   +---------+--------+   +---------+--------+
         |                     |                      |
+--------v---------------------v----------------------v--------+
|  DATA LAYER: MongoDB (+ cache) | Object storage (GRIB/NetCDF) |
+--------------------------------+------------------------------+
|  EXTERNAL SOURCES: Weather APIs, GFS/WRF, Satellite, Radar,   |
|  Official warning feeds (MQTT / WIS 2.0 / CAP)                |
+---------------------------------------------------------------+
```

### 10.2 Component Description

**Client layer (React.js).** A mobile-first single-page application delivered as a PWA. It contains the chat window, microphone control, language selector, location picker, interactive map, forecast cards, and alert center. HTML, CSS, and JavaScript are used for the structure, styling, and interactivity, with React managing state and components.

**API gateway (Node.js).** Handles authentication, request validation, rate limiting, and routing. Maintains WebSocket connections for streaming chat responses and pushing live alerts. Subscribes to MQTT topics for real-time events.

**AI service (Python/FastAPI).** Hosts the query understanding engine, prompt orchestration, language detection, translation, speech processing, and response generation.

**Weather data service (Python).** Fetches data from weather APIs, downloads and parses GFS and WRF outputs (GRIB2 and NetCDF), computes derived indices, and performs historical and climate analysis.

**Alert service.** Evaluates forecast and observation data against hazard thresholds, ingests official warnings (for example, CAP-formatted bulletins), matches them to subscribed users by geofence, and dispatches notifications.

**Data layer.** MongoDB stores structured data and uses geospatial (2dsphere) indexes for location queries and time-series collections for observations. Large model files are kept in cloud object storage, with a cache (Redis or MongoDB TTL collections) for frequently requested forecasts.

---

## 11. AI and LLM Design

### 11.1 Query Understanding Pipeline

1. **Input capture:** Text, or voice converted to text using speech-to-text.
2. **Language detection and normalization:** Detect the language; translate to a pivot language (English) if needed for processing, preserving the original for the reply.
3. **Intent and entity extraction:** The LLM, guided by a structured prompt, returns JSON such as:

```json
{
  "intent": "forecast",
  "location": "Nashik",
  "time_range": "2026-10-31/2026-11-01",
  "parameters": ["rainfall", "wind"],
  "domain": "agriculture",
  "language": "mr"
}
```

4. **Geocoding:** Resolve the location to latitude and longitude.
5. **Data retrieval:** Call the weather data service with the structured request.
6. **Grounded response generation:** The LLM receives only the retrieved data and writes the answer, with advisory text where relevant.
7. **Translation and output:** Translate to the user's language and optionally synthesize speech.

### 11.2 Retrieval-Grounded Generation (Reducing Hallucination)

The LLM is never asked to recall weather values from memory. All numbers come from tool calls to the data service. The system prompt instructs the model to use only supplied data, cite the source and issue time, and say so honestly when data is unavailable. A validation step checks that numerical values in the response match the retrieved data.

### 11.3 Advisory Engine

A hybrid approach combines rule-based domain knowledge with LLM phrasing:

- **Agriculture:** Rules based on crop stage, rainfall, temperature, humidity, and wind (irrigation timing, spraying windows, frost and heat stress alerts).
- **Aviation:** Summaries of visibility, cloud, wind, thunderstorm, and turbulence conditions along a route.
- **Marine:** Wave height, wind, and cyclone proximity guidance.
- **Urban:** Rainfall intensity, waterlogging risk, heat index, and air-quality context.

### 11.4 Multilingual and Voice Strategy

- Use multilingual LLM capability combined with dedicated translation and speech models for Indian languages.
- Provide automatic language detection with a manual override.
- Use browser Web Speech APIs where available, with a server-side speech-to-text fallback for better accuracy on regional languages and dialects.
- Provide text-to-speech replies and simple, short sentences suited to audio playback.

---

## 12. Data Sources and Ingestion

| Source Type | Examples | Format | Ingestion Method |
| --- | --- | --- | --- |
| Weather APIs | OpenWeatherMap, Open-Meteo, IMD public APIs | JSON | Scheduled and on-demand REST calls |
| NWP models | GFS (NOAA), WRF output | GRIB2, NetCDF | Scheduled download every 6 hours; parsed with cfgrib and xarray |
| Satellite and radar | INSAT, radar composites | Images, NetCDF | Periodic fetch; tiles served on map |
| Official warnings | National and state warning bulletins | CAP, RSS, JSON | Polling and MQTT or WIS 2.0 subscription |
| Historical climate | IMD gridded data, ERA5, station records | NetCDF, CSV | Batch import into MongoDB and object storage |

**Real-time ingestion.** An ingestion worker publishes normalized observations to MQTT topics. The API gateway and alert service subscribe to these topics, update MongoDB, and push updates to connected clients through WebSocket.

---

## 13. Database Design (MongoDB)

| Collection | Key Fields | Notes |
| --- | --- | --- |
| users | \_id, name, phone, language, preferred\_locations, role, created\_at | Role: public, farmer, admin, researcher |
| conversations | \_id, user\_id, messages\[\], language, context, updated\_at | Stores recent context for follow-up queries |
| locations | \_id, name, district, state, geometry (GeoJSON Point), aliases\[\] | 2dsphere index |
| observations | location\_id, timestamp, temp, humidity, wind, rain, pressure, source | Time-series collection |
| forecasts | location\_id, issued\_at, valid\_time, parameters{}, model, source | TTL index for old forecasts |
| alerts | \_id, hazard\_type, severity, area (GeoJSON Polygon), start, end, message, source, status | Geospatial matching with subscriptions |
| subscriptions | user\_id, location, hazard\_types\[\], channels\[\] | Push, SMS, in-chat |
| climate\_stats | location\_id, month, variable, normal, min, max, years | Precomputed normals |
| audit\_logs | actor, action, timestamp, details | For admin and alert actions |

---

## 14. API Design (Summary)

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | /api/auth/login | Authenticate user and return JWT |
| POST | /api/chat | Send a text query and receive a response |
| WS | /ws/chat | Stream chat responses in real time |
| POST | /api/voice/transcribe | Convert audio to text |
| POST | /api/voice/speak | Convert text to speech audio |
| GET | /api/weather/current?lat=&lon= | Current conditions |
| GET | /api/weather/forecast?lat=&lon=&days= | Forecast for a location |
| GET | /api/climate/history?location=&from=&to= | Historical series and statistics |
| GET | /api/alerts?lat=&lon= | Active alerts for an area |
| POST | /api/alerts/subscribe | Subscribe to location-based alerts |
| POST | /api/admin/alerts | Create or broadcast an alert (admin only) |

---

## 15. User Interface and Accessibility

### 15.1 Main Screens

1. **Chat screen:** Conversation thread, suggested questions, microphone button, language switcher, and quick-action chips (Today, This week, Alerts).
2. **Forecast view:** Current conditions card, hourly strip, 7-day outlook, and icons with simple labels.
3. **Map view:** Interactive map with rainfall, wind, cyclone track, and warning overlays.
4. **Alerts center:** Active and past alerts with severity color coding.
5. **Climate analytics:** Charts for temperature and rainfall trends, anomalies, and comparisons.
6. **Settings:** Language, saved locations, alert preferences, and accessibility options.
7. **Admin dashboard:** Alert approval, source health monitoring, and usage statistics.

### 15.2 Accessibility and Rural Usability

- Voice-first mode: tap once, speak, and hear the answer.
- Large buttons, simple icons, and minimal text.
- Support for low-bandwidth networks through lightweight payloads, caching, and offline display of the last forecast.
- Color-blind friendly severity palette with text labels, not color alone.
- Screen-reader compatibility and keyboard navigation.

---

## 16. Alerting and Early Warning Workflow

1. Official warning feed or model threshold rule triggers a potential alert.
2. The alert service creates a draft with hazard type, severity, area polygon, and validity period.
3. For automatic low-risk alerts, it is published directly; for high-severity alerts, an administrator can review first.
4. The system finds subscribed users inside the affected area using geospatial queries.
5. The alert is translated into each user's language and sent through web push, SMS, and in-chat notification, with optional voice call or audio message for critical alerts.
6. Delivery status is logged, and follow-up updates are issued as conditions change.

**Example thresholds (configurable):** rainfall above 115 mm in 24 hours (heavy to very heavy), maximum temperature at or above 40°C for plains (heatwave criteria), wind speed above 62 km/h, and cyclone proximity within a configured distance of the coast.

---

## 17. Deployment and Scalability

- **Containerization:** Each service (frontend, gateway, AI service, data service, alert service, ingestion worker) is packaged as a Docker image.
- **Orchestration:** Kubernetes manages deployment, auto-scaling (Horizontal Pod Autoscaler), rolling updates, and health checks.
- **Cloud:** Hosted on a cloud provider using managed MongoDB (for example, MongoDB Atlas), object storage for model data, a CDN for static assets, and a managed message broker for MQTT.
- **Caching:** Frequently requested forecasts are cached to cut latency and API cost.
- **Observability:** Centralized logging, metrics (Prometheus and Grafana), tracing, and uptime alerts.
- **CI/CD:** Automated build, test, and deployment through GitHub Actions or an equivalent pipeline.
- **Resilience:** Fallback to secondary weather API if the primary fails, and graceful messages when data is stale.

---

## 18. Security, Privacy, and Ethics

- Encrypt data in transit (TLS) and at rest.
- Use JWT authentication, role-based access control, and rate limiting.
- Collect only necessary personal data (phone number, language, saved locations); obtain consent for location and notifications, in line with applicable data-protection law.
- Protect against prompt injection by separating system instructions from user input and by restricting the LLM to approved tools.
- Display clear disclaimers: the platform supplements, and does not replace, official warnings from national meteorological and disaster management authorities.
- For safety-critical warnings, always show the issuing authority and issue time.

---

## 19. Implementation Plan

| Phase | Duration | Activities | Deliverables |
| --- | --- | --- | --- |
| 1. Planning and design | Weeks 1–2 | Requirements finalization, data source selection, architecture and UI wireframes | SRS, architecture document, wireframes |
| 2. Data layer and ingestion | Weeks 3–5 | MongoDB schema, weather API integration, GFS ingestion, geocoding | Working data pipeline |
| 3. AI engine | Weeks 5–8 | Intent extraction, grounded response generation, advisory rules, translation | Chat API with accurate answers |
| 4. Frontend | Weeks 6–9 | React chat UI, forecast cards, maps, PWA setup | Functional web app |
| 5. Voice and multilingual | Weeks 9–10 | Speech-to-text, text-to-speech, language support for Indian languages | Voice-enabled multilingual chat |
| 6. Alerts | Weeks 10–11 | Alert rules, subscriptions, push and SMS, admin dashboard | End-to-end alerting |
| 7. Climate analytics | Weeks 11–12 | Historical data import, charts, trend analysis | Analytics module |
| 8. Testing and deployment | Weeks 12–14 | Load testing, accuracy evaluation, security review, Docker and Kubernetes deployment | Production-ready system |
| 9. Documentation and demo | Week 14–15 | User guide, API docs, final presentation | Final report and demo |

---

## 20. Testing and Evaluation Strategy

| Evaluation Parameter | Method | Target |
| --- | --- | --- |
| Accuracy and relevance | Compare responses against source data using a test set of at least 200 queries; verify forecast values and advisory correctness | 95% or higher factual match with source data |
| Response latency | Load tests with simulated users; measure p50 and p95 response times | p95 under 6 seconds |
| Multilingual capability | Test sets in each supported language for intent accuracy and translation quality; review by native speakers | 90% or higher intent accuracy |
| UI and accessibility | Usability testing with rural and urban users; WCAG audit | Task completion above 90% |
| Scalability | Stress test with Kubernetes autoscaling | 10,000 concurrent users |
| Real-time integration | Measure delay from source update to user alert | Under 2 minutes for push alerts |
| Voice interaction | Word error rate and user trials in noisy environments | WER under 15% for supported languages |

Testing types: unit tests (Jest, PyTest), integration tests, end-to-end tests (Cypress or Playwright), load tests (k6 or Locust), and security tests.

---

## 21. Risks and Mitigation

| Risk | Impact | Mitigation |
| --- | --- | --- |
| LLM hallucination of weather values | High | Retrieval-grounded generation, numeric validation, source citation |
| API downtime or rate limits | Medium | Multiple providers, caching, fallback messages |
| Poor accuracy for regional languages and dialects | Medium | Dedicated translation and speech models, feedback loop, native-speaker evaluation |
| Large NWP file processing cost and time | Medium | Subset by region and variable, scheduled jobs, object storage, efficient formats |
| Alert delivery failure in low-connectivity areas | High | SMS fallback, retry logic, multiple channels |
| Misuse or misinformation | High | Official-source attribution, admin approval for critical alerts, disclaimers |
| Data privacy concerns | Medium | Minimal data collection, consent, encryption |

---

## 22. Expected Outcomes and Impact

- Faster dissemination of weather information to the public and to decision makers.
- Improved public accessibility to forecasts through natural language, local languages, and voice.
- Better disaster preparedness and response through timely, location-specific warnings.
- An intelligent weather decision-support system for agriculture, aviation, marine operations, and urban planning.
- A foundation for climate analytics and research through easy access to historical data.

---

## 23. Innovation Highlights

- A single conversational entry point for fragmented meteorological sources.
- Retrieval-grounded LLM that turns technical products into plain-language advice without inventing data.
- Voice-first multilingual design for rural India.
- Geofenced, language-aware alert delivery.
- Domain-aware advisory generation (crop-stage-aware farming guidance, route-based aviation briefing, sea-state advice).

---

## 24. Future Enhancements

- Native Android and iOS apps and WhatsApp or IVR channel integration for feature phone users
- Hyperlocal nowcasting using radar and satellite machine learning models
- Crop-specific recommendation models integrated with soil and market data
- IoT and automatic weather station integration
- Offline and edge deployment for areas with very poor connectivity
- Fine-tuned domain LLM on meteorological and agricultural literature
- Integration with disaster management systems for coordinated response

---

## 25. Conclusion

WeatherGPT addresses a real gap between the abundance of meteorological data and the ability of ordinary people and professionals to act on it. By combining reliable data sources, NWP model outputs, a grounded LLM, multilingual support, and voice interaction on a scalable cloud architecture, the platform can make weather and climate intelligence faster, more accessible, and more useful for farmers, disaster managers, aviation, cities, and researchers alike.

---

## Appendix A: Sample Conversations

**Farmer (Hindi, voice):**\
User: "कल मेरे खेत में स्प्रे करना ठीक रहेगा?"\
WeatherGPT: Checks the user's saved location, finds low wind and no rain forecast until evening, and replies that morning hours are suitable for spraying, with a caution about rain expected the following night.

**Aviation briefing (English):**\
User: "Weather briefing Bengaluru to Hyderabad at 6 PM."\
WeatherGPT: Provides origin and destination conditions, expected visibility, cloud base, thunderstorm risk along the route, and winds aloft summary, with source and issue time.

**Disaster alert (Tamil, push):**\
Alert: "Heavy rainfall warning for your district for the next 24 hours. Avoid low-lying areas and follow local authority instructions." Sent in Tamil with the issuing authority and validity time.

## Appendix B: Glossary

- **NWP:** Numerical Weather Prediction, computer models that simulate the atmosphere to forecast weather.
- **GFS:** Global Forecast System, a global NWP model run by NOAA.
- **WRF:** Weather Research and Forecasting model, a regional mesoscale model.
- **GRIB2 / NetCDF:** Common file formats for meteorological gridded data.
- **CAP:** Common Alerting Protocol, a standard format for public warnings.
- **MQTT:** Lightweight publish-subscribe messaging protocol for real-time data.
- **WIS 2.0:** WMO Information System 2.0, a framework for exchanging weather data.
- **LLM:** Large Language Model.
- **PWA:** Progressive Web App.
- **STT / TTS:** Speech-to-text and text-to-speech.
