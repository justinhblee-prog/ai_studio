import assert from 'node:assert/strict';
import { resolveModelBasePath } from '../src/modelBasePath.mjs';

const cases = [
  ['relative endpoint', 'api/assets/42/content', 'https://studio.example/workspace/7', 'https://studio.example/workspace/api/assets/42/'],
  ['root-relative endpoint', '/api/assets/42/content', 'https://studio.example/workspace/7', 'https://studio.example/api/assets/42/'],
  ['absolute HTTPS endpoint', 'https://cdn.example/models/item.glb?token=hidden', 'https://studio.example/', 'https://cdn.example/models/'],
  ['absolute HTTP endpoint', 'http://localhost:8000/assets/model.glb', 'https://studio.example/', 'http://localhost:8000/assets/'],
  ['query and fragment are excluded from base path', './models/character.gltf?rev=2#scene', 'https://studio.example/app/index.html', 'https://studio.example/app/models/'],
];
for (const [name, input, page, expected] of cases) {
  assert.equal(resolveModelBasePath(input, page), expected, name);
  console.log(`PASS ${name}`);
}
for (const [name, input, page] of [
  ['invalid URL', 'http://[invalid', 'https://studio.example/'],
  ['javascript scheme rejected', 'javascript:alert(1)', 'https://studio.example/'],
  ['data scheme rejected', 'data:model/gltf-binary;base64,AAAA', 'https://studio.example/'],
  ['unsupported FTP scheme rejected', 'ftp://files.example/model.glb', 'https://studio.example/'],
  ['invalid page base rejected', '/model.glb', 'not-a-url'],
]) {
  assert.throws(() => resolveModelBasePath(input, page), TypeError, name);
  console.log(`PASS ${name}`);
}
console.log('Model base path resolution: 10/10 passed');
