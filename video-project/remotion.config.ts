import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Encoder note: Remotion >=4.0.449 ships a compositor built with the macOS 15
// SDK which cannot load on macOS 13 (dyld symbol error). Pinned to 4.0.448.
Config.setChromiumOpenGlRenderer("angle");
Config.setConcurrency(4);
Config.setJpegQuality(95);
