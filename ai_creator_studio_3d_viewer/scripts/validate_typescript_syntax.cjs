#!/usr/bin/env node
/* Syntax/transpilation smoke check for Viewer TS/TSX without resolving React/Three packages. */
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const sourceDir = path.join(__dirname, '..', 'src');
const collectSourceFiles = (directory) => fs.readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectSourceFiles(fullPath);
    return entry.isFile() && /\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [fullPath] : [];
  });
const files = collectSourceFiles(sourceDir).sort();
const options = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.ESNext,
  jsx: ts.JsxEmit.ReactJSX,
  strict: true,
  isolatedModules: true,
  importsNotUsedAsValues: ts.ImportsNotUsedAsValues?.Remove,
};
let failures = 0;
for (const name of files) {
  const filePath = name;
  const displayName = path.relative(sourceDir, filePath);
  const source = fs.readFileSync(filePath, 'utf8');
  const result = ts.transpileModule(source, {
    compilerOptions: options,
    fileName: filePath,
    reportDiagnostics: true,
  });
  const errors = (result.diagnostics || []).filter((item) => item.category === ts.DiagnosticCategory.Error);
  if (errors.length) {
    failures += errors.length;
    for (const diagnostic of errors) {
      const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
      const position = diagnostic.file && diagnostic.start !== undefined
        ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
        : null;
      const location = position ? `${position.line + 1}:${position.character + 1}` : '';
      process.stderr.write(`${displayName}${location ? `:${location}` : ''}: ${message}\n`);
    }
  } else {
    process.stdout.write(`PASS ${displayName}\n`);
  }
}
const collectDeclarationFiles = (directory) => fs.readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectDeclarationFiles(fullPath);
    return entry.isFile() && entry.name.endsWith('.d.mts') ? [fullPath] : [];
  });
const declarationFiles = collectDeclarationFiles(sourceDir).sort();
for (const declarationPath of declarationFiles) {
  const declarationName = path.relative(sourceDir, declarationPath);
  const declaration = ts.createSourceFile(declarationPath, fs.readFileSync(declarationPath, 'utf8'), ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const parseErrors = declaration.parseDiagnostics || [];
  if (parseErrors.length) {
    failures += parseErrors.length;
    for (const diagnostic of parseErrors) process.stderr.write(`${declarationName}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')}\n`);
  } else {
    process.stdout.write(`PASS ${declarationName} (declaration parse)\n`);
  }
}
process.stdout.write(`TypeScript syntax/transpile check: ${files.length} source files + ${declarationFiles.length} declaration parses, ${failures} errors\n`);
process.exitCode = failures ? 1 : 0;
