import React from "react";
import { Composition } from "remotion";
import { OralVideo } from "./OralVideo";
import timingData from "./timing.json";

const timing = timingData as unknown as {
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="SuperagentVertical"
      component={OralVideo}
      width={timing.width}
      height={timing.height}
      fps={timing.fps}
      durationInFrames={timing.totalFrames}
    />
  );
};
