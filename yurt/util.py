import logging
import os

import config
from yurt.exceptions import (YurtCalledProcessException,
                             YurtCalledProcessTimeout, YurtException)


def is_ssh_available(port):
    from paramiko import SSHClient, AuthenticationException, client  # type: ignore
    from paramiko.ssh_exception import SSHException  # type: ignore
    import socket

    ssh = SSHClient()
    if not os.path.isfile(config.ssh_host_keys_file):
        with open(config.ssh_host_keys_file, "w") as f:
            f.write("")

    try:
        logging.debug(
            f"Trying SSH on port {port}.")
        ssh.load_host_keys(config.ssh_host_keys_file)
        ssh.set_missing_host_key_policy(client.AutoAddPolicy)
        ssh.connect("localhost", port, username=config.ssh_user_name,
                    key_filename=config.ssh_private_key_file, look_for_keys=False)
        return True
    except (AuthenticationException,
            SSHException, socket.error) as e:
        logging.debug(e)
        logging.debug("SSH not available on port {}".format(port))
    except socket.timeout:
        logging.error("SSH probe timed out")
    except Exception as e:
        logging.debug(e)
        logging.error("SSH probe failed with an unknown error")

    return False


def download_file(url, destination):
    import shutil
    import requests

    with requests.get(url, stream=True) as r:
        with open(destination, 'wb') as f:
            shutil.copyfileobj(r.raw, f)


def retry(fn, retries=3, wait_time=3):
    while True:
        try:
            return fn()
        except Exception as e:
            if retries > 0:
                retries -= 1
                sleep_for(wait_time, show_spinner=True)
            else:
                raise e


def find(fn, iterable, default):
    return next(filter(lambda i: fn(i), iterable), default)


def _spinner():
    frames = [
        ".  ",
        ".. ",
        "...",
        " ..",
        "  .",
        "   "
    ]

    frame = 0
    while True:
        if frame >= len(frames):
            frame = 0

        yield frames[frame]
        frame += 1


def _render_spinner(spinner, clear=False):
    import sys

    if clear:
        print(f"\r{' ' * 80}\r", end="", file=sys.stderr)
    elif spinner:
        print(f"\r{next(spinner)}\r", end="", file=sys.stderr)


def _async_spinner(worker_future):
    import time

    frame_step = 0.1
    spinner = _spinner()

    _render_spinner(None, clear=True)
    while not worker_future.done():
        _render_spinner(spinner)
        time.sleep(frame_step)
    _render_spinner(None, clear=True)


def sleep_for(timeout: float, show_spinner=False):
    import time

    if show_spinner:
        _render_spinner(None, clear=True)
        frame_step = 0.1
        spinner = _spinner()
        while timeout > 0:
            _render_spinner(spinner)
            time.sleep(frame_step)
            timeout -= frame_step
        _render_spinner(None, clear=True)
    else:
        time.sleep(timeout)


def _run(cmd, stdin=None, capture_output=True, timeout=None, env=None):
    import subprocess

    logging.debug(f"Running: {cmd}")

    new_env = dict(os.environ)
    if env:
        new_env.update(env)

    try:
        res = subprocess.run(cmd, capture_output=capture_output,
                             text=True, check=True, env=new_env, input=stdin, timeout=timeout)
        return res.stdout

    except subprocess.CalledProcessError as e:
        if e.stdout:
            logging.debug(f"{os.path.basename(cmd[0])}: {e.stdout}")
        if e.stderr:
            logging.error(f"{os.path.basename(cmd[0])}: {e.stderr}")
        raise YurtCalledProcessException("Operation failed.")

    except subprocess.TimeoutExpired as e:
        logging.debug(e)
        raise YurtCalledProcessTimeout("Operation timed out.")

    except KeyboardInterrupt:
        logging.error("Operation Aborted")


def run(cmd, show_spinner=False, **kwargs):
    """
    Run a command.
    - cmd: List[str]
        The command to be run.
    - capture_output: bool = True
        Capture stdout and stderr. Return stdout and log stderr.
    - show_spinner: bool = False
        Show a spinner while command runs.
        Spinner is shown only if capture_output=True.
    - timeout: float
        Cancel command if it runs for more than this.
    """
    if show_spinner:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            cmd_future = executor.submit(_run, cmd, **kwargs)
            executor.submit(_async_spinner, cmd_future)
            return cmd_future.result()

    else:
        return _run(cmd, **kwargs)
