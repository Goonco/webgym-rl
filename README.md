# webgym-rl

## Set up

### Clone Repository

```bash
git clone --recursive https://github.com/Goonco/webgym-rl
cd webgym-rl;
```

### Setup Webgym Environment

```bash
conda create -n webgym-rl python=3.10
conda activate webgym-rl

pip install -U pip uv
uv pip install -r requirements.txt

playwright install chromium

# Linux only
playwright install-deps chromium

# macOS
brew install redis

# 확실치는 않음
pip install redis
```

## Test And Run

### E2E Test

```bash
bash scripts/tests/e2e_test.sh
```

```bash
# requires api key in .env (OPENAI_API_KEY)
bash scripts/tests/gpt_e2e_test.sh
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
