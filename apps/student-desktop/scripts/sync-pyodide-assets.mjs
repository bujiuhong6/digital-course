import { createRequire } from "node:module";
import { mkdir, copyFile, readFile, writeFile, access } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const pyodidePkg = require("pyodide/package.json");
const pyodideRoot = path.dirname(require.resolve("pyodide/package.json"));
const appRoot = path.resolve(import.meta.dirname, "..");
const targetRoot = path.join(
  appRoot,
  "public",
  "pyodide",
  `v${pyodidePkg.version}`,
  "full",
);
const cdnRoot = `https://cdn.jsdelivr.net/pyodide/v${pyodidePkg.version}/full`;

const coreFiles = [
  "pyodide.js",
  "pyodide.asm.js",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

const builtinPackages = [
  "micropip",
  "numpy",
  "pandas",
  "matplotlib",
  "matplotlib-pyodide",
  "wordcloud",
  "Jinja2",
];

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function copyCoreFiles() {
  await mkdir(targetRoot, { recursive: true });
  for (const file of coreFiles) {
    await copyFile(path.join(pyodideRoot, file), path.join(targetRoot, file));
  }
}

async function downloadFile(fileName) {
  const out = path.join(targetRoot, fileName);
  if (await exists(out)) {
    return;
  }
  const url = `${cdnRoot}/${fileName}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download ${url}: HTTP ${response.status}`);
  }
  const data = Buffer.from(await response.arrayBuffer());
  await writeFile(out, data);
}

function collectPackages(lock, names) {
  const pending = [...names];
  const selected = new Set();
  while (pending.length > 0) {
    const name = pending.pop();
    const pkg = lock.packages[name] ?? lock.packages[String(name).toLowerCase()];
    if (!pkg || selected.has(pkg.file_name)) {
      continue;
    }
    selected.add(pkg.file_name);
    for (const dep of pkg.depends ?? []) {
      pending.push(dep);
    }
  }
  return [...selected].sort();
}

await copyCoreFiles();
const lock = JSON.parse(await readFile(path.join(targetRoot, "pyodide-lock.json"), "utf8"));
const wheelFiles = collectPackages(lock, builtinPackages);
for (const fileName of wheelFiles) {
  await downloadFile(fileName);
}

console.log(
  `Synced Pyodide ${pyodidePkg.version}: ${coreFiles.length} core files and ${wheelFiles.length} package files.`,
);
