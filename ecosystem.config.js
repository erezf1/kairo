// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: 'Kairo-Backend',
      script: 'main.py',
      interpreter: './venv/bin/python',
      cwd: __dirname, // Correct: run from project root
    },
    {
      name: 'Kairo-Bridge',
      // --- THIS IS THE FIX ---
      script: 'wa_bridge.js', // Just the script name
      // --- END OF FIX ---
      cwd: './WA', // Tell PM2 to run it from inside the WA directory
    },
  ],
};