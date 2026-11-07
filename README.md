# 🔬 The Research Desk

Developed an AI-powered research application using multi-agent workflows to generate detailed, cited reports from user queries, with authentication, conversation memory, clarification handling, caching, revision-based editing, and PDF/Word/Image export. 

Built with **NVIDIA NIM** (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`), **Google Serper API**, **Supabase** authentication, and hosted on **Vercel**.

![UI Preview](https://img.shields.io/badge/UI-Glassmorphism-blue)
![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?logo=python&logoColor=white)
![AI](https://img.shields.io/badge/AI-NVIDIA%20Nemotron%20Reasoning-76B900?logo=nvidia&logoColor=white)

## ✨ Features

- ⚡ **Reasoning AI:** Powered by NVIDIA's `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` via NVIDIA NIM (with automated Groq fallback).
- 🌍 **Institutional Google Search:** Powered by **Serper API** (Primary) with DuckDuckGo fallback and automated noise-filtering for directory scrapers.
- 🔒 **Secure User Accounts:** Full authentication and private research history powered by Supabase.
- 📱 **Fully Responsive:** A beautiful, responsive glassmorphism UI that looks perfect on desktops, tablets, and phones.
- 📄 **Rich Exports:** Download your research reports instantly as a **PDF**, **Word Document**, or **Image**.
- 🎙️ **Voice Enabled:** Use your microphone to dictate research topics, and use the built-in Text-to-Speech (TTS) engine to have the AI read the report out loud to you.
- 🔄 **Interactive Revisions:** Not happy with a section? Chat with the AI to revise, expand, or adjust specific parts of the generated report.

## 🛠️ Tech Stack

- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (No heavy frontend frameworks)
- **Backend:** Python, FastAPI
- **Database & Auth:** Supabase (PostgreSQL)
- **AI Models:** NVIDIA NIM (Nemotron-3 Nano Omni 30B Reasoning)
- **Deployment:** Vercel (Serverless Functions)

## 🚀 Local Development Setup

If you want to run this project locally on your own machine:

1. **Clone the repository:**
   `ash
   git clone https://github.com/mehak2921/ResearchDesk-.git
   cd ResearchDesk-
   `

2. **Install the dependencies:**
   `ash
   pip install -r requirements.txt
   `
   *(Or if you are using standard tools, install astapi, uvicorn, httpx, supabase, duckduckgo-search, pydantic)*

3. **Set up Environment Variables:**
   Create a .env file in the root directory and add your API keys:
   `env
   GROQ_API_KEY=your_groq_api_key
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   SERPER_API_KEY=your_serper_key # Optional fallback
   `

4. **Run the local server:**
   `ash
   uvicorn main:app --reload
   `
   The app will be available at http://localhost:8000.

## 📝 License
Copyright (c) 2026 MEHAK. All Rights Reserved.
