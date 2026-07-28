import esbuild from 'esbuild'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const args = process.argv.slice(2)
const watch = args.includes('--watch')

const buildOptions = {
  entryPoints: ['src/main.ts'],
  bundle: true,
  outfile: 'main.js',
  external: ['obsidian'],
  format: 'cjs',
  platform: 'node',
  sourcemap: watch ? 'inline' : false,
  minify: !watch,
  treeShaking: true,
}

const copyFiles = () => {
  const files = ['manifest.json', 'styles.css']
  const pluginDir = path.join(
    process.env.APPDATA || process.env.HOME,
    'Obsidian',
    'Plugins',
    'obsidian-exe-launcher'
  )
  
  // Also copy to the vault's .obsidian/plugins directory
  const vaultPluginDir = 'D:\\Obsidian\\LeoDiary\\.obsidian\\plugins\\obsidian-exe-launcher'
  
  for (const file of files) {
    const src = path.join(__dirname, file)
    if (fs.existsSync(src)) {
      if (!fs.existsSync(vaultPluginDir)) {
        fs.mkdirSync(vaultPluginDir, { recursive: true })
      }
      fs.copyFileSync(src, path.join(vaultPluginDir, file))
    }
  }
  
  // Copy main.js to vault plugin dir
  const mainJsSrc = path.join(__dirname, 'main.js')
  if (fs.existsSync(mainJsSrc)) {
    fs.copyFileSync(mainJsSrc, path.join(vaultPluginDir, 'main.js'))
  }
}

if (watch) {
  const ctx = esbuild.context(buildOptions)
  ctx.then(() => {
    ctx.watch().then(() => {
      console.log('Watching for changes...')
    })
  })
} else {
  esbuild.build(buildOptions).then(() => {
    console.log('Build complete!')
    copyFiles()
    console.log('Files copied to vault plugin directory')
  }).catch(err => {
    console.error('Build failed:', err)
    process.exit(1)
  })
}
