## Tic Kan Toe

You may run both client and API together with `python test.py`. First, install required dependencies with either `venv` or `conda`:

On Ubuntu with Python venv:

```
sudo apt install python3-pip python3.10-venv
python3 -m venv tic-kan-toe
source tic-kan-toe/bin/activate
pip install -r requirements.txt
```

Alternative with Anaconda

```
conda update -n base -c defaults conda
conda create -n tic-kan-toe python=3.10
conda env update --file environment.yaml --prune
conda activate tic-kan-toe 
```

You should be able to install anaconda [on Linux](https://docs.anaconda.com/anaconda/install/linux/), [on MacOS](https://docs.anaconda.com/anaconda/install/mac-os/), or [on Windows](https://docs.anaconda.com/anaconda/install/windows/).


## HTTPS

Install certbot with `sudo apt install certbot -y`, then follow one of two approaches:

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
