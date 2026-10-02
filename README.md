# Internet Lock

A lightweight cross-platform utility to block and restore system-wide internet access with password protection. It natively manages firewall and packet filter rules across **Windows**, **Linux**, and **macOS**, providing both a desktop graphical interface and command-line options.

## Supported Operating Systems & Requirements

- **Windows:** Windows 10 / 11 (uses Windows Defender Firewall via PowerShell, elevates via UAC)
- **Linux:** Ubuntu, Debian, Fedora, Arch, Mint, etc. (uses `iptables` with loopback preserved, elevates via `pkexec` / `sudo`)
- **macOS:** macOS Monterey, Ventura, Sonoma, Sequoia (uses `pfctl` isolated anchor `com.internetlock`, elevates via native macOS admin dialog)
- **Python:** Python 3.8 or higher (standard library only: `tkinter`, `hashlib`, `subprocess`, `json`, `base64`, `threading`). No `pip` dependencies required.

## Installation

Clone or download this repository to your local machine:

```bash
git clone https://github.com/Tan-g45/for_no_internet.git
cd for_no_internet
```

Verify that Python is installed and accessible in your command prompt:

```bash
python --version
```

---

## Practical Use Case: Preventing AI Assistance in Coding Tests and Lab Exams

In modern programming examinations and classroom lab evaluations, preventing unauthorized access to generative AI assistants (such as ChatGPT, Claude, Gemini, GitHub Copilot, and Cursor) is essential for fair testing.

Because cloud-based AI coding tools and LLM plugins require outbound internet access to function, blocking internet traffic enforces a strictly local, offline development environment without interfering with local compilers, editors, or test suites.

### Exam Workflow

1. **Setup by Teacher / Proctor:**
   - Before the exam starts, the instructor opens the application on each student machine.
   - The instructor enters a secret password known only to them and locks internet access.
   - Windows Defender Firewall immediately applies the outbound blocking rule.

2. **Blocking AI Tools and Preserving Offline Tools:**
   - Browser-based AI platforms (ChatGPT, Claude, web interfaces) cannot load.
   - IDE-integrated AI completion engines (GitHub Copilot, Tabnine cloud, Codeium) fail to communicate with remote inference servers and stop offering suggestions.
   - External search engines, documentation sites, and code repositories are completely inaccessible.
   - Students retain full access to local offline tools: local Python runtimes, C/C++ compilers, offline IDEs (VS Code, PyCharm, IDLE), and local test files.
   - Even if a student attempts to close, force-quit, or uninstall the Python script, internet access remains blocked by the underlying Windows firewall rule.

3. **Post-Exam Verification:**
   - Once testing concludes, the instructor returns to the workstation and unlocks the connection using the original password.
   - Successful verification confirms that the student could not unlock the machine, tamper with the configuration, or utilize network-based AI models during the test period.

---

## How to Use

### 1. Graphical Interface (GUI)

Run using Python:

```bash
python internet_lock.py
```

To run without keeping a terminal window open in the background, run the `.pyw` file or double-click it in Windows Explorer:

```bash
pythonw internet_lock.pyw
```

#### How to Lock Internet Access
1. Launch the application.
2. Enter your desired password in the password input box.
3. Click "LOCK INTERNET".
4. Accept the Windows User Account Control (UAC) prompt if requested.
5. All outbound internet traffic is immediately blocked.

#### How to Unlock Internet Access
1. Open the application.
2. Click "UNLOCK".
3. Type your password into the prompt window and confirm.
4. The firewall block rule is removed, and internet connectivity is restored.

#### Settings and Password Management
Click the settings gear icon in the bottom right corner of the window to access options:
- Refresh Status: Checks current firewall state against Windows Defender.
- Change Password: Update your current password or clear it.
- Relaunch as Admin: Elevates the application process to avoid multiple UAC prompts.

---

### 2. Command Line Interface (CLI)

The script provides command-line flags for status checking and emergency recovery without opening the graphical window.

#### Check Status
```bash
python internet_lock.py --status
```
Outputs whether internet access is currently active or blocked. Returns exit code `1` if blocked, `0` if active. Short flag `-s` is also supported.

#### Emergency Remove (Restore Internet)
```bash
python internet_lock.py --remove
```
Removes the `Block Internet` firewall rule immediately to restore connection. Short flag `-r` and `--emergency-remove` are also supported. If not already running from an elevated console, Windows will prompt for elevation.

#### Help
```bash
python internet_lock.py --help
```
Displays usage instructions for command-line arguments.

---

## Technical Details

- **Firewall Integration:** Creates an outbound rule named `Block Internet` in Windows Defender Firewall (`New-NetFirewallRule`) targeting the `Internet` remote address filter.
- **Security:** Passwords are protected using PBKDF2-HMAC-SHA256 with 100,000 iterations and a per-install cryptographic salt. Plaintext passwords are never saved.
- **Configuration:** Password hash and salt are stored locally in `.internet_lock_config.json`.
- **Privilege Handling:** Commands requiring administrative access use Windows `ShellExecuteExW` with the `runas` verb to request elevation when needed.

---

## 📦 Standalone Executables & Automated Builds

Pre-built binaries for **Windows (.exe)**, **Linux**, and **macOS** can be packaged together in a single `.zip` file:

- **Manual Trigger**: The GitHub Actions workflow is set to run only on manual trigger (`workflow_dispatch`). It does not run automatically on code push.
- **Single Download**: Generates `internet_lock-all-platforms.zip` containing ready-to-run executables for all platforms. Unzip and run immediately without needing Python installed.
- **Always Latest**: Each manual run automatically deletes any previous release build and replaces it with the latest binaries.

To trigger a build:
1. Navigate to the **Actions** tab on GitHub.
2. Select **Build Executables (Manual Only)**.
3. Click **Run workflow**.
