import { createInterface } from 'node:readline';
import { complete, modelFor, runAgent } from './runtime.mjs';

const lines = createInterface({ input: process.stdin, terminal: false })[Symbol.asyncIterator]();
const write = value => process.stdout.write(JSON.stringify(value) + '\n');
const read = async () => {
  const next = await lines.next();
  if (next.done) throw new Error('Ponte encerrada');
  return JSON.parse(next.value);
};
let sequence = 0;
async function rpc(method, params = {}) {
  const id = ++sequence;
  write({ type: 'request', id, method, params });
  const response = await read();
  if (response.id !== id || response.error) throw new Error('Ferramenta recusada pela ponte');
  return response.result;
}
try {
  const request = await read();
  const result = request.mode === 'agent'
    ? await runAgent(request, rpc)
    : await complete(request, modelFor(request.model));
  write({ type: 'result', result });
} catch (error) {
  // Não devolve corpo HTTP, headers ou credenciais do provider.
  write({ type: 'error', error: `AI SDK: ${error.name || 'Error'}; execução não concluída` });
  process.exitCode = 1;
} finally {
  process.stdin.destroy();
}
