// Browser and frontend share a network namespace. Forward the browser's
// localhost:8000 to the backend while retaining the real localhost CORS origin.
const net = require('node:net');
const { spawn } = require('node:child_process');
const server = net.createServer(client => {
  const upstream = net.connect(8000, 'backend');
  client.pipe(upstream).pipe(client);
  client.on('error', () => upstream.destroy());
  upstream.on('error', () => client.destroy());
  client.on('close', () => upstream.destroy());
});
server.on('error', error => {
  console.error(`Browser test forwarding failed: ${error.code}`);
  process.exit(1);
});
server.listen(8000, '127.0.0.1', () => {
  const child = spawn('npx', ['playwright', 'test'], { stdio: 'inherit' });
  child.on('error', () => { server.close(); process.exitCode = 1; });
  child.on('exit', code => { server.close(); process.exitCode = code ?? 1; });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => child.kill(signal));
  }
});
