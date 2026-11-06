const { withAppBuildGradle } = require('expo/config-plugins');

// Hash long generated C++ object paths so Ninja works in Windows workspaces.
module.exports = (config) => withAppBuildGradle(config, (mod) => {
  if (!mod.modResults.contents.includes('CMAKE_OBJECT_PATH_MAX')) {
    mod.modResults.contents = mod.modResults.contents.replace(/defaultConfig\s*\{/, `defaultConfig {
        externalNativeBuild {
            cmake { arguments "-DCMAKE_OBJECT_PATH_MAX=240" }
        }`);
  }
  return mod;
});
