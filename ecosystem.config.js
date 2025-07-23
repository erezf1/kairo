// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: 'Kairo-Backend',
      script: 'main.py',
      interpreter: './venv/bin/python',
      // The backend's CWD is the project root, which is correct.
      cwd: __dirname,
    },
    {
      name: 'Kairo-Bridge',
      // Provide the relative path to the script from the project root.
      script: './wa/wa_bridge.js', 
      // *** THIS IS THE CRITICAL CHANGE ***
      // Set the Current Working Directory FOR THIS SCRIPT to the 'wa' folder.
      cwd: './wa',
    },
  ],
};