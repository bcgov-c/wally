module.exports = {
  presets: [
    '@vue/app'
  ],
  env: {
    test: {
      plugins: ['dynamic-import-node']
    }
  }
}
