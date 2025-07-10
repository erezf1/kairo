
# Kairo - Internal Project Handbook

This document contains all the essential information for setting up, running, and managing the Kairo application. It is designed to be a quick reference to get you up to speed.

---

## 🚀 Quick Reference

| Item                  | Value                                         |
| --------------------- | --------------------------------------------- |
| **Project Path on VPS** | `/home/whatstasker/kairo/`                    |
| **Primary User**        | `whatstasker`                                 |
| **Python Backend Port** | `8001`                                        |
| **WhatsApp Number**     | `[Your Linked WhatsApp Number]`               |
| **Process Manager**     | **PM2** (Process Manager 2 for Node.js)       |

---

## 1. Project Overview

Kairo is an AI productivity coach that communicates with users via WhatsApp. The system is composed of two main services that must run simultaneously:

1.  **Python Backend (`main.py`):** A FastAPI application that contains all the business logic, agent intelligence (LLM calls), and data management (SQLite database).
2.  **Node.js WA Bridge (`WA/wa_bridge.js`):** A Node.js script that uses the `whatsapp-web.js` library to connect to a WhatsApp account and act as a bridge, relaying messages to and from the Python backend.

---

## 2. Project Structure

The project is organized into logical directories:

-   `agents/`: Contains the AI agent logic and tool definitions.
-   `bridge/`: Contains the FastAPI interface code for different communication channels (CLI, WhatsApp, Twilio).
-   `config/`: All prompts and user-facing messages are stored in `.yaml` files here.
-   `data/`: Stores the SQLite database (`kairo_activity_*.db`) and user preference JSON files.
-   `logs/`: PM2 and the Node.js script will write log files here.
-   `services/`: Core application services like the scheduler and task manager.
-   `tools/`: Utilities like the database connector (`activity_db.py`) and logger.
-   `users/`: Manages user preferences.
-   `WA/`: Contains the isolated Node.js WhatsApp bridge script and its dependencies.

---

## 3. Setup and Installation

This guide assumes a fresh clone of the repository.

### a. Python Backend

1.  **Navigate to the project root:**
    ```bash
    cd ~/kairo
    ```

2.  **Set up and activate the virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### b. Node.js WhatsApp Bridge

1.  **Navigate to the bridge directory:**
    ```bash
    cd ~/kairo/WA
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

### c. Environment Variables

1.  From the project root (`~/kairo`), copy the example environment file:
    ```bash
    cp .env.example .env
    ```

2.  **Edit the `.env` file** and fill in your `OPENAI_API_KEY`. The most important variable for testing is `BRIDGE_TYPE`.
    -   `BRIDGE_TYPE=whatsapp`: For connecting to the live WhatsApp bridge.
    -   `BRIDGE_TYPE=cli`: For testing with the command-line mock chat client.

---

## 4. Running the Application with PM2 (Production)

We use **PM2** to run both services in the background, ensuring they are stable and restart automatically on crashes or server reboots.

### a. One-Time Setup

1.  **Install PM2 globally:**
    ```bash
    sudo npm install pm2 -g
    ```

2.  **Start both services with PM2:** (Run from the project root `~/kairo`)
    ```bash
    # Start the Python backend
    pm2 start "python main.py" --name kairo-backend

    # Start the Node.js WhatsApp bridge
    pm2 start WA/wa_bridge.js --name kairo-wa-bridge
    ```

3.  **Scan the QR Code:** View the bridge logs to get the QR code for the initial link.
    ```bash
    pm2 logs kairo-wa-bridge
    ```
    Scan the code with your phone. You only need to do this once.

4.  **Save the process list and enable startup on boot:**
    ```bash
    # Save the current list of apps
    pm2 save

    # Create a startup script for your system
    pm2 startup
    # (This will give you a command to copy and paste, run it)
    ```

### b. Daily Management with PM2

-   **List all running processes:**
    ```bash
    pm2 list
    ```
-   **View live logs for a specific service:**
    ```bash
    pm2 logs kairo-backend
    pm2 logs kairo-wa-bridge
    ```
-   **Restart a service (e.g., after a code change):**
    ```bash
    pm2 restart kairo-backend
    ```
-   **Stop a service:**
    ```bash
    pm2 stop all
    ```

---

## 5. Manual Testing & Debugging

For development, it's often easier to run the services manually in separate terminals.

**Terminal 1: Start the Python Backend**
```bash
cd ~/kairo
source venv/bin/activate
python main.py
```

**Terminal 2: Start the WhatsApp Bridge**
```bash
cd ~/kairo/WA
node wa_bridge.js
```

### Viewing a User's Session

To debug a specific user's interaction, use the `session_viewer.py` script. It reads the database and prints a clean, chronological log of messages and tool calls.

```bash
cd ~/kairo
source venv/bin/activate

# For WhatsApp users:
python session_viewer.py [USER_PHONE_NUMBER] --mode prod

# For CLI testing users:
python session_viewer.py [USER_ID] --mode cli
```

---

## 6. Git and Version Control

The `.gitignore` file is configured to keep the repository clean by ignoring:
-   Python virtual environments (`venv/`)
-   Node.js dependencies (`WA/node_modules/`)
-   WhatsApp session data (`WA/.wwebjs_auth/`)
-   Log files (`logs/`)
-   Database files (`data/*.db`)
-   Environment files (`.env`)

Always commit changes from the project root (`~/kairo`).

```