"""Start the repository's local classroom stack and manage only its own child processes."""
import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import venv
from datetime import datetime
from pathlib import Path
from urllib.request import ProxyHandler, build_opener


ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'backend/data/yida-classroom'
STATE = BASE / 'state'
ENVIRONMENT = BASE / '.venv'
PYTHON = ENVIRONMENT / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
FRONTEND = ROOT / 'frontend'
BACKEND = ROOT / 'backend'
VITE = FRONTEND / 'node_modules/vite/bin/vite.js'
CONTROL = STATE / 'controller.json'
LOCK = BASE / 'launch.lock'
READY = STATE / 'initialized'
HOST = '127.0.0.1'
FRONT_URL = 'http://127.0.0.1:5173'
CHECKS = ('http://127.0.0.1:8002/health', 'http://127.0.0.1:8010/health', FRONT_URL + '/',
          FRONT_URL + '/api/v1/posts', FRONT_URL + '/__course/reco/cities', FRONT_URL + '/__course/media/look-02.webp')
HTTP = build_opener(ProxyHandler({}))


def run(args, cwd=ROOT):
    subprocess.run([str(value) for value in args], cwd=cwd, check=True)


def tools():
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise RuntimeError('Use Python 3.11, 3.12, or 3.13.')
    node = shutil.which('node')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not node or not npm:
        raise RuntimeError('Install Node.js and npm before setup.')
    version = tuple(map(int, subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')))
    if not (version[0] == 20 and version >= (20, 19, 0) or version >= (22, 12, 0)):
        raise RuntimeError('This lockfile needs Node 20.19+ in the 20.x line or Node 22.12+.')
    npm_major = int(subprocess.check_output([npm, '--version'], text=True).strip().split('.')[0])
    if npm_major < 9:
        raise RuntimeError('This package-lock requires npm 9 or newer.')
    return node, npm


def secret_json(path, contents):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        json.dump(contents, output)
    temporary.replace(path)


def call(action):
    try:
        record = json.loads(CONTROL.read_text(encoding='utf-8'))
        with socket.create_connection((HOST, int(record['port'])), timeout=1) as client:
            client.sendall(f"{record['key']} {action}\n".encode('ascii'))
            return client.recv(64).decode('ascii').strip()
    except (OSError, ValueError, KeyError):
        return ''


def wait_http(url, processes):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for name, process in processes.items():
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited; check {STATE / (name + ".log")}')
        try:
            with HTTP.open(url, timeout=2) as response:
                if response.status != 200:
                    continue
                if url.endswith('.webp') and response.headers.get_content_type() != 'image/webp':
                    raise RuntimeError('Course image proxy did not return WebP media.')
                if url.endswith(('/posts', '/cities')):
                    if response.headers.get_content_type() != 'application/json' or json.load(response).get('code') != 0:
                        raise RuntimeError(f'Business probe did not return the expected JSON: {url}')
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f'Health check timed out: {url}')


def stop_children(processes):
    for process in reversed(list(processes.values())):
        if process.poll() is not None:
            continue
        process.terminate()
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def supervise(initialize):
    key = secrets.token_urlsafe(32)
    processes = {}
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', VITE_COURSE_DEMO='1',
               YIDA_COURSE_MEDIA_DIR=str(STATE / 'media'), YIDA_DEMO_RUNTIME=str(STATE),
               APP_ENV='development', WARDROBE_AI_PROVIDER='mock', DATABASE_URL='sqlite:///' + (STATE/'public.sqlite3').as_posix(),
               UPLOAD_DIR=str(STATE / 'uploads'), ACCOUNT_ALLOWED_ORIGINS=FRONT_URL, ACCOUNT_COOKIE_SECURE='false',
               ACCOUNT_TEST_PAGE='false', ACCOUNT_COLOR_NAMES='', RECOMMENDATION_HOST=HOST, RECOMMENDATION_PORT='8010',
               RECOMMENDATION_MODE='mock', RECOMMENDATION_DB_PATH=str(STATE/'recommendation.sqlite3'),
               RECOMMENDATION_WEIGHTS='', LLM_API_KEY='', LLM_BASE_URL='', LLM_MODEL='', WEATHER_API_KEY='')
    node = shutil.which('node')

    def start(name, cmd, folder):
        with (STATE / f'{name}.log').open('ab') as log:
            processes[name] = subprocess.Popen([str(entry) for entry in cmd], cwd=folder, env=env,
                                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    with socket.socket() as server:
        server.bind((HOST, 0))
        server.listen(4)
        server.settimeout(0.5)
        try:
            start('public', [PYTHON, '-m', 'uvicorn', 'app.main:app', '--host', HOST, '--port', 8002], BACKEND)
            wait_http(CHECKS[0], processes)
            start('recommendation', [PYTHON, '-m', 'recommendation.api'], BACKEND)
            wait_http(CHECKS[1], processes)
            if initialize:
                subprocess.run([str(PYTHON), str(ROOT/'demo/seed-demo.py')], cwd=ROOT, env=env, check=True)
            start('frontend', [node, VITE, '--host', HOST, '--port', 5173, '--strictPort'], FRONTEND)
            for url in CHECKS[2:]:
                wait_http(url, processes)
            if initialize:
                READY.touch()
            secret_json(CONTROL, {'port': server.getsockname()[1], 'key': key})
            while all(process.poll() is None for process in processes.values()):
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                with client:
                    try:
                        client.settimeout(1)
                        with client.makefile('rb') as request:
                            payload = request.readline(160).decode('ascii').strip().split(' ')
                        if len(payload) != 2 or not secrets.compare_digest(payload[0], key):
                            continue
                        if payload[1] == 'stop':
                            client.sendall(b'stopping\n')
                            break
                        if payload[1] == 'status':
                            client.sendall(b'ready\n')
                    except (OSError, UnicodeError):
                        continue
        finally:
            stop_children(processes)
            CONTROL.unlink(missing_ok=True)


def stop():
    if call('stop') != 'stopping':
        print('No responsive classroom stack owned by this directory.')
        return
    for _ in range(100):
        if not CONTROL.exists():
            print('Classroom services stopped.')
            return
        time.sleep(0.2)
    raise RuntimeError('Classroom supervisor did not finish stopping; check its log.')


def launch(initialize=False):
    if call('status') == 'ready':
        for url in CHECKS:
            wait_http(url, {})
    else:
        if not initialize and (not READY.is_file() or not (STATE/'public.sqlite3').is_file() or not (STATE/'demo-account.json').is_file()):
            raise RuntimeError('Run the setup script on this copy first.')
        for port in (5173, 8002, 8010):
            with socket.socket() as probe:
                if os.name == 'nt':
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                else:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind((HOST, port))
                except OSError as error:
                    raise RuntimeError(f'Port {port} is occupied. Close its owner explicitly, then start this copy.') from error
        STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
        args = [str(PYTHON), '-u', str(Path(__file__)), 'worker-initialize' if initialize else 'worker']
        if os.name == 'nt':
            detach = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            detach = {'start_new_session': True}
        with (STATE/'supervisor.log').open('wb') as log:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **detach)
        for _ in range(320):
            if call('status') == 'ready':
                break
            if process.poll() is not None:
                raise RuntimeError(f'Classroom stack did not start; see {STATE / "supervisor.log"}')
            time.sleep(0.25)
        else:
            raise RuntimeError(f'Classroom startup is still pending; see {STATE / "supervisor.log"} before retrying.')
    print('YIDA:', FRONT_URL + '/#/login')
    print('Local demo credentials:', STATE / 'demo-account.json')


def install(npm):
    requirements = BACKEND/'requirements.txt'
    lockfile = FRONTEND/'package-lock.json'
    fingerprint = hashlib.sha256(requirements.read_bytes() + lockfile.read_bytes()).hexdigest()
    stamp = BASE/'dependencies.sha256'
    if PYTHON.is_file() and VITE.is_file() and stamp.is_file() and stamp.read_text().strip() == fingerprint:
        return
    if not PYTHON.is_file():
        venv.create(ENVIRONMENT, with_pip=True)
    run([PYTHON, '-m', 'pip', 'install', '-r', requirements])
    run([npm, 'ci'], FRONTEND)
    stamp.write_text(fingerprint, encoding='ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('setup', 'start', 'stop', 'worker', 'worker-initialize'))
    parser.add_argument('--reset', action='store_true')
    options = parser.parse_args()
    operation = options.operation
    if operation.startswith('worker'):
        supervise(operation == 'worker-initialize')
        return
    if options.reset and operation != 'setup':
        parser.error('--reset is only valid with setup')
    if operation == 'stop':
        stop()
        return
    _, npm = tools()
    BASE.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f'Another setup/start is running. Check {LOCK} if it was interrupted.') from error
    try:
        os.close(fd)
        if operation == 'setup':
            if options.reset and STATE.exists():
                if input('Reset only this copy\'s classroom state? Type RESET to continue: ') != 'RESET':
                    return
                stop()
                state = STATE.resolve()
                if state.parent != BASE.resolve() or state.name != 'state':
                    raise RuntimeError('Unexpected classroom state directory.')
                backup = BASE / ('saved-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
                state.rename(backup)
                print('Previous classroom state saved at', backup)
            install(npm)
            run([PYTHON, ROOT/'demo/prepare-media.py'])
        launch(initialize=operation == 'setup' and not READY.is_file())
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'YIDA: {error}', file=sys.stderr)
        sys.exit(1)
