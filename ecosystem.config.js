module.exports = {
  apps: [
    {
      name: 'crimedataanalysis',
      cwd: __dirname + '/backend',
      script: 'serve.py',
      interpreter: __dirname + '/backend/venv/Scripts/python.exe',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
