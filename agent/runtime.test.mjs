import test from 'node:test';
import assert from 'node:assert/strict';
import { complete, modelFor, runAgent } from './runtime.mjs';

function provider(responses, requests = []) {
  return modelFor('fake-model', { FEATHERLESS_API_KEY: 'fake' }, async (_url, init) => {
    requests.push(JSON.parse(init.body));
    const next = responses.shift();
    if (next instanceof Error) throw next;
    if (!next) throw new Error('Chamada extra inesperada');
    return Response.json({ id: 'fake', object: 'chat.completion', created: 0, model: 'fake-model',
      choices: [{ index: 0, message: { role: 'assistant', ...next },
        finish_reason: next.tool_calls ? 'tool_calls' : 'stop' }],
      usage: { prompt_tokens: 12, completion_tokens: 4, total_tokens: 16 } });
  });
}
const call = name => ({ content: null, tool_calls: [{ id: `call-${name}`, type: 'function',
  function: { name, arguments: '{"motivo":"executar passo liberado"}' } }] });

test('generateText usa provider compatível e preserva tokens/imagens', async () => {
  const requests = [];
  const result = await complete({ messages: [{ role: 'user', content: [
    { type: 'text', text: 'leia' },
    { type: 'image_url', image_url: { url: 'data:image/png;base64,aGVsbG8=' } },
  ] }] }, provider([{ content: '{"uc":"123"}' }], requests));
  assert.equal(result.text, '{"uc":"123"}');
  assert.equal(result.inputTokens, 12);
  assert.equal(result.outputTokens, 4);
  assert.match(requests[0].messages.find(m => m.role === 'user').content[1].image_url.url, /^data:image\/png;base64,/);
});

test('ToolLoopAgent executa ferramentas e atualiza activeTools até aguardar humano', async () => {
  const requests = [], executions = [], usages = [];
  let options = ['extrair_conta', 'extrair_kit'];
  const rpc = async (method, params) => {
    if (method === 'state') return { options, summary: { etapa: 'montagem' } };
    if (method === 'usage') { usages.push(params); return {}; }
    assert.ok(options.includes(params.name));
    executions.push(params.name);
    options = options.filter(n => n !== params.name);
    return { ok: true, state: { options, summary: {} } };
  };
  const result = await runAgent({ models: ['fake'], maxSteps: 5,
    tools: { extrair_conta: 'Ler conta', extrair_kit: 'Ler kit' } }, rpc,
    () => provider([call('extrair_kit'), call('extrair_conta')], requests));
  assert.deepEqual(executions, ['extrair_kit', 'extrair_conta']);
  assert.equal(result.steps, 2);
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1].tools.map(t => t.function.name), ['extrair_conta']);
  assert.equal(usages.reduce((sum, u) => sum + u.inputTokens, 0), 24);
});

test('sem ferramenta disponível não chama o modelo', async () => {
  const result = await runAgent({ models: ['fake'], tools: {} }, async () => ({ options: [] }),
    () => { throw new Error('Não deve chamar'); });
  assert.equal(result.steps, 0);
});

test('fallback retoma estado sem repetir ferramenta concluída', async () => {
  let options = ['primeiro', 'segundo'];
  const executed = [];
  const rpc = async (method, params) => {
    if (method === 'usage') return {};
    if (method === 'state') return { options, summary: {} };
    executed.push(params.name);
    options = options.filter(n => n !== params.name);
    return { ok: true, state: { options, summary: {} } };
  };
  await runAgent({ models: ['main', 'fallback'], maxSteps: 5,
    tools: { primeiro: '1', segundo: '2' } }, rpc,
    id => provider(id === 'main' ? [call('primeiro'), new Error('rede')] : [call('segundo')]));
  assert.deepEqual(executed, ['primeiro', 'segundo']);
});

test('limite de passos não declara execução concluída', async () => {
  await assert.rejects(runAgent({ models: ['fake'], maxSteps: 1, tools: { passo: 'passo' } },
    async method => method === 'usage' ? {} : method === 'execute'
      ? { state: { options: ['passo'], summary: {} } } : { options: ['passo'], summary: {} },
    () => provider([call('passo')])), /modelos falharam ou limite/);
});
