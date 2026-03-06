
# 🌐 TRANSLai
## Multilingual Prompt Translation & Enhancement Middleware for Image Generation Models
![GENEXUS-AI Banner](https://github.com/aymantaha-dev/TranslAI/blob/main/Banner.png?raw=true)


![Python Version](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.119.0-black)
![License](https://img.shields.io/badge/license-MIT-green)

---
> ⚠️ This is a **starter framework**. Developers must **adapt and customize** it for their own projects. It provides a **first-level setup** for prompt translation and enhancement, not a fully production-ready solution.
---

## 🎯 The Problem
Most image generation models (including OpenAI DALL-E, Midjourney, and similar systems) perform poorly when receiving prompts in non-English languages. Users from non-English speaking backgrounds face significant barriers to accessing these powerful creative tools, resulting in lower quality outputs and frustrating user experiences.

## ✨ The Solution
**TRANSLai** is a production-ready middleware service that bridges this language gap by:
- ✅ Accepting prompts in **any human language**
- ✅ Automatically detecting and translating them to high-quality English
- ✅ Optionally enhancing visual quality while **strictly preserving user intent**
- ✅ Forwarding the optimized prompt to image generation models
- ✅ Returning the generated image with comprehensive metadata

**This system does not train models and does not generate images internally** - it acts as an intelligent translation and enhancement layer between users and existing image generation APIs.

---

## 🏗️ Project Architecture
```
D:\TranslAI/
├── translai/                    # 📦 Main application package
│   ├── __init__.py              # 📄 Package initialization
│   └── app/                     # 📁 FastAPI application
│       ├── __init__.py          # 📄 App package initialization
│       ├── main.py              # 🚀 Application entry point
│       ├── config.py            # ⚙️  Configuration management
│       ├── schemas.py           # 📋 Pydantic models
│       ├── pipeline.py          # 🔗 Processing pipeline
│       ├── providers.py         # 🤖 LLM provider abstraction
│       ├── image_gateway.py     # 🖼️  Image generation gateway
│       └── logger.py            # 📝 Advanced logging system
├── venv/                        # 🌐 Virtual environment
├── .env.example                 # 📋 Environment example file
├── .env                         # 🔑 Environment configuration (created from .env.example)
├── requirements.txt             # 📦 Python dependencies
├── run.py                       # ⚡ Application runner
├── README.md                    # 📖 This documentation
└── LICENSE                      # 📄 MIT License
```

> **Note**: The `venv/` folder is **NOT** included in this repository (as per best practices). You'll need to create it locally following the setup instructions below.

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11 or higher
- Git (for cloning the repository)
- Windows 10/11, macOS, or Linux

### Step-by-Step Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/aymantaha3345/TranslAI.git
cd TranslAI
```

#### 2. Create Virtual Environment
**Windows (Command Prompt):**
```bash
python -m venv venv
```

**Windows (PowerShell):**
```powershell
python -m venv venv
```

**macOS/Linux:**
```bash
python3 -m venv venv
```

#### 3. Activate Virtual Environment
**Windows (Command Prompt):**
```bash
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

> After activation, you should see `(venv)` prefix in your command prompt:
> ```
> (venv) D:\TranslAI>
> ```

#### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 5. Configure Environment Variables
```bash
# Create .env file from example
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux
```

**Edit the `.env` file** and add your API keys:
```env
# Text LLM Provider Configuration
TEXT_PROVIDER=openai
TEXT_PROVIDER_API_KEY=your_openai_api_key_here
TEXT_PROVIDER_MODEL=gpt-4o-mini

# Image Generation Provider Configuration  
IMAGE_PROVIDER=openai
IMAGE_PROVIDER_API_KEY=your_openai_api_key_here
IMAGE_PROVIDER_MODEL=dall-e-3

# Security
AUTH_ENABLED=true
API_KEYS=change-me-api-key
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Application Settings
APP_ENV=development
DEBUG=true
```

#### 6. Run the Application
```bash
python run.py
```

#### 7. Access the API
- **API Documentation**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/api/health

---

## 💡 Usage Examples

### Basic Request (Arabic to Image)
```bash
curl -X POST "http://localhost:8000/api/v1/generate" ^
-H "Content-Type: application/json" ^
-d "{ \"prompt\": \"قطة زرقاء تلعب على العشب الأخضر\", \"enhance\": true }"
```


### Authenticated Request
```bash
curl -X POST "http://localhost:8000/api/v1/generate" ^
-H "Content-Type: application/json" ^
-H "X-API-Key: change-me-api-key" ^
-d "{ \"prompt\": \"قطة زرقاء تلعب على العشب الأخضر\", \"enhance\": true }"
```

### Response Example
```json
{
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "original_prompt": "قطة زرقاء تلعب على العشب الأخضر",
  "detected_language": {
    "language": "ar",
    "confidence": 0.98,
    "language_name": "Arabic"
  },
  "translated_prompt": "a blue cat playing on green grass",
  "enhanced_prompt": "A beautiful blue cat playing joyfully on lush green grass, natural sunlight, vibrant colors, high detail, professional photography",
  "enhancement_applied": true,
  "image_result": {
    "image_url": "https://images.openai.com/...",
    "model_used": "dall-e-3",
    "provider_used": "openai",
    "generation_time": 3.45
  },
  "processing_time": 4.78
}
```

---


---

## 🛠️ Troubleshooting Common Issues

### Virtual Environment Issues
**If activation fails on Windows PowerShell:**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
.\venv\Scripts\Activate.ps1
```

**If you see "command not found" errors:**
```bash
# Make sure you're in the project directory
cd TranslAI

# Make sure virtual environment is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Reinstall dependencies
pip install -r requirements.txt
```

### Missing Dependencies
```bash
# If you get import errors, install missing packages
pip install fastapi uvicorn pydantic httpx python-dotenv loguru openai fast-langdetect redis
```

### Language Detection Issues
```bash
# Reinstall the language detection package
pip uninstall -y fast-langdetect
pip install fast-langdetect --force-reinstall
```

---

## 🌟 Key Features

### ✅ Language Detection & Translation
- Supports 50+ languages with high accuracy
- Uses `fast-langdetect` for reliable language identification
- Professional translation preserving original meaning and style

### ✅ Intent-Preserving Enhancement
- **Strict rules** ensure user intent is never changed:
  - ✅ **Allowed**: Lighting improvements, composition enhancements, visual clarity
  - ❌ **Forbidden**: Adding new objects, changing subjects, altering artistic intent
- Validation system prevents intent drift

### ✅ Provider Abstraction
- Configuration-based provider switching
- No code changes needed to switch between providers
- Extensible architecture for new providers

### ✅ Production-Ready Features
- Structured logging with request correlation
- Comprehensive error handling and fallback mechanisms
- Health checks and monitoring endpoints

---


## 🤝 Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository
2. Create a new feature branch
3. Commit your changes
4. Push to your branch
5. Create a pull request

## 📧 Contact
For questions, suggestions, or support:
- GitHub Issues: https://github.com/aymantaha3345/TranslAI/issues
- Email: aymantaha89pp@gmail.com

---

**🚀 Ready to make image generation accessible to everyone, regardless of language!**
```

This README.md includes:

1. **Complete virtual environment setup instructions** for Windows, macOS, and Linux
2. **Clear activation commands** for different shells (Command Prompt, PowerShell, Bash)
3. **Dependency installation instructions** with pip
4. **Troubleshooting section** for common virtual environment and dependency issues
5. **Updated project structure** that reflects the actual repository structure (without venv folder)
6. **Windows-specific commands** using `^` for line continuation in curl examples
7. **Complete setup workflow** from cloning to running the application


The instructions are designed to be beginner-friendly while maintaining professional quality. The virtual environment setup is given proper emphasis since it's critical for the application to work correctly, and the user specifically mentioned deleting the venv folder for GitHub upload.



