// OpenMotion 复核渲染 11-22驱动：stdio MCP 客户端，模板→建工程→导出 MP4→轮询
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { writeFileSync, readFileSync } from 'node:fs';

const CHECKOUT = '/Users/huweixing/src/openmotion-check-269d25eb51a2/openmotion';
const DATA_DIR = '/Users/huweixing/src/openmotion-check-269d25eb51a2/work/openmotion/data';

const child = spawn('node', ['--experimental-strip-types', 'mcp.ts'], {
  cwd: CHECKOUT,
  env: { ...process.env, MOTION_DATA_DIR: DATA_DIR, PORT: '4173' },
  stdio: ['pipe', 'pipe', 'pipe'],
});
let seq = 0;
const pending = new Map();
let stderrTail = '';
child.stderr.on('data', c => { stderrTail = (stderrTail + c).slice(-4000); });
child.on('exit', (code, sig) => {
  for (const { reject } of pending.values()) reject(new Error(`MCP exited code=${code} sig=${sig}: ${stderrTail}`));
  pending.clear();
});
createInterface({ input: child.stdout }).on('line', line => {
  try {
    const v = JSON.parse(line);
    if (v.id !== undefined && pending.has(v.id)) { pending.get(v.id)(v); pending.delete(v.id); }
  } catch { /* ignore non-JSON lines */ }
});
function rpc(method, params, timeoutMs = 120_000) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timeout(${timeoutMs}ms); stderr=${stderrTail}`)); }, timeoutMs);
    pending.set(id, v => { clearTimeout(timer); resolve(v); });
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
}
const sc = r => r.result?.structuredContent ?? r.result;
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

async function main() {
  const hello = await rpc('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'om-recheck', version: '1' } });
  log('server:', hello.result?.serverInfo?.name, hello.result?.serverInfo?.version);
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');

  const { tools } = (await rpc('tools/list', {})).result;
  log('tools:', tools.map(t => t.name).join(', '));

  // 1. 列模板，挑可编辑内置模板
  const lt = await rpc('tools/call', { name: 'openmotion_list_templates', arguments: {} });
  const ltData = sc(lt);
  log('catalog source=', ltData?.source, 'total=', ltData?.total, 'indexPath=', ltData?.indexPath);
  let rows = ltData?.entries ?? ltData?.templates ?? [];
  if (!rows.length && ltData?.indexPath) {
    const text = readFileSync(ltData.indexPath, 'utf8');
    rows = text.split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return {}; } });
  }
  log('rows parsed:', rows.length);
  const wanted = r => ['decision-tree', 'product-promo', 'nyt-graph'].includes(r.id ?? r.templateId ?? r.name)
    || String(r.id ?? r.templateId ?? '').includes('decision-tree');
  const pick = rows.find(r => wanted(r) && (r.workflowGuide === 'template' || r.localSource || r.editable))
    ?? rows.find(wanted) ?? rows[0];
  log('picked row:', JSON.stringify(pick).slice(0, 300));
  const templateId = pick?.id ?? pick?.templateId;
  if (!templateId) { throw new Error('no editable builtin template found; rows sample=' + JSON.stringify(rows.slice(0, 3)).slice(0, 600)); }

  const gt = await rpc('tools/call', { name: 'openmotion_get_template', arguments: { templateId } });
  log('get_template workflowGuide:', JSON.stringify(sc(gt)?.workflowGuide ?? {}).slice(0, 200));

  // 2. 用模板创建工程
  const cp = await rpc('tools/call', {
    name: 'openmotion_create_project',
    arguments: {
      requestId: 'om-recheck-create-002', projectType: 'template', templateId,
      title: 'OpenMotion 复核渲染 11-22',
      requirements: '复核用：确认已装实例三天后仍能以内置模板出片（不改内容，零 API key）。',
      namingLanguage: 'zh',
    },
  }, 180_000);
  if (cp.result?.isError) throw new Error('create failed: ' + JSON.stringify(cp.result?.content ?? cp).slice(0, 800));
  const proj = sc(cp);
  const projectId = proj?.projectId ?? proj?.sessionId;
  log('project:', projectId, 'revision=', proj?.revision, 'version=', proj?.currentVersionId, 'dir=', proj?.directory ?? '');
  if (!projectId) throw new Error('no projectId: ' + JSON.stringify(proj).slice(0, 800));

  // 3. 读工程详情拿 revision/version
  const gp = await rpc('tools/call', { name: 'openmotion_get_project', arguments: { projectId } });
  const detail = sc(gp);
  const revision = detail?.revision; const versionId = detail?.currentVersionId;
  log('detail revision=', revision, 'versionId=', versionId, 'files=', (detail?.files ?? []).length);
  if (!revision || !versionId) throw new Error('missing revision/versionId: ' + JSON.stringify(detail).slice(0, 800));

  // 4. 请求导出
  const er = await rpc('tools/call', {
    name: 'openmotion_export_request',
    arguments: { projectId, requestId: 'om-recheck-export-002', expectedRevision: revision, versionId, audio: 'silent' },
  }, 300_000);
  if (er.result?.isError) throw new Error('export_request failed: ' + JSON.stringify(er.result?.content ?? er).slice(0, 800));
  const erData = sc(er);
  const jobId = erData?.job?.id ?? erData?.jobId ?? erData?.exportJob?.id ?? erData?.exportJob?.id;
  log('export jobId:', jobId, 'state=', erData?.state ?? erData?.exportJob?.state);
  if (!jobId) throw new Error('no jobId: ' + JSON.stringify(erData).slice(0, 800));

  // 5. 轮询直到完成
  const deadline = Date.now() + 12 * 60_000;
  let job = null;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 5000));
    const pj = await rpc('tools/call', { name: 'openmotion_get_project', arguments: { projectId, exportJobId: jobId } }, 60_000);
    job = sc(pj);
    const state = job?.state ?? job?.exportJob?.state;
    log('poll state=', state, JSON.stringify(job?.progress ?? job?.exportJob?.progress ?? {}).slice(0, 120));
    if (state === 'completed' || state === 'failed' || state === 'cancelled') break;
  }
  const finalState = job?.state ?? job?.exportJob?.state;
  const filePath = job?.path ?? job?.file ?? job?.exportJob?.path ?? job?.exportJob?.file;
  log('FINAL state=', finalState, 'path=', filePath);
  writeFileSync('/Users/huweixing/src/openmotion-recheck-369273b5351c/work/openmotion-recheck/render-result.json',
    JSON.stringify({ projectId, jobId, finalState, filePath, job }, null, 2));
  if (finalState !== 'completed') throw new Error('export did not complete: state=' + finalState);
  console.log('RENDER_OK ' + filePath);
}

main().catch(e => { console.error('DRIVE_FAILED', e.message); writeFileSync('/Users/huweixing/src/openmotion-recheck-369273b5351c/work/openmotion-recheck/render-result.json', JSON.stringify({ error: e.message, stderr: stderrTail }, null, 2)); process.exitCode = 1; })
  .finally(() => { try { child.stdin.end(); child.kill('SIGTERM'); } catch {} });
