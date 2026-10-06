"""
Execution engine for Mint Script Runner.
Runs .sh scripts asynchronously with live output capture and optional root elevation via pkexec.
"""

import os
import signal
import subprocess
import threading
from pathlib import Path
from gi.repository import GLib


class ScriptRunner:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.current_process = None
        self.is_running = False
        self.worker_thread = None

    def execute(
        self,
        script_path,
        args_list=None,
        as_admin=False,
        inject_github=True,
        working_dir=None,
        on_output=None,
        on_status=None,
        on_finished=None,
    ):
        """Starts script execution in a separate background thread."""
        if self.is_running:
            return False, "Another script is already running."

        script = Path(script_path)
        if not script.is_file():
            return False, f"Script does not exist: {script_path}"

        # Resolve working directory
        cwd = working_dir if working_dir and Path(working_dir).is_dir() else str(script.parent)

        # Prepare Environment Variables
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["PYTHONUNBUFFERED"] = "1"

        if inject_github:
            user = self.settings.get("github_username", "").strip()
            token = self.settings.get("github_token", "").strip()
            email = self.settings.get("github_email", "").strip()

            if user:
                env["GITHUB_USER"] = user
                env["GH_USER"] = user
                env["GIT_AUTHOR_NAME"] = user
                env["GIT_COMMITTER_NAME"] = user
                env["MINT_GIT_USER"] = user

            if token:
                env["GITHUB_TOKEN"] = token
                env["GH_TOKEN"] = token
                env["MINT_GIT_TOKEN"] = token

            if email:
                env["GIT_AUTHOR_EMAIL"] = email
                env["GIT_COMMITTER_EMAIL"] = email

            # Setup automated GIT_ASKPASS helper
            askpass_script = Path(__file__).parent / "askpass_helper.py"
            if not askpass_script.is_file():
                user_askpass = Path.home() / ".local" / "lib" / "mint-script-runner" / "git-askpass.py"
                if user_askpass.is_file():
                    askpass_script = user_askpass
                else:
                    # In system install, might be in /usr/lib/mint-script-runner/
                    askpass_script = Path("/usr/lib/mint-script-runner/git-askpass.py")

            if askpass_script.is_file():
                env["GIT_ASKPASS"] = str(askpass_script)
                env["SSH_ASKPASS"] = str(askpass_script)
                env["GIT_TERMINAL_PROMPT"] = "0"

        # Build Command
        args = args_list or []
        if as_admin:
            # pkexec launches PolicyKit GUI authentication
            cmd = ["/usr/bin/pkexec", "/bin/bash", str(script)] + args
        else:
            cmd = ["/bin/bash", str(script)] + args

        self.is_running = True

        def run_thread():
            try:
                if on_status:
                    mode_str = "Administrator (Root)" if as_admin else "Standard User"
                    GLib.idle_add(on_status, f"Starting ({mode_str})...")

                # Launch process group so children can be killed cleanly
                self.current_process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid,
                )

                if on_status:
                    GLib.idle_add(on_status, f"Running (PID: {self.current_process.pid})")

                # Stream output line by line
                for line in iter(self.current_process.stdout.readline, ""):
                    if not line:
                        break
                    if on_output:
                        GLib.idle_add(on_output, line)

                self.current_process.stdout.close()
                return_code = self.current_process.wait()

            except Exception as e:
                err_msg = f"\n❌ Execution Error: {str(e)}\n"
                if on_output:
                    GLib.idle_add(on_output, err_msg)
                return_code = -1

            finally:
                self.is_running = False
                self.current_process = None
                if on_finished:
                    GLib.idle_add(on_finished, return_code)

        self.worker_thread = threading.Thread(target=run_thread, daemon=True)
        self.worker_thread.start()
        return True, "Script launched."

    def stop(self):
        """Terminates the running process group."""
        if not self.is_running or not self.current_process:
            return False, "No active process to stop."

        try:
            pgid = os.getpgid(self.current_process.pid)
            os.killpg(pgid, signal.SIGTERM)
            return True, "Termination signal sent."
        except ProcessLookupError:
            return True, "Process already finished."
        except Exception as e:
            try:
                self.current_process.kill()
                return True, "Killed process directly."
            except Exception as e2:
                return False, f"Failed to stop: {e2}"
