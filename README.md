## Tic Kan Toe

Install anaconda [on Linux](https://docs.anaconda.com/anaconda/install/linux/), [on MacOS](https://docs.anaconda.com/anaconda/install/mac-os/), or [on Windows](https://docs.anaconda.com/anaconda/install/windows/).

On Ubuntu Linux without anaconda...

```
sudo apt install python3-pip python3.10-venv -y
python3 -m venv tic-kan-toe
source tic-kan-toe/bin/activate
pip install fastapi==0.103
pip install uvicorn==0.23
pip install python-dotenv==1
pip install pydantic==1.10
pip install pypokedex
```

With Anaconda...

```
conda update -n base -c defaults conda
conda update conda

conda create -n tic-kan-toe python=3.11
conda activate tic-kan-toe 
conda install fastapi=0
conda install uvicorn=0
conda install pydantic=1
conda install python-dotenv=1
pip install pypokedex==1
```

### Run demo

```
python test.py
```

### Scripts

```
pip install imageio==2.34.0
```

Generate "n" badges, `n=58` now matches "client/src/lib.badges.js". This should be re-run when "scripts/badges/" updated. The current list of badge images is given by [this GitHub repository commit](https://github.com/PokeAPI/sprites/tree/2a6a6b66983a97a6bdc889b9e0a2a42a25e2522e/sprites/badges).

```
python scripts/combine_badges.py 58 scripts/badges/ client/data/
```
