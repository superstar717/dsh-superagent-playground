'use strict';
// Regenerates renderer/captions.cjs from renderer/captions.js so the Node
// tests and the main process (CJS) use exactly the same normalisation as the
// ES module in the app. Same pattern as build-zoom-cjs.js.
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, '..', 'renderer', 'captions.js'), 'utf8');
const stripped = src.replace(/^export (const|function|let)\b/gm, '$1');
const exportNames = ['round2', 'normalizeCaptionSegments', 'captionTooLong'];
const tail = `\nmodule.exports = {\n${exportNames.map((n) => `  ${n}`).join(',\n')},\n};\n`;
fs.writeFileSync(path.join(__dirname, '..', 'renderer', 'captions.cjs'), stripped + tail);
console.log('renderer/captions.cjs rebuilt from renderer/captions.js');
