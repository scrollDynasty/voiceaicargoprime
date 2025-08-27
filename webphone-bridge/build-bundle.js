/**
 * Build script to create browser-compatible bundles
 */

const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

console.log('Building browser bundles...');

// Create a simple webpack config
const webpackConfig = `
const path = require('path');

module.exports = {
  mode: 'production',
  entry: {
    'ringcentral-sdk': '@ringcentral/sdk',
    'ringcentral-web-phone': 'ringcentral-web-phone'
  },
  output: {
    filename: '[name].bundle.js',
    path: path.resolve(__dirname, 'dist'),
    library: '[name]',
    libraryTarget: 'window'
  },
  resolve: {
    fallback: {
      "crypto": require.resolve("crypto-browserify"),
      "stream": require.resolve("stream-browserify"),
      "buffer": require.resolve("buffer/"),
      "process": require.resolve("process/browser"),
      "util": require.resolve("util/"),
      "url": require.resolve("url/"),
      "path": require.resolve("path-browserify"),
      "http": require.resolve("stream-http"),
      "https": require.resolve("https-browserify"),
      "zlib": require.resolve("browserify-zlib"),
      "querystring": require.resolve("querystring-es3"),
      "os": require.resolve("os-browserify/browser"),
      "fs": false,
      "net": false,
      "tls": false,
      "child_process": false
    }
  },
  module: {
    rules: [
      {
        test: /\.m?js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      }
    ]
  }
};
`;

// Write webpack config
fs.writeFileSync(path.join(__dirname, 'webpack.config.js'), webpackConfig);

console.log('Installing webpack and dependencies...');

// Install webpack and required dependencies
try {
  execSync('npm install --save-dev webpack webpack-cli babel-loader @babel/core @babel/preset-env', {
    cwd: __dirname,
    stdio: 'inherit'
  });
  
  execSync('npm install --save crypto-browserify stream-browserify buffer process util url path-browserify stream-http https-browserify browserify-zlib querystring-es3 os-browserify', {
    cwd: __dirname,
    stdio: 'inherit'
  });
  
  console.log('Building bundles with webpack...');
  
  execSync('npx webpack', {
    cwd: __dirname,
    stdio: 'inherit'
  });
  
  console.log('✅ Bundles built successfully in dist/ directory');
  
} catch (error) {
  console.error('❌ Build failed:', error.message);
  process.exit(1);
}