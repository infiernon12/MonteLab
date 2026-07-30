# ♠️ MonteLab — Advanced AI Poker Analyzer & Monte Carlo Engine

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![C++: MSVC%2FMinGW](https://img.shields.io/badge/C%2B%2B-Engine-orange.svg)
![PySide6: UI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Fusion-purple.svg)

**MonteLab** is an open-source poker hand analysis platform powered by Computer Vision (**YOLOX** + **ResNet-34**), a high-speed **C++ Monte Carlo simulation engine** (100,000+ iterations/run), and an **ABC Strategy & Tactical Advisor**.

> ### 📜 Project Origin & Retrospective
> **Note**: This repository represents a major milestone in my early software engineering journey. Built as a hands-on learning project to master C++ performance optimization, neural network integration (YOLOX & ResNet-34), PySide6 architecture, and Git workflows.
> 
> While it reflects an early pet-project scope (hence the absence of formal CI/CD pipelines and automated unit test suites), it highlights my foundational exploration into complex multi-language systems, computer vision, and real-time interactive software.

---

## 🚀 Key Features

* 👁️ **Computer Vision & Card Recognition**: 
  * Real-time desktop screen region capture (ROI selection overlay).
  * Table & card detection via **YOLOX** and rank/suit classification via **ResNet-34**.
* ⚡ **High-Speed C++ Monte Carlo Engine**: 
  * Simulates **100,000+ hands** in milliseconds using a persistent C++ daemon process.
  * Auto-generates binary evaluation lookup tables (`lookup_tablev3.bin`).
  * Automatic pure-Python fallback (`PythonMonteCarloBackend`) for cross-platform compatibility.
* 📊 **Hand Equity & Odds Calculator**: 
  * Calculates real-time **Win %**, **Tie %**, and **Lose %** probabilities.
  * Out breakdown (Flush, Straight, Set/Trips, Overcards) and street improvement odds.
* 💡 **ABC Strategy & Tactical Advisor**:
  * Actionable preflop and postflop strategic advice based on position, stack depth (BB), and opponent count.
  * GTO metrics: Pot Odds EV evaluation (`+EV PROFITABLE CALL` vs `-EV UNPROFITABLE CALL`), SPR (Stack-to-Pot Ratio), and recommended bet sizing in chips and Big Blinds.
* 🎨 **Dual Responsive UI Modes**:
  * **Adaptive Modern UI**: Fully dockable, floatable panels with persistent layout memory.
---

## 🖼️ User Interface Screenshots

| Adaptive Dockable UI | Classic Interface |
| :---: | :---: |
| <img src="https://raw.githubusercontent.com/infiernon12/MonteLab/main/docs/screenshots/adaptive_ui.png" alt="Adaptive UI" width="100%"/> | <img src="https://raw.githubusercontent.com/infiernon12/MonteLab/main/docs/screenshots/classic_ui.png" alt="Classic UI" width="100%"/> |

---

## 📦 Model Weight Files

Download trained neural network weight files from the [GitHub Releases](https://github.com/infiernon12/MonteLab/releases) section and place them inside the `models/` directory:

| File Name | Description | Recommended Path |
| :--- | :--- | :--- |
| **`YOLOX_Detector.pth`** | Table ROI & Card Detection Model | `models/YOLOX_Detector.pth` |
| **`ResNet_Classifier.pt`** | Card Rank & Suit Classification Model | `models/ResNet_Classifier.pt` |

---

## ⚙️ Installation & Getting Started

### 1. Requirements
* Python **3.10+** (64-bit)
* Windows 10/11 (or Linux/macOS using Python fallback)

### 2. Setup Environment
```bash
# Clone repository
git clone https://github.com/infiernon12/MonteLab.git
cd MonteLab

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running MonteLab
```bash
# Run application (interactive UI selector)
python main.py

# Launch Adaptive UI directly
python main.py --ui adaptive

# Launch Classic UI directly
python main.py --ui classic

# Or double-click launcher
run.bat
```

---

## 🛠️ Project Architecture

```text
MonteLab/
├── main.py                          # Main entrypoint & UI selector
├── run.bat                          # 1-click Windows launcher
├── models/                          # Neural network weights directory
├── core/
│   ├── domain/                      # GameState, Cards, TableData, DecisionEngine
│   └── poker/                       # EquityCalculator, HandEvaluator, Monte Carlo Backends
├── services/
│   ├── ml_service.py                # YOLOX + ResNet inference pipeline
│   ├── analysis_service.py          # Hand analysis orchestration
│   └── improved_abc_recommendations.py # ABC Tactical Advisor engine
├── ui/
│   ├── windows/                     # AdaptiveMainWindow & MainWindow
│   └── dock_widgets.py              # Responsive dock panels
└── utils/
    └── screen_capture.py            # Screen capture & ROI selection
```

---

## ⚖️ Legal Disclaimer & Limitation of Liability

> ### ⚠️ DISCLAIMER OF LIABILITY AND TERMS OF USE
>
> **1. EDUCATIONAL AND RESEARCH PURPOSE ONLY**  
> MonteLab is developed and provided **EXCLUSIVELY FOR EDUCATIONAL, ACADEMIC, AND RESEARCH PURPOSES**, as well as offline hand analysis and study. It is intended to help users understand poker mathematics, probability theory, computer vision techniques, and strategic decision-making algorithms.
>
> **2. COMPLIANCE WITH THIRD-PARTY TERMS OF SERVICE**  
> The user assumes **FULL AND SOLE RESPONSIBILITY** for complying with all applicable local laws, regulations, and third-party Terms of Service (including online gaming platforms and poker room rules). Using automated screen capture or analysis software during active real-money play on online poker platforms may violate their Terms of Service (anti-RTA policies). **The authors and contributors DO NOT condone, encourage, or support the use of this software during active online play where prohibited.**
>
> **3. NO WARRANTY (AS-IS)**  
> THE SOFTWARE IS PROVIDED **"AS IS"**, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
>
> **4. LIMITATION OF LIABILITY**  
> IN NO EVENT SHALL THE AUTHORS, COPYRIGHT HOLDERS, OR CONTRIBUTORS BE LIABLE FOR ANY CLAIM, DAMAGES, LOSSES, BANS, FINANCIAL LOSSES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
