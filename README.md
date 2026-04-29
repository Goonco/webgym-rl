# webgym-rl

A web-based reinforcement learning environment for CUA.

<br/>

## Setup

> [!NOTE]  
> This repository includes a slightly modified version of [webgym](https://github.com/praveen-palanisamy/webgym) as a submodule.


### 1. Clone the repository

```bash
git clone --recursive https://github.com/Goonco/webgym-rl
cd webgym-rl
```

<br/>

### 2. Set up the WebGym environment

```bash
conda create -n webgym-rl python=3.10
conda activate webgym-rl

pip install -U pip uv
uv pip install -r requirements.txt
```

The commands below install system-level dependencies and are not tied to the Conda environment.

```bash
playwright install chromium

# Linux only
playwright install-deps chromium

# macOS
brew install redis

# Linux
sudo apt-get update
sudo apt-get install -y redis-server
```

<br/>

## Run

To start the server, you need to run both the Gateway and the Omnibox Server.
For easier log monitoring, we recommend running them in separate terminal sessions.

You can configure both servers by editing config.json.
There is no need to modify setting.sh.

```bash
bash omnibox_launch.bash
```

```bash
bash webgym_rl_launch.bash
```

<br/>

## Testing

### Manual E2E Test

You can manually test tasks using the command below.

```bash
bash tests/e2e_test_manual.sh
```

<br/>

Before running the test, make sure to check the following settings in `tests/setting.sh` and `tests/e2e_test_manual/run.py`.

<br/>

```bash
# tests/setting.sh

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly TEST_DIR="$ROOT_DIR/tests"
readonly FIXTURE_DIR="$TEST_DIR/fixtures"
readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/config/config.json"

readonly WITH_FIXTURE_WEBSITE=false
readonly FIXTURE_WEBSITE_PORT=8123

# ============================================================
```

```python
# tests/e2e_test_manual/run.py

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================
TASK_ID = "form"
SESSION_ID = int(time.time() * 1000)
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "button": "left",
            "num_clicks": 5,
            "x": 849,
            "y": 303,
        },
    ]
]

# ============================================================
```

<br/>

### OpenAI E2E Test

> [!CAUTION]  
> Requires refactoring. Unavailable now.

> [!NOTE]  
> Requires an `OPENAI_API_KEY` in `.env`

You can test tasks using openai api using the command below.

```bash
bash tests/e2e_test_openai.sh
```

<br/>

Before running the test, make sure to check the following settings in `tests/setting.sh` and `tests/e2e_test_openai/run.py`.

<br/>


```bash
# tests/setting.sh

readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/config/test.json"
```

```python
# tests/e2e_test_openai/run.py

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

## TODO

- [ ] Multi Browser Tasks
- [ ] 중간에 response 주기
- [ ] 마우스 커서 사진과 위치
- [ ] a11ytree -> privileged information
    - {

    }