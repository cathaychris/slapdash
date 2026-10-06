// Builds the web frontend into ../slapdash/frontend, which the Python package serves.
// Usage: node build.mjs [--watch]
import * as esbuild from "esbuild";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const outdir = "../slapdash/frontend";
const watch = process.argv.includes("--watch");

const versionFile = readFileSync("../slapdash/version.py", "utf8");
const version = versionFile.match(/__version__\s*=\s*"([^"]+)"/)[1];

mkdirSync(outdir, { recursive: true });
for (const file of ["custom.css", "custom.js", "dashboard.css"]) {
  copyFileSync(file, `${outdir}/${file}`);
}
// the bundle's css (from imports in the sources) is written to index.css
writeFileSync(
  `${outdir}/index.html`,
  readFileSync("index.html", "utf8").replace(
    '<script src="custom.js"></script>',
    '<script src="custom.js"></script>\n    <link rel="stylesheet" href="index.css" />'
  )
);

const options = {
  entryPoints: { index: "src/index.tsx" },
  bundle: true,
  minify: !watch,
  sourcemap: watch,
  outdir,
  target: ["es2018"],
  loader: { ".woff": "file", ".woff2": "file", ".ttf": "file", ".eot": "file", ".svg": "file", ".png": "file" },
  define: {
    __SLAPDASH_VERSION__: JSON.stringify(version),
    "process.env.NODE_ENV": JSON.stringify(watch ? "development" : "production"),
  },
  logLevel: "info",
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
} else {
  await esbuild.build(options);
}
