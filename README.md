# prevfire-bot

Main repository for all scripts of CAJU's custom robot for fire detection and prevention, prevfire-bot.

The full documentation of the project is in [prevfire-bot Docs](https://caju-bot-docs.readthedocs.io/pt/latest/). Note that it is in Portuguese and I don't want to bother translating. Sorry!

This shouldn't be used as a guide or tutorial on how to make a robot. This is just a janky school project and our methods may not be good examples to follow!

## Installation

This is meant for Linux. It will not work in Windows or MacOS.

Clone this repository on your machine with git

```bash
git clone --depth 1 https://github.com/julliohenrik/prevfire-bot
```

Create a virtual environment for installing dependencies:

```bash
python -m venv .venv
```

Install dependencies with requirements.txt:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python-headless dill gpiozero
```

This installs the bare-minimum libraries for the scripts to work.
