## Tic Kan Toe

Install anaconda [on Linux](https://docs.anaconda.com/anaconda/install/linux/), [on MacOS](https://docs.anaconda.com/anaconda/install/mac-os/), or [on Windows](https://docs.anaconda.com/anaconda/install/windows/).

On Ubuntu Linux without anaconda...

```
sudo apt install python3-pip python3.10-venv certbot -y
python3 -m venv tic-kan-toe
source tic-kan-toe/bin/activate
pip install cryptography==42.0.3
pip install websockets==12.0
pip install fastapi==0.103
pip install uvicorn==0.23
pip install pydantic==1.10
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
```

## HTTPS

### Recommended DNS challenge

```
sudo certbot certonly --manual --preferred-challenges dns --agree-tos --cert-name owl -d tvquizphd.com
```

Follow instructions and hit `ENTER`.


### Alternative HTTP challenge

If no access to DNS settings, temporarily open firewall to `acme-v02.api.letsencrypt.org`.

```
CERT_IP=$(host -4 -t A acme-v02.api.letsencrypt.org |  awk '{print $4}' | tail -n 1)
sudo ufw allow in on enp8s0 proto tcp from $CERT_IP to any port 80
```

Temporarily open port `80` forwarding to your server, then run:

```
sudo certbot certonly --standalone --preferred-challenges http --agree-tos --cert-name owl -d tvquiz.mooo.com
```

You may now close port `80`. Also, `sudo ufw status numbered` and `sudo ufw delete LAST_NUM`.

**Note**: these instructions were insufficiently tested, due to rate limiting.

### Run demo

```
source tic-kan-toe/bin/activate
sudo env "PATH=$PATH VIRTUAL_ENV=$VIRTUAL_ENV" python test.py
```

### Scripts

```
pip install imageio==2.34.0
```

Generate "n" badges, `n=58` now matches "client/src/lib.badges.js". This should be re-run when "scripts/badges/" updated. The current list of badge images is given by [this GitHub repository commit](https://github.com/PokeAPI/sprites/tree/2a6a6b66983a97a6bdc889b9e0a2a42a25e2522e/sprites/badges).

```
python scripts/combine_badges.py 58 scripts/badges/ client/data/
```
