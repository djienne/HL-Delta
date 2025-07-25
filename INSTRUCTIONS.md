* Be on Linux (i.e. WSL Ubuntu on Windows or native Ubuntu)
* Create a `.env` file containing environment variables (for the docker container) `HYPERLIQUID_ADDRESS=0x...` and `HYPERLIQUID_PRIVATE_KEY=0x...`
* Must be keys of a didcated Hyperliquid account with a hot wallet
* Edit `config.json` to your needs (coins, leverage, ratio spot/perp, ...)
* Open Terminal and run `bash build.sh`
* run `docker compose up` to see terminal output and check if it works well
* You can then ctrl-c and run `docker compose up -d` to have it running persistently in the background
