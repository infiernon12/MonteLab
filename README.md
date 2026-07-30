# MonteLab — Advanced Poker Analysis & Monte Carlo Engine

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
![GUI: PySide6](https://img.shields.io/badge/GUI-PySide6-green)

**MonteLab** is an open-source poker equity calculation, game state analysis, and desktop visual assistant for Texas Hold'em. It combines computer vision (YOLO + ResNet card recognition) with a high-performance C++ Monte Carlo simulator to calculate pot odds, Stack-to-Pot Ratios (SPR), and real-time equity estimates.

---

## ✨ Features

- **🎯 Dual Interface Modes**:
  - **Adaptive Mode**: Modern dockable UI (PySide6) with floatable panels and layout persistence.
  - **Classic Mode**: Compact, traditional single-window layout for single-monitor setups.
- **⚡ High-Performance Monte Carlo Engine**:
  - Native C++ backend wrapper for fast equity calculations over millions of simulated hands.
  - Automatic fallback to Python equity calculator if C++ binaries are not compiled.
- **🤖 Computer Vision Card Detection**:
  - Integrated ML pipeline utilizing **YOLO** (table detection) and **ResNet** (card classification).
  - Region of Interest (ROI) screen capture overlay.
- **📊 Real-time Poker Decision Core**:
  - Pot Odds & Required Equity calculation.
  - SPR (Stack-to-Pot Ratio) indicator.
  - Distance-to-profit decision recommendation (FOLD / CALL / RAISE).

---

## 📁 Repository Structure

```text
MonteLab/
├── main.py                      # Primary application entry point
├── core/                        # Core poker logic and engine wrappers
│   ├── domain/                  # Game state, card, and hand domain models
│   └── poker/                   # Equity calculator & C++ Monte Carlo wrapper
├── services/                    # ML and Analysis services
├── ui/                          # PySide6 components, styles, and dockable windows
├── ml/                          # Computer vision pipeline (YOLO & ResNet detectors)
├── utils/                       # System utilities and helper functions
├── MonteCarlo-Poker-master/     # Source code for native C++ Monte Carlo engine (CMake)
├── models/                      # Location for ML model weights (.pt / .pth)
├── requirements.txt             # Python package dependencies
└── LICENSE                      # MIT License
```

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/infiernon12/MonteLab.git
cd MonteLab
```

### 2. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run MonteLab

```bash
python main.py
```

You can also specify the interface mode via command-line arguments:
```bash
# Launch Adaptive Dockable UI directly
python main.py --ui adaptive

# Launch Classic UI directly
python main.py --ui classic
```

---

## 🔧 Building the C++ Monte Carlo Backend (Optional)

For maximum simulation speed, you can build the native C++ Monte Carlo engine located in `MonteCarlo-Poker-master/`:

```bash
cd MonteCarlo-Poker-master
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

Once built, `MonteLab` will automatically detect and utilize the compiled binary for calculations.

---

## 🧠 ML Model Weights

MonteLab supports automated card detection from table screenshots. Place your trained model weight files into the `models/` directory:

- `models/epoch_50_ckpt.pth` (Table/Card YOLO Detector)
- `models/fine_tuned_resnet_cards_240EPOCH.pt` (ResNet Classifier)

*Note: If model files are absent, MonteLab runs seamlessly in manual card entry mode.*

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
