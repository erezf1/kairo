// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'kairo-backend',
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8001',
    interpreter: 'python3', // or just 'python' depending on your system
    
    // --- PM2's Watch & Restart Configuration ---
    watch: true, // This tells pm2 to watch for file changes
    ignore_watch: [
      "node_modules",
      "logs",
      "data",
      ".wwebjs_auth",
      ".wwebjs_cache",
      "__pycache__",
      "*.txt",
      "*.json",
      "*.yaml" // Ignore config changes unless you want to restart for them
    ],
    watch_options: {
      "followSymlinks": false
    },
    // ------------------------------------------

    // --- Environment Variables ---
    env: {
      "PROJECT_NAME": "kairo",
      "APP_ENV": "production" // Set this to "development" if you need debug features
    }
  }]
};