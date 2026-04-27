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

# Linux
sudo apt-get update
sudo apt-get install -y redis-server
```

## Test And Run

### E2E Test Manual

Test through manual action.

#### Checklist

You **must** check bellow settings before the test.

`scripts/setting.sh`

```bash
readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/config/test.json"
```

`tests/e2e_test_manual/manual_run.py`
```python
# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================
TASK_ID = "form"
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "button": "left",
            "num_clicks": 1,
            "x": 849,
            "y": 303,
        },
        {
            "action_type": "HOTKEY",
            "keys": ["ControlOrMeta", "a"],
        },
        {
            "action_type": "TYPING",
            "text": "1975",
        },
    ]
]
// ...
```

#### Run

```bash
bash scripts/tests/e2e_test_manual.sh
```

### E2E Test

Test through openai api. Requires API key.

#### Checklist

You **must** check bellow settings before the test.

`scripts/setting.sh`

```bash
readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/config/test.json"
```

`tests/e2e_test/run.py`
```python
# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "form"
SESSION_ID = int(time.time() * 1000)
CONFIG_PATH = (base_dir / "./tests/fixtures/config/test.json").resolve()
MODEL = "gpt-5.4-mini"
API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_STEPS = 10
MAX_TRAJECTORY_IMAGES = 4
```


#### Run

```bash
bash scripts/tests/e2e_test.sh
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
