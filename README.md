# webgym-rl

## Set up

### Clone Repository

```bash
git clone https://github.com/Goonco/webgym-rl
cd webgym-r;
```

### Setup Webgym Environment

```bash
conda create -n webgym-rl python=3.10
conda activate webgym-rl

pip install -U pip uv
cd environment/webgym
uv pip install -e ".[omnibox]"

playwright install chromium
# Linux only
playwright install-deps chromium

# macOS
brew install redis

cd ../../
```

## Test And Run

### E2E Test

```bash
bash scripts/e2e_test.sh
```

## Default Ports

### External Port
- `8123` : fixture website (for test)
- `5500` : omnibox master
- `18000` : gateway

### Internal Port
- `6379` : redis
- `8080` : omnibox node
- `9000+` : instance servers
