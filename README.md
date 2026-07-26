# prevfire-bot

Main repository for all scripts of CAJU's custom robot for fire detection and prevention, prevfire-bot.

The full documentation of the project is in [prevfire-bot Docs](https://caju-bot-docs.readthedocs.io/pt/latest/).

This shouldn't be used as a guide or tutorial on how to make a robot. We're are just learning and our methods may not be good examples to follow!

## Installation

Clone this repository on your machine with git

```bash
git clone --depth 1 https://github.com/julliohenrik/prevfire-bot
```

Create a virtual environment for installing dependencies:

```bash
python -m venv .venv
```

Install dependencies with pip using requirements.txt:

```bash
pip install -r requirements.txt
```

Or install it manually with:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python-headless
```

This installs the bare-minimum libraries for the scripts to work.
